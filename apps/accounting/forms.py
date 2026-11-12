from decimal import Decimal

from django import forms

from apps.accounting.models import ChartOfAccounts, InterestMaster, JournalEntry

tw = 'w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500'


class ChartOfAccountsForm(forms.ModelForm):
    class Meta:
        model = ChartOfAccounts
        fields = [
            'code',
            'name',
            'head_name_regional',
            'account_group',
            'account_code',
            'parent',
            'sub_group',
            'related_table_name',
            'opening_balance',
            'credit_balance',
            'debit_balance',
            'interest_affected',
            'overdue_affected',
            'interest_given',
            'interest_code',
            'report_position',
            'display_order',
            'allow_transactions',
        ]
        widgets = {
            'code': forms.TextInput(attrs={'class': tw}),
            'name': forms.TextInput(attrs={'class': tw}),
            'head_name_regional': forms.TextInput(attrs={'class': tw}),
            'account_code': forms.TextInput(attrs={'class': tw, 'maxlength': '3'}),
            'sub_group': forms.TextInput(attrs={'class': tw}),
            'account_group': forms.Select(attrs={'class': tw}),
            'parent': forms.Select(attrs={'class': tw}),
            'related_table_name': forms.Select(attrs={'class': tw}),
            'opening_balance': forms.NumberInput(attrs={'class': tw, 'step': '0.01'}),
            'credit_balance': forms.NumberInput(attrs={'class': tw, 'step': '0.01'}),
            'debit_balance': forms.NumberInput(attrs={'class': tw, 'step': '0.01'}),
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
        max_digits=15,
        decimal_places=2,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={'class': tw, 'step': '0.01'}),
    )


class InterestMasterForm(forms.ModelForm):
    class Meta:
        model = InterestMaster
        fields = [
            'account_head',
            'min_period',
            'max_period',
            'period_unit',
            'interest_rate',
            'penal_rate',
            'senior_citizen_extra',
            'widow_extra',
            'ex_military_extra',
            'disabled_extra',
            'employee_extra',
            'director_extra',
            'is_active',
        ]
        widgets = {
            'account_head': forms.Select(attrs={'class': tw}),
            'min_period': forms.NumberInput(attrs={'class': tw}),
            'max_period': forms.NumberInput(attrs={'class': tw}),
            'period_unit': forms.Select(attrs={'class': tw}),
            'interest_rate': forms.NumberInput(attrs={'class': tw, 'step': '0.01'}),
            'penal_rate': forms.NumberInput(attrs={'class': tw, 'step': '0.01'}),
            'senior_citizen_extra': forms.NumberInput(attrs={'class': tw, 'step': '0.01'}),
            'widow_extra': forms.NumberInput(attrs={'class': tw, 'step': '0.01'}),
            'ex_military_extra': forms.NumberInput(attrs={'class': tw, 'step': '0.01'}),
            'disabled_extra': forms.NumberInput(attrs={'class': tw, 'step': '0.01'}),
            'employee_extra': forms.NumberInput(attrs={'class': tw, 'step': '0.01'}),
            'director_extra': forms.NumberInput(attrs={'class': tw, 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['account_head'].queryset = ChartOfAccounts.objects.filter(is_active=True)
