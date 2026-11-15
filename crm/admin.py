from django.contrib import admin

from crm.forms.customers import CustomerForm
from crm.models import Customer, Product, ProductCategory, Service, SystemSettings


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    form = CustomerForm
    list_display = (
        "first_name",
        "last_name",
        "company",
        "email",
        "primary_phone",
        "secondary_phone",
        "is_archived",
    )
    search_fields = (
        "first_name",
        "last_name",
        "company",
        "email",
        "primary_phone",
        "secondary_phone",
    )
    list_filter = ("is_archived",)
    readonly_fields = ("is_archived",)


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "updated_at")
    search_fields = ("name", "description")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "updated_at")
    list_filter = ("category",)
    search_fields = ("name", "description", "category__name")


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "formatted_price", "updated_at")
    filter_horizontal = ("products",)
    search_fields = ("name", "description", "products__name")

    @admin.display(description="price")
    def formatted_price(self, obj):
        return f"{SystemSettings.get_solo().default_currency} {obj.price}"


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ("company_name", "default_currency")

    def has_add_permission(self, request):
        return not SystemSettings.objects.exists()
