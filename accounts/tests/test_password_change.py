"""Accounts password change behaviour."""

from django.contrib import auth
from django.test import TestCase
from django.urls import reverse

from .support import UserAccountManagementFixture


class UserAccountManagementPasswordChangeTests(UserAccountManagementFixture, TestCase):
    def test_protected_password_change_with_invalid_new_password_is_rejected(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)

        post_response = self.client.post(
            reverse("accounts:change_password"),
            {
                "old_password": self.USER_1["password"],
                "new_password1": "password",
                "new_password2": "password",
            },
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["password_form"].errors)
        self.assertIsNone(response.context["password_form"]["old_password"].value())
        self.assertIsNone(response.context["password_form"]["new_password1"].value())
        self.assertEqual(response.context["open_modal"], "changePasswordModal")
        self.assertRegex(response.content.decode(), r"data-validation-help\s+hidden")

        fresh_response = self.client.get(reverse("accounts:profile_page"))
        self.assertContains(fresh_response, "data-validation-help>Use at least eight characters")

        user.refresh_from_db()
        self.assertTrue(user.check_password(self.USER_1["password"]))
        self.assertFalse(user.check_password("password"))

    def test_protected_password_change_with_valid_new_password_is_successful(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)

        response = self.client.post(
            reverse("accounts:change_password"),
            {
                "old_password": self.USER_1["password"],
                "new_password1": self.NEW_PASSWORD,
                "new_password2": self.NEW_PASSWORD,
            },
        )

        self.assertRedirects(response, reverse("accounts:profile_page"))

        user.refresh_from_db()
        self.assertTrue(user.check_password(self.NEW_PASSWORD))
        self.assertFalse(user.check_password(self.USER_1["password"]))
        self.assertTrue(auth.get_user(self.client).is_authenticated)

    def test_protected_password_change_with_incorrect_current_password_is_rejected(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)

        post_response = self.client.post(
            reverse("accounts:change_password"),
            {
                "old_password": f"{self.USER_1['password']}_invalid",
                "new_password1": self.NEW_PASSWORD,
                "new_password2": self.NEW_PASSWORD,
            },
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["password_form"].errors)
        self.assertIsNone(response.context["password_form"]["old_password"].value())
        self.assertIsNone(response.context["password_form"]["new_password1"].value())
        self.assertEqual(response.context["open_modal"], "changePasswordModal")

        user.refresh_from_db()
        self.assertTrue(user.check_password(self.USER_1["password"]))
        self.assertFalse(user.check_password(self.NEW_PASSWORD))
