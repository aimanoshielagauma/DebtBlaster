from django.conf import settings
from django.db import models


class Client(models.Model):
    class ClientType(models.TextChoices):
        INDIVIDUAL = "individual", "Individual"
        BUSINESS = "business", "Business"

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="clients",
    )

    client_type = models.CharField(
        max_length=20,
        choices=ClientType.choices,
        default=ClientType.INDIVIDUAL,
    )

    full_name = models.CharField(max_length=200)

    email = models.EmailField(max_length=254)

    phone = models.CharField(
        max_length=30,
        blank=True,
    )

    notes = models.TextField(blank=True)

    is_archived = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["full_name"]
        indexes = [
            models.Index(fields=["owner", "email"]),
            models.Index(fields=["owner", "full_name"]),
        ]

    def __str__(self):
        return self.full_name

from .settings_models import BusinessSettings

from .audit_log import AuditLog