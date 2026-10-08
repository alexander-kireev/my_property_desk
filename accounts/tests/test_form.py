"""Accounts form behaviour."""

from django.test import TestCase, override_settings

from ..forms import EmailChangeForm, PendingRegistrationForm
from ..models import PendingRegistration, User


@override_settings(PMS_REGISTRATION_MODE="pending")
class PendingRegistrationFormTests(TestCase):
    VALID_DATA = {
        "first_name": "  Alice  ",
        "last_name": "  Smith  ",
        "email": "  ALICE.smith@EXAMPLE.com  ",
        "password_1": "HolidayHome123!",
        "password_2": "HolidayHome123!",
    }

    def test_valid_registration_form(self):
        form = PendingRegistrationForm(data=self.VALID_DATA)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["first_name"], "Alice")
        self.assertEqual(form.cleaned_data["last_name"], "Smith")
        self.assertEqual(form.cleaned_data["email"], "alice.smith@example.com")

    def test_name_and_email_limits(self):
        for field, length in (("first_name", 50), ("last_name", 50), ("email", 254)):
            data = self.VALID_DATA.copy()
            data[field] = (
                ("a" * (length - 12) + "@example.com") if field == "email" else "A" * length
            )
            self.assertTrue(PendingRegistrationForm(data=data).is_valid(), field)
            data[field] = (
                ("a" * (length - 11) + "@example.com") if field == "email" else "A" * (length + 1)
            )
            form = PendingRegistrationForm(data=data)
            self.assertFalse(form.is_valid())
            self.assertIn(field, form.errors)

    def test_weak_passwords_are_rejected(self):
        data = self.VALID_DATA.copy()
        data["password_1"] = "Password"
        data["password_2"] = data["password_1"]

        form = PendingRegistrationForm(data=data)

        self.assertFalse(form.is_valid())
        self.assertIn("password_1", form.errors)

    def test_missing_last_name(self):
        data = self.VALID_DATA.copy()
        data["last_name"] = "   "

        form = PendingRegistrationForm(data=data)

        self.assertFalse(form.is_valid())
        self.assertIn("last_name", form.errors)

    def test_invalid_email(self):
        data = self.VALID_DATA.copy()
        data["email"] = "invalid.email.com"

        form = PendingRegistrationForm(data=data)

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_passwords_dont_match(self):
        data = self.VALID_DATA.copy()
        data["password_2"] = "DifferentStrongPassword12!"

        form = PendingRegistrationForm(data=data)

        self.assertFalse(form.is_valid())
        self.assertIn("password_2", form.errors)

    def test_duplicate_email_in_pending_registration(self):
        pending_registration = PendingRegistration(
            first_name="Pending",
            last_name="User",
            email="pending@email.com",
        )

        pending_registration.set_password(self.VALID_DATA["password_1"])
        pending_registration.save()

        data = self.VALID_DATA.copy()
        data["email"] = "PENDING@EMAIL.COM"

        form = PendingRegistrationForm(data=data)

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_duplicate_email_in_users(self):
        User.objects.create_user(
            first_name="Existing",
            last_name="User",
            email="existing@email.com",
            password=self.VALID_DATA["password_1"],
        )

        data = self.VALID_DATA.copy()
        data["email"] = "EXISTING@EMAIL.COM"

        form = PendingRegistrationForm(data=data)

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)


class EmailChangeFormLimitTests(TestCase):
    def test_new_email_limit(self):
        user = User.objects.create_user(email="current@example.com", password="HolidayHome123!")
        valid_email = "a" * 242 + "@example.com"
        form = EmailChangeForm(
            data={"new_email": valid_email, "current_password": "HolidayHome123!"}, user=user
        )
        self.assertTrue(form.is_valid(), form.errors)

        form = EmailChangeForm(
            data={"new_email": "a" + valid_email, "current_password": "HolidayHome123!"}, user=user
        )
        self.assertFalse(form.is_valid())
        self.assertIn("new_email", form.errors)
