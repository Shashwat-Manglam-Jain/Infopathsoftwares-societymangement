import csv
from datetime import date
from decimal import Decimal

from django.db.models import Count, Max, Q, Sum
from django.http import HttpResponse
from django.shortcuts import render

from apps.accounts.permissions import auditor_or_above


def _csv_response(filename, headers, rows):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    writer = csv.writer(response)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return response


@auditor_or_above
def report_index(request):
    return render(request, 'reports/index.html')


@auditor_or_above
def personal_ledger(request):
    from apps.members.models import Member

    member_id = request.GET.get('member')
    from_date = request.GET.get('from_date', '')
    to_date = request.GET.get('to_date', '')

    members = Member.objects.filter(status='active').order_by('name')

    context = {
        'members': members,
        'selected_member': member_id,
        'from_date': from_date,
        'to_date': to_date,
    }

    if member_id and from_date and to_date:
        try:
            member = Member.objects.get(pk=member_id)
        except Member.DoesNotExist:
            return render(request, 'reports/personal_ledger.html', context)

        context['member'] = member
        accounts = []

        from apps.savings.models import AccountTransaction, SavingsAccount

        savings_accounts = SavingsAccount.objects.filter(member=member)
        for sa in savings_accounts:
            pre_agg = AccountTransaction.objects.filter(
                account=sa,
                txn_date__lt=from_date,
                is_reversed=False,
            ).aggregate(
                debit=Sum('amount', filter=Q(txn_type__in=['withdrawal', 'charge']), default=Decimal('0')),
                credit=Sum(
                    'amount', filter=Q(txn_type__in=['deposit', 'interest_credit', 'transfer']), default=Decimal('0')
                ),
            )
            opening = pre_agg['credit'] - pre_agg['debit']

            txns = AccountTransaction.objects.filter(
                account=sa,
                txn_date__gte=from_date,
                txn_date__lte=to_date,
                is_reversed=False,
            ).order_by('txn_date', 'created_at')
            rows = []
            running = opening
            for t in txns:
                debit = t.amount if t.txn_type in ('withdrawal', 'charge') else 0
                credit = t.amount if t.txn_type in ('deposit', 'interest_credit', 'transfer') else 0
                running = running + credit - debit
                rows.append(
                    {
                        'date': t.txn_date,
                        'description': t.narration or t.get_txn_type_display(),
                        'debit': debit,
                        'credit': credit,
                        'balance': running,
                    }
                )
            if rows or opening:
                accounts.append(
                    {
                        'type': f'{sa.get_account_type_display()}',
                        'account_no': sa.account_no,
                        'opening_balance': opening,
                        'current_balance': sa.current_balance,
                        'closing_balance': running if rows else opening,
                        'rows': rows,
                    }
                )

        from apps.shares.models import ShareHolding, ShareTransaction

        share_txns = ShareTransaction.objects.filter(
            member=member,
            txn_date__gte=from_date,
            txn_date__lte=to_date,
        ).order_by('txn_date')
        if share_txns.exists():
            holding = ShareHolding.objects.filter(member=member, status='active').first()
            rows = []
            for t in share_txns:
                debit = t.amount if t.txn_type == 'surrender' else 0
                credit = t.amount if t.txn_type == 'purchase' else 0
                rows.append(
                    {
                        'date': t.txn_date,
                        'description': t.get_txn_type_display(),
                        'debit': debit,
                        'credit': credit,
                        'balance': '',
                    }
                )
            accounts.append(
                {
                    'type': 'Share Capital',
                    'account_no': holding.certificate_no if holding else 'N/A',
                    'opening_balance': 0,
                    'current_balance': holding.total_amount if holding else 0,
                    'closing_balance': holding.total_amount if holding else 0,
                    'rows': rows,
                }
            )

        from apps.loans.models import LoanAccount, LoanRepayment

        loan_accounts = LoanAccount.objects.filter(member=member).exclude(
            status__in=['closed', 'rejected', 'written_off']
        )
        for la in loan_accounts:
            repayments = LoanRepayment.objects.filter(
                loan=la,
                payment_date__gte=from_date,
                payment_date__lte=to_date,
            ).order_by('payment_date')
            rows = []
            for r in repayments:
                rows.append(
                    {
                        'date': r.payment_date,
                        'description': f'EMI #{r.emi_schedule.installment_no}' if r.emi_schedule else 'Repayment',
                        'debit': r.amount,
                        'credit': 0,
                        'balance': '',
                    }
                )
            if rows:
                accounts.append(
                    {
                        'type': f'Loan ({la.loan_product.name})',
                        'account_no': la.loan_no,
                        'opening_balance': 0,
                        'current_balance': la.outstanding_principal,
                        'closing_balance': la.outstanding_principal,
                        'rows': rows,
                    }
                )

        from apps.deposits.models import FixedDeposit, RDInstallment, RecurringDeposit

        fds = FixedDeposit.objects.filter(member=member).exclude(status='renewed')
        for fd in fds:
            rows = [
                {
                    'date': fd.start_date,
                    'description': f'FD Opened — {fd.tenure_days} days @ {fd.interest_rate}%',
                    'debit': 0,
                    'credit': fd.deposit_amount,
                    'balance': fd.deposit_amount,
                }
            ]
            if fd.premature_closure_date and from_date <= str(fd.premature_closure_date) <= to_date:
                rows.append(
                    {
                        'date': fd.premature_closure_date,
                        'description': 'Premature Closure',
                        'debit': fd.premature_amount or fd.deposit_amount,
                        'credit': 0,
                        'balance': 0,
                    }
                )
            if rows:
                accounts.append(
                    {
                        'type': 'Fixed Deposit',
                        'account_no': fd.fd_no,
                        'opening_balance': fd.deposit_amount,
                        'current_balance': fd.deposit_amount if fd.status == 'active' else 0,
                        'closing_balance': fd.deposit_amount if fd.status == 'active' else 0,
                        'rows': rows,
                    }
                )

        rds = RecurringDeposit.objects.filter(member=member)
        for rd in rds:
            installments = RDInstallment.objects.filter(
                rd=rd,
                paid_date__gte=from_date,
                paid_date__lte=to_date,
                status='paid',
            ).order_by('paid_date')
            rows = []
            running = 0
            for inst in installments:
                running += inst.paid_amount
                rows.append(
                    {
                        'date': inst.paid_date,
                        'description': f'Installment #{inst.installment_no}',
                        'debit': 0,
                        'credit': inst.paid_amount,
                        'balance': running,
                    }
                )
            if rows:
                paid_total = (
                    RDInstallment.objects.filter(rd=rd, status='paid').aggregate(
                        t=Sum('paid_amount'),
                    )['t']
                    or 0
                )
                accounts.append(
                    {
                        'type': 'Recurring Deposit',
                        'account_no': rd.rd_no,
                        'opening_balance': 0,
                        'current_balance': paid_total,
                        'closing_balance': paid_total,
                        'rows': rows,
                    }
                )

        from apps.agents.models import PigmmyAccount, PigmmyTransaction

        pigmmy_accounts = PigmmyAccount.objects.filter(member=member)
        for pa in pigmmy_accounts:
            pre_total = (
                PigmmyTransaction.objects.filter(
                    account=pa,
                    txn_date__lt=from_date,
                    is_reversed=False,
                ).aggregate(t=Sum('amount'))['t']
                or 0
            )
            opening = pre_total

            txns = PigmmyTransaction.objects.filter(
                account=pa,
                txn_date__gte=from_date,
                txn_date__lte=to_date,
                is_reversed=False,
            ).order_by('txn_date', 'created_at')
            rows = []
            running = opening
            for t in txns:
                running += t.amount
                rows.append(
                    {
                        'date': t.txn_date,
                        'description': t.narration or f'Installment #{t.installment_no}',
                        'debit': 0,
                        'credit': t.amount,
                        'balance': running,
                    }
                )
            if rows or opening:
                accounts.append(
                    {
                        'type': f'Pigmy ({pa.get_deposit_type_display()})',
                        'account_no': pa.account_no,
                        'opening_balance': opening,
                        'current_balance': pa.current_balance,
                        'closing_balance': running if rows else opening,
                        'rows': rows,
                    }
                )

        context['accounts'] = accounts

        if request.GET.get('format') == 'csv' and accounts:
            rows = []
            for acct in accounts:
                for r in acct.get('rows', []):
                    rows.append(
                        [
                            acct['type'],
                            acct['account_no'],
                            r['date'],
                            r['description'],
                            r['debit'],
                            r['credit'],
                            r['balance'],
                        ]
                    )
            return _csv_response(
                f'personal_ledger_{member.member_no}_{date.today()}.csv',
                ['Account Type', 'Account No', 'Date', 'Description', 'Debit', 'Credit', 'Balance'],
                rows,
            )

    return render(request, 'reports/personal_ledger.html', context)


@auditor_or_above
def trial_balance(request):
    from apps.accounting.services import get_trial_balance

    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    context = {'from_date': from_date, 'to_date': to_date}
    if from_date and to_date:
        branch = None if request.user.can_access_all_branches else request.current_branch
        result = get_trial_balance(from_date=from_date, to_date=to_date, branch=branch)
        context['result'] = result
        if request.GET.get('format') == 'csv' and result:
            rows = []
            for item in result.get('accounts', []):
                rows.append(
                    [
                        item['code'],
                        item['name'],
                        item['opening_debit'],
                        item['opening_credit'],
                        item['period_debit'],
                        item['period_credit'],
                        item['closing_debit'],
                        item['closing_credit'],
                    ]
                )
            return _csv_response(
                f'trial_balance_{from_date}_to_{to_date}.csv',
                ['Code', 'Account', 'Opening Dr', 'Opening Cr', 'Period Dr', 'Period Cr', 'Closing Dr', 'Closing Cr'],
                rows,
            )
    return render(request, 'reports/trial_balance.html', context)


