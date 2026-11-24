import json

from django.contrib.auth import get_user_model
from django.test import TestCase

from .models import Client

User = get_user_model()


class ClientManagementTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="client_test_user",
            password="TestPassword123!",
        )
        self.other_user = User.objects.create_user(
            username="other_test_user",
            password="TestPassword456!",
        )
        self.client_record = Client.objects.create(
            owner=self.user,
            client_type="business",
            full_name="Test Business",
            email="test@example.com",
            phone="08000000000",
        )

    def test_unauthenticated_user_cannot_access_clients(self):
        response = self.client.get("/api/clients/")
        self.assertIn(response.status_code, [302, 403])

    def test_user_sees_only_their_clients(self):
        self.client.force_login(self.user)
        response = self.client.get("/api/clients/")
        self.assertEqual(response.status_code, 200)
        ids = [item["id"] for item in response.json()["results"]]
        self.assertIn(self.client_record.pk, ids)

    def test_user_cannot_view_another_users_client(self):
        self.client.force_login(self.other_user)
        response = self.client.get(f"/api/clients/{self.client_record.pk}/")
        self.assertEqual(response.status_code, 404)

    def test_client_creation_requires_a_name(self):
        self.client.force_login(self.user)
        response = self.client.post(
            "/api/clients/",
            data=json.dumps({"full_name": "   "}),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    def test_client_type_is_normalized_to_lowercase(self):
        self.client.force_login(self.user)
        response = self.client.post(
            "/api/clients/",
            data=json.dumps({
                "full_name": "New Business",
                "email": "new@example.com",
                "client_type": "BUSINESS",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 201, response.content)
        self.assertEqual(response.json()["client"]["client_type"], "business")

    def test_invalid_client_type_is_rejected(self):
        self.client.force_login(self.user)
        response = self.client.post(
            "/api/clients/",
            data=json.dumps({
                "full_name": "Invalid Type",
                "email": "valid@example.com",
                "client_type": "government",
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
