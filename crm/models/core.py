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
