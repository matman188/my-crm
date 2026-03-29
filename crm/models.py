from django.contrib.auth import get_user_model
from django.db import models


class SystemSettings(models.Model):
    CURRENCY_ZAR = "ZAR"
    CURRENCY_USD = "USD"
    CURRENCY_EUR = "EUR"
    CURRENCY_CHOICES = (
        (CURRENCY_ZAR, "South African Rand (ZAR)"),
        (CURRENCY_USD, "US Dollar (USD)"),
        (CURRENCY_EUR, "Euro (EUR)"),
    )

    company_name = models.CharField(max_length=150, default="My CRM")
    default_currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default=CURRENCY_ZAR,
    )

    class Meta:
        verbose_name = "system settings"
        verbose_name_plural = "system settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        settings, _ = cls.objects.get_or_create(pk=1)
        return settings

    def __str__(self):
        return "System Settings"


class UserAccess(models.Model):
    user = models.OneToOneField(
        get_user_model(),
        on_delete=models.CASCADE,
        related_name="crm_access",
    )
    can_manage_configuration = models.BooleanField(default=False)

    class Meta:
        verbose_name = "user access"
        verbose_name_plural = "user access"

    @classmethod
    def get_for_user(cls, user):
        access, _ = cls.objects.get_or_create(user=user)
        return access

    def __str__(self):
        return f"Access for {self.user.username}"


class Customer(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    primary_phone = models.CharField(max_length=30, blank=True)
    secondary_phone = models.CharField(max_length=30, blank=True)
    company = models.CharField(max_length=150, blank=True)
    notes = models.TextField(blank=True)
    owner = models.ForeignKey(
        get_user_model(),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="customers",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("first_name", "last_name", "id")

    def __str__(self):
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name or self.company or f"Customer {self.pk}"


class ProductCategory(models.Model):
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "id")
        verbose_name = "product category"
        verbose_name_plural = "product categories"

    def __str__(self):
        return self.name


class Product(models.Model):
    name = models.CharField(max_length=150)
    category = models.ForeignKey(
        ProductCategory,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "id")

    def __str__(self):
        return self.name


class Service(models.Model):
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    products = models.ManyToManyField(
        Product,
        blank=True,
        related_name="services",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "id")

    def __str__(self):
        return self.name