def _prev_year_date(d):
    """Return same date one year earlier, handling leap-year edge (Feb 29 → Feb 28)."""
    try:
        return d.replace(year=d.year - 1)
    except ValueError:
        return d.replace(year=d.year - 1, day=28)


def _compute_head_balances(heads, agg_map):
    """Return {head_pk: balance} from opening_balance + journal aggregates."""
    result = {}
    for head in heads:
        ob = head.opening_balance or 0
        row = agg_map.get(head.pk, {})
        dr = row.get('dr') or 0
        cr = row.get('cr') or 0
        if head.account_group in ('asset', 'expense'):
            result[head.pk] = ob + dr - cr
        else:
            result[head.pk] = ob + cr - dr
    return result


def _aggregate_journal_lines(heads, cutoff_date, branch):
    from apps.accounting.models import JournalLine

    base_filter = Q(
        journal_entry__entry_date__lte=cutoff_date,
        journal_entry__is_reversed=False,
        journal_entry__is_posted=True,
        gl_account__in=heads,
    )
    if branch:
        base_filter &= Q(journal_entry__branch=branch)
    return {
        row['gl_account_id']: row
        for row in JournalLine.objects.filter(base_filter)
        .values('gl_account_id')
        .annotate(dr=Sum('debit_amount'), cr=Sum('credit_amount'))
    }


def _build_groups(heads, cur_balances, prev_balances, group_filter):
    """Group heads by parent; return (groups_list, current_total, prev_total)."""
    from collections import OrderedDict

    buckets = OrderedDict()
    total_cur = Decimal('0')
    total_prev = Decimal('0')

    for head in heads:
        if not group_filter(head):
            continue
        cur = cur_balances.get(head.pk, 0)
        prev = prev_balances.get(head.pk, 0)
        if cur == 0 and prev == 0:
            continue
        group_name = head.parent.name if head.parent else f'Other {head.get_account_group_display()}s'
        if group_name not in buckets:
            buckets[group_name] = {
                'name': group_name,
                'items': [],
                'current_total': Decimal('0'),
                'prev_total': Decimal('0'),
            }
        buckets[group_name]['items'].append(
            {
                'name': head.name,
                'code': head.code,
                'current_amount': cur,
                'prev_amount': prev,
            }
        )
        buckets[group_name]['current_total'] += cur
        buckets[group_name]['prev_total'] += prev
        total_cur += cur
        total_prev += prev

    return list(buckets.values()), total_cur, total_prev


@auditor_or_above
def profit_loss(request):
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    context = {'from_date': from_date, 'to_date': to_date}
    if from_date and to_date:
        from apps.accounting.models import ChartOfAccounts, JournalLine

        branch = None if request.user.can_access_all_branches else request.current_branch
        fd = date.fromisoformat(from_date)
        td = date.fromisoformat(to_date)
        prev_fd = _prev_year_date(fd)
        prev_td = _prev_year_date(td)

        pl_heads = list(
            ChartOfAccounts.objects.filter(
                account_group__in=['income', 'expense'],
                allow_transactions=True,
                is_active=True,
            ).select_related('parent')
        )

        base_filter = Q(
            journal_entry__is_reversed=False,
            journal_entry__is_posted=True,
            gl_account__in=pl_heads,
        )
        if branch:
            base_filter &= Q(journal_entry__branch=branch)

        def _pl_balances(f_date, t_date):
            pre_aggs = (
                JournalLine.objects.filter(base_filter, journal_entry__entry_date__lt=f_date)
                .values('gl_account_id')
                .annotate(dr=Sum('debit_amount'), cr=Sum('credit_amount'))
            )
            pre_map = {row['gl_account_id']: row for row in pre_aggs}
            period_aggs = (
                JournalLine.objects.filter(
                    base_filter,
                    journal_entry__entry_date__gte=f_date,
                    journal_entry__entry_date__lte=t_date,
                )
                .values('gl_account_id')
                .annotate(dr=Sum('debit_amount'), cr=Sum('credit_amount'))
            )
            period_map = {row['gl_account_id']: row for row in period_aggs}
            balances = {}
            for head in pl_heads:
                ob = head.opening_balance or 0
                pre = pre_map.get(head.pk, {})
                prd = period_map.get(head.pk, {})
                if head.account_group == 'income':
                    ob += (pre.get('cr') or 0) - (pre.get('dr') or 0)
                    period = (prd.get('cr') or 0) - (prd.get('dr') or 0)
                else:
                    ob += (pre.get('dr') or 0) - (pre.get('cr') or 0)
                    period = (prd.get('dr') or 0) - (prd.get('cr') or 0)
                balances[head.pk] = ob + period
            return balances

        cur_bals = _pl_balances(from_date, to_date)
        prev_bals = _pl_balances(prev_fd.isoformat(), prev_td.isoformat())

        income_groups, total_income, prev_total_income = _build_groups(
            pl_heads,
            cur_bals,
            prev_bals,
            lambda h: h.account_group == 'income',
        )
        expense_groups, total_expense, prev_total_expense = _build_groups(
            pl_heads,
            cur_bals,
            prev_bals,
            lambda h: h.account_group == 'expense',
        )

        net_profit = total_income - total_expense
        prev_net_profit = prev_total_income - prev_total_expense

        context.update(
            {
                'income_groups': income_groups,
                'expense_groups': expense_groups,
                'total_income': total_income,
                'total_expense': total_expense,
                'net_profit': net_profit,
                'prev_total_income': prev_total_income,
                'prev_total_expense': prev_total_expense,
                'prev_net_profit': prev_net_profit,
                'prev_from_date': prev_fd.isoformat(),
                'prev_to_date': prev_td.isoformat(),
            }
        )
        if request.GET.get('format') == 'csv':
            rows = []
            for grp in income_groups:
                for item in grp['items']:
                    rows.append(
                        [item['code'], item['name'], 'Income', grp['name'], item['current_amount'], item['prev_amount']]
                    )
            for grp in expense_groups:
                for item in grp['items']:
                    rows.append(
                        [
                            item['code'],
                            item['name'],
                            'Expense',
                            grp['name'],
                            item['current_amount'],
                            item['prev_amount'],
                        ]
                    )
            rows.append(['', 'Total Income', '', '', total_income, prev_total_income])
            rows.append(['', 'Total Expense', '', '', total_expense, prev_total_expense])
            rows.append(['', 'Net Profit/(Loss)', '', '', net_profit, prev_net_profit])
            return _csv_response(
                f'profit_loss_{from_date}_to_{to_date}.csv',
                [
                    'Code',
                    'Account',
                    'Type',
                    'Group',
                    f'Current ({from_date} to {to_date})',
                    f'Previous ({prev_fd} to {prev_td})',
                ],
                rows,
            )
    return render(request, 'reports/profit_loss.html', context)


