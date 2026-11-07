from datetime import date
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AgentForm, CollectionForm, PigmmyAccountForm
from .models import Agent, AgentCollection, PigmmyAccount, PigmmyTransaction


@login_required
def agent_list(request):
    agents = Agent.objects.filter(status='active').select_related('member', 'branch')
    if not request.user.can_access_all_branches:
        agents = agents.filter(branch=request.current_branch)
    return render(request, 'agents/agent_list.html', {'agents': agents})


@login_required
def agent_create(request):
    if request.method == 'POST':
        form = AgentForm(request.POST)
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
        form = AgentForm()
    return render(request, 'agents/create.html', {'form': form})


@login_required
def agent_detail(request, pk):
    agent = get_object_or_404(Agent.objects.select_related('member', 'branch', 'savings_account'), pk=pk)
    client_accounts = PigmmyAccount.objects.filter(agent=agent).select_related('member')
    recent_collections = AgentCollection.objects.filter(agent=agent).order_by('-collection_date')[:20]
    return render(request, 'agents/detail.html', {
        'agent': agent,
        'client_accounts': client_accounts,
        'recent_collections': recent_collections,
    })


@login_required
def pigmmy_account_list(request):
    accounts = PigmmyAccount.objects.filter(status='active').select_related(
        'member', 'agent__member', 'branch',
    )
    if not request.user.can_access_all_branches:
        accounts = accounts.filter(branch=request.current_branch)
    agent_id = request.GET.get('agent')
    if agent_id:
        accounts = accounts.filter(agent_id=agent_id)
    agents = Agent.objects.filter(status='active')
    return render(request, 'agents/pigmmy_list.html', {'accounts': accounts, 'agents': agents})


@login_required
def pigmmy_create(request):
    if request.method == 'POST':
        form = PigmmyAccountForm(request.POST)
        if form.is_valid():
            from apps.agents.services import create_pigmmy_account

            try:
                branch = request.current_branch
                account = create_pigmmy_account(
                    member=form.cleaned_data['member'],
                    agent=form.cleaned_data['agent'],
                    branch=branch,
                    installment_amount=form.cleaned_data['installment_amount'],
                    deposit_period_months=form.cleaned_data['deposit_period_months'],
                    interest_rate=form.cleaned_data['interest_rate'],
                    deposit_type=form.cleaned_data['deposit_type'],
                    created_by=request.user,
                )
                messages.success(request, f'Pigmmy account {account.account_no} created.')
                return redirect('agents:pigmmy_detail', pk=account.pk)
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = PigmmyAccountForm()
    return render(request, 'agents/pigmmy_create.html', {'form': form})


@login_required
def pigmmy_detail(request, pk):
    account = get_object_or_404(
        PigmmyAccount.objects.select_related('member', 'agent__member', 'branch'), pk=pk,
    )
    transactions = PigmmyTransaction.objects.filter(account=account).order_by('-txn_date', '-created_at')[:50]
    return render(request, 'agents/pigmmy_detail.html', {
        'account': account,
        'transactions': transactions,
    })


@login_required
def collection_list(request):
    collections = AgentCollection.objects.select_related('agent__member', 'branch')
    if not request.user.can_access_all_branches:
        collections = collections.filter(branch=request.current_branch)
    collections = collections.order_by('-collection_date')
    return render(request, 'agents/collection_list.html', {'collections': collections})


@login_required
def collection_create(request):
    if request.method == 'POST':
        form = CollectionForm(request.POST)
        if form.is_valid():
            agent = form.cleaned_data['agent']
            collection_date = form.cleaned_data['collection_date']
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
                    branch = request.current_branch
                    record_agent_collection(
                        agent=agent,
                        collection_date=collection_date,
                        client_payments=client_payments,
                        branch=branch,
                        created_by=request.user,
                    )
                    messages.success(request, f'Collection recorded for {agent.agent_code} on {collection_date}.')
                    return redirect('agents:collection_list')
                except ValueError as e:
                    messages.error(request, str(e))
            else:
                messages.warning(request, 'No amounts entered.')
    else:
        form = CollectionForm()

    agent_id = request.GET.get('agent') or request.POST.get('agent')
    client_accounts = []
    if agent_id:
        try:
            client_accounts = PigmmyAccount.objects.filter(
                agent_id=int(agent_id), status='active',
            ).select_related('member')
        except (ValueError, TypeError):
            pass

    return render(request, 'agents/collection_create.html', {
        'form': form,
        'client_accounts': client_accounts,
    })
