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
        self.owner = User.objects.create_user(username="debt_owner", password="TestPassword123!")
        self.other = User.objects.create_user(username="debt_other", password="TestPassword123!")
        self.client_record = Client.objects.create(
            owner=self.owner, client_type="business", full_name="Owner Client",
            email="owner@example.com",
        )
        self.other_client = Client.objects.create(
            owner=self.other, client_type="business", full_name="Other Client",
            email="other@example.com",
        )
        self.debt = Debt.objects.create(
            owner=self.owner, client=self.client_record, description="Test invoice",
            original_amount=Decimal("100.00"), currency="NGN",
            due_date=timezone.localdate() + timedelta(days=10),
        )

    def post_json(self, path, data):
        return self.client.post(path, data=json.dumps(data), content_type="application/json")

    def patch_json(self, path, data):
        return self.client.patch(path, data=json.dumps(data), content_type="application/json")

    def test_user_cannot_view_another_users_debt(self):
        self.client.force_login(self.other)
        response = self.client.get(f"/api/debts/{self.debt.pk}/")
        self.assertEqual(response.status_code, 404)

    def test_cannot_create_debt_for_another_users_client(self):
        self.client.force_login(self.owner)
        response = self.post_json("/api/debts/", {
            "client_id": self.other_client.pk,
            "description": "Foreign client debt",
            "original_amount": "100.00",
            "due_date": (timezone.localdate() + timedelta(days=10)).isoformat(),
        })
        self.assertEqual(response.status_code, 404)

    def test_cannot_create_debt_for_archived_client(self):
        self.client_record.is_archived = True
        self.client_record.save(update_fields=["is_archived"])
        self.client.force_login(self.owner)
        response = self.post_json("/api/debts/", {
            "client_id": self.client_record.pk,
            "description": "Archived client debt",
            "original_amount": "100.00",
            "due_date": (timezone.localdate() + timedelta(days=10)).isoformat(),
        })
        self.assertEqual(response.status_code, 404)

    def test_original_amount_cannot_be_less_than_confirmed_payments(self):
        Payment.objects.create(
            owner=self.owner, debt=self.debt, amount=Decimal("80.00"),
            payment_date=timezone.localdate(), method="bank_transfer",
            reference="TEST-80", status=Payment.Status.CONFIRMED,
            recorded_by=self.owner,
        )
        self.client.force_login(self.owner)
        response = self.patch_json(f"/api/debts/{self.debt.pk}/", {"original_amount": "50.00"})
        self.assertEqual(response.status_code, 400)
        self.debt.refresh_from_db()
        self.assertEqual(self.debt.original_amount, Decimal("100.00"))

    def test_increasing_paid_debt_amount_recalculates_status(self):
        Payment.objects.create(
            owner=self.owner, debt=self.debt, amount=Decimal("100.00"),
            payment_date=timezone.localdate(), method="bank_transfer",
            reference="TEST-FULL", status=Payment.Status.CONFIRMED,
            recorded_by=self.owner,
        )
        self.debt.status = Debt.Status.PAID
        self.debt.save(update_fields=["status"])
        self.client.force_login(self.owner)
        response = self.patch_json(f"/api/debts/{self.debt.pk}/", {"original_amount": "150.00"})
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["status"], Debt.Status.PARTIAL)