@auditor_or_above
def balance_sheet(request):
    as_on_date = request.GET.get('as_on_date')
    context = {'as_on_date': as_on_date}
    if as_on_date:
        from apps.accounting.models import ChartOfAccounts

        branch = None if request.user.can_access_all_branches else request.current_branch
        aod = date.fromisoformat(as_on_date)
        prev_year_date = _prev_year_date(aod)

        all_heads = list(
            ChartOfAccounts.objects.filter(
                account_group__in=['asset', 'liability', 'equity', 'income', 'expense'],
                allow_transactions=True,
                is_active=True,
            ).select_related('parent')
        )

        cur_agg = _aggregate_journal_lines(all_heads, as_on_date, branch)
        prev_agg = _aggregate_journal_lines(all_heads, prev_year_date.isoformat(), branch)

        cur_bals = _compute_head_balances(all_heads, cur_agg)
        prev_bals = _compute_head_balances(all_heads, prev_agg)

        # Compute net profit (income - expense) for both periods
        cur_income = sum(cur_bals.get(h.pk, 0) for h in all_heads if h.account_group == 'income')
        cur_expense = sum(cur_bals.get(h.pk, 0) for h in all_heads if h.account_group == 'expense')
        net_profit = cur_income - cur_expense

        prev_income = sum(prev_bals.get(h.pk, 0) for h in all_heads if h.account_group == 'income')
        prev_expense = sum(prev_bals.get(h.pk, 0) for h in all_heads if h.account_group == 'expense')
        prev_net_profit = prev_income - prev_expense

        # Build grouped lists for BS heads
        def _is_liability(h):
            return h.account_group in ('liability', 'equity')

        def _is_asset(h):
            return h.account_group == 'asset'

        liability_groups, total_liability, prev_total_liability = _build_groups(
            all_heads,
            cur_bals,
            prev_bals,
            _is_liability,
        )
        asset_groups, total_asset, prev_total_asset = _build_groups(
            all_heads,
            cur_bals,
            prev_bals,
            _is_asset,
        )

        # Append net profit as a virtual liability item
        if net_profit != 0 or prev_net_profit != 0:
            liability_groups.append(
                {
                    'name': 'Profit & Loss',
                    'items': [
                        {
                            'name': 'Net Profit / (Loss)',
                            'code': '—',
                            'current_amount': net_profit,
                            'prev_amount': prev_net_profit,
                        }
                    ],
                    'current_total': net_profit,
                    'prev_total': prev_net_profit,
                }
            )
            total_liability += net_profit
            prev_total_liability += prev_net_profit

        # CRR & SLR ratios
        # Deposits = all liability heads linked to deposit account types
        deposit_tables = {'saving', 'current', 'recurring', 'fixed', 'security', 'client', 'agent'}
        total_deposits = sum(
            cur_bals.get(h.pk, 0)
            for h in all_heads
            if h.account_group in ('liability', 'equity') and h.related_table_name in deposit_tables
        )
        # Cash & Bank = cash heads + bank account heads (account_type 'cash' or 'bank')
        cash_bank = sum(
            cur_bals.get(h.pk, 0)
            for h in all_heads
            if h.account_group == 'asset' and h.account_type in ('cash', 'bank')
        )
        # Investments = bank FD investments (related_table_name 'bank') excluding the bank group heads
        investments = sum(
            cur_bals.get(h.pk, 0)
            for h in all_heads
            if h.account_group == 'asset' and h.related_table_name == 'bank' and h.allow_transactions
        )
        crr_ratio = (cash_bank / total_deposits * 100) if total_deposits else Decimal('0')
        slr_ratio = ((cash_bank + investments) / total_deposits * 100) if total_deposits else Decimal('0')

        context.update(
            {
                'liability_groups': liability_groups,
                'asset_groups': asset_groups,
                'total_liability': total_liability,
                'total_asset': total_asset,
                'prev_total_liability': prev_total_liability,
                'prev_total_asset': prev_total_asset,
                'difference': total_asset - total_liability,
                'net_profit': net_profit,
                'prev_net_profit': prev_net_profit,
                'prev_year_date': prev_year_date.isoformat(),
                'crr_ratio': crr_ratio,
                'slr_ratio': slr_ratio,
            }
        )
        if request.GET.get('format') == 'csv':
            rows = []
            for grp in liability_groups:
                for item in grp['items']:
                    rows.append(
                        [
                            item['code'],
                            item['name'],
                            'Liability/Equity',
                            grp['name'],
                            item['current_amount'],
                            item['prev_amount'],
                        ]
                    )
                rows.append(['', f'Sub-total: {grp["name"]}', '', '', grp['current_total'], grp['prev_total']])
            rows.append(['', 'Total Liabilities & Equity', '', '', total_liability, prev_total_liability])
            for grp in asset_groups:
                for item in grp['items']:
                    rows.append(
                        [item['code'], item['name'], 'Asset', grp['name'], item['current_amount'], item['prev_amount']]
                    )
                rows.append(['', f'Sub-total: {grp["name"]}', '', '', grp['current_total'], grp['prev_total']])
            rows.append(['', 'Total Assets', '', '', total_asset, prev_total_asset])
            return _csv_response(
                f'balance_sheet_{as_on_date}.csv',
                ['Code', 'Account', 'Type', 'Group', f'As on {as_on_date}', f'As on {prev_year_date}'],
                rows,
            )
    return render(request, 'reports/balance_sheet.html', context)


@auditor_or_above
def subsidiary_ledger(request):
    """Audit schedule: all accounts of a given type with closing balances."""
    ledger_type = request.GET.get('type', '')
    as_on_date = request.GET.get('as_on_date', '')
    branch = None if request.user.can_access_all_branches else request.current_branch

    ledger_types = [
        ('savings', 'Savings Deposits'),
        ('current', 'Current Accounts'),
        ('security', 'Security Deposits'),
        ('director_security', 'Director Security Deposits'),
        ('fixed_deposit', 'Fixed Deposits'),
        ('recurring_deposit', 'Recurring Deposits'),
        ('pigmmy', 'Daily / Pigmy Deposits'),
        ('share_capital', 'Share Capital'),
        ('regular_loan', 'Regular Loans'),
        ('emergency_loan', 'Emergency Loans'),
        ('mortgage_loan', 'Mortgage / Property Loans'),
        ('fd_loan', 'Loans Against FD'),
        ('pigmmy_loan', 'Loans Against Pigmy'),
        ('rd_loan', 'Loans Against RD'),
        ('agent_security', 'Agent Security Deposits'),
    ]

    context = {
        'ledger_type': ledger_type,
        'as_on_date': as_on_date,
        'ledger_types': ledger_types,
    }

    if not ledger_type:
        return render(request, 'reports/subsidiary_ledger.html', context)

    items = []
    total = Decimal('0')
    count = 0

    if ledger_type in ('savings', 'current', 'security', 'director_security'):
        from apps.savings.models import SavingsAccount

        qs = (
            SavingsAccount.objects.filter(
                account_type=ledger_type,
                status='active',
            )
            .select_related('member')
            .order_by('account_no')
        )
        if branch:
            qs = qs.filter(branch=branch)
        for acct in qs:
            items.append(
                {
                    'account_no': acct.account_no,
                    'member': acct.member.name,
                    'member_no': acct.member.member_no,
                    'balance': acct.current_balance,
                }
            )
            total += acct.current_balance
            count += 1

    elif ledger_type == 'fixed_deposit':
        from apps.deposits.models import FixedDeposit

        qs = FixedDeposit.objects.filter(status='active').select_related('member').order_by('fd_no')
        if branch:
            qs = qs.filter(branch=branch)
        for fd in qs:
            items.append(
                {
                    'account_no': fd.fd_no,
                    'member': fd.member.name,
                    'member_no': fd.member.member_no,
                    'balance': fd.deposit_amount,
                }
            )
            total += fd.deposit_amount
            count += 1

    elif ledger_type == 'recurring_deposit':
        from apps.deposits.models import RecurringDeposit

        qs = RecurringDeposit.objects.filter(status='active').select_related('member').order_by('rd_no')
        if branch:
            qs = qs.filter(branch=branch)
        for rd in qs:
            paid = rd.installments.filter(status='paid').aggregate(t=Sum('paid_amount'))['t'] or Decimal('0')
            items.append(
                {
                    'account_no': rd.rd_no,
                    'member': rd.member.name,
                    'member_no': rd.member.member_no,
                    'balance': paid,
                }
            )
            total += paid
            count += 1

    elif ledger_type == 'pigmmy':
        from apps.agents.models import PigmmyAccount

        qs = PigmmyAccount.objects.filter(status='active').select_related('member', 'agent').order_by('account_no')
        if branch:
            qs = qs.filter(branch=branch)
        for pa in qs:
            items.append(
                {
                    'account_no': pa.account_no,
                    'member': pa.member.name,
                    'member_no': pa.member.member_no,
                    'balance': pa.current_balance,
                }
            )
            total += pa.current_balance
            count += 1

    elif ledger_type == 'share_capital':
        from apps.shares.models import ShareHolding

        qs = ShareHolding.objects.filter(status='active').select_related('member').order_by('member__member_no')
        if branch:
            qs = qs.filter(branch=branch)
        for sh in qs:
            items.append(
                {
                    'account_no': sh.certificate_no or '—',
                    'member': sh.member.name,
                    'member_no': sh.member.member_no,
                    'balance': sh.total_amount,
                }
            )
            total += sh.total_amount
            count += 1

    elif ledger_type == 'agent_security':
        from apps.agents.models import Agent

        qs = Agent.objects.filter(status='active').select_related('member').order_by('agent_code')
        if branch:
            qs = qs.filter(branch=branch)
        for agent in qs:
            items.append(
                {
                    'account_no': agent.agent_code,
                    'member': agent.member.name,
                    'member_no': agent.member.member_no,
                    'balance': agent.security_deposit_amount,
                }
            )
            total += agent.security_deposit_amount
            count += 1

    else:
        from apps.loans.models import LoanAccount

        loan_type_map = {
            'regular_loan': {'loan_product__loan_category': 'regular'},
            'emergency_loan': {'loan_product__loan_category': 'emergency'},
            'mortgage_loan': {'loan_product__mortgage_type': 'property'},
            'fd_loan': {'loan_product__mortgage_type': 'fixed_deposit'},
            'pigmmy_loan': {'loan_product__mortgage_type': 'pigmmy'},
            'rd_loan': {'loan_product__mortgage_type': 'recurring_deposit'},
        }
        filters = loan_type_map.get(ledger_type, {})
        qs = (
            LoanAccount.objects.filter(
                status__in=['disbursed', 'npa'],
                **filters,
            )
            .select_related('member', 'loan_product')
            .order_by('loan_no')
        )
        if branch:
            qs = qs.filter(branch=branch)
        for loan in qs:
            items.append(
                {
                    'account_no': loan.loan_no,
                    'member': loan.member.name,
                    'member_no': loan.member.member_no,
                    'balance': loan.outstanding_principal,
                }
            )
            total += loan.outstanding_principal
            count += 1

    type_label = dict(ledger_types).get(ledger_type, ledger_type)
    context.update(
        {
            'items': items,
            'total': total,
            'count': count,
            'type_label': type_label,
        }
    )

    if request.GET.get('format') == 'csv' and items:
        rows = [[i['account_no'], i['member_no'], i['member'], i['balance']] for i in items]
        rows.append(['', '', 'Total', total])
        return _csv_response(
            f'subsidiary_ledger_{ledger_type}_{as_on_date or date.today()}.csv',
            ['Account No', 'Member No', 'Member Name', 'Balance'],
            rows,
        )

    return render(request, 'reports/subsidiary_ledger.html', context)


