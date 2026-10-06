"""Accounts profile behaviour."""

from django.core import mail
from django.test import TestCase
from django.urls import reverse

from ..forms import ProfileForm
from .support import UserAccountManagementFixture, email_change_path


class UserAccountManagementProfileTests(UserAccountManagementFixture, TestCase):
    def test_account_change_forms_load_empty_with_fresh_field_guard(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:profile_page"))
        self.assertContains(response, "data-fresh-account-form", count=3)
        self.assertContains(response, "js/fresh-account-form.js")
        for form_name, fields in (
            ("email_form", ("new_email", "current_password")),
            ("password_form", ("old_password", "new_password1", "new_password2")),
            ("delete_form", ("current_password", "confirmation")),
        ):
            for name in fields:
                with self.subTest(form=form_name, field=name):
                    self.assertIsNone(response.context[form_name][name].value())

        self.assertEqual(self.client.get(reverse("accounts:change_email")).status_code, 405)
        self.assertEqual(self.client.get(reverse("accounts:change_password")).status_code, 405)

    def test_profile_page_loads_for_authenticated_user(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)

        response = self.client.get(reverse("accounts:profile_page"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/profile_page.html")

        form = response.context["profile_form"]
        self.assertIsInstance(form, ProfileForm)
        self.assertEqual(form.instance, user)

    def test_profile_page_does_not_load_for_unauthenticated_user(self):
        response = self.client.get(reverse("accounts:profile_page"))
        self.assertEqual(response.status_code, 302)

    def test_user_can_only_access_own_profile_page(self):
        user_2 = self.create_user(self.USER_2)
        user = self.create_user(self.USER_1)

        self.client.force_login(user)

        response = self.client.get(reverse("accounts:profile_page"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/profile_page.html")

        form = response.context["profile_form"]
        self.assertIsInstance(form, ProfileForm)
        self.assertNotEqual(form.instance, user_2)
        self.assertEqual(form.instance, user)

    def test_old_login_works_until_new_email_is_verified(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)
        target = "alice.verified@example.com"
        self.client.post(
            reverse("accounts:change_email"),
            {"new_email": target, "current_password": self.USER_1["password"]},
        )
        confirmation_path = email_change_path(mail.outbox[-1])

        self.client.logout()
        self.assertTrue(
            self.client.login(username=self.USER_1["email"], password=self.USER_1["password"])
        )
        self.client.logout()
        self.assertFalse(self.client.login(username=target, password=self.USER_1["password"]))
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(confirmation_path)
        self.assertFalse(
            self.client.login(username=self.USER_1["email"], password=self.USER_1["password"])
        )
        self.assertTrue(self.client.login(username=target, password=self.USER_1["password"]))

    def test_valid_profile_name_changes_save_only_the_requested_field(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)
        for field, value in (("first_name", "Alicia"), ("last_name", "Jones")):
            with self.subTest(field=field):
                data = {"first_name": user.first_name, "last_name": user.last_name}
                data[field] = value
                response = self.client.post(reverse("accounts:profile_page"), data)
                self.assertRedirects(response, reverse("accounts:profile_page"))
                user.refresh_from_db()
                self.assertEqual(user.first_name, data["first_name"])
                self.assertEqual(user.last_name, data["last_name"])

    def test_empty_profile_names_restore_errors_without_saving(self):
        user = self.create_user(self.USER_1)
        self.client.force_login(user)
        for field in ("first_name", "last_name"):
            with self.subTest(field=field):
                data = {"first_name": user.first_name, "last_name": user.last_name}
                data[field] = ""
                response = self.client.post(reverse("accounts:profile_page"), data)
                self.assertEqual(response.status_code, 302)
                self.assertIn("form_state=", response.url)
                restored = self.client.get(response.url)
                self.assertEqual(restored.status_code, 200)
                self.assertIn(field, restored.context["profile_form"].errors)
                user.refresh_from_db()
                self.assertEqual(user.first_name, self.USER_1["first_name"])
                self.assertEqual(user.last_name, self.USER_1["last_name"])
