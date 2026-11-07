from datetime import date

from django import forms

tw = 'w-full rounded border-gray-300'


class DayEndForm(forms.Form):
    processing_date = forms.DateField(
        initial=date.today,
        widget=forms.DateInput(attrs={'class': tw, 'type': 'date'}),
    )


class FinancialYearForm(forms.Form):
    fy_code = forms.CharField(max_length=10, widget=forms.TextInput(attrs={'class': tw, 'placeholder': '2026-27'}))
    start_date = forms.DateField(widget=forms.DateInput(attrs={'class': tw, 'type': 'date'}))
    end_date = forms.DateField(widget=forms.DateInput(attrs={'class': tw, 'type': 'date'}))
