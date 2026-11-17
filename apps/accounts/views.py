from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CustomUserChangeForm, CustomUserCreationForm, UserProfileForm
from .models import CustomUser
from .permissions import admin_required, manager_required


def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard:index')
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            login(request, form.get_user())
            next_url = request.GET.get('next', 'dashboard:index')
            return redirect(next_url)
    else:
        form = AuthenticationForm()
    return render(request, 'registration/login.html', {'form': form})


def logout_view(request):
    if request.method != 'POST':
        return redirect('dashboard:index')
    logout(request)
    messages.success(request, 'You have been logged out.')
    return redirect('accounts:login')


@login_required
def profile_view(request):
    if request.method == 'POST':
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('accounts:profile')
    else:
        form = UserProfileForm(instance=request.user)
    return render(request, 'accounts/profile.html', {'form': form})


@login_required
def change_password_view(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Password changed successfully.')
            return redirect('accounts:profile')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'accounts/change_password.html', {'form': form})


@manager_required
def staff_list(request):
    from django.db.models import Q

    users = CustomUser.objects.select_related('branch').order_by('username')
    if not request.user.can_access_all_branches:
        users = users.filter(branch=request.current_branch)
    q = request.GET.get('q', '').strip()
    if q:
        users = users.filter(
            Q(username__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q)
        )
    role_filter = request.GET.get('role', '')
    if role_filter:
        users = users.filter(role=role_filter)
    return render(request, 'accounts/staff_list.html', {'users': users, 'role_filter': role_filter})


@admin_required
def staff_create(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(
            request.POST, request.FILES, current_branch=request.current_branch, request_user=request.user
        )
        if form.is_valid():
            user = form.save()
            messages.success(request, f'Staff user {user.username} created.')
            return redirect('accounts:staff_list')
    else:
        form = CustomUserCreationForm(current_branch=request.current_branch, request_user=request.user)
    return render(request, 'accounts/staff_form.html', {'form': form, 'title': 'Add Staff User'})


@admin_required
def staff_edit(request, pk):
    edit_user = get_object_or_404(CustomUser, pk=pk)
    if request.method == 'POST':
        form = CustomUserChangeForm(request.POST, request.FILES, instance=edit_user, request_user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f'User {edit_user.username} updated.')
            return redirect('accounts:staff_list')
    else:
        form = CustomUserChangeForm(instance=edit_user, request_user=request.user)
    return render(
        request,
        'accounts/staff_form.html',
        {
            'form': form,
            'title': f'Edit: {edit_user.username}',
            'edit_user': edit_user,
        },
    )
