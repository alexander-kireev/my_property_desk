"""Accounts email change behaviour."""

from datetime import timedelta

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ..models import PendingEmailChange, User
from .support import UserAccountManagementFixture, email_change_path


class UserAccountManagementEmailChangeTests(UserAccountManagementFixture, TestCase):
    def test_email_change_valid_form_and_valid_password_is_successful(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)

        new_email = "alice.new@example.com"

        response = self.client.post(
            reverse("accounts:change_email"),
            {
                "new_email": new_email,
                "current_password": self.USER_1["password"],
            },
        )

        self.assertRedirects(response, reverse("accounts:profile_page"))

        user.refresh_from_db()
        self.assertEqual(user.email, self.USER_1["email"])
        self.assertEqual(PendingEmailChange.objects.get(user=user).new_email, new_email)
        self.assertEqual(mail.outbox[-1].to, [new_email])

        confirmation_url = email_change_path(mail.outbox[-1])
        confirmation_path = confirmation_url
        self.assertEqual(self.client.get(confirmation_path).status_code, 200)
        user.refresh_from_db()
        self.assertEqual(user.email, self.USER_1["email"])

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(confirmation_path)
        self.assertRedirects(response, reverse("accounts:email_change_complete"))
        user.refresh_from_db()
        self.assertEqual(user.email, new_email)
        self.assertFalse(PendingEmailChange.objects.filter(user=user).exists())
        self.assertEqual(mail.outbox[-1].to, [self.USER_1["email"]])
        self.assertEqual(self.client.post(confirmation_path).status_code, 400)

    def test_email_change_link_expires_and_replaced_link_cannot_be_used(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)
        self.client.post(
            reverse("accounts:change_email"),
            {"new_email": "first@example.com", "current_password": self.USER_1["password"]},
        )
        first_path = email_change_path(mail.outbox[-1])
        self.client.post(
            reverse("accounts:change_email"),
            {"new_email": "second@example.com", "current_password": self.USER_1["password"]},
        )
        self.assertEqual(self.client.post(first_path).status_code, 400)
        pending = PendingEmailChange.objects.get(user=user)
        pending.expires_at = timezone.now() - timedelta(seconds=1)
        pending.save(update_fields=["expires_at"])
        second_path = email_change_path(mail.outbox[-1])
        self.assertEqual(self.client.post(second_path).status_code, 400)
        user.refresh_from_db()
        self.assertEqual(user.email, self.USER_1["email"])

    def test_email_change_rejects_address_taken_after_request(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)
        target = "later@example.com"
        self.client.post(
            reverse("accounts:change_email"),
            {"new_email": target, "current_password": self.USER_1["password"]},
        )
        confirmation_path = email_change_path(mail.outbox[-1])
        User.objects.create_user(email=target, password="StrongPassword123!")
        self.assertEqual(self.client.post(confirmation_path).status_code, 409)
        user.refresh_from_db()
        self.assertEqual(user.email, self.USER_1["email"])

    def test_email_change_taken_email_is_rejected(self):
        user = self.create_user(self.USER_1)
        user_2 = self.create_user(self.USER_2)
        self.client.force_login(user)

        post_response = self.client.post(
            reverse("accounts:change_email"),
            {
                "new_email": user_2.email,
                "current_password": self.USER_1["password"],
            },
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("form_state=", post_response.url)
        self.assertNotIn("modal=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["email_form"].errors)
        self.assertEqual(response.context["email_form"]["new_email"].value(), user_2.email)
        self.assertIsNone(response.context["email_form"]["current_password"].value())
        self.assertContains(response, "data-preserve-restored-email")
        self.assertEqual(response.context["open_modal"], "changeEmailModal")
        self.assertContains(response, 'data-modal-auto-open="changeEmailModal"')
        self.assertContains(response, 'data-modal-clear-query="form_state modal"', count=3)
        self.assertContains(response, "js/profile-modal-state.js")

        # The session token is one-use, even if the browser revisits the same URL.
        fresh_response = self.client.get(post_response.url)
        self.assertIsNone(fresh_response.context["email_form"]["new_email"].value())
        self.assertIsNone(fresh_response.context["email_form"]["current_password"].value())
        self.assertIsNone(fresh_response.context["open_modal"])
        self.assertNotContains(fresh_response, 'data-modal-auto-open="changeEmailModal"')

        user.refresh_from_db()
        self.assertEqual(user.email, self.USER_1["email"])

    def test_email_change_valid_email_invalid_password_is_rejected(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)

        new_email = "alice.new@example.com"

        post_response = self.client.post(
            reverse("accounts:change_email"),
            {
                "new_email": new_email,
                "current_password": f"{self.USER_1['password']}_invalid",
            },
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["email_form"].errors)
        self.assertEqual(response.context["email_form"]["new_email"].value(), new_email)
        self.assertIsNone(response.context["email_form"]["current_password"].value())
        self.assertContains(response, "data-preserve-restored-email")
        self.assertEqual(response.context["open_modal"], "changeEmailModal")

        user.refresh_from_db()
        self.assertEqual(user.email, self.USER_1["email"])

    def test_email_change_does_not_require_typed_email_confirmation(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)

        post_response = self.client.post(
            reverse("accounts:change_email"),
            {
                "new_email": "alice.new@example.com",
                "current_password": self.USER_1["password"],
            },
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertEqual(post_response.url, reverse("accounts:profile_page"))

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context["email_form"].errors)
        self.assertContains(response, "Verification pending")

        user.refresh_from_db()
        self.assertEqual(user.email, self.USER_1["email"])
