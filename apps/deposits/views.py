import json

from django.contrib import messages
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounting.models import ChartOfAccounts, InterestMaster
from apps.accounts.permissions import auditor_or_above, cashier_required, day_open_required, manager_required

from .models import FixedDeposit, RDInstallment, RecurringDeposit


@auditor_or_above
def fd_list(request):
    fds = FixedDeposit.objects.select_related('member', 'branch')
    if not request.user.can_access_all_branches:
        fds = fds.filter(branch=request.current_branch)
    status = request.GET.get('status', 'active')
    if status:
        fds = fds.filter(status=status)
    paginator = Paginator(fds, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(
        request,
        'deposits/fd_list.html',
        {
            'fds': page_obj,
            'current_status': status,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'paginator': paginator,
        },
    )


@cashier_required
@day_open_required
def fd_create(request):
    from apps.deposits.forms import FDCreateForm
    from apps.deposits.services import create_fd
    from apps.members.models import Member

    if request.current_branch is None:
        messages.warning(request, 'Please select a specific branch before creating a Fixed Deposit.')
        return redirect('deposits:fd_list')

    members = Member.objects.filter(status='active').order_by('name')
    if not request.user.can_access_all_branches:
        members = members.filter(branch=request.current_branch)

    fd_head = ChartOfAccounts.objects.filter(related_table_name='fixed', is_active=True).first()
    slabs = []
    if fd_head:
        for s in InterestMaster.objects.filter(account_head=fd_head, is_active=True).order_by('min_period'):
            slabs.append(
                {
                    'min_days': s.min_period,
                    'max_days': s.max_period,
                    'rate': float(s.interest_rate),
                    'senior_extra': float(s.senior_citizen_extra),
                }
            )
    slabs_json = json.dumps(slabs)

    if request.method == 'POST':
        form = FDCreateForm(request.POST)
        if form.is_valid():
            try:
                fd = create_fd(
                    member=form.cleaned_data['member'],
                    amount=form.cleaned_data['amount'],
                    tenure_days=form.cleaned_data['tenure_days'],
                    branch=request.current_branch,
                    user=request.user,
                    is_auto_renew=form.cleaned_data.get('is_auto_renew', False),
                    linked_savings_account=form.cleaned_data.get('linked_savings_account'),
                    is_senior=form.cleaned_data.get('is_senior', False),
                    compounding=form.cleaned_data['compounding'],
                )
                messages.success(request, f'Fixed Deposit {fd.fd_no} created successfully.')
                return redirect('deposits:fd_detail', pk=fd.pk)
            except (ValueError, Exception) as e:
                messages.error(request, str(e))
    else:
        form = FDCreateForm()

    return render(
        request,
        'deposits/fd_create.html',
        {
            'form': form,
            'members': members,
            'slabs_json': slabs_json,
        },
    )


@auditor_or_above
def fd_detail(request, pk):
    fd = get_object_or_404(
        FixedDeposit.objects.select_related('member', 'branch', 'fd_product', 'linked_savings_account', 'created_by'),
        pk=pk,
    )
    return render(request, 'deposits/fd_detail.html', {'fd': fd})


@manager_required
@day_open_required
def fd_premature_close(request, pk):
    if not request.current_branch:
        messages.warning(request, 'Please select a branch first.')
        return redirect('deposits:fd_list')
    from apps.deposits.services import premature_close_fd

    fd = get_object_or_404(FixedDeposit, pk=pk)
    if request.method == 'POST':
        try:
            premature_close_fd(fd, request.user)
            messages.success(request, f'FD {fd.fd_no} prematurely closed. Payout: {fd.premature_amount}')
        except (ValueError, Exception) as e:
            messages.error(request, str(e))
    return redirect('deposits:fd_detail', pk=pk)


@manager_required
@day_open_required
def fd_renew(request, pk):
    if not request.current_branch:
        messages.warning(request, 'Please select a branch first.')
        return redirect('deposits:fd_list')
    from apps.deposits.services import renew_fd

    fd = get_object_or_404(FixedDeposit, pk=pk)
    if request.method == 'POST':
        try:
            new_fd = renew_fd(fd, request.user)
            fd.status = 'renewed'
            fd.save(update_fields=['status'])
            messages.success(request, f'FD renewed. New FD: {new_fd.fd_no}')
            return redirect('deposits:fd_detail', pk=new_fd.pk)
        except (ValueError, Exception) as e:
            messages.error(request, str(e))
    return redirect('deposits:fd_detail', pk=pk)


@auditor_or_above
def rd_list(request):
    rds = RecurringDeposit.objects.select_related('member', 'branch')
    if not request.user.can_access_all_branches:
        rds = rds.filter(branch=request.current_branch)
    status = request.GET.get('status', 'active')
    if status:
        rds = rds.filter(status=status)
    paginator = Paginator(rds, 25)
    page_obj = paginator.get_page(request.GET.get('page'))
    return render(
        request,
        'deposits/rd_list.html',
        {
            'rds': page_obj,
            'current_status': status,
            'page_obj': page_obj,
            'is_paginated': page_obj.has_other_pages(),
            'paginator': paginator,
        },
    )


@cashier_required
@day_open_required
def rd_create(request):
    from apps.deposits.forms import RDCreateForm
    from apps.deposits.services import create_rd
    from apps.members.models import Member

    if request.current_branch is None:
        messages.warning(request, 'Please select a specific branch before creating a Recurring Deposit.')
        return redirect('deposits:rd_list')

    members = Member.objects.filter(status='active').order_by('name')
    if not request.user.can_access_all_branches:
        members = members.filter(branch=request.current_branch)

    # Build InterestMaster slabs for RD rate auto-fill
    rd_head = ChartOfAccounts.objects.filter(related_table_name='recurring', is_active=True).first()
    slabs = []
    if rd_head:
        for s in InterestMaster.objects.filter(account_head=rd_head, is_active=True).order_by('min_period'):
            slabs.append(
                {
                    'min_months': s.min_period,
                    'max_months': s.max_period,
                    'rate': float(s.interest_rate),
                }
            )
    slabs_json = json.dumps(slabs)

    if request.method == 'POST':
        form = RDCreateForm(request.POST)
        if form.is_valid():
            try:
                rd = create_rd(
                    member=form.cleaned_data['member'],
                    monthly_installment=form.cleaned_data['monthly_installment'],
                    tenure_months=form.cleaned_data['tenure_months'],
                    interest_rate=form.cleaned_data['interest_rate'],
                    branch=request.current_branch,
                    user=request.user,
                    linked_savings_account=form.cleaned_data.get('linked_savings_account'),
                )
                messages.success(request, f'Recurring Deposit {rd.rd_no} created successfully.')
                return redirect('deposits:rd_detail', pk=rd.pk)
            except (ValueError, Exception) as e:
                messages.error(request, str(e))
    else:
        form = RDCreateForm()

    return render(
        request,
        'deposits/rd_create.html',
        {
            'form': form,
            'members': members,
            'slabs_json': slabs_json,
        },
    )


@auditor_or_above
def rd_detail(request, pk):
    rd = get_object_or_404(
        RecurringDeposit.objects.select_related('member', 'branch', 'linked_savings_account', 'created_by'),
        pk=pk,
    )
    installments = RDInstallment.objects.filter(rd=rd).order_by('installment_no')
    paid_count = installments.filter(status='paid').count()
    total_deposited = sum(i.paid_amount for i in installments if i.status == 'paid')
    return render(
        request,
        'deposits/rd_detail.html',
        {
            'rd': rd,
            'installments': installments,
            'paid_count': paid_count,
            'total_deposited': total_deposited,
        },
    )


@cashier_required
@day_open_required
def rd_collect(request, pk):
    from apps.deposits.services import collect_rd_installment

    rd = get_object_or_404(RecurringDeposit, pk=pk)
    if request.current_branch is None:
        messages.warning(request, 'Please select a specific branch before collecting installments.')
        return redirect('deposits:rd_detail', pk=pk)
    if request.method == 'POST':
        try:
            amount = rd.monthly_installment
            collect_rd_installment(rd, amount, request.current_branch, request.user)
            messages.success(request, f'Installment collected for RD {rd.rd_no}.')
        except (ValueError, Exception) as e:
            messages.error(request, str(e))
    return redirect('deposits:rd_detail', pk=pk)
