"""Accounts password reset behaviour."""

from datetime import datetime, timedelta
from unittest.mock import patch

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .support import UserAccountManagementFixture


class UserAccountManagementPasswordResetTests(UserAccountManagementFixture, TestCase):
    def test_protected_password_reset_request_sends_token_to_email(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)

        response = self.client.post(reverse("accounts:reset_password_protected"))

        self.assertRedirects(response, reverse("accounts:profile_page"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [user.email])
        self.assertIn("/accounts/password/reset/", mail.outbox[0].body)

    def test_password_reset_with_valid_token_is_successful(self):
        user = self.create_user(self.USER_1)
        password_reset_form_url = self.open_password_reset_form(user)

        response = self.client.post(
            password_reset_form_url,
            {
                "new_password1": self.NEW_PASSWORD,
                "new_password2": self.NEW_PASSWORD,
            },
        )

        self.assertRedirects(response, reverse("accounts:password_reset_complete"))

        user.refresh_from_db()
        self.assertTrue(user.check_password(self.NEW_PASSWORD))
        self.assertFalse(user.check_password(self.USER_1["password"]))

    @override_settings(PASSWORD_RESET_TIMEOUT=3600)
    def test_password_reset_with_expired_token_is_rejected(self):
        user = self.create_user(self.USER_1)

        two_hours_ago = datetime.now() - timedelta(hours=2)

        with patch.object(default_token_generator, "_now", return_value=two_hours_ago):
            token = default_token_generator.make_token(user)

        response = self.client.get(self.create_password_reset_url(user, token))

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["validlink"])

        user.refresh_from_db()
        self.assertTrue(user.check_password(self.USER_1["password"]))

    def test_password_reset_with_used_token_is_rejected(self):
        user = self.create_user(self.USER_1)
        token = default_token_generator.make_token(user)
        password_reset_form_url = self.open_password_reset_form(user, token)

        response = self.client.post(
            password_reset_form_url,
            {
                "new_password1": self.NEW_PASSWORD,
                "new_password2": self.NEW_PASSWORD,
            },
        )

        self.assertRedirects(response, reverse("accounts:password_reset_complete"))

        reused_token_response = self.client.get(self.create_password_reset_url(user, token))

        self.assertEqual(reused_token_response.status_code, 200)
        self.assertFalse(reused_token_response.context["validlink"])

    def test_password_reset_with_invalid_new_password_is_rejected(self):
        user = self.create_user(self.USER_1)
        password_reset_form_url = self.open_password_reset_form(user)

        post_response = self.client.post(
            password_reset_form_url,
            {
                "new_password1": "password",
                "new_password2": "password",
            },
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertIsNone(response.context["form"]["new_password1"].value())
        self.assertIsNone(response.context["form"]["new_password2"].value())
        self.assertNotContains(response, 'class="form-text"')

        user.refresh_from_db()
        self.assertTrue(user.check_password(self.USER_1["password"]))
        self.assertFalse(user.check_password("password"))
