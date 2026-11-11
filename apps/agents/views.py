import json
from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Max
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounting.models import ChartOfAccounts, InterestMaster
from apps.accounts.permissions import auditor_or_above, cashier_required, manager_required
from apps.savings.models import SavingsAccount

from .forms import AgentForm, CollectionForm, PigmmyAccountForm
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
            'active_tab': 'agents',
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
        form = AgentForm(request.POST, branch=branch)
        if form.is_valid():
            agent = form.save(commit=False)
            agent.joining_date = date.today()
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
        form = AgentForm(branch=branch)
    return render(request, 'agents/create.html', {'form': form})


@auditor_or_above
def agent_detail(request, pk):
    agent = get_object_or_404(Agent.objects.select_related('member', 'branch', 'savings_account'), pk=pk)
    client_accounts = PigmmyAccount.objects.filter(agent=agent).select_related('member')
    recent_collections = AgentCollection.objects.filter(agent=agent).order_by('-collection_date')[:20]
    return render(
        request,
        'agents/detail.html',
        {
            'agent': agent,
            'client_accounts': client_accounts,
            'recent_collections': recent_collections,
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
            'active_tab': 'accounts',
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'paginator': paginator,
        },
    )


@cashier_required
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
        },
    )


@auditor_or_above
def pigmmy_detail(request, pk):
    account = get_object_or_404(
        PigmmyAccount.objects.select_related('member', 'agent__member', 'branch'),
        pk=pk,
    )
    transactions = PigmmyTransaction.objects.filter(account=account).order_by('-txn_date', '-created_at')[:50]
    return render(
        request,
        'agents/pigmmy_detail.html',
        {
            'account': account,
            'transactions': transactions,
        },
    )


@auditor_or_above
def collection_list(request):
    collections = AgentCollection.objects.select_related('agent__member', 'branch')
    if not request.user.can_access_all_branches:
        collections = collections.filter(branch=request.current_branch)
    collections = collections.order_by('-collection_date')
    paginator = Paginator(collections, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(
        request,
        'agents/collection_list.html',
        {
            'collections': page_obj,
            'active_tab': 'collections',
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'paginator': paginator,
        },
    )


@cashier_required
def collection_create(request):
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
                except Exception:
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
        form = CollectionForm(branch=branch)

    return render(request, 'agents/collection_create.html', {'form': form})


@cashier_required
def agent_clients_api(request, agent_id):
    agent = get_object_or_404(Agent, pk=agent_id, status='active')
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
def collection_posting_list(request):
    collections = (
        AgentCollection.objects.filter(
            status='submitted',
        )
        .select_related('agent__member', 'branch')
        .order_by('-collection_date')
    )
    if not request.user.can_access_all_branches:
        collections = collections.filter(branch=request.current_branch)

    posted = (
        AgentCollection.objects.filter(
            status='reconciled',
        )
        .select_related('agent__member', 'branch', 'reconciled_by')
        .order_by('-collection_date')
    )
    if not request.user.can_access_all_branches:
        posted = posted.filter(branch=request.current_branch)
    posted = posted[:20]

    return render(
        request,
        'agents/collection_posting.html',
        {
            'pending': collections,
            'posted': posted,
            'active_tab': 'posting',
        },
    )


@manager_required
def collection_post(request, pk):
    collection = get_object_or_404(AgentCollection, pk=pk)
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
