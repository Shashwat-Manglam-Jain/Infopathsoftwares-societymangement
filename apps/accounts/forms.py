from django import forms
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import CustomUser

_tw_input = (
    'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500'
)


class CustomUserCreationForm(UserCreationForm):
    STAFF_ROLES = [
        ('admin', 'Admin'),
        ('branch_manager', 'Branch Manager'),
        ('cashier', 'Cashier'),
        ('clerk', 'Clerk'),
        ('accountant', 'Accountant'),
        ('auditor', 'Auditor'),
        ('director', 'Director'),
    ]

    class Meta:
        model = CustomUser
        fields = [
            'username',
            'first_name',
            'last_name',
            'email',
            'phone',
            'role',
            'branch',
            'can_access_all_branches',
        ]
        widgets = {
            'username': forms.TextInput(attrs={'class': _tw_input}),
            'first_name': forms.TextInput(attrs={'class': _tw_input}),
            'last_name': forms.TextInput(attrs={'class': _tw_input}),
            'email': forms.EmailInput(attrs={'class': _tw_input}),
            'phone': forms.TextInput(attrs={'class': _tw_input}),
            'role': forms.Select(attrs={'class': _tw_input}),
            'branch': forms.Select(attrs={'class': _tw_input}),
        }

    def __init__(self, *args, **kwargs):
        self.current_branch = kwargs.pop('current_branch', None)
        self.request_user = kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)
        self.fields['role'].choices = self.STAFF_ROLES
        if self.request_user and not self.request_user.is_admin:
            self.fields['role'].choices = [(k, v) for k, v in self.STAFF_ROLES if k != 'admin']
        for field_name in ('password1', 'password2'):
            if field_name in self.fields:
                self.fields[field_name].widget.attrs['class'] = _tw_input
        if self.current_branch:
            self.fields['branch'].initial = self.current_branch

    def clean_role(self):
        new_role = self.cleaned_data.get('role')
        if new_role == 'admin' and self.request_user and not self.request_user.is_admin:
            raise forms.ValidationError('Only an admin can grant admin access.')
        return new_role


class CustomUserChangeForm(UserChangeForm):
    password = None

    class Meta:
        model = CustomUser
        fields = [
            'first_name',
            'last_name',
            'email',
            'phone',
            'role',
            'branch',
            'can_access_all_branches',
            'profile_photo',
            'is_active',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': _tw_input}),
            'last_name': forms.TextInput(attrs={'class': _tw_input}),
            'email': forms.EmailInput(attrs={'class': _tw_input}),
            'phone': forms.TextInput(attrs={'class': _tw_input}),
            'role': forms.Select(attrs={'class': _tw_input}),
            'branch': forms.Select(attrs={'class': _tw_input}),
        }

    def __init__(self, *args, **kwargs):
        self.request_user = kwargs.pop('request_user', None)
        super().__init__(*args, **kwargs)
        self.fields['role'].choices = CustomUserCreationForm.STAFF_ROLES
        if self.request_user and not self.request_user.is_admin:
            self.fields['role'].choices = [(k, v) for k, v in CustomUserCreationForm.STAFF_ROLES if k != 'admin']

    def clean_role(self):
        new_role = self.cleaned_data.get('role')
        old_role = self.instance.role if self.instance.pk else None

        if new_role == 'admin' and self.request_user and not self.request_user.is_admin:
            raise forms.ValidationError('Only an admin can grant admin access.')

        if self.request_user and self.instance.pk == self.request_user.pk:
            if old_role == 'admin' and new_role != 'admin':
                raise forms.ValidationError('You cannot remove admin role from yourself.')

        if old_role == 'admin' and new_role != 'admin':
            admin_count = CustomUser.objects.filter(role='admin', is_active=True).count()
            if admin_count <= 1:
                raise forms.ValidationError('Cannot remove the last admin. Society must have at least one admin.')

        return new_role

    def clean_is_active(self):
        is_active = self.cleaned_data.get('is_active')
        if self.instance.pk and self.instance.role == 'admin' and not is_active:
            admin_count = CustomUser.objects.filter(role='admin', is_active=True).count()
            if admin_count <= 1:
                raise forms.ValidationError('Cannot deactivate the last admin.')
        return is_active


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'phone', 'profile_photo']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': _tw_input}),
            'last_name': forms.TextInput(attrs={'class': _tw_input}),
            'email': forms.EmailInput(attrs={'class': _tw_input}),
            'phone': forms.TextInput(attrs={'class': _tw_input}),
        }
