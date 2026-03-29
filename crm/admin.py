from django.contrib import admin

from crm.models import Customer, Product, ProductCategory, Service


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "company", "email", "primary_phone", "secondary_phone", "owner")
    search_fields = ("first_name", "last_name", "company", "email", "primary_phone", "secondary_phone")


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
    list_display = ("name", "price", "updated_at")
    filter_horizontal = ("products",)
    search_fields = ("name", "description", "products__name")
