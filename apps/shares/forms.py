from django import forms

from apps.members.models import Member


class SharePurchaseForm(forms.Form):
    member = forms.ModelChoiceField(queryset=Member.objects.filter(status='active'))
    share_count = forms.IntegerField(min_value=1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['member'].widget.attrs.update(
            {
                'class': 'w-full px-3 py-2 border border-gray-300 rounded-lg',
            }
        )


class ShareTransferForm(forms.Form):
    from_member = forms.ModelChoiceField(
        queryset=Member.objects.filter(status='active'),
        label='From Member',
    )
    to_member = forms.ModelChoiceField(
        queryset=Member.objects.filter(status='active'),
        label='To Member',
    )
    share_count = forms.IntegerField(min_value=1)

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('from_member') == cleaned.get('to_member'):
            raise forms.ValidationError('Cannot transfer shares to the same member.')
        return cleaned


class ShareSurrenderForm(forms.Form):
    member = forms.ModelChoiceField(queryset=Member.objects.filter(status='active'))
    share_count = forms.IntegerField(min_value=1)
