from django import forms
from django.forms import inlineformset_factory

from .models import Member, MemberDocument, MemberNominee

_tw = 'w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500'
_tw_select = _tw
_tw_date = _tw
_tw_textarea = _tw
_tw_checkbox = 'rounded border-gray-300 text-primary-600 focus:ring-primary-500'


class MemberForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = [
            'member_no',
            'branch',
            'prefix',
            'name',
            'name_regional',
            'father_name',
            'mother_name',
            'dob',
            'gender',
            'marital_status',
            'aadhar_no',
            'pan_no',
            'voter_id',
            'phone',
            'alt_phone',
            'email',
            'address',
            'post',
            'area',
            'sub_area',
            'city_village',
            'city',
            'district',
            'tahsil',
            'state',
            'pincode',
            'occupation',
            'monthly_income',
            'education',
            'religion',
            'caste',
            'blood_group',
            'driving_licence_no',
            'join_date',
            'exit_date',
            'status',
            'category',
            'photo',
            'signature',
            'is_director',
            'is_employee',
            'is_minor',
            'is_nominal_member',
            'is_senior_citizen',
            'is_widow',
            'is_physically_disabled',
            'is_ex_military',
            'guardian_name',
            'guardian_address',
            'info',
        ]
        widgets = {
            'member_no': forms.TextInput(attrs={'class': _tw, 'readonly': 'readonly'}),
            'branch': forms.Select(attrs={'class': _tw_select}),
            'prefix': forms.Select(attrs={'class': _tw_select}),
            'name': forms.TextInput(attrs={'class': _tw}),
            'name_regional': forms.TextInput(attrs={'class': _tw}),
            'father_name': forms.TextInput(attrs={'class': _tw}),
            'mother_name': forms.TextInput(attrs={'class': _tw}),
            'dob': forms.DateInput(attrs={'class': _tw_date, 'type': 'date'}),
            'gender': forms.Select(attrs={'class': _tw_select}),
            'marital_status': forms.Select(attrs={'class': _tw_select}),
            'aadhar_no': forms.TextInput(attrs={'class': _tw}),
            'pan_no': forms.TextInput(attrs={'class': _tw}),
            'voter_id': forms.TextInput(attrs={'class': _tw}),
            'phone': forms.TextInput(attrs={'class': _tw}),
            'alt_phone': forms.TextInput(attrs={'class': _tw}),
            'email': forms.EmailInput(attrs={'class': _tw}),
            'address': forms.Textarea(attrs={'class': _tw_textarea, 'rows': 3}),
            'post': forms.TextInput(attrs={'class': _tw}),
            'area': forms.TextInput(attrs={'class': _tw}),
            'sub_area': forms.TextInput(attrs={'class': _tw}),
            'city_village': forms.TextInput(attrs={'class': _tw}),
            'city': forms.TextInput(attrs={'class': _tw}),
            'district': forms.TextInput(attrs={'class': _tw}),
            'tahsil': forms.TextInput(attrs={'class': _tw}),
            'state': forms.TextInput(attrs={'class': _tw}),
            'pincode': forms.TextInput(attrs={'class': _tw}),
            'occupation': forms.TextInput(attrs={'class': _tw}),
            'monthly_income': forms.NumberInput(attrs={'class': _tw, 'step': '0.01'}),
            'education': forms.TextInput(attrs={'class': _tw}),
            'religion': forms.TextInput(attrs={'class': _tw}),
            'caste': forms.TextInput(attrs={'class': _tw}),
            'blood_group': forms.Select(attrs={'class': _tw_select}),
            'driving_licence_no': forms.TextInput(attrs={'class': _tw}),
            'join_date': forms.DateInput(attrs={'class': _tw_date, 'type': 'date'}),
            'exit_date': forms.DateInput(attrs={'class': _tw_date, 'type': 'date'}),
            'status': forms.Select(attrs={'class': _tw_select}),
            'category': forms.Select(attrs={'class': _tw_select}),
            'is_director': forms.CheckboxInput(attrs={'class': _tw_checkbox}),
            'is_employee': forms.CheckboxInput(attrs={'class': _tw_checkbox}),
            'is_minor': forms.CheckboxInput(attrs={'class': _tw_checkbox}),
            'is_nominal_member': forms.CheckboxInput(attrs={'class': _tw_checkbox}),
            'is_senior_citizen': forms.CheckboxInput(attrs={'class': _tw_checkbox}),
            'is_widow': forms.CheckboxInput(attrs={'class': _tw_checkbox}),
            'is_physically_disabled': forms.CheckboxInput(attrs={'class': _tw_checkbox}),
            'is_ex_military': forms.CheckboxInput(attrs={'class': _tw_checkbox}),
            'guardian_name': forms.TextInput(attrs={'class': _tw}),
            'guardian_address': forms.Textarea(attrs={'class': _tw_textarea, 'rows': 2}),
            'info': forms.Textarea(attrs={'class': _tw_textarea, 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        self.current_branch = kwargs.pop('current_branch', None)
        super().__init__(*args, **kwargs)
        if self.current_branch and not self.instance.pk:
            self.fields['branch'].initial = self.current_branch
            self.fields['branch'].widget = forms.HiddenInput()
            self.initial['branch'] = self.current_branch.pk
        if not self.instance.pk:
            self.fields['member_no'].required = False
            self.fields['member_no'].widget = forms.HiddenInput()


class MemberNomineeForm(forms.ModelForm):
    class Meta:
        model = MemberNominee
        fields = [
            'name',
            'relation',
            'dob',
            'aadhar_no',
            'phone',
            'share_percentage',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': _tw}),
            'relation': forms.TextInput(attrs={'class': _tw}),
            'dob': forms.DateInput(attrs={'class': _tw_date, 'type': 'date'}),
            'aadhar_no': forms.TextInput(attrs={'class': _tw}),
            'phone': forms.TextInput(attrs={'class': _tw}),
            'share_percentage': forms.NumberInput(attrs={'class': _tw, 'step': '0.01'}),
        }


class MemberDocumentForm(forms.ModelForm):
    class Meta:
        model = MemberDocument
        fields = ['document_type', 'file']
        widgets = {
            'document_type': forms.Select(attrs={'class': _tw_select}),
        }


MemberNomineeFormSet = inlineformset_factory(
    Member,
    MemberNominee,
    form=MemberNomineeForm,
    extra=1,
    can_delete=True,
)


class MemberSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        label='Search',
        widget=forms.TextInput(attrs={'class': _tw, 'placeholder': 'Search by name, member no, phone...'}),
    )
    branch = forms.IntegerField(required=False, widget=forms.HiddenInput)
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All')] + Member.STATUS_CHOICES,
        widget=forms.Select(attrs={'class': _tw_select}),
    )
    category = forms.ChoiceField(
        required=False,
        choices=[('', 'All')] + Member.CATEGORY_CHOICES,
        widget=forms.Select(attrs={'class': _tw_select}),
    )
