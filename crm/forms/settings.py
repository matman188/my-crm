from django import forms

from crm.models import SystemSettings


class SystemSettingsForm(forms.ModelForm):
    class Meta:
        model = SystemSettings
        fields = ("company_name", "default_currency")
        labels = {
            "company_name": "Company Name",
            "default_currency": "Default Currency",
        }
