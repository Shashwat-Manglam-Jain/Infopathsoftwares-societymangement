from django import forms

from apps.savings.models import SavingsAccount


class SavingsAccountForm(forms.ModelForm):
    class Meta:
        model = SavingsAccount
        fields = ['member', 'branch', 'account_type', 'interest_rate', 'minimum_balance']
        widgets = {
            'member': forms.Select(attrs={'class': 'w-full rounded border-gray-300'}),
            'branch': forms.Select(attrs={'class': 'w-full rounded border-gray-300'}),
            'account_type': forms.Select(attrs={'class': 'w-full rounded border-gray-300'}),
            'interest_rate': forms.NumberInput(attrs={'class': 'w-full rounded border-gray-300', 'step': '0.01'}),
            'minimum_balance': forms.NumberInput(attrs={'class': 'w-full rounded border-gray-300', 'step': '0.01'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        member = cleaned_data.get('member')
        account_type = cleaned_data.get('account_type')
        if member and account_type == 'savings':
            if SavingsAccount.objects.filter(
                member=member, account_type='savings', status='active',
            ).exists():
                raise forms.ValidationError(
                    'Member already has an active savings account. Only one per member is allowed.'
                )
        return cleaned_data


class DepositForm(forms.Form):
    account_id = forms.IntegerField(widget=forms.HiddenInput())
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'w-full rounded border-gray-300', 'step': '0.01'}),
    )
    payment_mode = forms.ChoiceField(
        choices=[('cash', 'Cash'), ('cheque', 'Cheque'), ('transfer', 'Transfer'), ('upi', 'UPI')],
        widget=forms.Select(attrs={'class': 'w-full rounded border-gray-300'}),
    )
    narration = forms.CharField(
        required=False, widget=forms.TextInput(attrs={'class': 'w-full rounded border-gray-300'})
    )
    cheque_no = forms.CharField(
        required=False, widget=forms.TextInput(attrs={'class': 'w-full rounded border-gray-300'})
    )
    cheque_date = forms.DateField(
        required=False, widget=forms.DateInput(attrs={'class': 'w-full rounded border-gray-300', 'type': 'date'})
    )
    bank_name = forms.CharField(
        required=False, widget=forms.TextInput(attrs={'class': 'w-full rounded border-gray-300'})
    )


class WithdrawalForm(forms.Form):
    account_id = forms.IntegerField(widget=forms.HiddenInput())
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'w-full rounded border-gray-300', 'step': '0.01'}),
    )
    payment_mode = forms.ChoiceField(
        choices=[('cash', 'Cash'), ('cheque', 'Cheque'), ('transfer', 'Transfer')],
        widget=forms.Select(attrs={'class': 'w-full rounded border-gray-300'}),
    )
    narration = forms.CharField(
        required=False, widget=forms.TextInput(attrs={'class': 'w-full rounded border-gray-300'})
    )


class StatementFilterForm(forms.Form):
    account_id = forms.IntegerField(widget=forms.HiddenInput())
    from_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'w-full rounded border-gray-300', 'type': 'date'})
    )
    to_date = forms.DateField(widget=forms.DateInput(attrs={'class': 'w-full rounded border-gray-300', 'type': 'date'}))
