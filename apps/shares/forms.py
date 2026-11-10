from django import forms

from apps.members.models import Member

_tw = 'w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-primary-500 focus:ring-primary-500'


class SharePurchaseForm(forms.Form):
    member = forms.ModelChoiceField(
        queryset=Member.objects.filter(status='active'),
        widget=forms.Select(attrs={'class': 'searchable ' + _tw}),
    )
    share_count = forms.IntegerField(min_value=1, widget=forms.NumberInput(attrs={'class': _tw}))


class ShareTransferForm(forms.Form):
    from_member = forms.ModelChoiceField(
        queryset=Member.objects.filter(status='active'),
        label='From Member',
        widget=forms.Select(attrs={'class': 'searchable ' + _tw}),
    )
    to_member = forms.ModelChoiceField(
        queryset=Member.objects.filter(status='active'),
        label='To Member',
        widget=forms.Select(attrs={'class': 'searchable ' + _tw}),
    )
    share_count = forms.IntegerField(min_value=1, widget=forms.NumberInput(attrs={'class': _tw}))

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('from_member') == cleaned.get('to_member'):
            raise forms.ValidationError('Cannot transfer shares to the same member.')
        return cleaned


class ShareSurrenderForm(forms.Form):
    member = forms.ModelChoiceField(
        queryset=Member.objects.filter(status='active'),
        widget=forms.Select(attrs={'class': 'searchable ' + _tw}),
    )
    share_count = forms.IntegerField(min_value=1, widget=forms.NumberInput(attrs={'class': _tw}))
