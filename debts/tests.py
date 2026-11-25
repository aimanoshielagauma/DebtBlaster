
import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from clients.models import Client
from debts.models import Debt
from payments.models import Payment

User = get_user_model()


class DebtAPITests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="debt_owner",
            password="TestPassword123!",
        )
        self.other = User.objects.create_user(
            username="debt_other",
            password="TestPassword123!",
        )

        self.client_record = Client.objects.create(
            owner=self.owner,
            client_type="business",
            full_name="Owner Client",
            email="owner@example.com",
        )
        self.other_client = Client.objects.create(
            owner=self.other,
            client_type="business",
            full_name="Other Client",
            email="other@example.com",
        )

        self.debt = Debt.objects.create(
            owner=self.owner,
            client=self.client_record,
            description="Test invoice",
            original_amount=Decimal("100.00"),
            currency="NGN",
            due_date=timezone.localdate() + timedelta(days=10),
        )

    def post_json(self, path, data):
        return self.client.post(
            path,
            data=json.dumps(data),
            content_type="application/json",
        )

    def patch_json(self, path, data):
        return self.client.patch(
            path,
            data=json.dumps(data),
            content_type="application/json",
        )

    def test_user_cannot_view_another_users_debt(self):
        self.client.force_login(self.other)
        response = self.client.get(f"/api/debts/{self.debt.pk}/")
        self.assertEqual(response.status_code, 404)

    def test_cannot_create_debt_for_another_users_client(self):
        self.client.force_login(self.owner)
        response = self.post_json(
            "/api/debts/",
            {
                "client_id": self.other_client.pk,
                "description": "Foreign client debt",
                "original_amount": "100.00",
                "due_date": (
                    timezone.localdate() + timedelta(days=10)
                ).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 404)

    def test_cannot_create_debt_for_archived_client(self):
        self.client_record.is_archived = True
        self.client_record.save(update_fields=["is_archived"])

        self.client.force_login(self.owner)
        response = self.post_json(
            "/api/debts/",
            {
                "client_id": self.client_record.pk,
                "description": "Archived client debt",
                "original_amount": "100.00",
                "due_date": (
                    timezone.localdate() + timedelta(days=10)
                ).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 404)

    def test_original_amount_cannot_be_less_than_confirmed_payments(self):
        Payment.objects.create(
            owner=self.owner,
            debt=self.debt,
            amount=Decimal("80.00"),
            payment_date=timezone.localdate(),
            method="bank_transfer",
            reference="TEST-80",
            status=Payment.Status.CONFIRMED,
            recorded_by=self.owner,
        )

        self.client.force_login(self.owner)
        response = self.patch_json(
            f"/api/debts/{self.debt.pk}/",
            {"original_amount": "50.00"},
        )
        self.assertEqual(response.status_code, 400)

        self.debt.refresh_from_db()
        self.assertEqual(self.debt.original_amount, Decimal("100.00"))

    def test_increasing_paid_debt_amount_recalculates_status(self):
        Payment.objects.create(
            owner=self.owner,
            debt=self.debt,
            amount=Decimal("100.00"),
            payment_date=timezone.localdate(),
            method="bank_transfer",
            reference="TEST-FULL",
            status=Payment.Status.CONFIRMED,
            recorded_by=self.owner,
        )

        self.debt.status = Debt.Status.PAID
        self.debt.save(update_fields=["status"])

        self.client.force_login(self.owner)
        response = self.patch_json(
            f"/api/debts/{self.debt.pk}/",
            {"original_amount": "150.00"},
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["status"], Debt.Status.PARTIAL)

    def test_currency_can_be_changed_before_any_payment(self):
        self.client.force_login(self.owner)

        response = self.patch_json(
            f"/api/debts/{self.debt.pk}/",
            {"currency": "USD"},
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.debt.refresh_from_db()
        self.assertEqual(self.debt.currency, "USD")

    def test_currency_cannot_be_changed_after_payment(self):
        Payment.objects.create(
            owner=self.owner,
            debt=self.debt,
            amount=Decimal("20.00"),
            payment_date=timezone.localdate(),
            method="bank_transfer",
            reference="CURRENCY-LOCK-1",
            status=Payment.Status.CONFIRMED,
            recorded_by=self.owner,
        )

        self.client.force_login(self.owner)
        response = self.patch_json(
            f"/api/debts/{self.debt.pk}/",
            {"currency": "USD"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Currency cannot be changed",
            response.json()["error"],
        )

        self.debt.refresh_from_db()
        self.assertEqual(self.debt.currency, "NGN")

    def test_same_currency_is_allowed_after_payment(self):
        Payment.objects.create(
            owner=self.owner,
            debt=self.debt,
            amount=Decimal("20.00"),
            payment_date=timezone.localdate(),
            method="bank_transfer",
            reference="CURRENCY-LOCK-2",
            status=Payment.Status.CONFIRMED,
            recorded_by=self.owner,
        )

        self.client.force_login(self.owner)
        response = self.patch_json(
            f"/api/debts/{self.debt.pk}/",
            {"currency": "NGN"},
        )

        self.assertEqual(response.status_code, 200, response.content)
        self.debt.refresh_from_db()
        self.assertEqual(self.debt.currency, "NGN")


class DebtAgingReportTests(TestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username="aging_owner",
            password="TestPassword123!",
        )
        self.other = User.objects.create_user(
            username="aging_other",
            password="TestPassword123!",
        )

        self.client_record = Client.objects.create(
            owner=self.owner,
            client_type="business",
            full_name="Aging Report Client",
            email="aging@example.com",
        )
        self.other_client = Client.objects.create(
            owner=self.other,
            client_type="business",
            full_name="Other Aging Client",
            email="other-aging@example.com",
        )

        self.today = timezone.localdate()
        self.client.force_login(self.owner)

    def create_debt(
        self,
        description,
        due_date,
        amount="100.00",
        currency="NGN",
        owner=None,
        client=None,
        status=Debt.Status.UNPAID,
    ):
        owner = owner or self.owner
        client = client or self.client_record

        return Debt.objects.create(
            owner=owner,
            client=client,
            description=description,
            original_amount=Decimal(amount),
            currency=currency,
            due_date=due_date,
            status=status,
        )

    def test_report_loads_successfully(self):
        response = self.client.get("/debts/aging-report/")

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "debts/debt_aging_report.html",
        )

    def test_debts_are_grouped_into_correct_aging_categories(self):
        self.create_debt("Due Today", self.today)
        self.create_debt(
            "Overdue 15 Days",
            self.today - timedelta(days=15),
        )
        self.create_debt(
            "Overdue 45 Days",
            self.today - timedelta(days=45),
        )
        self.create_debt(
            "Overdue 75 Days",
            self.today - timedelta(days=75),
        )
        self.create_debt(
            "Overdue 100 Days",
            self.today - timedelta(days=100),
        )

        response = self.client.get("/debts/aging-report/")
        self.assertEqual(response.status_code, 200)

        report = response.context["currency_reports"]
        self.assertEqual(len(report), 1)

        buckets = {
            bucket["key"]: bucket
            for bucket in report[0]["buckets"]
        }

        self.assertEqual(buckets["not_overdue"]["count"], 1)
        self.assertEqual(buckets["days_1_30"]["count"], 1)
        self.assertEqual(buckets["days_31_60"]["count"], 1)
        self.assertEqual(buckets["days_61_90"]["count"], 1)
        self.assertEqual(buckets["days_90_plus"]["count"], 1)

    def test_report_groups_currencies_separately(self):
        self.create_debt(
            "Naira Debt",
            self.today,
            amount="100.00",
            currency="NGN",
        )
        self.create_debt(
            "Dollar Debt",
            self.today,
            amount="50.00",
            currency="USD",
        )

        response = self.client.get("/debts/aging-report/")

        report = {
            item["currency"]: item
            for item in response.context["currency_reports"]
        }

        self.assertEqual(report["NGN"]["total"], Decimal("100.00"))
        self.assertEqual(report["USD"]["total"], Decimal("50.00"))

    def test_confirmed_payments_reduce_report_balance(self):
        debt = self.create_debt(
            "Partially Paid Debt",
            self.today - timedelta(days=10),
            amount="100.00",
        )

        Payment.objects.create(
            owner=self.owner,
            debt=debt,
            amount=Decimal("40.00"),
            payment_date=self.today,
            method="bank_transfer",
            reference="AGING-TEST-40",
            status=Payment.Status.CONFIRMED,
            recorded_by=self.owner,
        )

        response = self.client.get("/debts/aging-report/")
        rows = response.context["debt_rows"]

        row = next(
            item for item in rows
            if item["debt"].pk == debt.pk
        )

        self.assertEqual(row["balance"], Decimal("60.00"))

    def test_paid_and_cancelled_debts_are_excluded(self):
        self.create_debt(
            "Paid Debt",
            self.today - timedelta(days=10),
            status=Debt.Status.PAID,
        )
        self.create_debt(
            "Cancelled Debt",
            self.today - timedelta(days=10),
            status=Debt.Status.CANCELLED,
        )

        response = self.client.get("/debts/aging-report/")

        descriptions = {
            row["debt"].description
            for row in response.context["debt_rows"]
        }

        self.assertNotIn("Paid Debt", descriptions)
        self.assertNotIn("Cancelled Debt", descriptions)

    def test_user_cannot_see_another_users_debts(self):
        foreign_debt = self.create_debt(
            "Private Foreign Debt",
            self.today - timedelta(days=20),
            owner=self.other,
            client=self.other_client,
        )

        response = self.client.get("/debts/aging-report/")
        self.assertEqual(response.status_code, 200)

        debt_ids = {
            row["debt"].pk
            for row in response.context["debt_rows"]
        }

        self.assertNotIn(foreign_debt.pk, debt_ids)
