from django.conf import settings
from django.db import models


class Invoice(models.Model):
    class Status(models.TextChoices):
        ISSUED = "issued", "Issued"
        SUPERSEDED = "superseded", "Superseded"
        VOID = "void", "Void"

    order = models.ForeignKey(
        "crm.ServiceOrder", on_delete=models.PROTECT, related_name="invoices"
    )
    issued_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="issued_invoices",
    )
    issued_at = models.DateTimeField()
    number_prefix = models.CharField(max_length=12)
    number_date = models.DateField(null=True, blank=True, editable=False)
    daily_sequence = models.PositiveIntegerField(null=True, blank=True, editable=False)
    snapshot = models.JSONField()
    logo = models.ImageField(upload_to="invoice_logos/", blank=True)
    template_version = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.ISSUED
    )
    replaces = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="replacement",
    )
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="closed_invoices",
    )
    closure_reason = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ("-pk",)
        constraints = [
            models.UniqueConstraint(
                fields=("order",),
                condition=models.Q(status="issued"),
                name="one_issued_invoice_per_order",
            ),
            models.UniqueConstraint(
                fields=("number_date", "daily_sequence"),
                name="unique_invoice_sequence_per_day",
            ),
            models.CheckConstraint(
                condition=models.Q(daily_sequence__isnull=True)
                | models.Q(number_date__isnull=False, daily_sequence__gte=1),
                name="invoice_daily_sequence_requires_date",
            ),
        ]

    @property
    def number(self):
        sequence = f"{self.pk:06d}"
        if self.number_date is None:
            return f"{self.number_prefix}-{sequence}"
        date_segment = self.number_date.isoformat().replace("-", "")
        if self.daily_sequence is not None:
            return f"{self.number_prefix}{date_segment}{self.daily_sequence:02d}"
        return f"{self.number_prefix}-{date_segment}-{sequence}"

    def __str__(self):
        return self.number


class InvoiceDaySequence(models.Model):
    issue_date = models.DateField(primary_key=True)
    last_number = models.PositiveIntegerField(default=0)
