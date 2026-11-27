from decimal import Decimal

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
            'phone',
            'area',
            'joining_date',
            'security_deposit_amount',
            'security_document',
            'status',
        ]
        widgets = {
            'member': forms.Select(attrs={'class': 'searchable ' + tw}),
            'phone': forms.TextInput(attrs={'class': tw}),
            'area': forms.TextInput(attrs={'class': tw}),
            'joining_date': forms.DateInput(attrs={'class': tw, 'type': 'date'}),
            'security_deposit_amount': forms.NumberInput(attrs={'class': tw, 'step': '0.01', 'min': '0'}),
            'security_document': forms.ClearableFileInput(attrs={'class': tw}),
            'status': forms.Select(attrs={'class': tw}),
        }

    def __init__(self, *args, **kwargs):
        self._branch = kwargs.pop('branch', None)
        super().__init__(*args, **kwargs)
        branch_filter = {'branch': self._branch} if self._branch else {}
        members_with_savings = set(
            SavingsAccount.objects.filter(status='active', account_type='savings', **branch_filter)
            .values_list('member_id', flat=True)
        )
        members_with_security = set(
            SavingsAccount.objects.filter(status='active', account_type='security', **branch_filter)
            .values_list('member_id', flat=True)
        )
        eligible_ids = members_with_savings & members_with_security
        self.fields['member'].queryset = Member.objects.filter(
            status='active', id__in=eligible_ids, **branch_filter,
        )
        self.fields['joining_date'].required = True
        self.fields['security_deposit_amount'].required = False
        self.fields['security_document'].required = False

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
        min_value=Decimal('1'),
        widget=forms.NumberInput(attrs={'class': tw, 'step': '0.01', 'min': '1'}),
    )
    deposit_period_months = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': tw, 'min': '1', 'max': '999'}),
    )
    interest_rate = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={
                'class': tw + ' bg-gray-50 cursor-not-allowed',
                'step': '0.01',
                'min': '0',
                'max': '100',
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


class PigmmyEditForm(forms.ModelForm):
    class Meta:
        model = PigmmyAccount
        fields = ['agent', 'installment_amount', 'deposit_type', 'interest_rate', 'deposit_period_months']
        widgets = {
            'agent': forms.Select(attrs={'class': 'searchable ' + tw}),
            'installment_amount': forms.NumberInput(attrs={'class': tw, 'step': '0.01', 'min': '1'}),
            'deposit_type': forms.Select(attrs={'class': tw}),
            'interest_rate': forms.NumberInput(attrs={'class': tw, 'step': '0.01', 'min': '0', 'max': '100'}),
            'deposit_period_months': forms.NumberInput(attrs={'class': tw, 'min': '1', 'max': '999'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.branch:
            self.fields['agent'].queryset = Agent.objects.filter(status='active', branch=self.instance.branch)
        else:
            self.fields['agent'].queryset = Agent.objects.filter(status='active')


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
