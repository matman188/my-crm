from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone


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
    business_timezone = models.CharField(max_length=64, default="Africa/Johannesburg")
    default_currency = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default=CURRENCY_ZAR,
    )
    INVOICE_ACCENTS = (
        ("#2f6f86", "Teal"),
        ("#243e59", "Navy"),
        ("#2e644e", "Forest"),
        ("#6d4575", "Plum"),
        ("#465462", "Slate"),
    )
    invoice_logo = models.ImageField(upload_to="invoice_logos/", blank=True)
    invoice_address = models.TextField(blank=True, max_length=600)
    invoice_email = models.EmailField(blank=True)
    invoice_phone = models.CharField(blank=True, max_length=50)
    invoice_registration_number = models.CharField(blank=True, max_length=100)
    invoice_tax_number = models.CharField(blank=True, max_length=100)
    invoice_bank_details = models.TextField(blank=True, max_length=2000)
    invoice_payment_instructions = models.TextField(blank=True, max_length=2000)
    invoice_prefix = models.CharField(max_length=12, default="INV")
    invoice_accent = models.CharField(
        max_length=7, choices=INVOICE_ACCENTS, default="#2f6f86"
    )
    invoice_terms = models.TextField(blank=True, max_length=4000)
    invoice_note = models.TextField(blank=True, max_length=2000)

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

    @property
    def business_zone(self):
        try:
            return ZoneInfo(self.business_timezone)
        except (ValueError, ZoneInfoNotFoundError):
            return timezone.get_default_timezone()

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
