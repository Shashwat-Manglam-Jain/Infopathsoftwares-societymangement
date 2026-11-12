from decimal import Decimal

from django import forms
from django.forms import inlineformset_factory

from apps.loans.models import LoanAccount, LoanCollateral, LoanGuarantor, LoanProduct

tw = 'w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500'


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for _name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs.setdefault(
                    'class', 'rounded border-gray-300 text-primary-600 focus:ring-primary-500'
                )
            elif isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = tw
            else:
                field.widget.attrs['class'] = tw


class LoanApplicationForm(forms.ModelForm):
    class Meta:
        model = LoanAccount
        fields = ['member', 'loan_product', 'applied_amount', 'tenure_months', 'director_recommendation', 'remarks']
        widgets = {
            'member': forms.Select(attrs={'class': 'searchable ' + tw}),
            'loan_product': forms.Select(attrs={'class': tw}),
            'applied_amount': forms.NumberInput(attrs={'class': tw, 'step': '0.01', 'min': '1'}),
            'tenure_months': forms.NumberInput(attrs={'class': tw, 'min': '1'}),
            'director_recommendation': forms.Select(attrs={'class': 'searchable ' + tw}),
            'remarks': forms.Textarea(attrs={'class': tw, 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.members.models import Member
        from apps.shares.models import ShareHolding

        director_ids = Member.objects.filter(
            is_director=True,
            status='active',
        ).values_list('id', flat=True)
        shareholder_ids = (
            ShareHolding.objects.filter(
                status='active',
                share_count__gt=0,
                member_id__in=director_ids,
            )
            .values_list('member_id', flat=True)
            .distinct()
        )
        self.fields['director_recommendation'].queryset = Member.objects.filter(
            id__in=shareholder_ids,
        )
        self.fields['director_recommendation'].required = False

    def clean_applied_amount(self):
        amount = self.cleaned_data.get('applied_amount')
        if amount is not None and amount < 1:
            raise forms.ValidationError('Amount must be at least 1.')
        return amount

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
        max_digits=15, decimal_places=2, min_value=Decimal('1'), required=False,
        widget=forms.NumberInput(attrs={'class': tw, 'step': '0.01'}),
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
        fields = ['guarantor_member', 'guarantee_amount', 'guarantor_share_account']
        widgets = {
            'guarantor_member': forms.Select(attrs={'class': 'searchable ' + tw}),
            'guarantee_amount': forms.NumberInput(attrs={'class': tw, 'step': '0.01', 'min': '0.01'}),
            'guarantor_share_account': forms.TextInput(attrs={'class': tw, 'readonly': 'readonly'}),
        }

    def clean_guarantor_member(self):
        member = self.cleaned_data.get('guarantor_member')
        if member:
            if hasattr(self, '_loan') and self._loan and self._loan.member_id == member.pk:
                raise forms.ValidationError('A member cannot be a guarantor for their own loan.')

            if hasattr(self, '_loan') and self._loan:
                existing = self._loan.guarantors.filter(guarantor_member=member)
                if self.instance and self.instance.pk:
                    existing = existing.exclude(pk=self.instance.pk)
                if existing.exists():
                    raise forms.ValidationError(f'{member.name} is already a guarantor on this loan.')

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
            # Auto-populate share account from active shareholding
            sh = ShareHolding.objects.filter(
                member=member,
                status='active',
            ).first()
            if sh:
                self.cleaned_data['_share_account'] = sh.certificate_no or f'SH-{sh.pk}'

            from apps.loans.services import get_active_guarantee_count

            count = get_active_guarantee_count(member)
            if count >= 3:
                raise forms.ValidationError(
                    f'{member.name} already has {count} active loan guarantees. '
                    f'Maximum 3 active guarantees allowed per member.'
                )
            if count > 0:
                self.cleaned_data['_guarantee_count'] = count
        return member


GuarantorFormSet = inlineformset_factory(
    LoanAccount,
    LoanGuarantor,
    form=GuarantorForm,
    fields=['guarantor_member', 'guarantee_amount'],
    extra=2,
    can_delete=True,
)


class LoanCollateralForm(forms.ModelForm):
    class Meta:
        model = LoanCollateral
        fields = ['collateral_type', 'description', 'estimated_value', 'document', 'status']
        widgets = {
            'collateral_type': forms.Select(attrs={'class': tw}),
            'description': forms.Textarea(attrs={'class': tw, 'rows': 3}),
            'estimated_value': forms.NumberInput(attrs={'class': tw, 'step': '0.01', 'min': '0.01'}),
            'document': forms.ClearableFileInput(attrs={'class': tw}),
            'status': forms.Select(attrs={'class': tw}),
        }
