from django import forms

from crm.models import Product, ProductCategory, Service, SystemSettings


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
