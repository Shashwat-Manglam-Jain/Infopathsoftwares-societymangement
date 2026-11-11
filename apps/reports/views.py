from datetime import date
from decimal import Decimal

from django.db.models import Count, Max, Q, Sum
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


@auditor_or_above
def balance_reports(request):
    from datetime import timedelta

    from django.db.models import Count, Max

    from apps.savings.models import SavingsAccount

    report_type = request.GET.get('type', 'nil_balance')
    branch = None if request.user.can_access_all_branches else getattr(request, 'current_branch', None)
    accounts = None
    type_summary = None

    base_qs = SavingsAccount.objects.select_related('member')
    if branch:
        base_qs = base_qs.filter(branch=branch)

    if report_type == 'nil_balance':
        accounts = base_qs.filter(
            status='active', current_balance=0
        ).annotate(last_txn=Max('transactions__txn_date'))

    elif report_type == 'non_operated':
        cutoff = date.today() - timedelta(days=180)
        accounts = base_qs.filter(status='active').annotate(
            last_txn=Max('transactions__txn_date')
        ).filter(
            Q(last_txn__lt=cutoff) | Q(last_txn__isnull=True)
        )

    elif report_type == 'dormant':
        accounts = base_qs.filter(status='dormant').annotate(
            last_txn=Max('transactions__txn_date')
        )

    elif report_type == 'balance_with_last_txn':
        accounts = base_qs.filter(status='active').annotate(
            last_txn=Max('transactions__txn_date')
        ).order_by('-current_balance')

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
        if min_amount:
            qs = qs.filter(current_balance__gte=Decimal(min_amount))
        if max_amount:
            qs = qs.filter(current_balance__lte=Decimal(max_amount))
        accounts = qs.annotate(last_txn=Max('transactions__txn_date')).order_by('-current_balance')

    context = {
        'report_type': report_type,
        'accounts': accounts,
        'type_summary': type_summary,
        'min_amount': request.GET.get('min_amount', ''),
        'max_amount': request.GET.get('max_amount', ''),
    }
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
            from apps.deposits.models import FixedDeposit, RDInstallment, RecurringDeposit
            from apps.loans.models import LoanAccount
            from apps.savings.models import SavingsAccount
            from apps.shares.models import ShareHolding

            context['savings'] = SavingsAccount.objects.filter(member=member).order_by('account_type')
            context['shares'] = ShareHolding.objects.filter(member=member, status='active')
            context['loans'] = LoanAccount.objects.filter(member=member).exclude(
                status__in=['closed', 'rejected', 'written_off']
            ).select_related('loan_product')
            context['fds'] = FixedDeposit.objects.filter(member=member).exclude(status='renewed')
            rds = RecurringDeposit.objects.filter(member=member)
            rd_list = []
            for rd in rds:
                paid = RDInstallment.objects.filter(rd=rd, status='paid').count()
                rd_list.append({'rd': rd, 'paid_count': paid})
            context['rds'] = rd_list
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
                entries.append({'type': f'Savings ({sa.get_account_type_display()})', 'account_no': sa.account_no,
                                'member': sa.member.name, 'date': sa.opening_date})
            for la in LoanAccount.objects.filter(
                applied_date__gte=from_date, applied_date__lte=to_date
            ).select_related('member', 'loan_product'):
                entries.append({'type': f'Loan ({la.loan_product.name})', 'account_no': la.loan_no,
                                'member': la.member.name, 'date': la.applied_date})
            for fd in FixedDeposit.objects.filter(
                start_date__gte=from_date, start_date__lte=to_date
            ).select_related('member'):
                entries.append({'type': 'Fixed Deposit', 'account_no': fd.fd_no,
                                'member': fd.member.name, 'date': fd.start_date})
            for rd in RecurringDeposit.objects.filter(
                start_date__gte=from_date, start_date__lte=to_date
            ).select_related('member'):
                entries.append({'type': 'Recurring Deposit', 'account_no': rd.rd_no,
                                'member': rd.member.name, 'date': rd.start_date})
            for pa in PigmmyAccount.objects.filter(
                opening_date__gte=from_date, opening_date__lte=to_date
            ).select_related('member'):
                entries.append({'type': f'Pigmmy ({pa.get_deposit_type_display()})', 'account_no': pa.account_no,
                                'member': pa.member.name, 'date': pa.opening_date})
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
                entries.append({'type': f'Savings ({sa.get_account_type_display()})', 'account_no': sa.account_no,
                                'member': sa.member.name, 'date': sa.closing_date})
            for la in LoanAccount.objects.filter(
                closure_date__gte=from_date, closure_date__lte=to_date
            ).select_related('member', 'loan_product'):
                entries.append({'type': f'Loan ({la.loan_product.name})', 'account_no': la.loan_no,
                                'member': la.member.name, 'date': la.closure_date})
            for fd in FixedDeposit.objects.filter(
                maturity_date__gte=from_date, maturity_date__lte=to_date, status__in=['matured', 'prematurely_closed']
            ).select_related('member'):
                entries.append({'type': 'Fixed Deposit', 'account_no': fd.fd_no,
                                'member': fd.member.name, 'date': fd.premature_closure_date or fd.maturity_date})
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
    from django.db.models import Count

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
        context['summary'] = qs.values('agent__agent_code', 'agent__member__name').annotate(
            client_count=Count('id'), total_balance=Sum('current_balance')
        ).order_by('agent__agent_code')

    elif report_type == 'date_daybook':
        report_date = request.GET.get('date', '')
        if report_date:
            qs = PigmmyTransaction.objects.filter(
                txn_date=report_date, is_reversed=False
            ).select_related('account__member', 'account__agent')
            if branch:
                qs = qs.filter(account__branch=branch)
            context['transactions'] = qs.order_by('account__agent__agent_code', 'account__account_no')
            context['total_amount'] = qs.aggregate(t=Sum('amount'))['t'] or Decimal('0')

    elif report_type == 'deposit_type':
        qs = PigmmyAccount.objects.filter(status='active')
        if branch:
            qs = qs.filter(branch=branch)
        context['type_summary'] = qs.values('deposit_type').annotate(
            count=Count('id'), total_balance=Sum('current_balance')
        ).order_by('deposit_type')

    elif report_type == 'matured':
        qs = PigmmyAccount.objects.filter(
            maturity_date__lte=date.today(), status='active'
        ).select_related('member', 'agent')
        if branch:
            qs = qs.filter(branch=branch)
        context['accounts'] = qs.order_by('maturity_date')

    elif report_type == 'commission':
        from_date = request.GET.get('from_date', '')
        to_date = request.GET.get('to_date', '')
        if from_date and to_date:
            qs = AgentCommission.objects.filter(
                month__gte=from_date, month__lte=to_date
            ).select_related('agent__member')
            context['commissions'] = qs.order_by('agent__agent_code', 'month')
            context['total_commission'] = qs.aggregate(t=Sum('commission_amount'))['t'] or Decimal('0')
            context['total_tds'] = qs.aggregate(t=Sum('tds_amount'))['t'] or Decimal('0')
            context['total_net'] = qs.aggregate(t=Sum('net_amount'))['t'] or Decimal('0')

    return render(request, 'reports/pigmmy_reports.html', context)


