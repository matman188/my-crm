from django import forms
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from crm.models import SystemSettings


class SystemSettingsForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.is_bound and "business_timezone" not in self.data:
            self.data = self.data.copy()
            self.data["business_timezone"] = (
                self.instance.business_timezone or "Africa/Johannesburg"
            )

    business_timezone = forms.CharField(
        initial="Africa/Johannesburg",
        help_text="Used for due-today and overdue work. For example: Africa/Johannesburg, Europe/London, or America/New_York.",
    )

    def clean_business_timezone(self):
        value = self.cleaned_data["business_timezone"]
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError):
            raise forms.ValidationError(
                "Enter a valid timezone, for example Africa/Johannesburg."
            )
        return value

    class Meta:
        model = SystemSettings
        fields = ("company_name", "default_currency", "business_timezone")
        labels = {
            "company_name": "Company Name",
            "default_currency": "Default Currency",
        }
