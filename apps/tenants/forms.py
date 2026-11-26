from django import forms

SOCIETY_TYPE_CHOICES = [
    ('credit_cooperative', 'Credit Cooperative Society'),
    ('multistate', 'Multistate Cooperative Society'),
    ('nidhi', 'Nidhi Company'),
    ('thrift', 'Thrift & Credit Society'),
]

STATE_CHOICES = [
    ('', 'Select State'),
    ('Andhra Pradesh', 'Andhra Pradesh'),
    ('Arunachal Pradesh', 'Arunachal Pradesh'),
    ('Assam', 'Assam'),
    ('Bihar', 'Bihar'),
    ('Chhattisgarh', 'Chhattisgarh'),
    ('Goa', 'Goa'),
    ('Gujarat', 'Gujarat'),
    ('Haryana', 'Haryana'),
    ('Himachal Pradesh', 'Himachal Pradesh'),
    ('Jharkhand', 'Jharkhand'),
    ('Karnataka', 'Karnataka'),
    ('Kerala', 'Kerala'),
    ('Madhya Pradesh', 'Madhya Pradesh'),
    ('Maharashtra', 'Maharashtra'),
    ('Manipur', 'Manipur'),
    ('Meghalaya', 'Meghalaya'),
    ('Mizoram', 'Mizoram'),
    ('Nagaland', 'Nagaland'),
    ('Odisha', 'Odisha'),
    ('Punjab', 'Punjab'),
    ('Rajasthan', 'Rajasthan'),
    ('Sikkim', 'Sikkim'),
    ('Tamil Nadu', 'Tamil Nadu'),
    ('Telangana', 'Telangana'),
    ('Tripura', 'Tripura'),
    ('Uttar Pradesh', 'Uttar Pradesh'),
    ('Uttarakhand', 'Uttarakhand'),
    ('West Bengal', 'West Bengal'),
    ('Andaman and Nicobar Islands', 'Andaman and Nicobar Islands'),
    ('Chandigarh', 'Chandigarh'),
    ('Dadra and Nagar Haveli and Daman and Diu', 'Dadra and Nagar Haveli and Daman and Diu'),
    ('Delhi', 'Delhi'),
    ('Jammu and Kashmir', 'Jammu and Kashmir'),
    ('Ladakh', 'Ladakh'),
    ('Lakshadweep', 'Lakshadweep'),
    ('Puducherry', 'Puducherry'),
]

INPUT_CLASS = (
    'w-full px-4 py-2.5 border border-gray-300 rounded-lg text-sm '
    'focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 '
    'transition text-gray-900'
)
SELECT_CLASS = INPUT_CLASS