@auditor_or_above
def cashbook_report(request):
    """Daily cashbook report with opening balance, head-wise receipts/payments, closing balance."""
    from apps.accounting.models import CashbookMaster, JournalEntry, JournalLine

    report_date = request.GET.get('date', '')
    context = {'report_date': report_date}

    if request.user.can_access_all_branches:
        from apps.branches.models import Branch

        context['branches'] = Branch.objects.filter(status='active').order_by('-is_head_office', 'branch_name')
        selected_branch_id = request.GET.get('branch', '')
        context['selected_branch'] = selected_branch_id
        if selected_branch_id:
            branch = Branch.objects.filter(pk=selected_branch_id).first()
        else:
            branch = None
    else:
        branch = request.current_branch

    if report_date:
        if branch:
            cb = CashbookMaster.objects.filter(branch=branch, txn_date=report_date).first()
            if cb:
                context['cashbook'] = cb

            entries = JournalEntry.objects.filter(
                branch=branch,
                entry_date=report_date,
                is_reversed=False,
                is_posted=True,
            )
        else:
            cbs = CashbookMaster.objects.filter(txn_date=report_date).select_related('branch')
            if cbs.exists():
                total_opening = sum(cb.opening_balance for cb in cbs)
                total_receipts = sum(cb.total_receipts for cb in cbs)
                total_payments = sum(cb.total_payments for cb in cbs)
                total_closing = sum(cb.closing_balance for cb in cbs)
                context['cashbook'] = type(
                    'CB',
                    (),
                    {
                        'opening_balance': total_opening,
                        'total_receipts': total_receipts,
                        'total_payments': total_payments,
                        'closing_balance': total_closing,
                    },
                )()
                context['branch_cashbooks'] = cbs

            entries = JournalEntry.objects.filter(
                entry_date=report_date,
                is_reversed=False,
                is_posted=True,
            )

        head_summary = {}
        for line in JournalLine.objects.filter(journal_entry__in=entries).select_related('gl_account'):
            code = line.gl_account.code
            name = line.gl_account.name
            if code not in head_summary:
                head_summary[code] = {'code': code, 'name': name, 'debit': Decimal('0'), 'credit': Decimal('0')}
            head_summary[code]['debit'] += line.debit_amount
            head_summary[code]['credit'] += line.credit_amount

        heads = sorted(head_summary.values(), key=lambda h: h['code'])
        context['heads'] = heads
        context['total_debit'] = sum(h['debit'] for h in heads)
        context['total_credit'] = sum(h['credit'] for h in heads)

        if request.GET.get('format') == 'csv' and heads:
            rows = [[h['code'], h['name'], h['debit'], h['credit']] for h in heads]
            return _csv_response(
                f'cashbook_{report_date}.csv',
                ['Code', 'Account', 'Debit', 'Credit'],
                rows,
            )

    return render(request, 'reports/cashbook_report.html', context)


@auditor_or_above
def balance_reports(request):
    from datetime import timedelta

    from apps.savings.models import SavingsAccount

    report_type = request.GET.get('type', 'nil_balance')
    branch = None if request.user.can_access_all_branches else getattr(request, 'current_branch', None)
    accounts = None
    type_summary = None

    base_qs = SavingsAccount.objects.select_related('member')
    if branch:
        base_qs = base_qs.filter(branch=branch)

    if report_type == 'nil_balance':
        accounts = base_qs.filter(status='active', current_balance=0).annotate(last_txn=Max('transactions__txn_date'))

    elif report_type == 'non_operated':
        cutoff = date.today() - timedelta(days=180)
        accounts = (
            base_qs.filter(status='active')
            .annotate(last_txn=Max('transactions__txn_date'))
            .filter(Q(last_txn__lt=cutoff) | Q(last_txn__isnull=True))
        )

    elif report_type == 'dormant':
        accounts = base_qs.filter(status='dormant').annotate(last_txn=Max('transactions__txn_date'))

    elif report_type == 'balance_with_last_txn':
        accounts = (
            base_qs.filter(status='active')
            .annotate(last_txn=Max('transactions__txn_date'))
            .order_by('-current_balance')
        )

    elif report_type == 'balance_by_type':
        type_summary = (
            SavingsAccount.objects.filter(status='active')
            .values('account_type')
            .annotate(count=Count('id'), total=Sum('current_balance'))
            .order_by('account_type')
        )
        if branch:
            type_summary = type_summary.filter(branch=branch)

    elif report_type == 'balance_range':
        min_amount = request.GET.get('min_amount', '')
        max_amount = request.GET.get('max_amount', '')
        qs = base_qs.filter(status='active')
        try:
            if min_amount:
                qs = qs.filter(current_balance__gte=Decimal(min_amount))
            if max_amount:
                qs = qs.filter(current_balance__lte=Decimal(max_amount))
        except Exception:
            pass
        accounts = qs.annotate(last_txn=Max('transactions__txn_date')).order_by('-current_balance')

    context = {
        'report_type': report_type,
        'accounts': accounts,
        'type_summary': type_summary,
        'min_amount': request.GET.get('min_amount', ''),
        'max_amount': request.GET.get('max_amount', ''),
    }

    if request.GET.get('format') == 'csv':
        if accounts is not None:
            rows = [
                [
                    a.account_no,
                    a.member.name,
                    a.get_account_type_display(),
                    a.current_balance,
                    getattr(a, 'last_txn', ''),
                ]
                for a in accounts
            ]
            return _csv_response(
                f'balance_report_{report_type}_{date.today()}.csv',
                ['Account No', 'Member', 'Type', 'Balance', 'Last Txn'],
                rows,
            )
        if type_summary is not None:
            rows = [[s['account_type'], s['count'], s['total']] for s in type_summary]
            return _csv_response(
                f'balance_by_type_{date.today()}.csv',
                ['Account Type', 'Count', 'Total Balance'],
                rows,
            )

    return render(request, 'reports/balance_reports.html', context)


@auditor_or_above
def enquiry(request):
    from apps.members.models import Member

    report_type = request.GET.get('type', 'all_accounts')
    members = Member.objects.filter(status='active').order_by('name')
    branch = None if request.user.can_access_all_branches else getattr(request, 'current_branch', None)

    context = {
        'report_type': report_type,
        'members': members,
        'from_date': request.GET.get('from_date', ''),
        'to_date': request.GET.get('to_date', ''),
    }

    if report_type == 'all_accounts':
        member_id = request.GET.get('member', '')
        context['selected_member'] = member_id
        if member_id:
            try:
                member = Member.objects.get(pk=member_id)
            except Member.DoesNotExist:
                return render(request, 'reports/enquiry.html', context)

            context['member'] = member

            from apps.agents.models import PigmmyAccount
            from apps.deposits.models import FixedDeposit, RecurringDeposit
            from apps.loans.models import LoanAccount
            from apps.savings.models import SavingsAccount
            from apps.shares.models import ShareHolding

            context['savings'] = SavingsAccount.objects.filter(member=member).order_by('account_type')
            context['shares'] = ShareHolding.objects.filter(member=member, status='active')
            context['loans'] = (
                LoanAccount.objects.filter(member=member)
                .exclude(status__in=['closed', 'rejected', 'written_off'])
                .select_related('loan_product')
            )
            context['fds'] = FixedDeposit.objects.filter(member=member).exclude(status='renewed')
            rds = RecurringDeposit.objects.filter(member=member).annotate(
                paid_count=Count('installments', filter=Q(installments__status='paid')),
            )
            context['rds'] = [{'rd': rd, 'paid_count': rd.paid_count} for rd in rds]
            context['pigmmy'] = PigmmyAccount.objects.filter(member=member).select_related('agent')

    elif report_type == 'opening_register':
        from_date = request.GET.get('from_date', '')
        to_date = request.GET.get('to_date', '')
        if from_date and to_date:
            from apps.agents.models import PigmmyAccount
            from apps.deposits.models import FixedDeposit, RecurringDeposit
            from apps.loans.models import LoanAccount
            from apps.savings.models import SavingsAccount

            entries = []
            for sa in SavingsAccount.objects.filter(
                opening_date__gte=from_date, opening_date__lte=to_date
            ).select_related('member'):
                entries.append(
                    {
                        'type': f'Savings ({sa.get_account_type_display()})',
                        'account_no': sa.account_no,
                        'member': sa.member.name,
                        'date': sa.opening_date,
                    }
                )
            for la in LoanAccount.objects.filter(applied_date__gte=from_date, applied_date__lte=to_date).select_related(
                'member', 'loan_product'
            ):
                entries.append(
                    {
                        'type': f'Loan ({la.loan_product.name})',
                        'account_no': la.loan_no,
                        'member': la.member.name,
                        'date': la.applied_date,
                    }
                )
            for fd in FixedDeposit.objects.filter(start_date__gte=from_date, start_date__lte=to_date).select_related(
                'member'
            ):
                entries.append(
                    {'type': 'Fixed Deposit', 'account_no': fd.fd_no, 'member': fd.member.name, 'date': fd.start_date}
                )
            for rd in RecurringDeposit.objects.filter(
                start_date__gte=from_date, start_date__lte=to_date
            ).select_related('member'):
                entries.append(
                    {
                        'type': 'Recurring Deposit',
                        'account_no': rd.rd_no,
                        'member': rd.member.name,
                        'date': rd.start_date,
                    }
                )
            for pa in PigmmyAccount.objects.filter(
                opening_date__gte=from_date, opening_date__lte=to_date
            ).select_related('member'):
                entries.append(
                    {
                        'type': f'Pigmmy ({pa.get_deposit_type_display()})',
                        'account_no': pa.account_no,
                        'member': pa.member.name,
                        'date': pa.opening_date,
                    }
                )
            entries.sort(key=lambda e: e['date'])
            context['entries'] = entries

    elif report_type == 'closing_register':
        from_date = request.GET.get('from_date', '')
        to_date = request.GET.get('to_date', '')
        if from_date and to_date:
            from apps.deposits.models import FixedDeposit
            from apps.loans.models import LoanAccount
            from apps.savings.models import SavingsAccount

            entries = []
            for sa in SavingsAccount.objects.filter(
                closing_date__gte=from_date, closing_date__lte=to_date
            ).select_related('member'):
                entries.append(
                    {
                        'type': f'Savings ({sa.get_account_type_display()})',
                        'account_no': sa.account_no,
                        'member': sa.member.name,
                        'date': sa.closing_date,
                    }
                )
            for la in LoanAccount.objects.filter(closure_date__gte=from_date, closure_date__lte=to_date).select_related(
                'member', 'loan_product'
            ):
                entries.append(
                    {
                        'type': f'Loan ({la.loan_product.name})',
                        'account_no': la.loan_no,
                        'member': la.member.name,
                        'date': la.closure_date,
                    }
                )
            for fd in FixedDeposit.objects.filter(
                maturity_date__gte=from_date, maturity_date__lte=to_date, status__in=['matured', 'prematurely_closed']
            ).select_related('member'):
                entries.append(
                    {
                        'type': 'Fixed Deposit',
                        'account_no': fd.fd_no,
                        'member': fd.member.name,
                        'date': fd.premature_closure_date or fd.maturity_date,
                    }
                )
            entries.sort(key=lambda e: e['date'])
            context['entries'] = entries

    elif report_type == 'shareholder_details':
        from apps.shares.models import ShareHolding

        holdings = ShareHolding.objects.filter(status='active').select_related('member').order_by('member__name')
        if branch:
            holdings = holdings.filter(branch=branch)
        context['holdings'] = holdings
        context['total_shares'] = holdings.aggregate(t=Sum('share_count'))['t'] or 0
        context['total_amount'] = holdings.aggregate(t=Sum('total_amount'))['t'] or Decimal('0')

    return render(request, 'reports/enquiry.html', context)


