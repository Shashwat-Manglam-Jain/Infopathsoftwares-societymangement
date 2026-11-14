from django import forms

from .models import NotificationTemplate


class NotificationTemplateForm(forms.ModelForm):
    class Meta:
        model = NotificationTemplate
        fields = ['name', 'channel', 'subject', 'template_text', 'is_active']
        widgets = {
            'name': forms.TextInput(
                attrs={'class': 'w-full rounded border border-gray-300 px-2.5 py-1.5 text-sm focus:ring-primary-500 focus:border-primary-500'}
            ),
            'channel': forms.Select(
                attrs={'class': 'w-full rounded border border-gray-300 px-2.5 py-1.5 text-sm focus:ring-primary-500 focus:border-primary-500'}
            ),
            'subject': forms.TextInput(
                attrs={'class': 'w-full rounded border border-gray-300 px-2.5 py-1.5 text-sm focus:ring-primary-500 focus:border-primary-500'}
            ),
            'template_text': forms.Textarea(
                attrs={
                    'class': 'w-full rounded border border-gray-300 px-2.5 py-1.5 text-sm focus:ring-primary-500 focus:border-primary-500',
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
            attrs={'class': 'w-full rounded border border-gray-300 px-2.5 py-1.5 text-sm focus:ring-primary-500 focus:border-primary-500',
                   'id': 'id_recipient_type'}
        ),
    )
    branch = forms.ModelChoiceField(
        required=False,
        queryset=None,
        empty_label='— Select Branch —',
        widget=forms.Select(
            attrs={'class': 'w-full rounded border border-gray-300 px-2.5 py-1.5 text-sm focus:ring-primary-500 focus:border-primary-500'}
        ),
    )
    member_ids = forms.CharField(
        required=False,
        widget=forms.TextInput(
            attrs={
                'class': 'w-full rounded border border-gray-300 px-2.5 py-1.5 text-sm focus:ring-primary-500 focus:border-primary-500',
                'placeholder': 'e.g. 1, 2, 5, 12',
            }
        ),
        help_text='Comma-separated member IDs',
    )
    message = forms.CharField(
        widget=forms.Textarea(
            attrs={
                'class': 'w-full rounded border border-gray-300 px-2.5 py-1.5 text-sm focus:ring-primary-500 focus:border-primary-500',
                'rows': 4,
                'placeholder': 'Enter your message here...',
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.branches.models import Branch
        self.fields['branch'].queryset = Branch.objects.all()

    def clean(self):
        cleaned = super().clean()
        rtype = cleaned.get('recipient_type')
        if rtype == 'branch' and not cleaned.get('branch'):
            self.add_error('branch', 'Select a branch.')
        if rtype == 'selected':
            ids_str = cleaned.get('member_ids', '').strip()
            if not ids_str:
                self.add_error('member_ids', 'Enter at least one member ID.')
        return cleaned
