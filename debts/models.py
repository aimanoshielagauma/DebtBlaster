from django.conf import settings
from django.db import models
from django.db.models import Sum


class Debt(models.Model):
    class Status(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PARTIAL = "partial", "Partially paid"
        PAID = "paid", "Paid"
        CANCELLED = "cancelled", "Cancelled"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="debts",
    )

    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.PROTECT,
        related_name="debts",
    )

    description = models.CharField(max_length=255)

    invoice_number = models.CharField(
        max_length=100,
        blank=True,
    )

    original_amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    currency = models.CharField(
        max_length=3,
        default="NGN",
    )

    due_date = models.DateField()

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.UNPAID,
    )

    reminder_enabled = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["due_date", "id"]
        indexes = [
            models.Index(fields=["owner", "status"]),
            models.Index(fields=["owner", "due_date"]),
            models.Index(fields=["client", "status"]),
        ]

    def __str__(self):
        return f"{self.description} - {self.client.full_name}"

    @property
    def total_paid(self):
        return self.payments.filter(
            status="confirmed"
        ).aggregate(
            total=Sum("amount")
        )["total"] or 0

    @property
    def outstanding_balance(self):
        return max(
            0,
            self.original_amount - self.total_paid,
        )