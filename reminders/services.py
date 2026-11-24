from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from .models import ReminderSchedule, ReminderLog

ZERO = Decimal("0.00")


def valid_email_address(value):
    if not value:
        return False
    try:
        validate_email(value)
    except ValidationError:
        return False
    return True


def frequency_delta(schedule):
    frequency_days = {
        ReminderSchedule.Frequency.DAILY: 1,
        ReminderSchedule.Frequency.EVERY_3_DAYS: 3,
        ReminderSchedule.Frequency.WEEKLY: 7,
    }
    days = frequency_days.get(schedule.frequency)
    if days is None:
        raise ValueError(f"Unsupported reminder frequency: {schedule.frequency}")
    return timedelta(days=days)


@transaction.atomic
def stop_schedule(schedule, reason):
    schedule = ReminderSchedule.objects.select_for_update().get(pk=schedule.pk)
    schedule.enabled = False
    schedule.stopped_at = timezone.now()
    schedule.stop_reason = reason
    schedule.next_reminder_at = None
    schedule.save(update_fields=[
        "enabled", "stopped_at", "stop_reason", "next_reminder_at", "updated_at"
    ])
    return schedule


def build_reminder_context(debt):
    client = debt.client
    today = timezone.localdate()
    total_paid = debt.total_paid
    outstanding_balance = max(ZERO, debt.original_amount - total_paid)
    business_settings = getattr(debt.owner, "business_settings", None)
    return {
        "debt": debt,
        "client_name": client.full_name,
        "invoice_number": debt.invoice_number,
        "currency": debt.currency,
        "original_amount": f"{debt.original_amount:,.2f}",
        "total_paid": f"{total_paid:,.2f}",
        "outstanding_balance": f"{outstanding_balance:,.2f}",
        "due_date": debt.due_date,
        "is_overdue": debt.due_date < today,
        "is_due_today": debt.due_date == today,
        "business_name": getattr(business_settings, "business_name", "") or "Your service provider",
        "contact_email": getattr(business_settings, "contact_email", ""),
    }


def reminder_is_due(schedule, debt, now=None):
    now = now or timezone.now()
    today = timezone.localdate()

    # Validate the cross-links and owner before any reminder can be considered.
    if schedule.debt_id != debt.pk or schedule.owner_id != debt.owner_id:
        return False
    if not schedule.enabled or not debt.reminder_enabled:
        return False
    if schedule.next_reminder_at is None or schedule.next_reminder_at > now:
        return False
    if debt.status == debt.Status.CANCELLED or debt.outstanding_balance <= ZERO:
        return False

    if debt.due_date > today:
        if not schedule.send_before_due:
            return False
        days_until_due = (debt.due_date - today).days
        return days_until_due <= schedule.before_due_days
    if debt.due_date == today:
        return schedule.send_on_due_date
    return schedule.send_after_due


def record_log(
    *, schedule, debt, recipient_email, scheduled_for,
    attempt_number, idempotency_key, status, error_message="",
    provider_message_id="",
):
    if schedule.debt_id != debt.pk or schedule.owner_id != debt.owner_id:
        raise ValidationError("Reminder schedule and debt ownership do not match.")
    return ReminderLog.objects.create(
        schedule=schedule,
        debt=debt,
        recipient_email=recipient_email,
        scheduled_for=scheduled_for,
        attempted_at=timezone.now(),
        attempt_number=attempt_number,
        idempotency_key=idempotency_key,
        status=status,
        error_message=error_message[:4000],
        provider_message_id=provider_message_id,
    )
