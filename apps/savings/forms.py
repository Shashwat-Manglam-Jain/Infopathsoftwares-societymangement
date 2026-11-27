from django import forms

from apps.accounting.models import ChartOfAccounts
from apps.savings.models import SavingsAccount

_tw = 'w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500'
_tw_s = 'searchable ' + _tw


def _get_leaf_heads(related_types):
    """Return children of heads with matching related_table_name.
    Falls back to the parent heads themselves if no children exist."""
    parents = ChartOfAccounts.objects.filter(
        related_table_name__in=related_types,
        is_active=True,
    )
    children = ChartOfAccounts.objects.filter(
        parent__in=parents,
        allow_transactions=True,
        is_active=True,
    )
    if children.exists():
        return children.order_by('display_order', 'name')
    return parents.filter(allow_transactions=True).order_by('display_order', 'name')


class SavingsAccountForm(forms.ModelForm):
    class Meta:
        model = SavingsAccount
        fields = [
            'member',
            'branch',
            'gl_head',
            'interest_rate',
            'minimum_balance',
            'interest_posting_frequency',
            'opening_date',
            'introducer',
        ]
        widgets = {
            'member': forms.Select(attrs={'class': _tw_s}),
            'branch': forms.Select(attrs={'class': _tw}),
            'gl_head': forms.Select(attrs={'class': _tw}),
            'interest_rate': forms.NumberInput(
                attrs={
                    'class': _tw + ' bg-gray-50 cursor-not-allowed',
                    'step': '0.01',
                    'min': '0',
                    'max': '100',
                    'readonly': True,
                    'tabindex': '-1',
                }
            ),
            'minimum_balance': forms.NumberInput(attrs={'class': _tw, 'step': '0.01', 'min': '0'}),
            'interest_posting_frequency': forms.Select(attrs={'class': _tw}),
            'opening_date': forms.DateInput(attrs={'class': _tw, 'type': 'date'}),
            'introducer': forms.Select(attrs={'class': _tw_s}),
        }
        labels = {
            'gl_head': 'Account Type',
        }

    def __init__(self, *args, **kwargs):
        self.current_branch = kwargs.pop('current_branch', None)
        super().__init__(*args, **kwargs)
        self.fields['gl_head'].queryset = _get_leaf_heads(SavingsAccount.GL_RELATED_TYPES)
        self.fields['gl_head'].required = True
        self.fields['gl_head'].empty_label = '-- Select Account Type --'
        self.fields['opening_date'].required = True
        self.fields['introducer'].required = False
        self.fields['branch'].empty_label = None
        if self.current_branch:
            self.fields['branch'].initial = self.current_branch
            self.fields['branch'].widget = forms.HiddenInput()
            self.initial['branch'] = self.current_branch.pk

    def clean(self):
        cleaned_data = super().clean()
        member = cleaned_data.get('member')
        gl_head = cleaned_data.get('gl_head')
        if member and gl_head:
            qs = SavingsAccount.objects.filter(
                member=member,
                gl_head=gl_head,
                status='active',
            )
            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise forms.ValidationError(
                    f'Member already has an active {gl_head.name}. Only one per member is allowed.'
                )
        return cleaned_data


class SavingsAccountEditForm(forms.ModelForm):
    class Meta:
        model = SavingsAccount
        fields = ['status', 'interest_rate', 'minimum_balance', 'interest_posting_frequency']
        widgets = {
            'status': forms.Select(attrs={'class': _tw}),
            'interest_rate': forms.NumberInput(
                attrs={
                    'class': _tw + ' bg-gray-50 cursor-not-allowed',
                    'step': '0.01',
                    'min': '0',
                    'max': '100',
                    'readonly': True,
                    'tabindex': '-1',
                }
            ),
            'minimum_balance': forms.NumberInput(attrs={'class': _tw, 'step': '0.01', 'min': '0'}),
            'interest_posting_frequency': forms.Select(attrs={'class': _tw}),
        }

    def clean_status(self):
        status = self.cleaned_data['status']
        if status == 'closed' and self.instance.current_balance != 0:
            raise forms.ValidationError(
                'Account cannot be closed while balance is non-zero. '
                f'Current balance: ₹{self.instance.current_balance:,.2f}'
            )
        return status


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
