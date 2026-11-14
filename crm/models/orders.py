from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


class ServiceOrder(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"

    customer = models.ForeignKey(
        "crm.Customer", on_delete=models.PROTECT, related_name="orders"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_orders",
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_orders",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT
    )
    currency = models.CharField(max_length=3)
    notes = models.TextField(blank=True)
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    @property
    def reference(self):
        return f"SO-{self.pk:06d}" if self.pk else "New order"

    @property
    def total(self):
        return sum((charge.total for charge in self.charges.all()), Decimal("0.00"))

    def __str__(self):
        return self.reference


class OrderItem(models.Model):
    order = models.ForeignKey(
        ServiceOrder, on_delete=models.CASCADE, related_name="items"
    )
    product = models.ForeignKey(
        "crm.Product", on_delete=models.PROTECT, related_name="order_items"
    )
    due_date = models.DateField("Deadline date")
    due_time = models.TimeField("Deadline time", null=True, blank=True)
    notes = models.TextField("Item instructions", blank=True)

    class Meta:
        ordering = ("pk",)

    @property
    def total(self):
        return sum((charge.total for charge in self.charges.all()), Decimal("0.00"))

    def __str__(self):
        return str(self.product)


class OrderServiceCharge(models.Model):
    order = models.ForeignKey(
        ServiceOrder, on_delete=models.CASCADE, related_name="charges"
    )
    item = models.ForeignKey(
        OrderItem,
        on_delete=models.CASCADE,
        related_name="charges",
        null=True,
        blank=True,
    )
    service = models.ForeignKey(
        "crm.Service", on_delete=models.PROTECT, related_name="order_charges"
    )
    quantity = models.PositiveIntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(100000000)]
    )
    unit_price = models.DecimalField(
        max_digits=10, decimal_places=2, validators=[MinValueValidator(0)]
    )
    notes = models.TextField("Internal service note", blank=True)

    class Meta:
        ordering = ("pk",)
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1),
                name="order_charge_quantity_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(unit_price__gte=0),
                name="order_charge_price_nonnegative",
            ),
        ]

    @property
    def total(self):
        return self.unit_price * self.quantity

    def __str__(self):
        return f"{self.service} × {self.quantity}"
