from django import forms

from apps.accounting.models import ChartOfAccounts, JournalEntry

tw = 'w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500'


class ChartOfAccountsForm(forms.ModelForm):
    class Meta:
        model = ChartOfAccounts
        fields = [
            'code', 'name', 'account_group', 'parent', 'related_table_name',
            'interest_affected', 'overdue_affected', 'interest_given', 'interest_code',
            'report_position', 'display_order', 'allow_transactions',
        ]
        widgets = {
            'code': forms.TextInput(attrs={'class': tw}),
            'name': forms.TextInput(attrs={'class': tw}),
            'account_group': forms.Select(attrs={'class': tw}),
            'parent': forms.Select(attrs={'class': tw}),
            'related_table_name': forms.Select(attrs={'class': tw}),
            'interest_code': forms.Select(attrs={'class': tw}),
            'report_position': forms.Select(attrs={'class': tw}),
            'display_order': forms.NumberInput(attrs={'class': tw}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['parent'].queryset = ChartOfAccounts.objects.filter(is_active=True)
        self.fields['parent'].required = False
        self.fields['interest_code'].queryset = ChartOfAccounts.objects.filter(is_active=True)
        self.fields['interest_code'].required = False


class VoucherForm(forms.Form):
    voucher_type = forms.ChoiceField(
        choices=JournalEntry.VOUCHER_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': tw}),
    )
    narration = forms.CharField(
        widget=forms.Textarea(attrs={'class': tw, 'rows': 2}),
    )
    debit_account = forms.ModelChoiceField(
        queryset=ChartOfAccounts.objects.filter(allow_transactions=True, is_active=True),
        widget=forms.Select(attrs={'class': tw}),
        label='Debit (DR) Account',
    )
    credit_account = forms.ModelChoiceField(
        queryset=ChartOfAccounts.objects.filter(allow_transactions=True, is_active=True),
        widget=forms.Select(attrs={'class': tw}),
        label='Credit (CR) Account',
    )
    amount = forms.DecimalField(
        max_digits=15, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': tw, 'step': '0.01'}),
    )
