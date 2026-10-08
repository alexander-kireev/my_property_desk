"""Accounts password reset behaviour."""

from datetime import datetime, timedelta
from unittest.mock import patch
from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from ..models import PasswordResetRequestBucket
from .support import UserAccountManagementFixture


class UserAccountManagementPasswordResetTests(UserAccountManagementFixture, TestCase):
    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", DEBUG=False)
    def test_public_request_sends_https_link_and_is_not_prefilled(self):
        user = self.create_user(self.USER_1)
        request_url = reverse("accounts:password_reset_request")

        page = self.client.get(request_url)
        self.assertContains(page, 'autocomplete="off"')
        self.assertNotContains(page, f'value="{user.email}"')

        response = self.client.post(request_url, {"email": user.email})
        self.assertRedirects(response, reverse("accounts:password_reset_sent"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [user.email])
        self.assertIn("https://testserver/accounts/password/reset/", mail.outbox[0].body)
        self.assertIn("one hour", mail.outbox[0].body)
        self.assertEqual(settings.PASSWORD_RESET_TIMEOUT, 3600)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_unknown_address_has_same_public_response_without_email(self):
        url = reverse("accounts:password_reset_request")
        unknown = self.client.post(url, {"email": "unknown@example.test"})
        self.assertRedirects(unknown, reverse("accounts:password_reset_sent"))
        self.assertEqual(len(mail.outbox), 0)

        self.create_user(self.USER_1)
        known = self.client.post(url, {"email": self.USER_1["email"]})
        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.url, unknown.url)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(PasswordResetRequestBucket.objects.count(), 3)
        self.assertFalse(
            PasswordResetRequestBucket.objects.filter(key_hash__contains="example").exists()
        )

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_public_requests_are_limited_per_address(self):
        self.create_user(self.USER_1)
        url = reverse("accounts:password_reset_request")
        for _ in range(4):
            response = self.client.post(url, {"email": self.USER_1["email"]})
            self.assertRedirects(response, reverse("accounts:password_reset_sent"))
        self.assertEqual(len(mail.outbox), 3)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    @patch("accounts.password_reset_requests.SOURCE_LIMIT", 2)
    def test_public_requests_are_limited_per_client_source(self):
        self.create_user(self.USER_1)
        url = reverse("accounts:password_reset_request")
        for address in ("first@example.test", "second@example.test"):
            self.client.post(url, {"email": address}, REMOTE_ADDR="192.0.2.10")

        response = self.client.post(url, {"email": self.USER_1["email"]}, REMOTE_ADDR="192.0.2.10")
        self.assertRedirects(response, reverse("accounts:password_reset_sent"))
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_public_link_changes_password_and_can_only_be_used_once(self):
        user = self.create_user(self.USER_1)
        self.client.post(reverse("accounts:password_reset_request"), {"email": user.email})
        link = next(
            line for line in mail.outbox[0].body.splitlines() if "/accounts/password/reset/" in line
        )
        first_response = self.client.get(urlsplit(link).path)
        self.assertEqual(first_response.status_code, 302)
        form_url = first_response.url

        changed = self.client.post(
            form_url,
            {"new_password1": self.NEW_PASSWORD, "new_password2": self.NEW_PASSWORD},
        )
        self.assertRedirects(changed, reverse("accounts:password_reset_complete"))
        user.refresh_from_db()
        self.assertTrue(user.check_password(self.NEW_PASSWORD))
        self.assertContains(self.client.get(form_url), "Request a new link")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_delivery_failure_keeps_neutral_response(self):
        self.create_user(self.USER_1)
        with self.assertLogs("accounts.views", level="ERROR"):
            with patch(
                "accounts.views._send_reset_email", side_effect=RuntimeError("Mail unavailable")
            ):
                response = self.client.post(
                    reverse("accounts:password_reset_request"),
                    {"email": self.USER_1["email"]},
                )
        self.assertRedirects(response, reverse("accounts:password_reset_sent"))

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

    def test_password_change_invalidates_existing_signed_in_session(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)
        form_url = self.open_password_reset_form(user)
        self.client.post(
            form_url,
            {"new_password1": self.NEW_PASSWORD, "new_password2": self.NEW_PASSWORD},
        )

        response = self.client.get(reverse("accounts:profile_page"))
        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('accounts:profile_page')}",
        )

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
