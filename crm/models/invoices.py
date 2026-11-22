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
        ]

    @property
    def number(self):
        return f"{self.number_prefix}-{self.pk:06d}"

    def __str__(self):
        return self.number
