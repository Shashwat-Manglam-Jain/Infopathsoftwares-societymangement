from django import forms
from django.contrib.auth.forms import UserChangeForm, UserCreationForm

from .models import CustomUser


_tw_input = 'block w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500'


class CustomUserCreationForm(UserCreationForm):
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
            'branch': forms.Select(attrs={'class': _tw_input}),
        }


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
            'is_active',
        ]
        widgets = {
            'branch': forms.Select(attrs={'class': _tw_input}),
        }


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
