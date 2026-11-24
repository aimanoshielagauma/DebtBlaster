from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from clients.models import Client
from debts.models import Debt
from reminders.models import ReminderSchedule
from reminders.services import frequency_delta, reminder_is_due, valid_email_address

User = get_user_model()


class ReminderServiceTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="reminder_owner", password="TestPassword123!")
        self.client_record = Client.objects.create(
            owner=self.owner, client_type="individual",
            full_name="Reminder Client", email="client@example.com",
        )
        self.debt = Debt.objects.create(
            owner=self.owner, client=self.client_record,
            description="Reminder invoice", original_amount=Decimal("10000.00"),
            currency="NGN", due_date=timezone.localdate() + timedelta(days=3),
            reminder_enabled=True,
        )
        self.schedule = ReminderSchedule.objects.create(
            owner=self.owner, debt=self.debt, enabled=True,
            next_reminder_at=timezone.now() - timedelta(minutes=1),
        )

    def test_valid_email_address(self):
        self.assertTrue(valid_email_address("client@example.com"))

    def test_invalid_email_address(self):
        self.assertFalse(valid_email_address("not-an-email"))

    def test_empty_email_address(self):
        self.assertFalse(valid_email_address(""))

    def test_frequency_delta(self):
        cases = [
            (ReminderSchedule.Frequency.DAILY, 1),
            (ReminderSchedule.Frequency.EVERY_3_DAYS, 3),
            (ReminderSchedule.Frequency.WEEKLY, 7),
        ]
        for frequency, expected in cases:
            with self.subTest(frequency=frequency):
                self.schedule.frequency = frequency
                self.assertEqual(frequency_delta(self.schedule), timedelta(days=expected))

    def test_reminder_is_due_when_schedule_is_enabled(self):
        self.assertTrue(reminder_is_due(self.schedule, self.debt))

    def test_disabled_schedule_is_not_due(self):
        self.schedule.enabled = False
        self.assertFalse(reminder_is_due(self.schedule, self.debt))

    def test_disabled_debt_reminders_are_not_due(self):
        self.debt.reminder_enabled = False
        self.assertFalse(reminder_is_due(self.schedule, self.debt))

    def test_future_reminder_is_not_due(self):
        self.schedule.next_reminder_at = timezone.now() + timedelta(days=1)
        self.assertFalse(reminder_is_due(self.schedule, self.debt))

    def test_schedule_must_belong_to_same_debt_and_owner(self):
        other_user = User.objects.create_user(username="reminder_other", password="TestPassword123!")
        other_client = Client.objects.create(
            owner=other_user, client_type="individual",
            full_name="Other Client", email="other@example.com",
        )
        other_debt = Debt.objects.create(
            owner=other_user, client=other_client, description="Other debt",
            original_amount=Decimal("100.00"), currency="NGN",
            due_date=timezone.localdate() + timedelta(days=3),
        )
        self.assertFalse(reminder_is_due(self.schedule, other_debt))
