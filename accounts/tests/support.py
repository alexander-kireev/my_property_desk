"""Shared test fixtures and small setup helpers; no tests are defined here."""

from urllib.parse import urlsplit

from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from ..models import User


class UserAccountManagementFixture:
    USER_1 = {
        "first_name": "Alice",
        "last_name": "Smith",
        "email": "alice.smith@example.com",
        "password": "HolidayHome123!",
    }

    USER_2 = {
        "first_name": "Bob",
        "last_name": "Jackson",
        "email": "bob.jackson@example.com",
        "password": "CountryRoad123!",
    }

    NEW_PASSWORD = "NewHolidayHome456!"

    def create_user(self, user_data):
        return User.objects.create_user(
            email=user_data["email"],
            first_name=user_data["first_name"],
            last_name=user_data["last_name"],
            password=user_data["password"],
        )

    def login_user(self, user_data):
        self.client.login(username=user_data["email"], password=user_data["password"])

    def create_password_reset_url(self, user, token=None):
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = token or default_token_generator.make_token(user)

        return reverse(
            "accounts:password_reset_confirm",
            kwargs={"uidb64": uidb64, "token": token},
        )

    def open_password_reset_form(self, user, token=None):
        response = self.client.get(self.create_password_reset_url(user, token))
        self.assertEqual(response.status_code, 302)

        return response.url


def email_change_path(message):
    """Find the confirmation URL, failing clearly if the expected mail is missing it."""
    for line in message.body.splitlines():
        if "/change_email/confirm/" in line:
            return urlsplit(line.strip()).path
    raise AssertionError("Email change confirmation link was not found in the message.")
