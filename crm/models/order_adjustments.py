from django.conf import settings
from django.db import models


class OrderComplaint(models.Model):
    class Outcome(models.TextChoices):
        REDO = "redo", "Free redo"
        REFUND = "refund", "Refund"
        BOTH = "both", "Free redo and refund"

    order = models.OneToOneField(
        "crm.ServiceOrder", on_delete=models.PROTECT, related_name="complaint"
    )
    logged = models.BooleanField(default=True)
    logged_at = models.DateTimeField(auto_now_add=True)
    details = models.TextField(max_length=2000, blank=True)
    outcome = models.CharField(max_length=10, choices=Outcome.choices, blank=True)
    affected_service = models.ForeignKey(
        "crm.OrderServiceCharge", on_delete=models.SET_NULL, null=True, blank=True
    )
    service_description = models.CharField(max_length=400, blank=True)


class OrderRefund(models.Model):
    order = models.ForeignKey(
        "crm.ServiceOrder", on_delete=models.PROTECT, related_name="refunds"
    )
    amount = models.DecimalField(max_digits=22, decimal_places=2)
    refunded_on = models.DateField()
    reason = models.CharField(max_length=500, blank=True)
    recorded_at = models.DateTimeField(auto_now_add=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="recorded_refunds",
    )
    affected_service = models.ForeignKey(
        "crm.OrderServiceCharge", on_delete=models.SET_NULL, null=True, blank=True
    )
    service_description = models.CharField(max_length=400, blank=True)

    class Meta:
        ordering = ("-refunded_on", "-pk")
        constraints = [
            models.CheckConstraint(
                condition=models.Q(amount__gt=0), name="order_refund_positive"
            )
        ]


class OrderRefundAmountChange(models.Model):
    refund = models.ForeignKey(
        OrderRefund, on_delete=models.PROTECT, related_name="amount_changes"
    )
    previous_amount = models.DecimalField(max_digits=22, decimal_places=2)
    new_amount = models.DecimalField(max_digits=22, decimal_places=2)
    changed_at = models.DateTimeField(auto_now_add=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="refund_amount_changes",
    )

    class Meta:
        ordering = ("-pk",)
