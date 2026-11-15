from django import forms
from django.db.models.functions import Lower, Trim

from crm.models import Customer


class CustomerForm(forms.ModelForm):
    mark_required_fields = True
    duplicate_email_message = "A customer with this email already exists."

    def save(self, commit=True):
        customer = super().save(commit=False)
        if commit:
            fields = [*self.Meta.fields, "updated_at"] if customer.pk else None
            customer.save(update_fields=fields)
            self.save_m2m()
        return customer

    def _email_in_use(self, email):
        return (
            Customer.objects.annotate(normalized_email=Lower(Trim("email")))
            .filter(normalized_email=email.strip().lower())
            .exclude(pk=self.instance.pk)
            .exists()
        )

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if self._email_in_use(email):
            raise forms.ValidationError(self.duplicate_email_message)
        return email

    def add_duplicate_email_error(self):
        """Handle a concurrent customer save after form validation succeeded."""
        email = self.cleaned_data.get("email")
        if email and self._email_in_use(email):
            self.add_error("email", self.duplicate_email_message)
            return True
        return False

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
