from django import forms

from apps.agents.models import Agent, PigmmyAccount
from apps.members.models import Member
from apps.savings.models import SavingsAccount

tw = 'w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500'


class AgentForm(forms.ModelForm):
    class Meta:
        model = Agent
        fields = [
            'member', 'branch', 'savings_account', 'security_deposit_account',
            'commission_rate', 'phone', 'area',
        ]
        widgets = {
            'member': forms.Select(attrs={'class': tw}),
            'branch': forms.Select(attrs={'class': tw}),
            'savings_account': forms.Select(attrs={'class': tw}),
            'security_deposit_account': forms.Select(attrs={'class': tw}),
            'commission_rate': forms.NumberInput(attrs={'class': tw, 'step': '0.01'}),
            'phone': forms.TextInput(attrs={'class': tw}),
            'area': forms.TextInput(attrs={'class': tw}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['member'].queryset = Member.objects.filter(status='active')
        self.fields['savings_account'].queryset = SavingsAccount.objects.filter(
            status='active', account_type='savings',
        )
        self.fields['security_deposit_account'].queryset = SavingsAccount.objects.filter(
            status='active', account_type='security',
        )
        self.fields['security_deposit_account'].required = False


class PigmmyAccountForm(forms.Form):
    member = forms.ModelChoiceField(
        queryset=Member.objects.filter(status='active'),
        widget=forms.Select(attrs={'class': tw}),
    )
    agent = forms.ModelChoiceField(
        queryset=Agent.objects.filter(status='active'),
        widget=forms.Select(attrs={'class': tw}),
    )
    deposit_type = forms.ChoiceField(
        choices=PigmmyAccount.DEPOSIT_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': tw}),
    )
    installment_amount = forms.DecimalField(
        max_digits=15, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': tw, 'step': '0.01'}),
    )
    deposit_period_months = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': tw}),
    )
    interest_rate = forms.DecimalField(
        max_digits=5, decimal_places=2,
        widget=forms.NumberInput(attrs={'class': tw, 'step': '0.01'}),
    )


class CollectionForm(forms.Form):
    agent = forms.ModelChoiceField(
        queryset=Agent.objects.filter(status='active'),
        widget=forms.Select(attrs={'class': tw}),
    )
    collection_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': tw, 'type': 'date'}),
    )
