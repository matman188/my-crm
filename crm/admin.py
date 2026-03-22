from django.contrib import admin

from crm.models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("first_name", "last_name", "company", "email", "primary_phone", "secondary_phone", "owner")
    search_fields = ("first_name", "last_name", "company", "email", "primary_phone", "secondary_phone")
