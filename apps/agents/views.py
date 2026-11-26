import json
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounting.models import ChartOfAccounts, InterestMaster
from apps.accounts.permissions import (
    auditor_or_above,
    cashier_required,
    day_open_required,
    has_branch_access,
    manager_required,
)
from apps.savings.models import SavingsAccount

from .forms import AgentForm, CollectionForm, PigmmyAccountForm, PigmmyEditForm
from .models import Agent, AgentCollection, PigmmyAccount, PigmmyTransaction


@auditor_or_above
def agent_list(request):
    agents = Agent.objects.filter(status='active').select_related('member', 'branch')
    if not request.user.can_access_all_branches:
        agents = agents.filter(branch=request.current_branch)
    paginator = Paginator(agents, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(
        request,
        'agents/agent_list.html',
        {
            'agents': page_obj,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'paginator': paginator,
        },
    )


@manager_required
def agent_create(request):
    branch = request.current_branch
    if branch is None:
        messages.warning(request, 'Please select a specific branch before creating an agent.')
        return redirect('agents:list')
    if request.method == 'POST':
        form = AgentForm(request.POST, request.FILES, branch=branch)
        if form.is_valid():
            agent = form.save(commit=False)
            agent.created_by = request.user
            max_code = Agent.objects.aggregate(m=Max('agent_code'))['m']
            if max_code:
                try:
                    seq = int(''.join(filter(str.isdigit, max_code))) + 1
                except ValueError:
                    seq = Agent.objects.count() + 1
            else:
                seq = 1
            agent.agent_code = f'AG{seq:04d}'
            agent.save()
            messages.success(request, f'Agent {agent.agent_code} created successfully.')
            return redirect('agents:detail', pk=agent.pk)
    else:
        form = AgentForm(branch=branch, initial={'joining_date': date.today().isoformat()})
    return render(request, 'agents/create.html', {'form': form})


@auditor_or_above
def agent_detail(request, pk):
    agent = get_object_or_404(Agent.objects.select_related('member', 'branch', 'savings_account'), pk=pk)
    if not has_branch_access(request, agent.branch):
        messages.error(request, 'You do not have access to this agent.')
        return redirect('agents:list')
    client_accounts = PigmmyAccount.objects.filter(agent=agent).select_related('member')
    recent_collections = AgentCollection.objects.filter(agent=agent).order_by('-collection_date')[:20]
    return render(
        request,
        'agents/detail.html',
        {
            'agent': agent,
            'client_accounts': client_accounts,
            'recent_collections': recent_collections,
            'daily_count': client_accounts.filter(deposit_type='daily').count(),
            'weekly_count': client_accounts.filter(deposit_type='weekly').count(),
            'monthly_count': client_accounts.filter(deposit_type='monthly').count(),
        },
    )


@auditor_or_above
def pigmmy_account_list(request):
    accounts = PigmmyAccount.objects.filter(status='active').select_related(
        'member',
        'agent__member',
        'branch',
    )
    if not request.user.can_access_all_branches:
        accounts = accounts.filter(branch=request.current_branch)
    agent_id = request.GET.get('agent')
    if agent_id:
        accounts = accounts.filter(agent_id=agent_id)
    agents = Agent.objects.filter(status='active')
    if not request.user.can_access_all_branches:
        agents = agents.filter(branch=request.current_branch)
    paginator = Paginator(accounts, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(
        request,
        'agents/pigmmy_list.html',
        {
            'accounts': page_obj,
            'agents': agents,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'paginator': paginator,
        },
    )


@cashier_required
@day_open_required
def pigmmy_create(request):
    branch = request.current_branch
    if branch is None:
        messages.warning(request, 'Please select a specific branch before creating a pigmmy account.')
        return redirect('agents:pigmmy_list')

    # Query InterestMaster slabs for pigmmy (Daily / Pigmmy Deposits)
    head = ChartOfAccounts.objects.filter(related_table_name='client', is_active=True).first()
    slabs = []
    if head:
        slabs = list(
            InterestMaster.objects.filter(
                account_head=head,
                is_active=True,
                period_unit='months',
            )
            .order_by('min_period')
            .values('min_period', 'max_period', 'interest_rate')
        )
    slabs_json = json.dumps(
        [
            {
                'min_months': s['min_period'],
                'max_months': s['max_period'],
                'rate': float(s['interest_rate']),
            }
            for s in slabs
        ]
    )

    if request.method == 'POST':
        form = PigmmyAccountForm(request.POST, branch=branch)
        if form.is_valid():
            from apps.agents.services import create_pigmmy_account

            interest_rate = form.cleaned_data['interest_rate']
            months = form.cleaned_data['deposit_period_months']
            if head:
                slab = InterestMaster.objects.filter(
                    account_head=head,
                    is_active=True,
                    period_unit='months',
                    min_period__lte=months,
                    max_period__gte=months,
                ).first()
                if slab:
                    interest_rate = slab.interest_rate

            try:
                account = create_pigmmy_account(
                    member=form.cleaned_data['member'],
                    agent=form.cleaned_data['agent'],
                    branch=branch,
                    installment_amount=form.cleaned_data['installment_amount'],
                    deposit_period_months=months,
                    interest_rate=interest_rate,
                    deposit_type=form.cleaned_data['deposit_type'],
                    created_by=request.user,
                    linked_savings=form.cleaned_data.get('linked_savings_account'),
                )
                messages.success(request, f'Pigmmy account {account.account_no} created.')
                return redirect('agents:pigmmy_detail', pk=account.pk)
            except ValueError as e:
                messages.error(request, str(e))
    else:
        initial = {}
        agent_id = request.GET.get('agent')
        if agent_id:
            try:
                initial['agent'] = int(agent_id)
            except (ValueError, TypeError):
                pass
        form = PigmmyAccountForm(branch=branch, initial=initial)
    selected_agent = None
    if request.GET.get('agent'):
        try:
            selected_agent = Agent.objects.select_related('member').get(pk=int(request.GET['agent']))
        except (Agent.DoesNotExist, ValueError, TypeError):
            pass
    return render(
        request,
        'agents/pigmmy_create.html',
        {
            'form': form,
            'selected_agent': selected_agent,
            'slabs_json': slabs_json,
            'pigmmy_head_id': head.pk if head else '',
        },
    )


@auditor_or_above
def pigmmy_detail(request, pk):
    account = get_object_or_404(
        PigmmyAccount.objects.select_related('member', 'agent__member', 'branch'),
        pk=pk,
    )
    if not has_branch_access(request, account.branch):
        messages.error(request, 'You do not have access to this account.')
        return redirect('agents:pigmmy_list')
    transactions = PigmmyTransaction.objects.filter(account=account).order_by('-txn_date', '-created_at')[:50]
    return render(
        request,
        'agents/pigmmy_detail.html',
        {
            'account': account,
            'transactions': transactions,
        },
    )


@manager_required
def pigmmy_edit(request, pk):
    account = get_object_or_404(PigmmyAccount, pk=pk)
    if not has_branch_access(request, account.branch):
        messages.error(request, 'You do not have access to this account.')
        return redirect('agents:pigmmy_list')
    if request.method == 'POST':
        form = PigmmyEditForm(request.POST, instance=account)
        if form.is_valid():
            form.save()
            messages.success(request, f'Pigmmy account {account.account_no} updated.')
            return redirect('agents:pigmmy_detail', pk=account.pk)
    else:
        form = PigmmyEditForm(instance=account)
    return render(request, 'agents/pigmmy_edit.html', {'form': form, 'account': account})


@manager_required
def pigmmy_close(request, pk):
    account = get_object_or_404(PigmmyAccount, pk=pk)
    if not has_branch_access(request, account.branch):
        messages.error(request, 'You do not have access to this account.')
        return redirect('agents:pigmmy_list')
    if account.status != 'active':
        messages.warning(request, 'Account is already closed.')
        return redirect('agents:pigmmy_detail', pk=account.pk)
    if request.method == 'POST':
        account.status = 'closed'
        account.save(update_fields=['status'])
        messages.success(request, f'Pigmmy account {account.account_no} closed.')
        return redirect('agents:pigmmy_detail', pk=account.pk)
    return render(request, 'agents/pigmmy_close_confirm.html', {'account': account})


@auditor_or_above
def collection_list(request):
    collections = AgentCollection.objects.select_related('agent__member', 'branch')
    if not request.user.can_access_all_branches:
        collections = collections.filter(branch=request.current_branch)
    agent_id = request.GET.get('agent')
    if agent_id:
        collections = collections.filter(agent_id=agent_id)
    status = request.GET.get('status')
    if status:
        collections = collections.filter(status=status)
    date_from = request.GET.get('date_from')
    if date_from:
        collections = collections.filter(collection_date__gte=date_from)
    date_to = request.GET.get('date_to')
    if date_to:
        collections = collections.filter(collection_date__lte=date_to)
    deposit_type = request.GET.get('type')
    if deposit_type:
        from django.db.models import Exists, OuterRef

        collections = collections.filter(
            Exists(
                PigmmyTransaction.objects.filter(
                    collected_by=OuterRef('agent'),
                    txn_date=OuterRef('collection_date'),
                    is_reversed=False,
                    account__deposit_type=deposit_type,
                )
            )
        )
    collections = collections.order_by('-collection_date')
    agents = Agent.objects.filter(status='active').select_related('member')
    if not request.user.can_access_all_branches:
        agents = agents.filter(branch=request.current_branch)
    paginator = Paginator(collections, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    for col in page_obj:
        col.client_transactions = (
            PigmmyTransaction.objects.filter(
                collected_by=col.agent,
                txn_date=col.collection_date,
                is_reversed=False,
            )
            .select_related('account__member')
            .order_by('account__account_no')
        )
    return render(
        request,
        'agents/collection_list.html',
        {
            'collections': page_obj,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'paginator': paginator,
            'agents': agents,
            'status_choices': AgentCollection.STATUS_CHOICES,
        },
    )


@cashier_required
@day_open_required
def collection_create(request):
    from apps.dayend.models import WorkingDay

    branch = request.current_branch
    if branch is None:
        messages.warning(request, 'Please select a specific branch before recording a collection.')
        return redirect('agents:collection_list')
    if request.method == 'POST':
        form = CollectionForm(request.POST, branch=branch)
        if form.is_valid():
            agent = form.cleaned_data['agent']
            collection_date = form.cleaned_data['collection_date']
            agent_collection_amount = form.cleaned_data.get('agent_collection_amount')
            client_accounts = PigmmyAccount.objects.filter(agent=agent, status='active')

            client_payments = []
            for acct in client_accounts:
                amt = request.POST.get(f'amount_{acct.id}', '0')
                try:
                    amt = Decimal(amt)
                except (ValueError, InvalidOperation):
                    amt = Decimal('0')
                if amt > 0:
                    client_payments.append({'account_id': acct.id, 'amount': amt})

            if client_payments:
                from apps.agents.services import record_agent_collection

                try:
                    record_agent_collection(
                        agent=agent,
                        collection_date=collection_date,
                        client_payments=client_payments,
                        branch=branch,
                        created_by=request.user,
                        agent_collection_amount=agent_collection_amount,
                    )
                    messages.success(request, f'Collection recorded for {agent.agent_code} on {collection_date}.')
                    return redirect('agents:collection_list')
                except ValueError as e:
                    messages.error(request, str(e))
            else:
                messages.warning(request, 'No amounts entered.')
    else:
        initial = {}
        agent_id = request.GET.get('agent')
        if agent_id:
            try:
                initial['agent'] = int(agent_id)
            except (ValueError, TypeError):
                pass
        working_day = WorkingDay.objects.filter(branch=branch, is_day_open=True).first()
        if working_day:
            initial['collection_date'] = working_day.current_date
        form = CollectionForm(branch=branch, initial=initial)

    working_day = WorkingDay.objects.filter(branch=branch, is_day_open=True).first()
    return render(
        request,
        'agents/collection_create.html',
        {
            'form': form,
            'working_day_date': working_day.current_date.isoformat() if working_day else '',
            'preselected_agent': request.GET.get('agent', ''),
        },
    )


@cashier_required
def agent_clients_api(request, agent_id):
    agent = get_object_or_404(Agent, pk=agent_id, status='active')
    if not has_branch_access(request, agent.branch):
        return JsonResponse({'clients': []})
    accounts = (
        PigmmyAccount.objects.filter(
            agent=agent,
            status='active',
        )
        .select_related('member')
        .order_by('account_no')
    )
    data = [
        {
            'id': acct.id,
            'account_no': acct.account_no,
            'member_name': acct.member.name,
            'deposit_type': acct.get_deposit_type_display(),
            'installment_amount': str(acct.installment_amount),
            'current_balance': str(acct.current_balance),
            'paid_installments': acct.paid_installments,
            'total_installments': acct.total_installments,
        }
        for acct in accounts
    ]
    return JsonResponse({'clients': data})


@auditor_or_above
def collection_detail(request, pk):
    collection = get_object_or_404(
        AgentCollection.objects.select_related('agent__member', 'branch', 'reconciled_by'),
        pk=pk,
    )
    if not has_branch_access(request, collection.branch):
        messages.error(request, 'You do not have access to this collection.')
        return redirect('agents:collection_list')
    transactions = (
        PigmmyTransaction.objects.filter(
            collected_by=collection.agent,
            txn_date=collection.collection_date,
            is_reversed=False,
        )
        .select_related('account__member')
        .order_by('account__account_no')
    )
    return render(
        request,
        'agents/collection_detail.html',
        {
            'collection': collection,
            'transactions': transactions,
        },
    )


@auditor_or_above
def collection_posting_list(request):
    from django.db.models import Q, Sum

    from apps.accounting.models import JournalEntry

    branch = request.current_branch
    branch_filter = {}
    if not request.user.can_access_all_branches and branch:
        branch_filter['branch'] = branch

    # --- Pending agent collections ---
    collections = (
        AgentCollection.objects.filter(status='submitted', **branch_filter)
        .select_related('agent__member', 'branch')
        .order_by('-collection_date')
    )
    agent_id = request.GET.get('agent')
    if agent_id:
        collections = collections.filter(agent_id=agent_id)
    collections = list(collections)

    for col in collections:
        col.client_transactions = (
            PigmmyTransaction.objects.filter(
                collected_by=col.agent,
                txn_date=col.collection_date,
                is_reversed=False,
            )
            .select_related('account__member')
            .order_by('account__account_no')
        )

    # --- Recently posted / rejected agent collections ---
    posted = (
        AgentCollection.objects.filter(status__in=['reconciled', 'discrepancy'], **branch_filter)
        .select_related('agent__member', 'branch', 'reconciled_by')
        .order_by('-collection_date')
    )
    if agent_id:
        posted = posted.filter(agent_id=agent_id)
    posted = list(posted[:20])

    today = date.today()
    for col in posted:
        col.client_transactions = (
            PigmmyTransaction.objects.filter(
                collected_by=col.agent,
                txn_date=col.collection_date,
                is_reversed=False,
            )
            .select_related('account__member')
            .order_by('account__account_no')
        )
        col.can_rollback = col.status == 'reconciled' and col.collection_date == today

    today_rollbackable = [c for c in posted if c.can_rollback]

    agents = Agent.objects.filter(status='active', **branch_filter).select_related('member')

    # --- All recent journal entries (unified transaction view) ---
    entries = (
        JournalEntry.objects.select_related('branch', 'created_by')
        .annotate(amount=Sum('lines__debit_amount'))
    )
    if not request.user.can_access_all_branches and branch:
        entries = entries.filter(branch=branch)

    q = request.GET.get('q', '').strip()
    if q:
        entries = entries.filter(Q(voucher_no__icontains=q) | Q(narration__icontains=q))

    from_date = request.GET.get('from_date', '')
    to_date = request.GET.get('to_date', '')
    if from_date:
        entries = entries.filter(entry_date__gte=from_date)
    if to_date:
        entries = entries.filter(entry_date__lte=to_date)

    voucher_type = request.GET.get('type', '')
    if voucher_type in ('receipt', 'payment', 'journal', 'contra'):
        entries = entries.filter(voucher_type=voucher_type)

    source_filter = request.GET.get('source', '')
    if source_filter == 'manual':
        entries = entries.filter(reference_type='manual')
    elif source_filter == 'agent':
        entries = entries.filter(reference_type='pigmmy_collection')
    elif source_filter == 'system':
        entries = entries.exclude(reference_type__in=['manual', 'pigmmy_collection', 'modification'])

    status_filter = request.GET.get('status', '')
    if status_filter == 'posted':
        entries = entries.filter(is_posted=True, is_reversed=False)
    elif status_filter == 'reversed':
        entries = entries.filter(is_reversed=True)

    entries = entries.order_by('-entry_date', '-created_at')

    # --- Summary stats (today) ---
    today_entries = JournalEntry.objects.filter(
        entry_date=today, is_posted=True, is_reversed=False, **branch_filter,
    )
    today_receipts = today_entries.filter(voucher_type='receipt').aggregate(
        total=Sum('lines__debit_amount'),
    )['total'] or Decimal('0')
    today_payments = today_entries.filter(voucher_type='payment').aggregate(
        total=Sum('lines__debit_amount'),
    )['total'] or Decimal('0')
    today_collections = today_entries.filter(reference_type='pigmmy_collection').aggregate(
        total=Sum('lines__debit_amount'),
    )['total'] or Decimal('0')
    today_journal = today_entries.filter(voucher_type__in=['journal', 'contra']).aggregate(
        total=Sum('lines__debit_amount'),
    )['total'] or Decimal('0')

    paginator = Paginator(entries, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(
        request,
        'agents/collection_posting.html',
        {
            'pending': collections,
            'posted': posted,
            'agents': agents,
            'today_rollback_count': len(today_rollbackable),
            'today_rollback_total': sum(c.collected_amount for c in today_rollbackable),
            # Unified transaction data
            'entries': page_obj,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'paginator': paginator,
            'q': q,
            'from_date': from_date,
            'to_date': to_date,
            'voucher_type': voucher_type,
            'source_filter': source_filter,
            'status_filter': status_filter,
            # Summary stats
            'today_receipts': today_receipts,
            'today_payments': today_payments,
            'today_collections': today_collections,
            'today_journal': today_journal,
            'today_total': today_receipts + today_payments + today_journal,
        },
    )


@manager_required
@day_open_required
def collection_post(request, pk):
    collection = get_object_or_404(AgentCollection, pk=pk)
    if not has_branch_access(request, collection.branch):
        messages.error(request, 'You do not have access to this collection.')
        return redirect('agents:collection_posting')
    if request.method == 'POST':
        from apps.agents.services import post_collection

        try:
            result = post_collection(collection, posted_by=request.user)
            messages.success(
                request,
                f'Collection posted: {result["posted_count"]} accounts, total {result["total_amount"]}.',
            )
        except ValueError as e:
            messages.error(request, str(e))
    return redirect('agents:collection_posting')


@manager_required
@day_open_required
def collection_reject(request, pk):
    collection = get_object_or_404(AgentCollection, pk=pk)
    if not has_branch_access(request, collection.branch):
        messages.error(request, 'You do not have access to this collection.')
        return redirect('agents:collection_posting')
    if request.method == 'POST':
        if collection.status != 'submitted':
            messages.warning(request, 'Only submitted collections can be rejected.')
        else:
            with transaction.atomic():
                txns = PigmmyTransaction.objects.filter(
                    collected_by=collection.agent,
                    txn_date=collection.collection_date,
                    is_reversed=False,
                ).select_related('account')
                for txn in txns:
                    acct = txn.account
                    acct.current_balance -= txn.amount
                    acct.total_deposited -= txn.amount
                    acct.paid_installments -= 1
                    acct.save(update_fields=['current_balance', 'total_deposited', 'paid_installments', 'updated_at'])
                    txn.is_reversed = True
                    txn.save(update_fields=['is_reversed'])
                from apps.accounting.models import JournalEntry
                from apps.accounting.services import reverse_journal_entry

                journals = JournalEntry.objects.filter(
                    reference_type='pigmmy_collection',
                    reference_id=collection.pk,
                    is_reversed=False,
                )
                if not journals.exists():
                    journals = JournalEntry.objects.filter(
                        reference_type='pigmmy_collection',
                        entry_date=collection.collection_date,
                        narration__contains=collection.agent.agent_code,
                        is_reversed=False,
                    )
                for je in journals:
                    reverse_journal_entry(je, request.user)

                collection.status = 'discrepancy'
                collection.remarks = request.POST.get('remarks', '')
                collection.save(update_fields=['status', 'remarks'])
            messages.success(
                request,
                f'Collection for {collection.agent.agent_code} on {collection.collection_date} rejected and transactions reversed.',
            )
    return redirect('agents:collection_posting')


@manager_required
@day_open_required
def collection_rollback(request, pk):
    collection = get_object_or_404(AgentCollection, pk=pk)
    if not has_branch_access(request, collection.branch):
        messages.error(request, 'You do not have access to this collection.')
        return redirect('agents:collection_posting')
    if request.method == 'POST':
        from apps.agents.services import rollback_collection

        try:
            amount = rollback_collection(collection, user=request.user)
            messages.success(
                request,
                f'Collection for {collection.agent.agent_code} on {collection.collection_date} '
                f'rolled back (₹{amount}).',
            )
        except ValueError as e:
            messages.error(request, str(e))
    return redirect('agents:collection_posting')


@manager_required
@day_open_required
def collection_rollback_all(request):
    if request.method != 'POST':
        return redirect('agents:collection_posting')

    from apps.agents.services import rollback_collection

    today = date.today()
    branch = getattr(request, 'current_branch', None)
    qs = AgentCollection.objects.filter(status='reconciled', collection_date=today)
    if branch and not request.user.can_access_all_branches:
        qs = qs.filter(branch=branch)

    collections = list(qs)
    if not collections:
        messages.info(request, 'No posted collections to rollback for today.')
        return redirect('agents:collection_posting')

    rolled_back = 0
    total_amount = Decimal('0')
    for collection in collections:
        try:
            amount = rollback_collection(collection, user=request.user)
            rolled_back += 1
            total_amount += amount
        except ValueError:
            pass

    messages.success(request, f'Rolled back {rolled_back} collection(s) — total ₹{total_amount}')
    return redirect('agents:collection_posting')


@manager_required
def member_accounts_api(request, member_id):
    branch = request.current_branch
    savings_qs = SavingsAccount.objects.filter(
        member_id=member_id,
        status='active',
        account_type='savings',
    )
    security_qs = SavingsAccount.objects.filter(
        member_id=member_id,
        status='active',
        account_type='security',
    )
    if branch:
        savings_qs = savings_qs.filter(branch=branch)
        security_qs = security_qs.filter(branch=branch)
    return JsonResponse(
        {
            'savings': [{'id': a.id, 'label': str(a)} for a in savings_qs],
            'security': [{'id': a.id, 'label': str(a)} for a in security_qs],
        }
    )


@auditor_or_above
def agent_client_sheet(request, pk):
    agent = get_object_or_404(Agent.objects.select_related('member', 'branch'), pk=pk)
    if not has_branch_access(request, agent.branch):
        messages.error(request, 'You do not have access to this agent.')
        return redirect('agents:list')
    accounts = (
        PigmmyAccount.objects.filter(
            agent=agent,
            status='active',
        )
        .select_related('member')
        .order_by('account_no')
    )
    total_installment = sum(a.installment_amount for a in accounts)
    return render(
        request,
        'agents/client_sheet.html',
        {
            'agent': agent,
            'accounts': accounts,
            'total_installment': total_installment,
            'today': date.today(),
        },
    )
