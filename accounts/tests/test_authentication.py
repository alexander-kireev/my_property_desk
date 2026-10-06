"""Accounts authentication behaviour."""

from django.contrib import auth
from django.test import TestCase
from django.urls import reverse

from ..models import User


class UserAuthenticationTests(TestCase):
    VALID_CLEANED_DATA = {
        "first_name": "Alice",
        "last_name": "Smith",
        "email": "alice.smith@example.com",
        "password_1": "HolidayHome123!",
        "password_2": "HolidayHome123!",
    }

    def setUp(self):
        User.objects.create_user(
            email=self.VALID_CLEANED_DATA["email"],
            first_name=self.VALID_CLEANED_DATA["first_name"],
            last_name=self.VALID_CLEANED_DATA["last_name"],
            password=self.VALID_CLEANED_DATA["password_1"],
        )

    def test_valid_details_log_user_in(self):
        response = self.client.post(
            reverse("accounts:login"),
            {
                "username": self.VALID_CLEANED_DATA["email"],
                "password": self.VALID_CLEANED_DATA["password_1"],
            },
        )

        self.assertRedirects(response, reverse("pages:dashboard"))
        user = auth.get_user(self.client)
        self.assertTrue(user.is_authenticated)

    def test_invalid_details_do_not_log_user_in(self):
        invalid_password = f"{self.VALID_CLEANED_DATA['password_1']}_invalid"

        post_response = self.client.post(
            reverse("accounts:login"),
            {"username": self.VALID_CLEANED_DATA["email"], "password": invalid_password},
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        user = auth.get_user(self.client)
        self.assertFalse(user.is_authenticated)

        form = response.context["form"]
        self.assertTrue(form.non_field_errors())
        self.assertIsNone(form["password"].value())

    def test_post_request_logs_user_out(self):
        self.client.login(
            email=self.VALID_CLEANED_DATA["email"], password=self.VALID_CLEANED_DATA["password_1"]
        )

        user = auth.get_user(self.client)
        self.assertTrue(user.is_authenticated)

        response = self.client.post(reverse("accounts:logout"))

        self.assertEqual(response.status_code, 302)
        user = auth.get_user(self.client)
        self.assertFalse(user.is_authenticated)

    def test_get_request_does_not_log_user_out(self):
        self.client.login(
            email=self.VALID_CLEANED_DATA["email"], password=self.VALID_CLEANED_DATA["password_1"]
        )

        user = auth.get_user(self.client)
        self.assertTrue(user.is_authenticated)

        response = self.client.get(reverse("accounts:logout"))

        self.assertEqual(response.status_code, 405)
        user = auth.get_user(self.client)
        self.assertTrue(user.is_authenticated)
