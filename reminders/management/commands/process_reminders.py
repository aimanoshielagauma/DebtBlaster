import uuid
from datetime import timedelta

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone

from debts.models import Debt
from reminders.models import ReminderEvent
from reminders.services import build_reminder_context, frequency_delta, reminder_is_due


class Command(BaseCommand):
    help = "Process due DebtBlaster reminder events."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Preview due events without changing records or sending email.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=50,
            help="Maximum number of events to process in one run.",
        )

    def handle(self, *args, **options):
        limit = max(1, min(options["limit"], 500))
        now = timezone.now()

        due = ReminderEvent.objects.filter(
            status=ReminderEvent.Status.PENDING,
            next_attempt_at__lte=now,
        ).select_related("schedule", "debt", "debt__client").order_by(
            "next_attempt_at", "id"
        )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(
                f"DRY RUN: {due.count()} due pending event(s); no records changed and no emails sent."
            ))
            for event in due[:limit]:
                self.stdout.write(
                    f"event={event.pk} debt={event.debt_id} "
                    f"client={event.debt.client.full_name!r} "
                    f"scheduled={event.scheduled_for} recipient={event.recipient_email}"
                )
            return

        processed = 0
        while processed < limit:
            event = self._claim_one()
            if event is None:
                break
            self._process_claimed(event)
            processed += 1

        self.stdout.write(self.style.SUCCESS(f"Processed {processed} reminder event(s)."))

    def _claim_one(self):
        now = timezone.now()
        with transaction.atomic():
            event = (
                ReminderEvent.objects.select_for_update(skip_locked=True)
                .filter(
                    status=ReminderEvent.Status.PENDING,
                    next_attempt_at__lte=now,
                )
                .order_by("next_attempt_at", "id")
                .first()
            )
            if event is None:
                return None
            event.status = ReminderEvent.Status.PROCESSING
            event.claimed_at = now
            event.claim_token = uuid.uuid4()
            event.attempt_count += 1
            event.save(update_fields=[
                "status", "claimed_at", "claim_token", "attempt_count", "updated_at"
            ])
            return event

    def _process_claimed(self, event):
        event.refresh_from_db()
        token = event.claim_token
        debt = Debt.objects.select_related("client", "owner").get(pk=event.debt_id)
        schedule = event.schedule
        if event.recipient_email != debt.client.email:
            event.recipient_email = debt.client.email
            event.save(update_fields=["recipient_email", "updated_at"])

        # Do not trust an old queued event; validate current state just before sending.
        if (
            schedule.debt_id != debt.pk
            or schedule.owner_id != debt.owner_id
            or not reminder_is_due(schedule, debt, now=timezone.now())
            or not event.recipient_email
            or not debt.client.email
        ):
            self._finish(event.pk, token, ReminderEvent.Status.SKIPPED,
                         error="Debt, schedule, balance, reminder preference, or recipient is no longer eligible.")
            return

        context = build_reminder_context(debt)
        subject = f"Payment reminder: {debt.description}"
        body = (
            f"Hello {debt.client.full_name},\n\n"
            f"This is a reminder about {debt.description}.\n"
            f"Original amount: {debt.currency} {context['original_amount']}\n"
            f"Amount paid: {debt.currency} {context['total_paid']}\n"
            f"Outstanding balance: {debt.currency} {context['outstanding_balance']}\n"
            f"Due date: {debt.due_date:%d %b %Y}\n\n"
            f"Regards,\n{context['business_name']}"
        )
        sender = getattr(settings, "DEFAULT_FROM_EMAIL", "")
        try:
            sent_count = send_mail(
                subject=subject,
                message=body,
                from_email=sender,
                recipient_list=[event.recipient_email],
                fail_silently=False,
            )
            if sent_count != 1:
                raise RuntimeError("Email backend did not confirm sending the reminder.")
        except Exception as exc:
            self._record_failure(event, token, str(exc))
            return

        self._finish(
            event.pk, token, ReminderEvent.Status.SENT,
            sent_at=timezone.now(), error=""
        )
        from reminders.models import ReminderSchedule
        schedule = ReminderSchedule.objects.filter(pk=event.schedule_id, enabled=True).first()
        if schedule:
            schedule.next_reminder_at = timezone.now() + frequency_delta(schedule)
            schedule.save(update_fields=["next_reminder_at", "updated_at"])

    def _record_failure(self, event, token, error):
        with transaction.atomic():
            current = ReminderEvent.objects.select_for_update().filter(
                pk=event.pk, claim_token=token,
                status=ReminderEvent.Status.PROCESSING,
            ).first()
            if current is None:
                return
            max_attempts = current.schedule.max_attempts
            if current.attempt_count >= max_attempts:
                current.status = ReminderEvent.Status.FAILED
                schedule = current.schedule
                if schedule.enabled:
                    schedule.next_reminder_at = timezone.now() + frequency_delta(schedule)
                    schedule.save(update_fields=["next_reminder_at", "updated_at"])
            else:
                current.status = ReminderEvent.Status.PENDING
                current.next_attempt_at = timezone.now() + timedelta(
                    minutes=current.schedule.retry_after_minutes
                )
            current.last_error = error[:4000]
            current.claimed_at = None
            current.claim_token = None
            current.save(update_fields=[
                "status", "next_attempt_at", "last_error",
                "claimed_at", "claim_token", "updated_at"
            ])

    def _finish(self, event_id, token, status, sent_at=None, error=""):
        with transaction.atomic():
            current = ReminderEvent.objects.select_for_update().filter(
                pk=event_id, claim_token=token,
                status=ReminderEvent.Status.PROCESSING,
            ).first()
            if current is None:
                return
            current.status = status
            current.sent_at = sent_at
            current.last_error = error[:4000]
            current.claimed_at = None
            current.claim_token = None
            current.save(update_fields=[
                "status", "sent_at", "last_error",
                "claimed_at", "claim_token", "updated_at"
            ])
