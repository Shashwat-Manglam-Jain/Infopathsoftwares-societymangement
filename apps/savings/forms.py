from django import forms

from apps.savings.models import SavingsAccount

_tw = 'w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500'
_tw_s = 'searchable ' + _tw


class SavingsAccountForm(forms.ModelForm):
    class Meta:
        model = SavingsAccount
        fields = ['member', 'branch', 'account_type', 'interest_rate', 'minimum_balance', 'interest_posting_frequency']
        widgets = {
            'member': forms.Select(attrs={'class': _tw_s}),
            'branch': forms.Select(attrs={'class': _tw}),
            'account_type': forms.Select(attrs={'class': _tw}),
            'interest_rate': forms.NumberInput(
                attrs={
                    'class': _tw + ' bg-gray-50 cursor-not-allowed',
                    'step': '0.01',
                    'readonly': True,
                    'tabindex': '-1',
                }
            ),
            'minimum_balance': forms.NumberInput(attrs={'class': _tw, 'step': '0.01'}),
            'interest_posting_frequency': forms.Select(attrs={'class': _tw}),
        }

    def __init__(self, *args, **kwargs):
        self.current_branch = kwargs.pop('current_branch', None)
        super().__init__(*args, **kwargs)
        if self.current_branch:
            self.fields['branch'].initial = self.current_branch
            self.fields['branch'].widget = forms.HiddenInput()
            self.initial['branch'] = self.current_branch.pk

    def clean(self):
        cleaned_data = super().clean()
        member = cleaned_data.get('member')
        account_type = cleaned_data.get('account_type')
        if member and account_type == 'savings':
            qs = SavingsAccount.objects.filter(
                member=member,
                account_type='savings',
                status='active',
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    'Member already has an active savings account. Only one per member is allowed.'
                )
        return cleaned_data


class SavingsAccountEditForm(forms.ModelForm):
    class Meta:
        model = SavingsAccount
        fields = ['interest_rate', 'minimum_balance', 'interest_posting_frequency']
        widgets = {
            'interest_rate': forms.NumberInput(
                attrs={
                    'class': _tw + ' bg-gray-50 cursor-not-allowed',
                    'step': '0.01',
                    'readonly': True,
                    'tabindex': '-1',
                }
            ),
            'minimum_balance': forms.NumberInput(attrs={'class': _tw, 'step': '0.01'}),
            'interest_posting_frequency': forms.Select(attrs={'class': _tw}),
        }


class DepositForm(forms.Form):
    account_id = forms.IntegerField(widget=forms.HiddenInput())
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=1,
        widget=forms.NumberInput(attrs={'class': _tw, 'step': '0.01'}),
    )
    payment_mode = forms.ChoiceField(
        choices=[('cash', 'Cash'), ('cheque', 'Cheque'), ('transfer', 'Transfer'), ('upi', 'UPI')],
        widget=forms.Select(attrs={'class': _tw}),
    )
    narration = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': _tw}),
    )
    cheque_no = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': _tw}),
    )
    cheque_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': _tw, 'type': 'date'}),
    )
    bank_name = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': _tw}),
    )


class WithdrawalForm(forms.Form):
    account_id = forms.IntegerField(widget=forms.HiddenInput())
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=1,
        widget=forms.NumberInput(attrs={'class': _tw, 'step': '0.01'}),
    )
    payment_mode = forms.ChoiceField(
        choices=[('cash', 'Cash'), ('cheque', 'Cheque'), ('transfer', 'Transfer')],
        widget=forms.Select(attrs={'class': _tw}),
    )
    narration = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': _tw}),
    )


class StatementFilterForm(forms.Form):
    account_id = forms.IntegerField(widget=forms.HiddenInput())
    from_date = forms.DateField(widget=forms.DateInput(attrs={'class': _tw, 'type': 'date'}))
    to_date = forms.DateField(widget=forms.DateInput(attrs={'class': _tw, 'type': 'date'}))
