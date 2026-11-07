from django import forms

tw = 'w-full rounded border-gray-300'


class FDCreateForm(forms.Form):
    member = forms.IntegerField(widget=forms.HiddenInput())
    product = forms.IntegerField(widget=forms.HiddenInput())
    amount = forms.DecimalField(
        max_digits=15, decimal_places=2, widget=forms.NumberInput(attrs={'class': tw, 'step': '0.01'})
    )
    tenure_days = forms.IntegerField(widget=forms.NumberInput(attrs={'class': tw}))
    is_auto_renew = forms.BooleanField(required=False, widget=forms.CheckboxInput(attrs={'class': 'rounded'}))
    linked_savings_account = forms.IntegerField(required=False, widget=forms.Select(attrs={'class': tw}))
    is_senior = forms.BooleanField(
        required=False, label='Senior Citizen', widget=forms.CheckboxInput(attrs={'class': 'rounded'})
    )

    def clean_member(self):
        from apps.members.models import Member

        return Member.objects.get(pk=self.cleaned_data['member'])

    def clean_product(self):
        from apps.deposits.models import FDProduct

        return FDProduct.objects.get(pk=self.cleaned_data['product'])

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
        max_digits=5, decimal_places=2, widget=forms.NumberInput(attrs={'class': tw, 'step': '0.01'})
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


class RDInstallmentCollectionForm(forms.Form):
    rd_id = forms.IntegerField(widget=forms.HiddenInput())
    amount = forms.DecimalField(
        max_digits=15, decimal_places=2, widget=forms.NumberInput(attrs={'class': tw, 'step': '0.01'})
    )
