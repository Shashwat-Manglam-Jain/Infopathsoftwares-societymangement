import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import FDProduct, FixedDeposit, RDInstallment, RecurringDeposit


@login_required
def fd_list(request):
    fds = FixedDeposit.objects.select_related('member', 'branch')
    if not request.user.can_access_all_branches:
        fds = fds.filter(branch=request.current_branch)
    status = request.GET.get('status', 'active')
    if status:
        fds = fds.filter(status=status)
    return render(request, 'deposits/fd_list.html', {'fds': fds, 'current_status': status})


@login_required
def fd_create(request):
    from apps.deposits.forms import FDCreateForm
    from apps.deposits.models import FDProduct
    from apps.deposits.services import create_fd
    from apps.members.models import Member

    products = FDProduct.objects.filter(is_active=True)
    members = Member.objects.filter(status='active').order_by('name')
    if not request.user.can_access_all_branches:
        members = members.filter(branch=request.current_branch)

    if request.method == 'POST':
        form = FDCreateForm(request.POST)
        if form.is_valid():
            try:
                fd = create_fd(
                    member=form.cleaned_data['member'],
                    product=form.cleaned_data['product'],
                    amount=form.cleaned_data['amount'],
                    tenure_days=form.cleaned_data['tenure_days'],
                    branch=request.current_branch,
                    user=request.user,
                    is_auto_renew=form.cleaned_data.get('is_auto_renew', False),
                    linked_savings_account=form.cleaned_data.get('linked_savings_account'),
                    is_senior=form.cleaned_data.get('is_senior', False),
                )
                messages.success(request, f'Fixed Deposit {fd.fd_no} created successfully.')
                return redirect('deposits:fd_detail', pk=fd.pk)
            except (ValueError, Exception) as e:
                messages.error(request, str(e))
    else:
        form = FDCreateForm()

    return render(request, 'deposits/fd_create.html', {
        'form': form, 'products': products, 'members': members,
    })


@login_required
def fd_detail(request, pk):
    fd = get_object_or_404(
        FixedDeposit.objects.select_related('member', 'branch', 'fd_product', 'linked_savings_account', 'created_by'),
        pk=pk,
    )
    return render(request, 'deposits/fd_detail.html', {'fd': fd})


@login_required
def fd_premature_close(request, pk):
    from apps.deposits.services import premature_close_fd

    fd = get_object_or_404(FixedDeposit, pk=pk)
    if request.method == 'POST':
        try:
            premature_close_fd(fd, request.user)
            messages.success(request, f'FD {fd.fd_no} prematurely closed. Payout: {fd.premature_amount}')
        except (ValueError, Exception) as e:
            messages.error(request, str(e))
    return redirect('deposits:fd_detail', pk=pk)


@login_required
def fd_renew(request, pk):
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


@login_required
def rd_list(request):
    rds = RecurringDeposit.objects.select_related('member', 'branch')
    if not request.user.can_access_all_branches:
        rds = rds.filter(branch=request.current_branch)
    status = request.GET.get('status', 'active')
    if status:
        rds = rds.filter(status=status)
    return render(request, 'deposits/rd_list.html', {'rds': rds, 'current_status': status})


@login_required
def rd_create(request):
    from apps.deposits.forms import RDCreateForm
    from apps.deposits.services import create_rd
    from apps.members.models import Member

    members = Member.objects.filter(status='active').order_by('name')
    if not request.user.can_access_all_branches:
        members = members.filter(branch=request.current_branch)

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

    return render(request, 'deposits/rd_create.html', {'form': form, 'members': members})


@login_required
def rd_detail(request, pk):
    rd = get_object_or_404(
        RecurringDeposit.objects.select_related('member', 'branch', 'linked_savings_account', 'created_by'),
        pk=pk,
    )
    installments = RDInstallment.objects.filter(rd=rd).order_by('installment_no')
    paid_count = installments.filter(status='paid').count()
    total_deposited = sum(i.paid_amount for i in installments if i.status == 'paid')
    return render(request, 'deposits/rd_detail.html', {
        'rd': rd, 'installments': installments, 'paid_count': paid_count,
        'total_deposited': total_deposited,
    })


@login_required
def rd_collect(request, pk):
    from apps.deposits.services import collect_rd_installment

    rd = get_object_or_404(RecurringDeposit, pk=pk)
    if request.method == 'POST':
        try:
            amount = rd.monthly_installment
            collect_rd_installment(rd, amount, request.current_branch, request.user)
            messages.success(request, f'Installment collected for RD {rd.rd_no}.')
        except (ValueError, Exception) as e:
            messages.error(request, str(e))
    return redirect('deposits:rd_detail', pk=pk)


@login_required
def fd_product_list(request):
    products = FDProduct.objects.all().order_by('name')
    return render(request, 'deposits/fd_product_list.html', {'products': products})


@login_required
def fd_product_create(request):
    if request.method == 'POST':
        return _save_fd_product(request)
    return render(request, 'deposits/fd_product_form.html', {'title': 'Create FD Scheme', 'product': None})


@login_required
def fd_product_edit(request, pk):
    product = get_object_or_404(FDProduct, pk=pk)
    if request.method == 'POST':
        return _save_fd_product(request, product)
    return render(request, 'deposits/fd_product_form.html', {
        'title': f'Edit: {product.name}',
        'product': product,
        'rates_json': json.dumps(product.interest_rates),
    })


def _save_fd_product(request, product=None):
    from decimal import Decimal, InvalidOperation

    name = request.POST.get('name', '').strip()
    if not name:
        messages.error(request, 'Scheme name is required.')
        return render(request, 'deposits/fd_product_form.html', {
            'title': 'Edit FD Scheme' if product else 'Create FD Scheme', 'product': product,
        })

    try:
        min_amount = Decimal(request.POST.get('min_amount', '0'))
        max_amount = Decimal(request.POST.get('max_amount', '0'))
        min_tenure = int(request.POST.get('min_tenure_days', '0'))
        max_tenure = int(request.POST.get('max_tenure_days', '0'))
        premature_penalty = Decimal(request.POST.get('premature_penalty_percent', '1'))
    except (InvalidOperation, ValueError):
        messages.error(request, 'Invalid numeric values.')
        return render(request, 'deposits/fd_product_form.html', {
            'title': 'Edit FD Scheme' if product else 'Create FD Scheme', 'product': product,
        })

    compounding = request.POST.get('compounding', 'quarterly')
    is_active = request.POST.get('is_active') == 'on'

    rate_count = int(request.POST.get('rate_count', '0'))
    rates = []
    for i in range(rate_count):
        try:
            slab = {
                'min_days': int(request.POST.get(f'rate_{i}_min_days', '0')),
                'max_days': int(request.POST.get(f'rate_{i}_max_days', '0')),
                'rate': float(request.POST.get(f'rate_{i}_rate', '0')),
                'senior_rate': float(request.POST.get(f'rate_{i}_senior_rate', '0')),
            }
            if slab['min_days'] or slab['max_days'] or slab['rate']:
                rates.append(slab)
        except (ValueError, TypeError):
            continue

    if product is None:
        product = FDProduct()

    product.name = name
    product.min_amount = min_amount
    product.max_amount = max_amount
    product.min_tenure_days = min_tenure
    product.max_tenure_days = max_tenure
    product.interest_rates = rates
    product.compounding = compounding
    product.premature_penalty_percent = premature_penalty
    product.is_active = is_active
    product.save()

    messages.success(request, f'FD Scheme "{product.name}" saved.')
    return redirect('deposits:fd_product_list')