@auditor_or_above
def pigmmy_reports(request):

    from apps.agents.models import Agent, AgentCommission, PigmmyAccount, PigmmyTransaction

    report_type = request.GET.get('type', 'agent_clients')
    agents = Agent.objects.filter(status='active').order_by('agent_code')
    branch = None if request.user.can_access_all_branches else getattr(request, 'current_branch', None)

    context = {
        'report_type': report_type,
        'agents': agents,
        'selected_agent': request.GET.get('agent', ''),
        'report_date': request.GET.get('date', ''),
        'from_date': request.GET.get('from_date', ''),
        'to_date': request.GET.get('to_date', ''),
    }

    if report_type == 'agent_clients':
        agent_id = request.GET.get('agent', '')
        qs = PigmmyAccount.objects.filter(status='active').select_related('member', 'agent')
        if branch:
            qs = qs.filter(branch=branch)
        if agent_id:
            qs = qs.filter(agent_id=agent_id)
        context['accounts'] = qs.order_by('agent__agent_code', 'account_no')
        context['summary'] = (
            qs.values('agent__agent_code', 'agent__member__name')
            .annotate(client_count=Count('id'), total_balance=Sum('current_balance'))
            .order_by('agent__agent_code')
        )

    elif report_type == 'date_daybook':
        report_date = request.GET.get('date', '')
        if report_date:
            qs = PigmmyTransaction.objects.filter(txn_date=report_date, is_reversed=False).select_related(
                'account__member', 'account__agent'
            )
            if branch:
                qs = qs.filter(account__branch=branch)
            context['transactions'] = qs.order_by('account__agent__agent_code', 'account__account_no')
            context['total_amount'] = qs.aggregate(t=Sum('amount'))['t'] or Decimal('0')

    elif report_type == 'deposit_type':
        qs = PigmmyAccount.objects.filter(status='active')
        if branch:
            qs = qs.filter(branch=branch)
        context['type_summary'] = (
            qs.values('deposit_type')
            .annotate(count=Count('id'), total_balance=Sum('current_balance'))
            .order_by('deposit_type')
        )

    elif report_type == 'matured':
        qs = PigmmyAccount.objects.filter(maturity_date__lte=date.today(), status='active').select_related(
            'member', 'agent'
        )
        if branch:
            qs = qs.filter(branch=branch)
        context['accounts'] = qs.order_by('maturity_date')

    elif report_type == 'commission':
        from_date = request.GET.get('from_date', '')
        to_date = request.GET.get('to_date', '')
        if from_date and to_date:
            qs = AgentCommission.objects.filter(month__gte=from_date, month__lte=to_date).select_related(
                'agent__member'
            )
            context['commissions'] = qs.order_by('agent__agent_code', 'month')
            context['total_commission'] = qs.aggregate(t=Sum('commission_amount'))['t'] or Decimal('0')
            context['total_tds'] = qs.aggregate(t=Sum('tds_amount'))['t'] or Decimal('0')
            context['total_net'] = qs.aggregate(t=Sum('net_amount'))['t'] or Decimal('0')

    if request.GET.get('format') == 'csv':
        if report_type == 'agent_clients' and context.get('accounts') is not None:
            rows = [[a.agent.agent_code, a.account_no, a.member.name, a.current_balance] for a in context['accounts']]
            return _csv_response(
                f'pigmmy_agent_clients_{date.today()}.csv',
                ['Agent Code', 'Account No', 'Member', 'Balance'],
                rows,
            )
        if report_type == 'date_daybook' and context.get('transactions') is not None:
            rows = [
                [t.account.agent.agent_code, t.account.account_no, t.account.member.name, t.amount]
                for t in context['transactions']
            ]
            return _csv_response(
                f'pigmmy_daybook_{context.get("report_date", date.today())}.csv',
                ['Agent', 'Account No', 'Member', 'Amount'],
                rows,
            )
        if report_type == 'commission' and context.get('commissions') is not None:
            rows = [
                [c.agent.member.name, c.agent.agent_code, c.month, c.commission_amount, c.tds_amount, c.net_amount]
                for c in context['commissions']
            ]
            return _csv_response(
                f'pigmmy_commission_{date.today()}.csv',
                ['Agent', 'Code', 'Month', 'Commission', 'TDS', 'Net'],
                rows,
            )

    return render(request, 'reports/pigmmy_reports.html', context)


def _branch_filter(request, qs):
    if not request.user.can_access_all_branches:
        qs = qs.filter(branch=request.current_branch)
    return qs


DEPOSIT_AMOUNT_RANGES = [
    (0, 10000, '<=10,000'),
    (10001, 50000, '10,001 - 50,000'),
    (50001, 100000, '50,001 - 1,00,000'),
    (100001, 500000, '1,00,001 - 5,00,000'),
    (500001, None, '5,00,001+'),
]

FD_PERIOD_RANGES = [
    (0, 90, '<=90 days'),
    (91, 180, '91 - 180 days'),
    (181, 365, '181 - 365 days'),
    (366, 730, '1 - 2 years'),
    (731, 1825, '2 - 5 years'),
    (1826, None, '5+ years'),
]

LOAN_AMOUNT_RANGES = [
    (0, 25000, '<=25,000'),
    (25001, 50000, '25,001 - 50,000'),
    (50001, 100000, '50,001 - 1,00,000'),
    (100001, 500000, '1,00,001 - 5,00,000'),
    (500001, None, '5,00,001+'),
]


