from django import forms

tw = 'w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500'


class FDCreateForm(forms.Form):
    member = forms.IntegerField(widget=forms.HiddenInput())
    amount = forms.DecimalField(
        max_digits=15, decimal_places=2, widget=forms.NumberInput(attrs={'class': tw, 'step': '0.01'})
    )
    tenure_days = forms.IntegerField(widget=forms.NumberInput(attrs={'class': tw}))
    compounding = forms.ChoiceField(
        choices=[
            ('quarterly', 'Quarterly'),
            ('half_yearly', 'Half Yearly'),
            ('yearly', 'Yearly'),
            ('cumulative', 'Cumulative'),
        ],
        initial='quarterly',
        widget=forms.Select(attrs={'class': 'w-full rounded-lg border-gray-300 px-3 py-2'}),
    )
    is_auto_renew = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'rounded'}))
    linked_savings_account = forms.IntegerField(required=False, widget=forms.Select(attrs={'class': tw}))
    is_senior = forms.BooleanField(
        required=False, label='Senior Citizen', widget=forms.CheckboxInput(attrs={'class': 'rounded'})
    )

    def clean_member(self):
        from apps.members.models import Member

        return Member.objects.get(pk=self.cleaned_data['member'])

    def clean_linked_savings_account(self):
        val = self.cleaned_data.get('linked_savings_account')
        if val:
            from apps.savings.models import SavingsAccount

            return SavingsAccount.objects.get(pk=val)
        return None


class RDCreateForm(forms.Form):
    member = forms.IntegerField(widget=forms.HiddenInput())
    monthly_installment = forms.DecimalField(
        max_digits=15, decimal_places=2, widget=forms.NumberInput(attrs={'class': tw, 'step': '0.01'})
    )
    tenure_months = forms.IntegerField(widget=forms.NumberInput(attrs={'class': tw}))
    interest_rate = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={
                'class': 'w-full rounded-lg border-gray-300 px-3 py-2 bg-gray-50 cursor-not-allowed',
                'step': '0.01',
                'readonly': True,
                'tabindex': '-1',
            }
        ),
    )
    linked_savings_account = forms.IntegerField(required=False, widget=forms.Select(attrs={'class': tw}))

    def clean_member(self):
        from apps.members.models import Member

        return Member.objects.get(pk=self.cleaned_data['member'])

    def clean_linked_savings_account(self):
        val = self.cleaned_data.get('linked_savings_account')
        if val:
            from apps.savings.models import SavingsAccount

            return SavingsAccount.objects.get(pk=val)
        return None
