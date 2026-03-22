from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm, UserCreationForm

from crm.models import Customer


class SystemUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    is_staff = forms.BooleanField(
        required=False,
        initial=True,
        label="Can access admin site",
    )

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("username", "email", "first_name", "last_name", "is_staff")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data.get("first_name", "")
        user.last_name = self.cleaned_data.get("last_name", "")
        user.is_staff = self.cleaned_data.get("is_staff", False)
        if commit:
            user.save()
        return user


class SystemUserUpdateForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ("username", "email", "first_name", "last_name", "is_staff", "is_active")
        labels = {
            "is_staff": "Can access admin site",
            "is_active": "Account is active",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.is_superuser:
            self.fields.pop("is_staff", None)
            self.fields.pop("is_active", None)


class SystemUserPasswordChangeForm(SetPasswordForm):
    pass


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ("username", "email", "first_name", "last_name")


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