@auditor_or_above
def deposit_reports(request):
    from apps.deposits.models import FixedDeposit, RDInstallment, RecurringDeposit
    from apps.loans.models import LoanAccount

    report_type = request.GET.get('type', '')
    fd_or_rd = request.GET.get('fd_or_rd', 'fd')
    from_date = request.GET.get('from_date', '')
    to_date = request.GET.get('to_date', '')

    context = {
        'report_type': report_type,
        'fd_or_rd': fd_or_rd,
        'from_date': from_date,
        'to_date': to_date,
    }

    if not report_type:
        return render(request, 'reports/deposit_reports.html', context)

    if report_type == 'period_wise':
        groups = []
        if fd_or_rd in ('fd', 'all'):
            fds = _branch_filter(request, FixedDeposit.objects.filter(status='active'))
            for lo, hi, label in FD_PERIOD_RANGES:
                qs = fds.filter(tenure_days__gte=lo)
                if hi is not None:
                    qs = qs.filter(tenure_days__lte=hi)
                agg = qs.aggregate(count=Count('id'), total=Sum('deposit_amount'))
                groups.append(
                    {
                        'label': label,
                        'count': agg['count'] or 0,
                        'total': agg['total'] or 0,
                        'deposit_type': 'FD',
                    }
                )
        if fd_or_rd in ('rd', 'all'):
            rds = _branch_filter(request, RecurringDeposit.objects.filter(status='active'))
            rd_ranges = [
                (0, 12, '≤ 12 months'),
                (13, 24, '13 - 24 months'),
                (25, 36, '25 - 36 months'),
                (37, 60, '37 - 60 months'),
                (61, None, '60+ months'),
            ]
            for lo, hi, label in rd_ranges:
                qs = rds.filter(tenure_months__gte=lo)
                if hi is not None:
                    qs = qs.filter(tenure_months__lte=hi)
                agg = qs.aggregate(count=Count('id'), total=Sum('monthly_installment'))
                groups.append(
                    {
                        'label': label,
                        'count': agg['count'] or 0,
                        'total': agg['total'] or 0,
                        'deposit_type': 'RD',
                    }
                )
        context['groups'] = groups
        context['total_count'] = sum(g['count'] for g in groups)
        context['total_amount'] = sum(g['total'] for g in groups)

    elif report_type == 'amount_wise':
        groups = []
        if fd_or_rd in ('fd', 'all'):
            fds = _branch_filter(request, FixedDeposit.objects.filter(status='active'))
            for lo, hi, label in DEPOSIT_AMOUNT_RANGES:
                qs = fds.filter(deposit_amount__gte=lo)
                if hi is not None:
                    qs = qs.filter(deposit_amount__lte=hi)
                agg = qs.aggregate(count=Count('id'), total=Sum('deposit_amount'))
                groups.append(
                    {
                        'label': label,
                        'count': agg['count'] or 0,
                        'total': agg['total'] or 0,
                        'deposit_type': 'FD',
                    }
                )
        if fd_or_rd in ('rd', 'all'):
            rds = _branch_filter(request, RecurringDeposit.objects.filter(status='active'))
            for lo, hi, label in DEPOSIT_AMOUNT_RANGES:
                qs = rds.filter(monthly_installment__gte=lo)
                if hi is not None:
                    qs = qs.filter(monthly_installment__lte=hi)
                agg = qs.aggregate(count=Count('id'), total=Sum('monthly_installment'))
                groups.append(
                    {
                        'label': label,
                        'count': agg['count'] or 0,
                        'total': agg['total'] or 0,
                        'deposit_type': 'RD',
                    }
                )
        context['groups'] = groups
        context['total_count'] = sum(g['count'] for g in groups)
        context['total_amount'] = sum(g['total'] for g in groups)

    elif report_type == 'maturity_wise':
        if from_date and to_date:
            items = []
            if fd_or_rd in ('fd', 'all'):
                fds = _branch_filter(
                    request,
                    FixedDeposit.objects.filter(
                        maturity_date__gte=from_date,
                        maturity_date__lte=to_date,
                    ).select_related('member'),
                )
                for fd in fds:
                    items.append(
                        {
                            'account_no': fd.fd_no,
                            'member': fd.member.name,
                            'amount': fd.deposit_amount,
                            'maturity_date': fd.maturity_date,
                            'maturity_amount': fd.maturity_amount,
                            'interest_rate': fd.interest_rate,
                            'status': fd.get_status_display(),
                            'deposit_type': 'FD',
                        }
                    )
            if fd_or_rd in ('rd', 'all'):
                rds = _branch_filter(
                    request,
                    RecurringDeposit.objects.filter(
                        maturity_date__gte=from_date,
                        maturity_date__lte=to_date,
                    ).select_related('member'),
                )
                for rd in rds:
                    items.append(
                        {
                            'account_no': rd.rd_no,
                            'member': rd.member.name,
                            'amount': rd.monthly_installment,
                            'maturity_date': rd.maturity_date,
                            'maturity_amount': rd.maturity_amount,
                            'interest_rate': rd.interest_rate,
                            'status': rd.get_status_display(),
                            'deposit_type': 'RD',
                        }
                    )
            items.sort(key=lambda x: x['maturity_date'])
            context['items'] = items

    elif report_type == 'interest_wise':
        groups = []
        if fd_or_rd in ('fd', 'all'):
            fds = _branch_filter(request, FixedDeposit.objects.filter(status='active'))
            rates = fds.values_list('interest_rate', flat=True).distinct().order_by('interest_rate')
            for rate in rates:
                agg = fds.filter(interest_rate=rate).aggregate(count=Count('id'), total=Sum('deposit_amount'))
                groups.append(
                    {
                        'label': f'{rate}%',
                        'rate': rate,
                        'count': agg['count'] or 0,
                        'total': agg['total'] or 0,
                        'deposit_type': 'FD',
                    }
                )
        if fd_or_rd in ('rd', 'all'):
            rds = _branch_filter(request, RecurringDeposit.objects.filter(status='active'))
            rates = rds.values_list('interest_rate', flat=True).distinct().order_by('interest_rate')
            for rate in rates:
                agg = rds.filter(interest_rate=rate).aggregate(count=Count('id'), total=Sum('monthly_installment'))
                groups.append(
                    {
                        'label': f'{rate}%',
                        'rate': rate,
                        'count': agg['count'] or 0,
                        'total': agg['total'] or 0,
                        'deposit_type': 'RD',
                    }
                )
        context['groups'] = groups
        context['total_count'] = sum(g['count'] for g in groups)
        context['total_amount'] = sum(g['total'] for g in groups)

    elif report_type == 'matured_not_paid':
        fds = _branch_filter(
            request,
            FixedDeposit.objects.filter(
                maturity_date__lte=date.today(),
                status='active',
            ).select_related('member'),
        )
        context['items'] = [
            {
                'account_no': fd.fd_no,
                'member': fd.member.name,
                'amount': fd.deposit_amount,
                'maturity_date': fd.maturity_date,
                'maturity_amount': fd.maturity_amount,
                'interest_rate': fd.interest_rate,
                'days_overdue': (date.today() - fd.maturity_date).days,
                'deposit_type': 'FD',
            }
            for fd in fds
        ]

    elif report_type == 'renewal_list':
        fds = _branch_filter(
            request,
            FixedDeposit.objects.filter(status='renewed').select_related('member'),
        )
        if from_date and to_date:
            fds = fds.filter(start_date__gte=from_date, start_date__lte=to_date)
        context['items'] = [
            {
                'account_no': fd.fd_no,
                'member': fd.member.name,
                'amount': fd.deposit_amount,
                'start_date': fd.start_date,
                'maturity_date': fd.maturity_date,
                'interest_rate': fd.interest_rate,
                'deposit_type': 'FD',
            }
            for fd in fds
        ]

    elif report_type == 'premature_list':
        fds = _branch_filter(
            request,
            FixedDeposit.objects.filter(
                status='prematurely_closed',
            ).select_related('member'),
        )
        if from_date and to_date:
            fds = fds.filter(
                premature_closure_date__gte=from_date,
                premature_closure_date__lte=to_date,
            )
        context['items'] = [
            {
                'account_no': fd.fd_no,
                'member': fd.member.name,
                'amount': fd.deposit_amount,
                'closure_date': fd.premature_closure_date,
                'premature_amount': fd.premature_amount,
                'interest_rate': fd.interest_rate,
                'deposit_type': 'FD',
            }
            for fd in fds
        ]

    elif report_type == 'loan_against_deposit':
        loans = _branch_filter(
            request,
            LoanAccount.objects.filter(
                loan_product__mortgage_type='fixed_deposit',
                status__in=['disbursed', 'npa', 'approved'],
            ).select_related('member', 'loan_product'),
        )
        context['items'] = [
            {
                'loan_no': la.loan_no,
                'member': la.member.name,
                'loan_amount': la.disbursed_amount or la.approved_amount,
                'outstanding': la.outstanding_principal,
                'mortgage_account_no': la.mortgage_account_no,
                'status': la.get_status_display(),
            }
            for la in loans
        ]

    elif report_type == 'rd_due':
        installments = RDInstallment.objects.filter(
            status__in=['pending', 'overdue'],
        ).select_related('rd__member', 'rd')
        if from_date and to_date:
            installments = installments.filter(due_date__gte=from_date, due_date__lte=to_date)
        if not request.user.can_access_all_branches:
            installments = installments.filter(rd__branch=request.current_branch)
        context['items'] = [
            {
                'rd_no': inst.rd.rd_no,
                'member': inst.rd.member.name,
                'installment_no': inst.installment_no,
                'due_date': inst.due_date,
                'amount': inst.amount,
                'status': inst.get_status_display(),
            }
            for inst in installments[:500]
        ]

    if request.GET.get('format') == 'csv' and report_type:
        if 'groups' in context:
            rows = [[g.get('deposit_type', ''), g['label'], g['count'], g['total']] for g in context['groups']]
            return _csv_response(
                f'deposit_{report_type}_{date.today()}.csv',
                ['Deposit Type', 'Range', 'Count', 'Total'],
                rows,
            )
        if 'items' in context:
            items = context['items']
            if items and 'account_no' in items[0]:
                rows = [
                    [
                        i.get('account_no', i.get('rd_no', '')),
                        i.get('member', ''),
                        i.get('amount', ''),
                        i.get('maturity_date', i.get('due_date', '')),
                        i.get('interest_rate', ''),
                        i.get('status', ''),
                    ]
                    for i in items
                ]
                return _csv_response(
                    f'deposit_{report_type}_{date.today()}.csv',
                    ['Account No', 'Member', 'Amount', 'Date', 'Rate%', 'Status'],
                    rows,
                )

    return render(request, 'reports/deposit_reports.html', context)