def _branch_filter(request, qs):
    if not request.user.can_access_all_branches:
        qs = qs.filter(branch=request.current_branch)
    return qs


DEPOSIT_AMOUNT_RANGES = [
    (0, 10000, '≤ 10,000'),
    (10001, 50000, '10,001 – 50,000'),
    (50001, 100000, '50,001 – 1,00,000'),
    (100001, 500000, '1,00,001 – 5,00,000'),
    (500001, None, '5,00,001+'),
]

FD_PERIOD_RANGES = [
    (0, 90, '≤ 90 days'),
    (91, 180, '91 – 180 days'),
    (181, 365, '181 – 365 days'),
    (366, 730, '1 – 2 years'),
    (731, 1825, '2 – 5 years'),
    (1826, None, '5+ years'),
]

LOAN_AMOUNT_RANGES = [
    (0, 25000, '≤ 25,000'),
    (25001, 50000, '25,001 – 50,000'),
    (50001, 100000, '50,001 – 1,00,000'),
    (100001, 500000, '1,00,001 – 5,00,000'),
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
                groups.append({
                    'label': label,
                    'count': agg['count'] or 0,
                    'total': agg['total'] or 0,
                    'deposit_type': 'FD',
                })
        if fd_or_rd in ('rd', 'all'):
            rds = _branch_filter(request, RecurringDeposit.objects.filter(status='active'))
            rd_ranges = [
                (0, 12, '≤ 12 months'),
                (13, 24, '13 – 24 months'),
                (25, 36, '25 – 36 months'),
                (37, 60, '37 – 60 months'),
                (61, None, '60+ months'),
            ]
            for lo, hi, label in rd_ranges:
                qs = rds.filter(tenure_months__gte=lo)
                if hi is not None:
                    qs = qs.filter(tenure_months__lte=hi)
                agg = qs.aggregate(count=Count('id'), total=Sum('monthly_installment'))
                groups.append({
                    'label': label,
                    'count': agg['count'] or 0,
                    'total': agg['total'] or 0,
                    'deposit_type': 'RD',
                })
        context['groups'] = groups

    elif report_type == 'amount_wise':
        groups = []
        if fd_or_rd in ('fd', 'all'):
            fds = _branch_filter(request, FixedDeposit.objects.filter(status='active'))
            for lo, hi, label in DEPOSIT_AMOUNT_RANGES:
                qs = fds.filter(deposit_amount__gte=lo)
                if hi is not None:
                    qs = qs.filter(deposit_amount__lte=hi)
                agg = qs.aggregate(count=Count('id'), total=Sum('deposit_amount'))
                groups.append({
                    'label': label,
                    'count': agg['count'] or 0,
                    'total': agg['total'] or 0,
                    'deposit_type': 'FD',
                })
        if fd_or_rd in ('rd', 'all'):
            rds = _branch_filter(request, RecurringDeposit.objects.filter(status='active'))
            for lo, hi, label in DEPOSIT_AMOUNT_RANGES:
                qs = rds.filter(monthly_installment__gte=lo)
                if hi is not None:
                    qs = qs.filter(monthly_installment__lte=hi)
                agg = qs.aggregate(count=Count('id'), total=Sum('monthly_installment'))
                groups.append({
                    'label': label,
                    'count': agg['count'] or 0,
                    'total': agg['total'] or 0,
                    'deposit_type': 'RD',
                })
        context['groups'] = groups

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
                    items.append({
                        'account_no': fd.fd_no,
                        'member': fd.member.name,
                        'amount': fd.deposit_amount,
                        'maturity_date': fd.maturity_date,
                        'maturity_amount': fd.maturity_amount,
                        'interest_rate': fd.interest_rate,
                        'status': fd.get_status_display(),
                        'deposit_type': 'FD',
                    })
            if fd_or_rd in ('rd', 'all'):
                rds = _branch_filter(
                    request,
                    RecurringDeposit.objects.filter(
                        maturity_date__gte=from_date,
                        maturity_date__lte=to_date,
                    ).select_related('member'),
                )
                for rd in rds:
                    items.append({
                        'account_no': rd.rd_no,
                        'member': rd.member.name,
                        'amount': rd.monthly_installment,
                        'maturity_date': rd.maturity_date,
                        'maturity_amount': rd.maturity_amount,
                        'interest_rate': rd.interest_rate,
                        'status': rd.get_status_display(),
                        'deposit_type': 'RD',
                    })
            items.sort(key=lambda x: x['maturity_date'])
            context['items'] = items

    elif report_type == 'interest_wise':
        groups = []
        if fd_or_rd in ('fd', 'all'):
            fds = _branch_filter(request, FixedDeposit.objects.filter(status='active'))
            rates = fds.values_list('interest_rate', flat=True).distinct().order_by('interest_rate')
            for rate in rates:
                agg = fds.filter(interest_rate=rate).aggregate(count=Count('id'), total=Sum('deposit_amount'))
                groups.append({
                    'label': f'{rate}%',
                    'rate': rate,
                    'count': agg['count'] or 0,
                    'total': agg['total'] or 0,
                    'deposit_type': 'FD',
                })
        if fd_or_rd in ('rd', 'all'):
            rds = _branch_filter(request, RecurringDeposit.objects.filter(status='active'))
            rates = rds.values_list('interest_rate', flat=True).distinct().order_by('interest_rate')
            for rate in rates:
                agg = rds.filter(interest_rate=rate).aggregate(count=Count('id'), total=Sum('monthly_installment'))
                groups.append({
                    'label': f'{rate}%',
                    'rate': rate,
                    'count': agg['count'] or 0,
                    'total': agg['total'] or 0,
                    'deposit_type': 'RD',
                })
        context['groups'] = groups

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
            groups.append({
                'label': label,
                'count': agg['count'] or 0,
                'total': agg['total'] or 0,
            })
        context['groups'] = groups

    elif report_type == 'sanction_date_wise':
        if from_date and to_date:
            loans = _branch_filter(
                request,
                LoanAccount.objects.filter(
                    approved_date__gte=from_date,
                    approved_date__lte=to_date,
                ).select_related('member', 'loan_product').order_by('approved_date'),
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
                ).select_related('member', 'loan_product').order_by('disbursed_date'),
            )
            items = []
            for la in loans:
                guarantor_names = ', '.join(
                    g.guarantor_member.name
                    for g in la.guarantors.select_related('guarantor_member').all()
                )
                items.append({
                    'loan_no': la.loan_no,
                    'member': la.member.name,
                    'product': la.loan_product.name,
                    'disbursed_date': la.disbursed_date,
                    'disbursed_amount': la.disbursed_amount,
                    'interest_rate': la.interest_rate,
                    'tenure': la.tenure_months,
                    'guarantors': guarantor_names,
                })
            context['items'] = items

    elif report_type == 'demand_list':
        if from_date and to_date:
            emis = EMISchedule.objects.filter(
                due_date__gte=from_date,
                due_date__lte=to_date,
                status__in=['pending', 'overdue'],
            ).select_related('loan__member', 'loan__loan_product').order_by('due_date')
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
            repayments = LoanRepayment.objects.filter(
                payment_date__gte=from_date,
                payment_date__lte=to_date,
            ).select_related('loan__member', 'loan__loan_product').order_by('payment_date')
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
            ).select_related('member', 'loan_product').order_by('-outstanding_interest'),
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
        guarantors = LoanGuarantor.objects.filter(
            loan__status__in=active_statuses,
        ).select_related('guarantor_member', 'loan').values(
            'guarantor_member__id',
            'guarantor_member__name',
            'guarantor_member__member_number',
        ).annotate(
            guarantee_count=Count('id'),
            total_exposure=Sum('guarantee_amount'),
        ).order_by('-total_exposure')
        if not request.user.can_access_all_branches:
            guarantors = LoanGuarantor.objects.filter(
                loan__status__in=active_statuses,
                loan__branch=request.current_branch,
            ).select_related('guarantor_member', 'loan').values(
                'guarantor_member__id',
                'guarantor_member__name',
                'guarantor_member__member_number',
            ).annotate(
                guarantee_count=Count('id'),
                total_exposure=Sum('guarantee_amount'),
            ).order_by('-total_exposure')
        context['items'] = [
            {
                'member_name': g['guarantor_member__name'],
                'member_number': g['guarantor_member__member_number'],
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
            ).select_related('member', 'loan_product').order_by('-overdue_days'),
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

    return render(request, 'reports/loan_reports.html', context)


@auditor_or_above
def notices(request):
    from apps.deposits.models import FixedDeposit
    from apps.members.models import Member
    from apps.shares.models import ShareTransaction

    notice_type = request.GET.get('type', 'balance_confirmation')
    context = {'notice_type': notice_type}

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
                    accounts.append({
                        'type': sa.get_account_type_display(),
                        'account_no': sa.account_no,
                        'balance': sa.current_balance,
                    })
                from apps.loans.models import LoanAccount
                for la in LoanAccount.objects.filter(member=member).exclude(
                    status__in=['closed', 'rejected', 'written_off']
                ):
                    accounts.append({
                        'type': f'Loan ({la.loan_product.name})',
                        'account_no': la.loan_no,
                        'balance': la.outstanding_principal,
                    })
                from apps.shares.models import ShareHolding
                holding = ShareHolding.objects.filter(member=member, status='active').first()
                if holding:
                    accounts.append({
                        'type': 'Share Capital',
                        'account_no': holding.certificate_no or '—',
                        'balance': holding.total_amount,
                    })
                for fd in FixedDeposit.objects.filter(member=member, status='active'):
                    accounts.append({
                        'type': 'Fixed Deposit',
                        'account_no': fd.fd_no,
                        'balance': fd.deposit_amount,
                    })
                context['accounts'] = accounts
            except Member.DoesNotExist:
                pass

    elif notice_type == 'fd_maturity':
        from datetime import timedelta
        days = int(request.GET.get('days', 30))
        context['days'] = days
        cutoff = date.today() + timedelta(days=days)
        fds = FixedDeposit.objects.filter(
            status='active',
            maturity_date__lte=cutoff,
            maturity_date__gte=date.today(),
        ).select_related('member').order_by('maturity_date')
        context['fds'] = fds

    elif notice_type == 'dividend_certificate':
        from_date = request.GET.get('from_date', '')
        to_date = request.GET.get('to_date', '')
        context['from_date'] = from_date
        context['to_date'] = to_date
        if from_date and to_date:
            txns = ShareTransaction.objects.filter(
                txn_type='dividend',
                txn_date__gte=from_date,
                txn_date__lte=to_date,
            ).select_related('member').order_by('member__name')
            context['dividend_txns'] = txns

    return render(request, 'reports/notices.html', context)


@auditor_or_above
def calculator(request):
    return render(request, 'reports/calculator.html')
