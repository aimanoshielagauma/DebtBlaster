from django.conf import settings
from django.db import models


class BusinessSettings(models.Model):
    owner = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="business_settings",
    )

    business_name = models.CharField(
        max_length=200,
        blank=True,
    )

    contact_email = models.EmailField(blank=True)

    phone = models.CharField(max_length=30, blank=True)

    default_currency = models.CharField(
        max_length=3,
        default="NGN",
    )

    timezone = models.CharField(
        max_length=64,
        default="Africa/Lagos",
    )

    default_reminder_frequency = models.CharField(
        max_length=20,
        default="weekly",
    )

    default_reminders_enabled = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.business_name or str(self.owner)