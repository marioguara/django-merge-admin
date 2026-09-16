from django import forms


class MergePartnerForm(forms.Form):
    """Used from the change view: pick another record to merge with."""

    partner = forms.IntegerField(
        label="Altro record da unire",
        widget=forms.HiddenInput(),
    )
    partner_query = forms.CharField(
        label="Cerca",
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "off", "class": "vTextField"}),
    )
