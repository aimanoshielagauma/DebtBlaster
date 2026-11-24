
from django.conf import settings
from django.db import models


class ReminderSchedule(models.Model):
    class Frequency(models.TextChoices):
        WEEKLY = "weekly", "Weekly"
        EVERY_3_DAYS = "every_3_days", "Every 3 days"
        DAILY = "daily", "Daily"

    debt = models.OneToOneField(
        "debts.Debt",
        on_delete=models.CASCADE,
        related_name="reminder_schedule",
    )

    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reminder_schedules",
    )

    enabled = models.BooleanField(default=True)

    frequency = models.CharField(
        max_length=20,
        choices=Frequency.choices,
        default=Frequency.WEEKLY,
    )

    send_before_due = models.BooleanField(default=True)
    send_on_due_date = models.BooleanField(default=True)
    send_after_due = models.BooleanField(default=True)

    # Number of days before the due date for an upcoming reminder
    before_due_days = models.PositiveSmallIntegerField(default=3)

    # Retry configuration
    max_attempts = models.PositiveSmallIntegerField(default=4)
    retry_after_minutes = models.PositiveSmallIntegerField(default=15)

    next_reminder_at = models.DateTimeField(null=True, blank=True)
    stopped_at = models.DateTimeField(null=True, blank=True)
    stop_reason = models.CharField(max_length=100, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Reminder schedule for debt {self.debt_id}"


class ReminderLog(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        SKIPPED = "skipped", "Skipped"

    schedule = models.ForeignKey(
        ReminderSchedule,
        on_delete=models.PROTECT,
        related_name="logs",
    )

    debt = models.ForeignKey(
        "debts.Debt",
        on_delete=models.PROTECT,
        related_name="reminder_logs",
    )

    recipient_email = models.EmailField()
    scheduled_for = models.DateTimeField()
    attempted_at = models.DateTimeField(null=True, blank=True)

    # Tracks the individual delivery attempt
    attempt_number = models.PositiveSmallIntegerField(default=1)

    # Unique identifier for each scheduled reminder attempt.
    # The scheduling code must generate the appropriate key.
    idempotency_key = models.CharField(
        max_length=100,
        unique=True,
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.QUEUED,
    )

    provider_message_id = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "scheduled_for"]),
            models.Index(fields=["debt", "created_at"]),
        ]

    def __str__(self):
        return f"{self.debt_id} - {self.status}"



from django.db import models


class ReminderEvent(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        SKIPPED = "skipped", "Skipped"
        REVIEW = "review", "Needs review"

    class EventType(models.TextChoices):
        BEFORE_DUE = "before_due", "Before due date"
        DUE_DATE = "due_date", "On due date"
        AFTER_DUE = "after_due", "After due date"
        RECURRING = "recurring", "Recurring reminder"

    schedule = models.ForeignKey(
        "reminders.ReminderSchedule",
        on_delete=models.PROTECT,
        related_name="events",
    )

    debt = models.ForeignKey(
        "debts.Debt",
        on_delete=models.PROTECT,
        related_name="reminder_events",
    )

    event_key = models.CharField(max_length=150, unique=True)

    event_type = models.CharField(
        max_length=30,
        choices=EventType.choices,
    )

    recipient_email = models.EmailField()

    scheduled_for = models.DateTimeField()

    # Set explicitly when creating each event.
    next_attempt_at = models.DateTimeField(db_index=True)

    attempt_count = models.PositiveSmallIntegerField(default=0)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    claimed_at = models.DateTimeField(null=True, blank=True)

    claim_token = models.UUIDField(null=True, blank=True)

    sent_at = models.DateTimeField(null=True, blank=True)

    last_error = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["next_attempt_at", "id"]
        indexes = [
            models.Index(fields=["status", "next_attempt_at"]),
            models.Index(fields=["schedule", "scheduled_for"]),
        ]

    def __str__(self):
        return f"Reminder event {self.event_key} ({self.status})"
