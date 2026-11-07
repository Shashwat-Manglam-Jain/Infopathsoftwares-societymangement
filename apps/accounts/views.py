from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, PasswordChangeForm
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CustomUserChangeForm, CustomUserCreationForm, UserProfileForm
from .models import CustomUser


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


@login_required
def staff_list(request):
    if not request.user.is_manager:
        messages.error(request, 'Permission denied.')
        return redirect('dashboard:index')
    users = CustomUser.objects.select_related('branch').order_by('username')
    if not request.user.can_access_all_branches:
        users = users.filter(branch=request.current_branch)
    return render(request, 'accounts/staff_list.html', {'users': users})


@login_required
def staff_create(request):
    if not request.user.is_manager:
        messages.error(request, 'Permission denied.')
        return redirect('dashboard:index')
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'Staff user {user.username} created.')
            return redirect('accounts:staff_list')
    else:
        form = CustomUserCreationForm()
    return render(request, 'accounts/staff_form.html', {'form': form, 'title': 'Add Staff User'})


@login_required
def staff_edit(request, pk):
    if not request.user.is_manager:
        messages.error(request, 'Permission denied.')
        return redirect('dashboard:index')
    edit_user = get_object_or_404(CustomUser, pk=pk)
    if request.method == 'POST':
        form = CustomUserChangeForm(request.POST, instance=edit_user)
        if form.is_valid():
            form.save()
            messages.success(request, f'User {edit_user.username} updated.')
            return redirect('accounts:staff_list')
    else:
        form = CustomUserChangeForm(instance=edit_user)
    return render(request, 'accounts/staff_form.html', {
        'form': form,
        'title': f'Edit: {edit_user.username}',
        'edit_user': edit_user,
    })
