from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import SetPasswordForm, UserCreationForm

from crm.models import Customer, Product, ProductCategory, Service


class SystemUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    is_staff = forms.BooleanField(
        required=False,
        initial=True,
        label="Can access admin site",
    )

    class Meta(UserCreationForm.Meta): # type: ignore[attr-defined]
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
