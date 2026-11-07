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
    ('Bihar', 'Bihar'),
    ('Chhattisgarh', 'Chhattisgarh'),
    ('Delhi', 'Delhi'),
    ('Goa', 'Goa'),
    ('Gujarat', 'Gujarat'),
    ('Haryana', 'Haryana'),
    ('Himachal Pradesh', 'Himachal Pradesh'),
    ('Jharkhand', 'Jharkhand'),
    ('Karnataka', 'Karnataka'),
    ('Kerala', 'Kerala'),
    ('Madhya Pradesh', 'Madhya Pradesh'),
    ('Maharashtra', 'Maharashtra'),
    ('Odisha', 'Odisha'),
    ('Punjab', 'Punjab'),
    ('Rajasthan', 'Rajasthan'),
    ('Tamil Nadu', 'Tamil Nadu'),
    ('Telangana', 'Telangana'),
    ('Uttar Pradesh', 'Uttar Pradesh'),
    ('Uttarakhand', 'Uttarakhand'),
    ('West Bengal', 'West Bengal'),
]

INPUT_CLASS = (
    'w-full px-4 py-3 border border-gray-300 rounded-lg '
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

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm = cleaned_data.get('confirm_password')
        if password and confirm and password != confirm:
            raise forms.ValidationError('Passwords do not match.')
        return cleaned_data
