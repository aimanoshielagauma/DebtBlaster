from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from clients.models import Client
from debts.models import Debt
from payments.models import Payment
from payments.services import record_payment
from reminders.models import ReminderEvent, ReminderSchedule

User = get_user_model()


class DebtPaymentScenarioTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(username="payment_owner", password="TestPassword123!")
        self.other = User.objects.create_user(username="payment_other", password="TestPassword123!")
        self.client_record = Client.objects.create(
            owner=self.owner, client_type="business",
            full_name="Payment Client", email="pay@example.com",
        )
        self.debt = Debt.objects.create(
            owner=self.owner, client=self.client_record, description="Invoice 1",
            original_amount=Decimal("100.00"), currency="NGN",
            due_date=timezone.localdate() + timedelta(days=7),
        )

    def pay(self, amount, reference=""):
        return record_payment(
            debt_id=self.debt.pk, owner=self.owner, recorded_by=self.owner,
            amount=amount, payment_date=timezone.localdate(),
            method=Payment.Method.BANK_TRANSFER, reference=reference,
        )

    def test_partial_payment_updates_balance_and_status(self):
        self.pay("25.00", "PART-25")
        self.debt.refresh_from_db()
        self.assertEqual(self.debt.status, Debt.Status.PARTIAL)
        self.assertEqual(self.debt.outstanding_balance, Decimal("75.00"))

    def test_full_payment_closes_debt(self):
        self.pay("100.00", "FULL-100")
        self.debt.refresh_from_db()
        self.assertEqual(self.debt.status, Debt.Status.PAID)
        self.assertEqual(self.debt.outstanding_balance, Decimal("0.00"))

    def test_overpayment_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.pay("100.01", "OVER-100")

    def test_duplicate_reference_is_rejected(self):
        self.pay("25.00", "DUPLICATE")
        with self.assertRaises(ValidationError):
            self.pay("10.00", "DUPLICATE")

    def test_cannot_record_payment_for_another_owners_debt(self):
        with self.assertRaises(ValidationError):
            record_payment(
                debt_id=self.debt.pk, owner=self.other, recorded_by=self.other,
                amount="10.00", payment_date=timezone.localdate(),
            )

    def test_full_payment_cancels_pending_events(self):
        schedule = ReminderSchedule.objects.create(
            owner=self.owner, debt=self.debt, enabled=True,
            next_reminder_at=timezone.now() + timedelta(days=1),
        )
        ReminderEvent.objects.create(
            schedule=schedule, debt=self.debt,
            event_key="test-debt-full-payment",
            event_type=ReminderEvent.EventType.RECURRING,
            recipient_email="pay@example.com",
            scheduled_for=timezone.now() + timedelta(days=1),
            next_attempt_at=timezone.now() + timedelta(days=1),
        )
        self.pay("100.00", "FULL-CANCEL")
        event = ReminderEvent.objects.get(event_key="test-debt-full-payment")
        self.assertEqual(event.status, ReminderEvent.Status.CANCELLED)
