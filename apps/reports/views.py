from decimal import Decimal

from django.db.models import Sum
from django.shortcuts import render

from apps.accounts.permissions import auditor_or_above


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
            pre_txns = AccountTransaction.objects.filter(
                account=sa,
                txn_date__lt=from_date,
                is_reversed=False,
            )
            pre_debit = sum(t.amount for t in pre_txns if t.txn_type in ('withdrawal', 'charge'))
            pre_credit = sum(t.amount for t in pre_txns if t.txn_type in ('deposit', 'interest_credit', 'transfer'))
            opening = pre_credit - pre_debit

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
                    'current_balance': holding.total_amount if holding else 0,
                    'rows': rows,
                }
            )

        from apps.loans.models import LoanAccount as LA
        from apps.loans.models import LoanRepayment

        loan_accounts = LA.objects.filter(member=member).exclude(status__in=['closed', 'rejected', 'written_off'])
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
                        'current_balance': la.outstanding_principal,
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
                        'current_balance': fd.deposit_amount if fd.status == 'active' else 0,
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
                        'current_balance': paid_total,
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
    return render(request, 'reports/trial_balance.html', context)


@auditor_or_above
def profit_loss(request):
    from_date = request.GET.get('from_date')
    to_date = request.GET.get('to_date')
    context = {'from_date': from_date, 'to_date': to_date}
    if from_date and to_date:
        from apps.accounting.models import ChartOfAccounts, JournalLine

        branch = None if request.user.can_access_all_branches else request.current_branch
        income_heads = ChartOfAccounts.objects.filter(account_group='income', allow_transactions=True, is_active=True)
        expense_heads = ChartOfAccounts.objects.filter(account_group='expense', allow_transactions=True, is_active=True)
        income_items = []
        total_income = 0
        for head in income_heads:
            ob = head.opening_balance or 0
            pre_qs = JournalLine.objects.filter(
                gl_account=head,
                journal_entry__entry_date__lt=from_date,
                journal_entry__is_reversed=False,
                journal_entry__is_posted=True,
            )
            if branch:
                pre_qs = pre_qs.filter(journal_entry__branch=branch)
            pre = pre_qs.aggregate(dr=Sum('debit_amount'), cr=Sum('credit_amount'))
            ob += (pre['cr'] or 0) - (pre['dr'] or 0)

            qs = JournalLine.objects.filter(
                gl_account=head,
                journal_entry__entry_date__gte=from_date,
                journal_entry__entry_date__lte=to_date,
                journal_entry__is_reversed=False,
                journal_entry__is_posted=True,
            )
            if branch:
                qs = qs.filter(journal_entry__branch=branch)
            agg = qs.aggregate(dr=Sum('debit_amount'), cr=Sum('credit_amount'))
            period = (agg['cr'] or 0) - (agg['dr'] or 0)
            closing = ob + period
            if closing != 0:
                income_items.append({'name': head.name, 'code': head.code, 'amount': closing})
                total_income += closing

        expense_items = []
        total_expense = 0
        for head in expense_heads:
            ob = head.opening_balance or 0
            pre_qs = JournalLine.objects.filter(
                gl_account=head,
                journal_entry__entry_date__lt=from_date,
                journal_entry__is_reversed=False,
                journal_entry__is_posted=True,
            )
            if branch:
                pre_qs = pre_qs.filter(journal_entry__branch=branch)
            pre = pre_qs.aggregate(dr=Sum('debit_amount'), cr=Sum('credit_amount'))
            ob += (pre['dr'] or 0) - (pre['cr'] or 0)

            qs = JournalLine.objects.filter(
                gl_account=head,
                journal_entry__entry_date__gte=from_date,
                journal_entry__entry_date__lte=to_date,
                journal_entry__is_reversed=False,
                journal_entry__is_posted=True,
            )
            if branch:
                qs = qs.filter(journal_entry__branch=branch)
            agg = qs.aggregate(dr=Sum('debit_amount'), cr=Sum('credit_amount'))
            period = (agg['dr'] or 0) - (agg['cr'] or 0)
            closing = ob + period
            if closing != 0:
                expense_items.append({'name': head.name, 'code': head.code, 'amount': closing})
                total_expense += closing

        context.update(
            {
                'income_items': income_items,
                'expense_items': expense_items,
                'total_income': total_income,
                'total_expense': total_expense,
                'net_profit': total_income - total_expense,
            }
        )
    return render(request, 'reports/profit_loss.html', context)


@auditor_or_above
def balance_sheet(request):
    as_on_date = request.GET.get('as_on_date')
    context = {'as_on_date': as_on_date}
    if as_on_date:
        from apps.accounting.models import ChartOfAccounts, JournalLine

        branch = None if request.user.can_access_all_branches else request.current_branch

        def _head_balance(head, is_debit_normal):
            ob = head.opening_balance or 0
            qs = JournalLine.objects.filter(
                gl_account=head,
                journal_entry__entry_date__lte=as_on_date,
                journal_entry__is_reversed=False,
                journal_entry__is_posted=True,
            )
            if branch:
                qs = qs.filter(journal_entry__branch=branch)
            agg = qs.aggregate(dr=Sum('debit_amount'), cr=Sum('credit_amount'))
            if is_debit_normal:
                return ob + (agg['dr'] or 0) - (agg['cr'] or 0)
            return ob + (agg['cr'] or 0) - (agg['dr'] or 0)

        liability_heads = ChartOfAccounts.objects.filter(
            account_group__in=['liability', 'equity'], allow_transactions=True, is_active=True
        )
        asset_heads = ChartOfAccounts.objects.filter(account_group='asset', allow_transactions=True, is_active=True)

        liabilities = []
        total_liability = 0
        for head in liability_heads:
            balance = _head_balance(head, is_debit_normal=False)
            if balance != 0:
                liabilities.append({'name': head.name, 'code': head.code, 'amount': balance})
                total_liability += balance

        income_heads = ChartOfAccounts.objects.filter(account_group='income', allow_transactions=True, is_active=True)
        expense_heads = ChartOfAccounts.objects.filter(account_group='expense', allow_transactions=True, is_active=True)
        total_income = sum(_head_balance(h, is_debit_normal=False) for h in income_heads)
        total_expense = sum(_head_balance(h, is_debit_normal=True) for h in expense_heads)
        net_profit = total_income - total_expense
        if net_profit != 0:
            liabilities.append({'name': 'Net Profit / (Loss)', 'code': '—', 'amount': net_profit})
            total_liability += net_profit

        assets = []
        total_asset = 0
        for head in asset_heads:
            balance = _head_balance(head, is_debit_normal=True)
            if balance != 0:
                assets.append({'name': head.name, 'code': head.code, 'amount': balance})
                total_asset += balance

        context.update(
            {
                'liabilities': liabilities,
                'assets': assets,
                'total_liability': total_liability,
                'total_asset': total_asset,
                'difference': total_asset - total_liability,
                'net_profit': net_profit,
            }
        )
    return render(request, 'reports/balance_sheet.html', context)


@auditor_or_above
def cashbook_report(request):
    """Daily cashbook report with opening balance, head-wise receipts/payments, closing balance."""
    from apps.accounting.models import CashbookMaster, JournalEntry, JournalLine

    report_date = request.GET.get('date', '')
    context = {'report_date': report_date}

    if report_date:
        branch = request.current_branch

        cb = CashbookMaster.objects.filter(branch=branch, txn_date=report_date).first()
        if cb:
            context['cashbook'] = cb

        entries = JournalEntry.objects.filter(
            branch=branch,
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

    return render(request, 'reports/cashbook_report.html', context)
