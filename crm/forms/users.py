from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm, UserCreationForm

from crm.authz import (
    ACCESS_LEVEL_ADMIN,
    ACCESS_LEVEL_SYSTEM_ADMIN,
    ACCESS_LEVEL_USER,
    assign_access_level,
    get_access_level,
)


ACCESS_LEVEL_CHOICES = (
    (ACCESS_LEVEL_USER, "User"),
    (ACCESS_LEVEL_ADMIN, "Admin"),
    (ACCESS_LEVEL_SYSTEM_ADMIN, "System Admin"),
)


ACCESS_LEVEL_HELP_TEXT = (
    "User: standard CRM access. "
    "Admin: can open Configuration and System Settings in the CRM. "
    "System Admin: includes Admin access and can sign in to Django admin at /admin/."
)


class SystemUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    access_level = forms.ChoiceField(
        choices=ACCESS_LEVEL_CHOICES,
        initial=ACCESS_LEVEL_USER,
        label="Access Level",
        help_text=ACCESS_LEVEL_HELP_TEXT,
    )

    class Meta(UserCreationForm.Meta):  # type: ignore[attr-defined]
        model = get_user_model()
        fields = ("username", "email", "first_name", "last_name")

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop("current_user", None)
        super().__init__(*args, **kwargs)
        self.fields["access_level"].choices = self._get_access_level_choices()

    def _get_access_level_choices(self):
        choices = [
            (ACCESS_LEVEL_USER, "User"),
            (ACCESS_LEVEL_ADMIN, "Admin"),
        ]
        if self.current_user and self.current_user.is_staff:
            choices.append((ACCESS_LEVEL_SYSTEM_ADMIN, "System Admin"))
        return choices

    def _apply_access_level(self, user):
        access_level = self.cleaned_data["access_level"]
        assign_access_level(user, access_level)

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        user.first_name = self.cleaned_data.get("first_name", "")
        user.last_name = self.cleaned_data.get("last_name", "")
        if commit:
            user.save()
            self._apply_access_level(user)
        return user


class SystemUserUpdateForm(forms.ModelForm):
    access_level = forms.ChoiceField(
        choices=ACCESS_LEVEL_CHOICES,
        label="Access Level",
        help_text=ACCESS_LEVEL_HELP_TEXT,
    )

    class Meta:
        model = get_user_model()
        fields = ("username", "email", "first_name", "last_name", "is_active")
        labels = {
            "is_active": "Account is active",
        }

    def __init__(self, *args, **kwargs):
        self.current_user = kwargs.pop("current_user", None)
        super().__init__(*args, **kwargs)
        self.fields["access_level"].choices = self._get_access_level_choices()
        self.initial["access_level"] = get_access_level(self.instance)
        if self.instance and self.instance.is_superuser:
            self.fields.pop("access_level", None)
            self.fields.pop("is_active", None)

    def _get_access_level_choices(self):
        choices = [
            (ACCESS_LEVEL_USER, "User"),
            (ACCESS_LEVEL_ADMIN, "Admin"),
        ]
        if self.current_user and self.current_user.is_staff:
            choices.append((ACCESS_LEVEL_SYSTEM_ADMIN, "System Admin"))
        return choices

    def _apply_access_level(self, user):
        if user.is_superuser or "access_level" not in self.cleaned_data:
            return
        access_level = self.cleaned_data["access_level"]
        assign_access_level(user, access_level)

    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            self._apply_access_level(user)
        return user


class SystemUserPasswordChangeForm(SetPasswordForm):
    pass


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = get_user_model()
        fields = ("username", "email", "first_name", "last_name")
