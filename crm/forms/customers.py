from django import forms

from crm.models import Customer


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = (
            "first_name",
            "last_name",
            "email",
            "primary_phone",
            "secondary_phone",
            "company",
            "notes",
        )
        labels = {
            "primary_phone": "Primary phone",
            "secondary_phone": "Secondary phone",
        }
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 5}),
        }
