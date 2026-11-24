from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="debtblaster_audit_events",
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="debtblaster_actions",
    )

    action = models.CharField(max_length=100)

    entity_type = models.CharField(max_length=50)

    entity_id = models.CharField(max_length=100)

    details = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner", "created_at"]),
            models.Index(fields=["entity_type", "entity_id"]),
        ]

    def __str__(self):
        return f"{self.action} - {self.entity_type} {self.entity_id}"