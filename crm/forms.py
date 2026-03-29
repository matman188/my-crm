from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm, UserCreationForm

from crm.access import get_access_level
from crm.models import Customer, Product, ProductCategory, Service, SystemSettings
from crm.roles import (
    ACCESS_LEVEL_ADMIN,
    ACCESS_LEVEL_SYSTEM_ADMIN,
    ACCESS_LEVEL_USER,
    assign_access_level,
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

    class Meta(UserCreationForm.Meta): # type: ignore[attr-defined]
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


class SystemSettingsForm(forms.ModelForm):
    class Meta:
        model = SystemSettings
        fields = ("company_name", "default_currency")
        labels = {
            "company_name": "Company Name",
            "default_currency": "Default Currency",
        }


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


class ProductCategoryForm(forms.ModelForm):
    class Meta:
        model = ProductCategory
        fields = ("name", "description")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }


class ProductForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = ProductCategory.objects.order_by("name")
        self.fields["category"].empty_label = "No category"

    class Meta:
        model = Product
        fields = ("name", "category", "description")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }


class ServiceForm(forms.ModelForm):
    products = forms.ModelMultipleChoiceField(
        queryset=Product.objects.none(),
        required=False,
        help_text="Optional. Leave all unchecked if this service is not tied to a product yet.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        product_queryset = Product.objects.select_related("category").all()
        self.fields["products"].queryset = product_queryset.order_by("name", "id")
        self.product_groups = self._build_product_groups(product_queryset)
        currency_code = SystemSettings.get_solo().default_currency
        self.fields["price"].label = f"Price ({currency_code})"

    def _build_product_groups(self, product_queryset):
        selected_product_ids = self._get_selected_product_ids()
        groups = []
        grouped_products = {}

        sorted_products = sorted(
            product_queryset,
            key=lambda product: (
                product.category is None,
                (product.category.name.lower() if product.category else ""),
                product.name.lower(),
                product.id,
            ),
        )

        for product in sorted_products:
            category_name = product.category.name if product.category else "No category"
            grouped_products.setdefault(category_name, []).append(
                {
                    "id_for_label": f"id_products_{product.id}",
                    "value": str(product.id),
                    "label": product.name,
                    "checked": str(product.id) in selected_product_ids,
                }
            )

        for index, (group_name, products) in enumerate(grouped_products.items()):
            groups.append(
                {
                    "name": group_name,
                    "products": products,
                    "count": len(products),
                    "is_open": any(product["checked"] for product in products) or index == 0,
                }
            )

        return groups

    def _get_selected_product_ids(self):
        field_name = self.add_prefix("products")

        if self.is_bound:
            return set(self.data.getlist(field_name))

        if self.instance.pk:
            return {str(product_id) for product_id in self.instance.products.values_list("id", flat=True)}

        initial_products = self.initial.get("products", [])
        return {str(product_id) for product_id in initial_products}

    class Meta:
        model = Service
        fields = ("name", "price", "products", "description")
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
        }
