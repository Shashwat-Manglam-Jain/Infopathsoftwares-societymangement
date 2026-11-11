from django import forms

from apps.agents.models import Agent, PigmmyAccount
from apps.members.models import Member
from apps.savings.models import SavingsAccount

tw = 'w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500'


class AgentForm(forms.ModelForm):
    class Meta:
        model = Agent
        fields = [
            'member',
            'savings_account',
            'security_deposit_account',
            'commission_rate',
            'phone',
            'area',
        ]
        widgets = {
            'member': forms.Select(attrs={'class': 'searchable ' + tw}),
            'savings_account': forms.Select(attrs={'class': 'searchable ' + tw}),
            'security_deposit_account': forms.Select(attrs={'class': 'searchable ' + tw}),
            'commission_rate': forms.NumberInput(attrs={'class': tw, 'step': '0.01'}),
            'phone': forms.TextInput(attrs={'class': tw}),
            'area': forms.TextInput(attrs={'class': tw}),
        }

    def __init__(self, *args, **kwargs):
        self._branch = kwargs.pop('branch', None)
        super().__init__(*args, **kwargs)
        qs_filter = {'status': 'active'}
        if self._branch:
            qs_filter['branch'] = self._branch
        members_with_savings = SavingsAccount.objects.filter(
            status='active',
            account_type='savings',
        ).values_list('member_id', flat=True)
        self.fields['member'].queryset = Member.objects.filter(
            **qs_filter,
            id__in=members_with_savings,
        )
        savings_filter = {'status': 'active', 'account_type': 'savings'}
        security_filter = {'status': 'active', 'account_type': 'security'}
        if self._branch:
            savings_filter['branch'] = self._branch
            security_filter['branch'] = self._branch
        self.fields['savings_account'].queryset = SavingsAccount.objects.filter(**savings_filter)
        self.fields['security_deposit_account'].queryset = SavingsAccount.objects.filter(**security_filter)
        self.fields['security_deposit_account'].required = False

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self._branch:
            instance.branch = self._branch
        if commit:
            instance.save()
        return instance


class PigmmyAccountForm(forms.Form):
    member = forms.ModelChoiceField(
        queryset=Member.objects.none(),
        widget=forms.Select(attrs={'class': 'searchable ' + tw}),
    )
    agent = forms.ModelChoiceField(
        queryset=Agent.objects.none(),
        widget=forms.Select(attrs={'class': 'searchable ' + tw}),
    )
    deposit_type = forms.ChoiceField(
        choices=PigmmyAccount.DEPOSIT_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': tw}),
    )
    installment_amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': tw, 'step': '0.01'}),
    )
    deposit_period_months = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': tw}),
    )
    interest_rate = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={
                'class': tw + ' bg-gray-50 cursor-not-allowed',
                'step': '0.01',
                'readonly': True,
                'tabindex': '-1',
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        branch = kwargs.pop('branch', None)
        super().__init__(*args, **kwargs)
        member_qs = Member.objects.filter(status='active')
        agent_qs = Agent.objects.filter(status='active')
        if branch:
            member_qs = member_qs.filter(branch=branch)
            agent_qs = agent_qs.filter(branch=branch)
        self.fields['member'].queryset = member_qs
        self.fields['agent'].queryset = agent_qs


class CollectionForm(forms.Form):
    agent = forms.ModelChoiceField(
        queryset=Agent.objects.none(),
        widget=forms.Select(attrs={'class': 'searchable ' + tw, 'id': 'id_agent'}),
    )
    collection_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': tw, 'type': 'date'}),
    )
    agent_collection_amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': tw, 'step': '0.01', 'placeholder': 'Agent declared amount'}),
    )

    def __init__(self, *args, **kwargs):
        branch = kwargs.pop('branch', None)
        super().__init__(*args, **kwargs)
        agent_qs = Agent.objects.filter(status='active')
        if branch:
            agent_qs = agent_qs.filter(branch=branch)
        self.fields['agent'].queryset = agent_qs
