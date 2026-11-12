from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.permissions import admin_required, auditor_or_above

from .forms import BranchForm
from .models import Branch


def _next_branch_code():
    last = Branch.objects.order_by('-branch_code').first()
    if last and last.branch_code:
        digits = ''.join(filter(str.isdigit, last.branch_code))
        num = int(digits) + 1 if digits else Branch.objects.count() + 1
    else:
        num = 1
    return f'BR{num:02d}'


@auditor_or_above
def branch_list(request):
    branches = Branch.objects.filter(status='active')
    return render(request, 'branches/list.html', {'branches': branches})


@admin_required
def branch_create(request):
    if request.method == 'POST':
        form = BranchForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Branch created successfully.')
            return redirect('branches:list')
    else:
        form = BranchForm(initial={'branch_code': _next_branch_code()})
    return render(request, 'branches/form.html', {'form': form, 'title': 'Create Branch'})


@admin_required
def branch_edit(request, pk):
    branch = get_object_or_404(Branch, pk=pk)
    if request.method == 'POST':
        form = BranchForm(request.POST, instance=branch)
        if form.is_valid():
            form.save()
            messages.success(request, 'Branch updated successfully.')
            return redirect('branches:list')
    else:
        form = BranchForm(instance=branch)
    return render(request, 'branches/form.html', {'form': form, 'title': f'Edit: {branch.branch_name}'})


@login_required
def switch_branch(request, branch_id):
    branch = get_object_or_404(Branch, id=branch_id, status='active')
    if not request.user.can_access_all_branches and request.user.branch_id != branch.id:
        if not request.user.is_admin:
            messages.error(request, 'You do not have access to this branch.')
            return redirect('dashboard:index')
    request.session['current_branch_id'] = branch.id
    messages.success(request, f'Switched to {branch.branch_name}.')
    return redirect('dashboard:index')
