from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from debts.models import Debt
from reminders.models import ReminderEvent, ReminderSchedule
from reminders.services import frequency_delta, reminder_is_due


class Command(BaseCommand):
    help = "Queue reminder emails that are due to be sent."

    def handle(self, *args, **options):
        now = timezone.now()
        schedules = ReminderSchedule.objects.select_related("debt", "debt__client").filter(
            enabled=True, next_reminder_at__lte=now, debt__reminder_enabled=True
        ).order_by("next_reminder_at", "id")
        created = 0
        skipped = 0
        for schedule in schedules.iterator():
            with transaction.atomic():
                schedule = ReminderSchedule.objects.select_for_update().select_related(
                    "debt", "debt__client"
                ).get(pk=schedule.pk)
                debt = Debt.objects.select_related("client").get(pk=schedule.debt_id)
                if not reminder_is_due(schedule, debt, now=now):
                    # Revisit at the configured interval until the debt enters an enabled window.
                    schedule.next_reminder_at = now + frequency_delta(schedule)
                    schedule.save(update_fields=["next_reminder_at", "updated_at"])
                    skipped += 1
                    continue
                if ReminderEvent.objects.filter(
                    schedule=schedule,
                    status__in=[ReminderEvent.Status.PENDING, ReminderEvent.Status.PROCESSING],
                ).exists():
                    continue
                event_key = f"schedule-{schedule.pk}-{schedule.next_reminder_at.timestamp():.0f}"
                _, was_created = ReminderEvent.objects.get_or_create(
                    event_key=event_key,
                    defaults={
                        "schedule": schedule,
                        "debt": debt,
                        "event_type": self._event_type(debt),
                        "recipient_email": debt.client.email,
                        "scheduled_for": schedule.next_reminder_at,
                        "next_attempt_at": now,
                    },
                )
                created += int(was_created)
        self.stdout.write(self.style.SUCCESS(f"Queued {created} reminder(s); advanced {skipped} not-yet-eligible schedule(s)."))

    @staticmethod
    def _event_type(debt):
        today = timezone.localdate()
        if debt.due_date > today:
            return ReminderEvent.EventType.BEFORE_DUE
        if debt.due_date == today:
            return ReminderEvent.EventType.DUE_DATE
        return ReminderEvent.EventType.AFTER_DUE
