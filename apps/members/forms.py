from django import forms
from django.forms import inlineformset_factory

from .models import Member, MemberDocument, MemberNominee


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
            'dob': forms.DateInput(attrs={'type': 'date'}),
            'join_date': forms.DateInput(attrs={'type': 'date'}),
            'exit_date': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
            'guardian_address': forms.Textarea(attrs={'rows': 2}),
        }


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
            'dob': forms.DateInput(attrs={'type': 'date'}),
        }


class MemberDocumentForm(forms.ModelForm):
    class Meta:
        model = MemberDocument
        fields = ['document_type', 'file']


MemberNomineeFormSet = inlineformset_factory(
    Member,
    MemberNominee,
    form=MemberNomineeForm,
    extra=1,
    can_delete=True,
)


class MemberSearchForm(forms.Form):
    q = forms.CharField(required=False, label='Search')
    branch = forms.IntegerField(required=False, widget=forms.HiddenInput)
    status = forms.ChoiceField(
        required=False,
        choices=[('', 'All')] + Member.STATUS_CHOICES,
    )
    category = forms.ChoiceField(
        required=False,
        choices=[('', 'All')] + Member.CATEGORY_CHOICES,
    )
