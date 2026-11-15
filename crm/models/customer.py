from django.contrib.auth import get_user_model
from django.db import models
from django.db.models.functions import Lower, Trim


class Customer(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    primary_phone = models.CharField(max_length=30)
    secondary_phone = models.CharField(max_length=30, blank=True)
    company = models.CharField(max_length=150, blank=True)
    notes = models.TextField(blank=True)
    is_archived = models.BooleanField(default=False, db_index=True)
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
        constraints = [
            models.UniqueConstraint(
                Lower(Trim("email")),
                name="customer_email_unique_ci",
                violation_error_message="A customer with this email already exists.",
            ),
        ]

    def __str__(self):
        full_name = f"{self.first_name} {self.last_name}".strip()
        return full_name or self.company or f"Customer {self.pk}"
