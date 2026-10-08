"""Registration retries and mail failures must leave an honest, usable outcome."""

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.email_change import confirm_email_change, token_digest
from accounts.forms import EmailChangeForm, PendingRegistrationForm
from accounts.models import PendingEmailChange, PendingRegistration, User
from accounts.tokens import create_confirmation_token


@override_settings(PMS_REGISTRATION_MODE="pending")
class RegistrationRecoveryTests(TestCase):
    def data(self):
        return {
            "first_name": "Amelia",
            "last_name": "Manager",
            "email": "retry@example.invalid",
            "password_1": "ValidPassword123!",
            "password_2": "ValidPassword123!",
        }

    def test_expired_registration_can_be_replaced_and_old_token_is_invalid(self):
        old = PendingRegistration.objects.create(
            first_name="Old",
            last_name="Name",
            email=self.data()["email"],
            expires_at=timezone.now() - timedelta(seconds=1),
        )
        old_token = create_confirmation_token(old)
        response = self.client.post(reverse("accounts:register"), self.data())
        self.assertRedirects(response, reverse("accounts:registration_pending"))
        replacement = PendingRegistration.objects.get(email=old.email)
        self.assertNotEqual(replacement.pk, old.pk)
        self.assertTrue(replacement.check_password(self.data()["password_1"]))
        self.assertEqual(
            self.client.get(reverse("accounts:confirm_registration", args=[old_token])).status_code,
            400,
        )
        token = create_confirmation_token(replacement)
        self.assertEqual(
            self.client.get(reverse("accounts:confirm_registration", args=[token])).status_code, 302
        )
        self.assertEqual(
            self.client.get(reverse("accounts:confirm_registration", args=[token])).status_code, 400
        )

    def test_failed_delivery_leaves_retry_possible_without_storing_passwords(self):
        for outcome in (OSError("simulated mail failure"), 0):
            with self.subTest(outcome=type(outcome).__name__):
                mail_options = (
                    {"side_effect": outcome}
                    if isinstance(outcome, Exception)
                    else {"return_value": outcome}
                )
                with patch("accounts.registration.send_mail", **mail_options):
                    response = self.client.post(reverse("accounts:register"), self.data())
                self.assertEqual(response.status_code, 302)
                self.assertFalse(
                    PendingRegistration.objects.filter(email=self.data()["email"]).exists()
                )
                self.assertNotIn(self.data()["password_1"], str(dict(self.client.session)))
                restored = self.client.get(response.url)
                self.assertContains(restored, "Please try again.")
                self.assertTrue(PendingRegistrationForm(self.data()).is_valid())
        response = self.client.post(reverse("accounts:register"), self.data())
        self.assertRedirects(response, reverse("accounts:registration_pending"))

    def test_live_pending_registration_still_blocks_case_variant_retry(self):
        PendingRegistration.objects.create(email=self.data()["email"])
        data = self.data()
        data["email"] = data["email"].upper()
        form = PendingRegistrationForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_password_similarity_uses_submitted_identity(self):
        data = self.data()
        data["first_name"] = "DistinctiveRegistrationName"
        data["password_1"] = data["password_2"] = data["first_name"]
        form = PendingRegistrationForm(data)
        self.assertFalse(form.is_valid())
        self.assertIn("password_1", form.errors)


class EmailChangeRecoveryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="old@example.invalid", password="ValidPassword123!"
        )
        self.pending = PendingEmailChange.objects.create(
            user=self.user,
            old_email=self.user.email,
            new_email="new@example.invalid",
            token_hash=token_digest("local-token"),
        )

    def test_expired_registration_does_not_reserve_new_email(self):
        PendingRegistration.objects.create(
            email=self.pending.new_email, expires_at=timezone.now() - timedelta(seconds=1)
        )
        form = EmailChangeForm(
            {"new_email": self.pending.new_email, "current_password": "ValidPassword123!"},
            user=self.user,
        )
        self.assertTrue(form.is_valid(), form.errors)
        confirm_email_change("local-token")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, self.pending.new_email)

    def test_notification_failure_does_not_escape_after_commit(self):
        for outcome in (OSError("simulated notification failure"), 0):
            with self.subTest(outcome=type(outcome).__name__):
                options = (
                    {"side_effect": outcome}
                    if isinstance(outcome, Exception)
                    else {"return_value": outcome}
                )
                # Each subcase needs a fresh, independently confirmable request.
                self.user.refresh_from_db()
                token = "token-" + str(type(outcome).__name__)
                target = "changed-" + str(type(outcome).__name__).lower() + "@example.invalid"
                PendingEmailChange.objects.update_or_create(
                    user=self.user,
                    defaults={
                        "old_email": self.user.email,
                        "new_email": target,
                        "token_hash": token_digest(token),
                    },
                )
                with (
                    patch("accounts.email_change.send_mail", **options),
                    self.captureOnCommitCallbacks(execute=True),
                ):
                    confirm_email_change(token)
                self.user.refresh_from_db()
                self.assertEqual(self.user.email, target)
                self.assertFalse(PendingEmailChange.objects.filter(user=self.user).exists())
