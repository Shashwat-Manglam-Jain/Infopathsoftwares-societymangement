from django import forms

from .models import Branch

tw = 'w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500'


class BranchForm(forms.ModelForm):
    class Meta:
        model = Branch
        fields = [
            'branch_code',
            'branch_name',
            'address',
            'address_line_2',
            'city',
            'state',
            'pincode',
            'phone',
            'email',
            'ifsc_code',
            'locker_facility',
            'neft_imps_service',
            'is_head_office',
            'opening_date',
            'status',
            'manager',
        ]
        widgets = {
            'branch_code': forms.TextInput(attrs={'class': tw}),
            'branch_name': forms.TextInput(attrs={'class': tw}),
            'address': forms.Textarea(attrs={'class': tw, 'rows': 3}),
            'address_line_2': forms.TextInput(attrs={'class': tw}),
            'city': forms.TextInput(attrs={'class': tw}),
            'state': forms.TextInput(attrs={'class': tw}),
            'pincode': forms.TextInput(attrs={'class': tw}),
            'phone': forms.TextInput(attrs={'class': tw}),
            'email': forms.EmailInput(attrs={'class': tw}),
            'opening_date': forms.DateInput(attrs={'class': tw, 'type': 'date'}),
            'status': forms.Select(attrs={'class': tw}),
            'manager': forms.Select(attrs={'class': tw}),
            'ifsc_code': forms.TextInput(attrs={'class': tw, 'maxlength': '11'}),
            'locker_facility': forms.CheckboxInput(
                attrs={'class': 'rounded border-gray-300 text-primary-600 focus:ring-primary-500'}
            ),
            'neft_imps_service': forms.CheckboxInput(
                attrs={'class': 'rounded border-gray-300 text-primary-600 focus:ring-primary-500'}
            ),
        }
