from django import forms
from django.forms import inlineformset_factory

from apps.loans.models import LoanAccount, LoanCollateral, LoanGuarantor, LoanProduct

tw = 'w-full rounded border-gray-300'


class LoanProductForm(forms.ModelForm):
    class Meta:
        model = LoanProduct
        fields = [
            'name',
            'interest_rate',
            'max_amount',
            'max_tenure_months',
            'interest_type',
            'loan_category',
            'mortgage_type',
            'allow_multiple',
            'requires_guarantor',
            'min_guarantors',
            'max_guarantors',
            'guarantor_must_be_shareholder',
            'requires_director_recommendation',
            'requires_collateral',
            'max_loan_to_deposit_ratio',
            'processing_fee_percent',
            'penal_interest_rate',
            'npa_days_threshold',
            'is_active',
        ]
        widgets = {
            'interest_type': forms.Select(attrs={'class': tw}),
            'loan_category': forms.Select(attrs={'class': tw}),
            'mortgage_type': forms.Select(attrs={'class': tw}),
        }


class LoanApplicationForm(forms.ModelForm):
    class Meta:
        model = LoanAccount
        fields = ['member', 'loan_product', 'applied_amount', 'tenure_months', 'director_recommendation', 'remarks']
        widgets = {
            'member': forms.Select(attrs={'class': tw}),
            'loan_product': forms.Select(attrs={'class': tw}),
            'applied_amount': forms.NumberInput(attrs={'class': tw, 'step': '0.01'}),
            'tenure_months': forms.NumberInput(attrs={'class': tw}),
            'director_recommendation': forms.Select(attrs={'class': tw}),
            'remarks': forms.Textarea(attrs={'class': tw, 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.members.models import Member
        from apps.shares.models import ShareHolding

        director_ids = Member.objects.filter(
            is_director=True, status='active',
        ).values_list('id', flat=True)
        shareholder_ids = ShareHolding.objects.filter(
            status='active', share_count__gt=0,
            member_id__in=director_ids,
        ).values_list('member_id', flat=True).distinct()
        self.fields['director_recommendation'].queryset = Member.objects.filter(
            id__in=shareholder_ids,
        )
        self.fields['director_recommendation'].required = False

    def clean_director_recommendation(self):
        director = self.cleaned_data.get('director_recommendation')
        loan_product = self.cleaned_data.get('loan_product')
        if loan_product and loan_product.requires_director_recommendation and not director:
            raise forms.ValidationError('Director recommendation is required for this loan type.')
        if director and not director.is_director:
            raise forms.ValidationError('Selected member is not a director.')
        return director


class LoanApprovalForm(forms.Form):
    action = forms.ChoiceField(
        choices=[('approve', 'Approve'), ('reject', 'Reject')], widget=forms.Select(attrs={'class': tw})
    )
    approved_amount = forms.DecimalField(
        max_digits=15, decimal_places=2, required=False, widget=forms.NumberInput(attrs={'class': tw, 'step': '0.01'})
    )
    remarks = forms.CharField(required=False, widget=forms.Textarea(attrs={'class': tw, 'rows': 2}))


class EMICollectionForm(forms.Form):
    loan_id = forms.IntegerField(widget=forms.HiddenInput())
    amount = forms.DecimalField(
        max_digits=15, decimal_places=2, min_value=1, widget=forms.NumberInput(attrs={'class': tw, 'step': '0.01'})
    )
    payment_mode = forms.ChoiceField(
        choices=[('cash', 'Cash'), ('cheque', 'Cheque'), ('transfer', 'Transfer'), ('upi', 'UPI')],
        widget=forms.Select(attrs={'class': tw}),
    )


class GuarantorForm(forms.ModelForm):
    class Meta:
        model = LoanGuarantor
        fields = ['guarantor_member', 'guarantee_amount']

    def clean_guarantor_member(self):
        member = self.cleaned_data.get('guarantor_member')
        if member:
            from apps.shares.models import ShareHolding

            has_shares = ShareHolding.objects.filter(
                member=member,
                status='active',
                share_count__gt=0,
            ).exists()
            if not has_shares:
                raise forms.ValidationError(
                    f'{member.name} does not have active shares. Guarantor must be a shareholder.'
                )
        return member


GuarantorFormSet = inlineformset_factory(
    LoanAccount,
    LoanGuarantor,
    form=GuarantorForm,
    fields=['guarantor_member', 'guarantee_amount'],
    extra=2,
    can_delete=True,
)

CollateralFormSet = inlineformset_factory(
    LoanAccount,
    LoanCollateral,
    fields=['collateral_type', 'description', 'estimated_value', 'document'],
    extra=1,
    can_delete=True,
)