class SocietySignupForm(forms.Form):
    society_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(
            attrs={
                'class': INPUT_CLASS,
                'placeholder': 'e.g., Shri Ganesh Credit Cooperative Society',
            }
        ),
        label='Society Name',
    )
    society_type = forms.ChoiceField(
        choices=SOCIETY_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
        label='Society Type',
    )
    registration_no = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(
            attrs={
                'class': INPUT_CLASS,
                'placeholder': 'Registration number (optional for trial)',
            }
        ),
        label='Registration Number',
    )

    address = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.TextInput(
            attrs={
                'class': INPUT_CLASS,
                'placeholder': 'Head office address',
            }
        ),
        label='Address',
    )
    city = forms.CharField(
        max_length=100,
        widget=forms.TextInput(
            attrs={
                'class': INPUT_CLASS,
                'placeholder': 'City',
            }
        ),
    )
    state = forms.ChoiceField(
        choices=STATE_CHOICES,
        widget=forms.Select(attrs={'class': SELECT_CLASS}),
    )
    pincode = forms.CharField(
        max_length=6,
        widget=forms.TextInput(
            attrs={
                'class': INPUT_CLASS,
                'placeholder': '411001',
                'pattern': '[0-9]{6}',
                'maxlength': '6',
            }
        ),
    )
    phone = forms.CharField(
        max_length=15,
        widget=forms.TextInput(
            attrs={
                'class': INPUT_CLASS,
                'placeholder': '9876543210',
            }
        ),
        label='Phone Number',
    )
    email = forms.EmailField(
        widget=forms.EmailInput(
            attrs={
                'class': INPUT_CLASS,
                'placeholder': 'admin@yoursociety.com',
            }
        ),
    )

    admin_name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(
            attrs={
                'class': INPUT_CLASS,
                'placeholder': 'Your full name',
            }
        ),
        label='Your Name',
    )
    admin_username = forms.CharField(
        max_length=50,
        widget=forms.TextInput(
            attrs={
                'class': INPUT_CLASS,
                'placeholder': 'Choose a username',
            }
        ),
        label='Username',
    )
    password = forms.CharField(
        min_length=8,
        widget=forms.PasswordInput(
            attrs={
                'class': INPUT_CLASS,
                'placeholder': 'Minimum 8 characters',
            }
        ),
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(
            attrs={
                'class': INPUT_CLASS,
                'placeholder': 'Confirm password',
            }
        ),
    )

    pan_no = forms.CharField(
        max_length=10,
        required=False,
        widget=forms.TextInput(
            attrs={
                'class': INPUT_CLASS,
                'placeholder': 'ABCDE1234F',
                'maxlength': '10',
            }
        ),
        label='PAN Number',
    )
    tan_no = forms.CharField(
        max_length=10,
        required=False,
        widget=forms.TextInput(
            attrs={
                'class': INPUT_CLASS,
                'placeholder': 'ABCD12345E',
                'maxlength': '10',
            }
        ),
        label='TAN Number',
    )
    gst_no = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(
            attrs={
                'class': INPUT_CLASS,
                'placeholder': '22ABCDE1234F1Z5',
                'maxlength': '15',
            }
        ),
        label='GST Number',
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm = cleaned_data.get('confirm_password')
        if password and confirm and password != confirm:
            raise forms.ValidationError('Passwords do not match.')
        return cleaned_data


_tw = 'w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500'
_tw_select = _tw
_tw_date = _tw
_tw_textarea = _tw


class SocietyEditForm(forms.ModelForm):
    class Meta:
        from .models import Society

        model = Society
        fields = [
            'name',
            'name_regional',
            'society_type',
            'registration_no',
            'registration_date',
            'registration_authority',
            'society_category',
            'address',
            'city',
            'state',
            'pincode',
            'phone',
            'fax',
            'email',
            'pan_no',
            'pan_doc',
            'tan_no',
            'tan_doc',
            'gst_no',
            'gst_doc',
            'authorized_capital',
            'paid_up_capital',
            'share_nominal_value',
            'logo',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': _tw}),
            'name_regional': forms.TextInput(attrs={'class': _tw, 'placeholder': 'Name in regional language'}),
            'society_type': forms.Select(attrs={'class': _tw_select}),
            'registration_no': forms.TextInput(attrs={'class': _tw}),
            'registration_date': forms.DateInput(attrs={'class': _tw_date, 'type': 'date'}),
            'registration_authority': forms.TextInput(attrs={'class': _tw}),
            'society_category': forms.TextInput(attrs={'class': _tw}),
            'address': forms.Textarea(attrs={'class': _tw_textarea, 'rows': 3}),
            'city': forms.TextInput(attrs={'class': _tw}),
            'state': forms.TextInput(attrs={'class': _tw}),
            'pincode': forms.TextInput(attrs={'class': _tw, 'maxlength': '10'}),
            'phone': forms.TextInput(attrs={'class': _tw}),
            'fax': forms.TextInput(attrs={'class': _tw}),
            'email': forms.EmailInput(attrs={'class': _tw}),
            'pan_no': forms.TextInput(attrs={'class': _tw, 'maxlength': '10'}),
            'pan_doc': forms.ClearableFileInput(attrs={'class': _tw}),
            'tan_no': forms.TextInput(attrs={'class': _tw, 'maxlength': '10'}),
            'tan_doc': forms.ClearableFileInput(attrs={'class': _tw}),
            'gst_no': forms.TextInput(attrs={'class': _tw, 'maxlength': '15'}),
            'gst_doc': forms.ClearableFileInput(attrs={'class': _tw}),
            'authorized_capital': forms.NumberInput(attrs={'class': _tw}),
            'paid_up_capital': forms.NumberInput(attrs={'class': _tw}),
            'share_nominal_value': forms.NumberInput(attrs={'class': _tw}),
            'logo': forms.ClearableFileInput(attrs={'class': _tw}),
        }
