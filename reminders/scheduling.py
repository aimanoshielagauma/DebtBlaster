from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from debts.models import Debt
from .models import ReminderEvent, ReminderLog, ReminderSchedule


@transaction.atomic
def sync_debt_schedule(debt):
    """Create or stop the reminder schedule to match the current debt state."""
    schedule, _ = ReminderSchedule.objects.get_or_create(
        debt=debt,
        defaults={"owner_id": debt.owner_id, "next_reminder_at": timezone.now()},
    )
    eligible = (
        debt.reminder_enabled
        and debt.status != Debt.Status.CANCELLED
        and debt.outstanding_balance > Decimal("0.00")
    )
    if eligible and not schedule.enabled:
        schedule.enabled = True
        schedule.stopped_at = None
        schedule.stop_reason = ""
        schedule.next_reminder_at = timezone.now()
        schedule.save(update_fields=["enabled", "stopped_at", "stop_reason", "next_reminder_at", "updated_at"])
    elif not eligible and schedule.enabled:
        schedule.enabled = False
        schedule.stopped_at = timezone.now()
        schedule.stop_reason = "Debt settled or reminders disabled"
        schedule.next_reminder_at = None
        schedule.save(update_fields=["enabled", "stopped_at", "stop_reason", "next_reminder_at", "updated_at"])
        ReminderEvent.objects.filter(
            debt=debt, status=ReminderEvent.Status.PENDING
        ).update(status=ReminderEvent.Status.CANCELLED, last_error=schedule.stop_reason)
        ReminderLog.objects.filter(
            debt=debt, status=ReminderLog.Status.QUEUED
        ).update(status=ReminderLog.Status.CANCELLED)
    return schedule
