from django import forms

from .models import NotificationTemplate


class NotificationTemplateForm(forms.ModelForm):
    class Meta:
        model = NotificationTemplate
        fields = ['name', 'channel', 'subject', 'template_text', 'is_active']
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500'
                }
            ),
            'channel': forms.Select(
                attrs={
                    'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500'
                }
            ),
            'subject': forms.TextInput(
                attrs={
                    'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500'
                }
            ),
            'template_text': forms.Textarea(
                attrs={
                    'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                    'rows': 5,
                }
            ),
        }


class BulkSMSForm(forms.Form):
    RECIPIENT_CHOICES = [
        ('all', 'All Active Members'),
        ('branch', 'Members of Selected Branch'),
        ('selected', 'Selected Members'),
    ]

    recipient_type = forms.ChoiceField(
        choices=RECIPIENT_CHOICES,
        widget=forms.Select(
            attrs={'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500'}
        ),
    )
    branch = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput(),
    )
    member_ids = forms.CharField(
        required=False,
        widget=forms.HiddenInput(),
        help_text='Comma-separated member IDs',
    )
    message = forms.CharField(
        widget=forms.Textarea(
            attrs={
                'class': 'w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500',
                'rows': 4,
                'placeholder': 'Enter your message here...',
            }
        ),
    )