@auditor_or_above
def loan_reports(request):
    from apps.loans.models import EMISchedule, LoanAccount, LoanGuarantor, LoanRepayment

    report_type = request.GET.get('type', '')
    from_date = request.GET.get('from_date', '')
    to_date = request.GET.get('to_date', '')

    context = {
        'report_type': report_type,
        'from_date': from_date,
        'to_date': to_date,
    }

    if not report_type:
        return render(request, 'reports/loan_reports.html', context)

    active_statuses = ['disbursed', 'npa']

    if report_type == 'sanction_amount_wise':
        loans = _branch_filter(
            request,
            LoanAccount.objects.filter(status__in=active_statuses + ['approved', 'closed']),
        )
        groups = []
        for lo, hi, label in LOAN_AMOUNT_RANGES:
            amt_field = 'approved_amount'
            qs = loans.filter(**{f'{amt_field}__gte': lo})
            if hi is not None:
                qs = qs.filter(**{f'{amt_field}__lte': hi})
            agg = qs.aggregate(count=Count('id'), total=Sum(amt_field))
            groups.append(
                {
                    'label': label,
                    'count': agg['count'] or 0,
                    'total': agg['total'] or 0,
                }
            )
        context['groups'] = groups

    elif report_type == 'sanction_date_wise':
        if from_date and to_date:
            loans = _branch_filter(
                request,
                LoanAccount.objects.filter(
                    approved_date__gte=from_date,
                    approved_date__lte=to_date,
                )
                .select_related('member', 'loan_product')
                .order_by('approved_date'),
            )
            context['items'] = [
                {
                    'loan_no': la.loan_no,
                    'member': la.member.name,
                    'product': la.loan_product.name,
                    'approved_date': la.approved_date,
                    'approved_amount': la.approved_amount,
                    'interest_rate': la.interest_rate,
                    'tenure': la.tenure_months,
                    'status': la.get_status_display(),
                }
                for la in loans
            ]

    elif report_type == 'disbursement_register':
        if from_date and to_date:
            loans = _branch_filter(
                request,
                LoanAccount.objects.filter(
                    disbursed_date__gte=from_date,
                    disbursed_date__lte=to_date,
                )
                .select_related('member', 'loan_product')
                .order_by('disbursed_date'),
            )
            items = []
            for la in loans:
                guarantor_names = ', '.join(
                    g.guarantor_member.name for g in la.guarantors.select_related('guarantor_member').all()
                )
                items.append(
                    {
                        'loan_no': la.loan_no,
                        'member': la.member.name,
                        'product': la.loan_product.name,
                        'disbursed_date': la.disbursed_date,
                        'disbursed_amount': la.disbursed_amount,
                        'interest_rate': la.interest_rate,
                        'tenure': la.tenure_months,
                        'guarantors': guarantor_names,
                    }
                )
            context['items'] = items

    elif report_type == 'demand_list':
        if from_date and to_date:
            emis = (
                EMISchedule.objects.filter(
                    due_date__gte=from_date,
                    due_date__lte=to_date,
                    status__in=['pending', 'overdue'],
                )
                .select_related('loan__member', 'loan__loan_product')
                .order_by('due_date')
            )
            if not request.user.can_access_all_branches:
                emis = emis.filter(loan__branch=request.current_branch)
            context['items'] = [
                {
                    'loan_no': emi.loan.loan_no,
                    'member': emi.loan.member.name,
                    'installment_no': emi.installment_no,
                    'due_date': emi.due_date,
                    'principal': emi.principal_component,
                    'interest': emi.interest_component,
                    'total_emi': emi.total_emi,
                    'status': emi.get_status_display(),
                }
                for emi in emis[:500]
            ]
            total = emis.aggregate(
                total_principal=Sum('principal_component'),
                total_interest=Sum('interest_component'),
                total_emi=Sum('total_emi'),
            )
            context['totals'] = {
                'principal': total['total_principal'] or 0,
                'interest': total['total_interest'] or 0,
                'emi': total['total_emi'] or 0,
            }

    elif report_type == 'recovery_statement':
        if from_date and to_date:
            repayments = (
                LoanRepayment.objects.filter(
                    payment_date__gte=from_date,
                    payment_date__lte=to_date,
                )
                .select_related('loan__member', 'loan__loan_product')
                .order_by('payment_date')
            )
            if not request.user.can_access_all_branches:
                repayments = repayments.filter(branch=request.current_branch)
            context['items'] = [
                {
                    'loan_no': r.loan.loan_no,
                    'member': r.loan.member.name,
                    'payment_date': r.payment_date,
                    'amount': r.amount,
                    'principal': r.principal_adjusted,
                    'interest': r.interest_adjusted,
                    'penalty': r.penalty_adjusted,
                    'mode': r.get_payment_mode_display() if hasattr(r, 'get_payment_mode_display') else r.payment_mode,
                }
                for r in repayments[:500]
            ]
            total = repayments.aggregate(
                total_amount=Sum('amount'),
                total_principal=Sum('principal_adjusted'),
                total_interest=Sum('interest_adjusted'),
                total_penalty=Sum('penalty_adjusted'),
            )
            context['totals'] = {
                'amount': total['total_amount'] or 0,
                'principal': total['total_principal'] or 0,
                'interest': total['total_interest'] or 0,
                'penalty': total['total_penalty'] or 0,
            }

    elif report_type == 'interest_receivable':
        loans = _branch_filter(
            request,
            LoanAccount.objects.filter(
                status__in=active_statuses,
                outstanding_interest__gt=0,
            )
            .select_related('member', 'loan_product')
            .order_by('-outstanding_interest'),
        )
        context['items'] = [
            {
                'loan_no': la.loan_no,
                'member': la.member.name,
                'product': la.loan_product.name,
                'outstanding_principal': la.outstanding_principal,
                'outstanding_interest': la.outstanding_interest,
                'interest_rate': la.interest_rate,
                'overdue_days': la.overdue_days,
                'status': la.get_status_display(),
            }
            for la in loans
        ]
        context['total_interest'] = loans.aggregate(t=Sum('outstanding_interest'))['t'] or 0

    elif report_type == 'guarantor_report':
        guarantors = (
            LoanGuarantor.objects.filter(
                loan__status__in=active_statuses,
            )
            .select_related('guarantor_member', 'loan')
            .values(
                'guarantor_member__id',
                'guarantor_member__name',
                'guarantor_member__member_no',
            )
            .annotate(
                guarantee_count=Count('id'),
                total_exposure=Sum('guarantee_amount'),
            )
            .order_by('-total_exposure')
        )
        if not request.user.can_access_all_branches:
            guarantors = (
                LoanGuarantor.objects.filter(
                    loan__status__in=active_statuses,
                    loan__branch=request.current_branch,
                )
                .select_related('guarantor_member', 'loan')
                .values(
                    'guarantor_member__id',
                    'guarantor_member__name',
                    'guarantor_member__member_no',
                )
                .annotate(
                    guarantee_count=Count('id'),
                    total_exposure=Sum('guarantee_amount'),
                )
                .order_by('-total_exposure')
            )
        context['items'] = [
            {
                'member_name': g['guarantor_member__name'],
                'member_no': g['guarantor_member__member_no'],
                'guarantee_count': g['guarantee_count'],
                'total_exposure': g['total_exposure'],
            }
            for g in guarantors
        ]

    elif report_type == 'defaulter_list':
        loans = _branch_filter(
            request,
            LoanAccount.objects.filter(
                status__in=active_statuses,
                overdue_days__gt=0,
            )
            .select_related('member', 'loan_product')
            .order_by('-overdue_days'),
        )
        groups = {
            '1-3 months': [],
            '3-6 months': [],
            '6-12 months': [],
            '12+ months': [],
        }
        for la in loans:
            months = la.overdue_days / 30
            item = {
                'loan_no': la.loan_no,
                'member': la.member.name,
                'product': la.loan_product.name,
                'disbursed_amount': la.disbursed_amount,
                'outstanding': la.outstanding_principal,
                'overdue_amount': la.overdue_amount,
                'overdue_days': la.overdue_days,
                'status': la.get_status_display(),
            }
            if months <= 3:
                groups['1-3 months'].append(item)
            elif months <= 6:
                groups['3-6 months'].append(item)
            elif months <= 12:
                groups['6-12 months'].append(item)
            else:
                groups['12+ months'].append(item)
        context['defaulter_groups'] = groups
        context['total_defaulters'] = loans.count()

    elif report_type == 'loan_against_deposit':
        loans = _branch_filter(
            request,
            LoanAccount.objects.filter(
                loan_product__mortgage_type='fixed_deposit',
                status__in=active_statuses + ['approved'],
            ).select_related('member', 'loan_product'),
        )
        context['items'] = [
            {
                'loan_no': la.loan_no,
                'member': la.member.name,
                'product': la.loan_product.name,
                'loan_amount': la.disbursed_amount or la.approved_amount,
                'outstanding': la.outstanding_principal,
                'mortgage_account_no': la.mortgage_account_no,
                'mortgage_value': la.mortgage_value,
                'status': la.get_status_display(),
            }
            for la in loans
        ]

    if request.GET.get('format') == 'csv' and report_type:
        if 'groups' in context:
            rows = [[g['label'], g['count'], g['total']] for g in context['groups']]
            return _csv_response(
                f'loan_{report_type}_{date.today()}.csv',
                ['Range', 'Count', 'Total'],
                rows,
            )
        if 'items' in context:
            items = context['items']
            if items:
                headers = list(items[0].keys())
                rows = [list(i.values()) for i in items]
                return _csv_response(f'loan_{report_type}_{date.today()}.csv', headers, rows)
        elif 'defaulter_groups' in context:
            rows = []
            for group_name, group_items in context['defaulter_groups'].items():
                for item in group_items:
                    rows.append(
                        [
                            group_name,
                            item['loan_no'],
                            item['member'],
                            item['outstanding'],
                            item['overdue_amount'],
                            item['overdue_days'],
                        ]
                    )
            return _csv_response(
                f'loan_defaulters_{date.today()}.csv',
                ['Category', 'Loan No', 'Member', 'Outstanding', 'Overdue Amt', 'Overdue Days'],
                rows,
            )

    return render(request, 'reports/loan_reports.html', context)


