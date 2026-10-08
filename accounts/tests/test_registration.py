"""Accounts registration behaviour."""

from datetime import timedelta

from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from ..forms import PendingRegistrationForm
from ..models import PendingRegistration, User
from ..tokens import create_confirmation_token


@override_settings(PMS_REGISTRATION_MODE="pending")
class RegistrationViewTests(TestCase):
    VALID_DATA = {
        "first_name": "  Alice  ",
        "last_name": "  Smith  ",
        "email": "alice.smith@example.com",
        "password_1": "HolidayHome123!",
        "password_2": "HolidayHome123!",
    }

    VALID_CLEANED_DATA = {
        "first_name": "Alice",
        "last_name": "Smith",
        "email": "alice.smith@example.com",
        "password_1": "HolidayHome123!",
        "password_2": "HolidayHome123!",
    }

    def create_valid_pending_registration(self):
        pending_registration = PendingRegistration(
            first_name=self.VALID_CLEANED_DATA["first_name"],
            last_name=self.VALID_CLEANED_DATA["last_name"],
            email=self.VALID_CLEANED_DATA["email"],
        )

        pending_registration.set_password(self.VALID_CLEANED_DATA["password_1"])

        return pending_registration

    def create_valid_pending_registration_and_token_and_return(self):
        pending_registration = self.create_valid_pending_registration()
        pending_registration.save()

        token = create_confirmation_token(pending_registration)

        confirmation_url = reverse("accounts:confirm_registration", kwargs={"token": token})

        response = self.client.get(confirmation_url)

        return {
            "token": token,
            "pending_registration": pending_registration,
            "confirmation_url": confirmation_url,
            "response": response,
            "pk": pending_registration.pk,
        }

    def test_get_registration_page(self):
        response = self.client.get(reverse("accounts:register"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "accounts/register.html")
        self.assertIsInstance(response.context["form"], PendingRegistrationForm)

    def test_invalid_post_does_not_create_pending_registration(self):
        data = self.VALID_DATA.copy()
        data["password_2"] = "DifferentPassword12!"

        post_response = self.client.post(reverse("accounts:register"), data=data)

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("password_2", response.context["form"].errors)
        self.assertIsNone(response.context["form"]["email"].value())
        self.assertIsNone(response.context["form"]["password_1"].value())
        self.assertIsNone(response.context["form"]["password_2"].value())
        self.assertEqual(PendingRegistration.objects.count(), 0)

    def test_valid_post_creates_pending_registration(self):
        response = self.client.post(reverse("accounts:register"), data=self.VALID_DATA)

        self.assertRedirects(response, reverse("accounts:registration_pending"))
        pending_registration = PendingRegistration.objects.get(email=self.VALID_DATA["email"])
        self.assertEqual(pending_registration.first_name, self.VALID_CLEANED_DATA["first_name"])
        self.assertEqual(pending_registration.last_name, self.VALID_CLEANED_DATA["last_name"])
        self.assertTrue(pending_registration.check_password(self.VALID_DATA["password_1"]))
        self.assertNotEqual(pending_registration.password_hash, self.VALID_DATA["password_1"])
        self.assertEqual(len(mail.outbox), 1)

        sent_email = mail.outbox[0]

        self.assertEqual(sent_email.to, [self.VALID_DATA["email"]])

        self.assertEqual(sent_email.subject, "Confirm your registration")

        self.assertIn(
            "http://testserver/accounts/confirm/",
            sent_email.body,
        )

    def test_pending_registration_deleted_after_user_created_and_user_is_created(self):
        r = self.create_valid_pending_registration_and_token_and_return()

        self.assertTrue(User.objects.filter(email=self.VALID_CLEANED_DATA["email"]).exists())
        self.assertFalse(PendingRegistration.objects.filter(pk=r["pk"]).exists())

    def test_invalid_token_returns_400_and_does_not_create_user_and_does_not_delete_pending_request(
        self,
    ):
        pending_registration = self.create_valid_pending_registration()
        pending_registration.save()

        token = create_confirmation_token(pending_registration)
        token = token + "invalid_token"

        confirmation_url = reverse("accounts:confirm_registration", kwargs={"token": token})

        response = self.client.get(confirmation_url)

        self.assertEqual(response.status_code, 400)
        self.assertTemplateUsed(response, "accounts/confirm_registration.html")

        pending_registration_id = pending_registration.pk

        self.assertTrue(PendingRegistration.objects.filter(pk=pending_registration_id).exists())
        self.assertFalse(User.objects.filter(email=pending_registration.email).exists())

    def test_expired_registration_returns_400_and_does_not_create_user_and_does_not_delete_pending_request(
        self,
    ):
        pending_registration = self.create_valid_pending_registration()

        pending_registration.expires_at = timezone.now() - timedelta(seconds=1)

        pending_registration.save()

        token = create_confirmation_token(pending_registration)

        confirmation_url = reverse("accounts:confirm_registration", kwargs={"token": token})

        response = self.client.get(confirmation_url)

        self.assertEqual(response.status_code, 400)

        self.assertEqual(User.objects.count(), 0)
        self.assertTrue(PendingRegistration.objects.filter(pk=pending_registration.pk).exists())

    def test_reused_token_returns_is_rejected_and_does_not_create_duplicate_user(self):
        r = self.create_valid_pending_registration_and_token_and_return()

        self.assertTrue(User.objects.filter(email=self.VALID_CLEANED_DATA["email"]).exists())
        self.assertFalse(PendingRegistration.objects.filter(pk=r["pk"]).exists())

        response_2 = self.client.get(r["confirmation_url"])

        self.assertEqual(response_2.status_code, 400)
        self.assertTemplateUsed(response_2, "accounts/confirm_registration.html")

        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(PendingRegistration.objects.count(), 0)

    def test_valid_token_creates_and_authenticates_user(self):
        r = self.create_valid_pending_registration_and_token_and_return()

        self.assertTrue(User.objects.filter(email=self.VALID_CLEANED_DATA["email"]).exists())

        self.assertRedirects(r["response"], reverse("pages:dashboard"))

        dashboard_response = self.client.get(reverse("pages:dashboard"))

        self.assertEqual(dashboard_response.status_code, 200)

    def test_password_works_after_hash_transfer(self):
        r = self.create_valid_pending_registration_and_token_and_return()

        user = User.objects.get(email=r["pending_registration"].email)

        self.assertTrue(user.check_password(self.VALID_DATA["password_1"]))


@override_settings(PMS_REGISTRATION_MODE="instant")
class InstantRegistrationTests(TestCase):
    DATA = RegistrationViewTests.VALID_DATA

    def test_signup_creates_account_and_authenticated_dashboard_session_without_email(self):
        response = self.client.post(reverse("accounts:register"), self.DATA)

        self.assertRedirects(response, reverse("pages:dashboard"))
        user = User.objects.get(email=self.DATA["email"])
        self.assertEqual((user.first_name, user.last_name), ("Alice", "Smith"))
        self.assertTrue(user.check_password(self.DATA["password_1"]))
        self.assertEqual(self.client.session.get("_auth_user_id"), str(user.pk))
        self.assertFalse(PendingRegistration.objects.exists())
        self.assertEqual(len(mail.outbox), 0)

    def test_existing_pending_request_is_replaced_and_its_link_expires(self):
        pending = PendingRegistration.objects.create(
            first_name="Older", last_name="Person", email=self.DATA["email"]
        )
        pending.set_password("OlderPassword123!")
        pending.save(update_fields=["password_hash"])
        old_token = create_confirmation_token(pending)

        response = self.client.post(reverse("accounts:register"), self.DATA)

        self.assertRedirects(response, reverse("pages:dashboard"))
        self.assertFalse(PendingRegistration.objects.exists())
        self.assertEqual(
            self.client.get(reverse("accounts:confirm_registration", args=[old_token])).status_code,
            400,
        )
        self.assertEqual(User.objects.count(), 1)

    def test_duplicate_email_and_invalid_password_do_not_create_another_account(self):
        User.objects.create_user(email=self.DATA["email"], password="ExistingPassword123!")
        duplicate = dict(self.DATA, email=self.DATA["email"].upper())
        response = self.client.post(reverse("accounts:register"), duplicate)
        self.assertEqual(response.status_code, 302)
        self.assertContains(self.client.get(response.url), "already exists", status_code=200)

        invalid = dict(self.DATA, email="new@example.com", password_2="OtherPassword123!")
        response = self.client.post(reverse("accounts:register"), invalid)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(len(mail.outbox), 0)
