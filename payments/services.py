from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from debts.models import Debt
from .models import Payment


@transaction.atomic
def record_payment(
    *,
    debt_id,
    owner,
    recorded_by,
    amount,
    payment_date,
    method=Payment.Method.BANK_TRANSFER,
    reference="",
    notes="",
):
    try:
        amount = Decimal(str(amount))
    except (InvalidOperation, ValueError, TypeError):
        raise ValidationError("Enter a valid payment amount.")

    if not amount.is_finite() or amount <= Decimal("0.00"):
        raise ValidationError("Payment amount must be greater than zero.")
    if amount.as_tuple().exponent < -2:
        raise ValidationError("Payment amount cannot have more than two decimal places.")

    debt = Debt.objects.select_for_update().filter(pk=debt_id, owner=owner).first()
    if debt is None:
        raise ValidationError("Debt not found or access denied.")
    if debt.status == Debt.Status.CANCELLED:
        raise ValidationError("Cannot pay a cancelled debt.")
    if recorded_by.pk != owner.pk:
        raise ValidationError("Only the debt owner can record this payment.")

    reference = (reference or "").strip()
    if reference and Payment.objects.filter(
        debt=debt, owner=owner, reference=reference
    ).exists():
        raise ValidationError("This payment reference has already been used.")

    total_paid = debt.payments.filter(
        status=Payment.Status.CONFIRMED, owner=owner
    ).aggregate(total=Sum("amount"))["total"] or Decimal("0.00")
    balance = max(Decimal("0.00"), debt.original_amount - total_paid)

    if balance <= Decimal("0.00"):
        raise ValidationError("This debt has no outstanding balance.")
    if amount > balance:
        raise ValidationError(f"Payment exceeds the outstanding balance of {balance}.")

    payment = Payment.objects.create(
        owner=owner,
        debt=debt,
        recorded_by=recorded_by,
        amount=amount,
        payment_date=payment_date,
        method=method,
        reference=reference,
        notes=notes,
        status=Payment.Status.CONFIRMED,
    )

    new_balance = balance - amount
    if new_balance == Decimal("0.00"):
        debt.status = Debt.Status.PAID
    elif total_paid + amount > Decimal("0.00"):
        debt.status = Debt.Status.PARTIAL
    else:
        debt.status = Debt.Status.UNPAID
    debt.save(update_fields=["status", "updated_at"])

    if new_balance == Decimal("0.00"):
        from reminders.models import ReminderEvent, ReminderLog, ReminderSchedule

        now = timezone.now()
        schedule = ReminderSchedule.objects.filter(
            debt=debt, owner=owner
        ).first()
        if schedule:
            schedule.enabled = False
            schedule.stopped_at = now
            schedule.stop_reason = "Debt fully paid"
            schedule.next_reminder_at = None
            schedule.save(update_fields=[
                "enabled", "stopped_at", "stop_reason",
                "next_reminder_at", "updated_at",
            ])

        ReminderEvent.objects.filter(
            debt=debt,
            status__in=[
                ReminderEvent.Status.PENDING,
                ReminderEvent.Status.FAILED,
            ],
        ).update(
            status=ReminderEvent.Status.CANCELLED,
            last_error="Debt fully paid; reminder cancelled.",
            updated_at=now,
        )
        ReminderLog.objects.filter(
            debt=debt,
            status=ReminderLog.Status.QUEUED,
        ).update(status=ReminderLog.Status.CANCELLED)

    return payment