@auditor_or_above
def notices(request):
    from apps.deposits.models import FixedDeposit
    from apps.members.models import Member
    from apps.shares.models import ShareTransaction

    notice_type = request.GET.get('type', 'balance_confirmation')
    context = {'notice_type': notice_type, 'today': date.today()}

    if notice_type == 'balance_confirmation':
        member_id = request.GET.get('member')
        context['members'] = Member.objects.filter(status='active').order_by('name')
        context['selected_member'] = member_id

        if member_id:
            try:
                member = Member.objects.get(pk=member_id)
                context['member'] = member
                accounts = []
                from apps.savings.models import SavingsAccount

                for sa in SavingsAccount.objects.filter(member=member, status='active'):
                    accounts.append(
                        {
                            'type': sa.get_account_type_display(),
                            'account_no': sa.account_no,
                            'balance': sa.current_balance,
                        }
                    )
                from apps.loans.models import LoanAccount

                for la in LoanAccount.objects.filter(member=member).exclude(
                    status__in=['closed', 'rejected', 'written_off']
                ):
                    accounts.append(
                        {
                            'type': f'Loan ({la.loan_product.name})',
                            'account_no': la.loan_no,
                            'balance': la.outstanding_principal,
                        }
                    )
                from apps.shares.models import ShareHolding

                holding = ShareHolding.objects.filter(member=member, status='active').first()
                if holding:
                    accounts.append(
                        {
                            'type': 'Share Capital',
                            'account_no': holding.certificate_no or '—',
                            'balance': holding.total_amount,
                        }
                    )
                for fd in FixedDeposit.objects.filter(member=member, status='active'):
                    accounts.append(
                        {
                            'type': 'Fixed Deposit',
                            'account_no': fd.fd_no,
                            'balance': fd.deposit_amount,
                        }
                    )
                context['accounts'] = accounts
            except Member.DoesNotExist:
                pass

    elif notice_type == 'fd_maturity':
        from datetime import timedelta

        try:
            days = int(request.GET.get('days', 30))
        except (ValueError, TypeError):
            days = 30
        context['days'] = days
        cutoff = date.today() + timedelta(days=days)
        fds = (
            FixedDeposit.objects.filter(
                status='active',
                maturity_date__lte=cutoff,
                maturity_date__gte=date.today(),
            )
            .select_related('member')
            .order_by('maturity_date')
        )
        context['fds'] = fds

    elif notice_type == 'dividend_certificate':
        from_date = request.GET.get('from_date', '')
        to_date = request.GET.get('to_date', '')
        context['from_date'] = from_date
        context['to_date'] = to_date
        if from_date and to_date:
            txns = (
                ShareTransaction.objects.filter(
                    txn_type='dividend',
                    txn_date__gte=from_date,
                    txn_date__lte=to_date,
                )
                .select_related('member')
                .order_by('member__name')
            )
            context['dividend_txns'] = txns

    return render(request, 'reports/notices.html', context)


@auditor_or_above
def calculator(request):
    from apps.accounting.models import InterestMaster

    rates = (
        InterestMaster.objects.filter(is_active=True)
        .select_related('account_head')
        .order_by('account_head__code', 'min_period')
    )
    return render(request, 'reports/calculator.html', {'interest_rates': rates})


@auditor_or_above
def npa_report(request):
    from apps.loans.npa_service import classify_all_loans, get_npa_report

    branch = None if request.user.can_access_all_branches else request.current_branch

    if request.method == 'POST' and request.POST.get('action') == 'reclassify':
        from django.contrib import messages
        from django.shortcuts import redirect

        result = classify_all_loans()
        messages.success(
            request, f'NPA reclassification complete: {result["updated"]}/{result["total"]} loans updated.'
        )
        return redirect('reports:npa_report')

    report = get_npa_report(branch=branch)

    npa_categories = [
        ('standard', 'Standard Asset', '0.25%', 'green'),
        ('sub_standard', 'Sub-Standard Asset', '6%', 'yellow'),
        ('doubtful_1', 'Doubtful Asset - 1', '20-70%', 'orange'),
        ('doubtful_2', 'Doubtful Asset - 2', '25-80%', 'red'),
        ('doubtful_3', 'Doubtful Asset - 3', '30-90%', 'red'),
        ('loss', 'Loss Asset', '100%', 'red'),
    ]

    category_rows = []
    summary = report['category_summary']
    for key, label, pct_range, color in npa_categories:
        if key in summary:
            category_rows.append(
                {
                    'key': key,
                    'label': label,
                    'pct_range': pct_range,
                    'color': color,
                    'count': summary[key]['count'],
                    'outstanding': summary[key]['outstanding'],
                    'provision': summary[key]['provision'],
                }
            )

    context = {
        'report': report,
        'category_rows': category_rows,
    }

    if request.GET.get('format') == 'csv':
        rows = []
        for loan in report['loans']:
            rows.append(
                [
                    loan.loan_no,
                    loan.member.name,
                    loan.loan_product.name,
                    loan.disbursed_amount or loan.approved_amount,
                    loan.outstanding_principal,
                    loan.bal_interest,
                    loan.bal_penal,
                    loan.overdue_days,
                    loan.computed_category,
                    loan.computed_provision_pct,
                    loan.computed_provision_amt,
                ]
            )
        return _csv_response(
            f'npa_report_{date.today()}.csv',
            [
                'Loan No',
                'Member',
                'Product',
                'Sanction Amt',
                'Principal',
                'Interest',
                'Penal',
                'Overdue Days',
                'NPA Category',
                'Provision %',
                'Provision Amt',
            ],
            rows,
        )

    return render(request, 'reports/npa_report.html', context)


@auditor_or_above
def agent_reconciliation(request):
    """Compare GL balance of pigmy/agent heads with sum of individual account balances."""
    from apps.accounting.models import ChartOfAccounts, JournalLine
    from apps.agents.models import Agent, PigmmyAccount

    branch = None if request.user.can_access_all_branches else request.current_branch

    pigmy_heads = ChartOfAccounts.objects.filter(
        related_table_name='client',
        is_active=True,
        allow_transactions=True,
    )

    rows = []
    for head in pigmy_heads:
        gl_agg = JournalLine.objects.filter(
            gl_account=head,
            journal_entry__is_reversed=False,
            journal_entry__is_posted=True,
        )
        if branch:
            gl_agg = gl_agg.filter(journal_entry__branch=branch)
        gl_agg = gl_agg.aggregate(dr=Sum('debit_amount'), cr=Sum('credit_amount'))
        gl_balance = (head.opening_balance or 0) + (gl_agg['cr'] or 0) - (gl_agg['dr'] or 0)

        acct_qs = PigmmyAccount.objects.filter(status='active')
        if branch:
            acct_qs = acct_qs.filter(branch=branch)
        acct_total = acct_qs.aggregate(t=Sum('current_balance'))['t'] or Decimal('0')

        rows.append(
            {
                'head_code': head.code,
                'head_name': head.name,
                'gl_balance': gl_balance,
                'account_balance': acct_total,
                'difference': gl_balance - acct_total,
            }
        )

    agent_heads = ChartOfAccounts.objects.filter(
        related_table_name='agent',
        is_active=True,
        allow_transactions=True,
    )
    for head in agent_heads:
        gl_agg = JournalLine.objects.filter(
            gl_account=head,
            journal_entry__is_reversed=False,
            journal_entry__is_posted=True,
        )
        if branch:
            gl_agg = gl_agg.filter(journal_entry__branch=branch)
        gl_agg = gl_agg.aggregate(dr=Sum('debit_amount'), cr=Sum('credit_amount'))
        gl_balance = (head.opening_balance or 0) + (gl_agg['cr'] or 0) - (gl_agg['dr'] or 0)

        agent_qs = Agent.objects.filter(status='active')
        if branch:
            agent_qs = agent_qs.filter(branch=branch)
        agent_total = agent_qs.aggregate(
            t=Sum('security_deposit_amount'),
        )['t'] or Decimal('0')

        rows.append(
            {
                'head_code': head.code,
                'head_name': head.name,
                'gl_balance': gl_balance,
                'account_balance': agent_total,
                'difference': gl_balance - agent_total,
            }
        )

    context = {'rows': rows, 'has_difference': any(r['difference'] != 0 for r in rows)}

    if request.GET.get('format') == 'csv' and rows:
        csv_rows = [
            [r['head_code'], r['head_name'], r['gl_balance'], r['account_balance'], r['difference']] for r in rows
        ]
        return _csv_response(
            f'agent_reconciliation_{date.today()}.csv',
            ['GL Code', 'Head Name', 'GL Balance', 'Account Balance', 'Difference'],
            csv_rows,
        )

    return render(request, 'reports/agent_reconciliation.html', context)


@auditor_or_above
def fixed_asset_report(request):
    """Fixed asset register with depreciation details."""
    from apps.accounting.models import FixedAsset

    assets = FixedAsset.objects.filter(is_active=True).select_related('gl_head', 'depreciation_head', 'branch')
    totals = assets.aggregate(
        total_purchase=Sum('purchase_amount'),
        total_depreciation=Sum('accumulated_depreciation'),
    )
    total_purchase = totals['total_purchase'] or Decimal('0')
    total_depreciation = totals['total_depreciation'] or Decimal('0')
    total_wdv = total_purchase - total_depreciation

    context = {
        'assets': assets,
        'total_purchase': total_purchase,
        'total_depreciation': total_depreciation,
        'total_wdv': total_wdv,
    }

    if request.GET.get('format') == 'csv':
        rows = [
            [
                a.asset_code,
                a.name,
                a.purchase_date,
                a.purchase_amount,
                a.depreciation_rate,
                a.accumulated_depreciation,
                a.net_book_value,
            ]
            for a in assets
        ]
        return _csv_response(
            f'fixed_assets_{date.today()}.csv',
            ['Code', 'Name', 'Purchase Date', 'Purchase Amt', 'Dep Rate %', 'Accum Dep', 'Net Book Value'],
            rows,
        )

    return render(request, 'reports/fixed_asset_report.html', context)
