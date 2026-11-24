from django.conf import settings
from django.db import models


class Payment(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        REVERSED = "reversed", "Reversed"

    class Method(models.TextChoices):
        BANK_TRANSFER = "bank_transfer", "Bank transfer"
        CASH = "cash", "Cash"
        CARD = "card", "Card"
        OTHER = "other", "Other"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments",
    )

    debt = models.ForeignKey(
        "debts.Debt",
        on_delete=models.PROTECT,
        related_name="payments",
    )

    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
    )

    payment_date = models.DateField()

    method = models.CharField(
        max_length=30,
        choices=Method.choices,
        default=Method.BANK_TRANSFER,
    )

    reference = models.CharField(
        max_length=150,
        blank=True,
    )

    notes = models.TextField(blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.CONFIRMED,
    )

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="recorded_debt_payments",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-payment_date", "-id"]
        indexes = [
            models.Index(fields=["owner", "payment_date"]),
            models.Index(fields=["debt", "status"]),
        ]

    def __str__(self):
        return f"{self.debt.description}: {self.amount}"