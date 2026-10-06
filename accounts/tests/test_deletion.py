"""Accounts deletion behaviour."""

from unittest.mock import patch

from django.contrib import auth
from django.db import DatabaseError
from django.db.models.signals import post_delete
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from contact.models import Contact, ContactMethod
from event.models import Event, EventContact
from issue.models import Issue
from note.models import Note
from property.models import Property
from task.models import Task

from ..models import User


class AccountDeletionTests(TestCase):
    PASSWORD = "HolidayHome123!"

    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            first_name="Owner",
            last_name="Example",
            password=self.PASSWORD,
        )
        self.other_user = User.objects.create_user(
            email="other@example.com",
            first_name="Other",
            last_name="Example",
            password=self.PASSWORD,
        )
        self.property = Property.objects.create(user=self.user, name="Home")
        self.contact = Contact.objects.create(user=self.user, first_name="Tenant")
        self.method = ContactMethod.objects.create(
            contact=self.contact, type=ContactMethod.Type.EMAIL, value="tenant@example.com"
        )
        self.issue = Issue.objects.create(
            user=self.user, property=self.property, title="Leaking tap"
        )
        self.task = Task.objects.create(user=self.user, issue=self.issue, title="Call plumber")
        self.event = Event.objects.create(
            user=self.user,
            property=self.property,
            title="Inspection",
            scheduled_date=timezone.localdate(),
            all_day=True,
        )
        self.attendance = EventContact.objects.create(event=self.event, contact=self.contact)
        self.note = Note.objects.create(
            user=self.user, contact=self.contact, content="Call before visiting"
        )
        self.dashboard_note = Note.objects.create(user=self.user, content="Review this week")
        self.other_property = Property.objects.create(user=self.other_user, name="Other home")
        self.client.force_login(self.user)

    def delete(self, password=None, confirmation="DELETE"):
        return self.client.post(
            reverse("accounts:delete_account"),
            {
                "current_password": password or self.PASSWORD,
                "confirmation": confirmation,
            },
        )

    def test_delete_requires_post(self):
        self.assertEqual(self.client.get(reverse("accounts:delete_account")).status_code, 405)
        self.assertTrue(User.objects.filter(pk=self.user.pk).exists())

    def test_wrong_password_and_confirmation_keep_account_and_data(self):
        for password, confirmation in (("wrong", "DELETE"), (self.PASSWORD, "delete")):
            with self.subTest(password=password, confirmation=confirmation):
                response = self.delete(password, confirmation)
                self.assertIn("form_state=", response.url)
                page = self.client.get(response.url)
                self.assertEqual(page.context["open_modal"], "deleteAccountConfirmModal")
                self.assertTrue(page.context["delete_form"].errors)
                self.assertIsNone(page.context["delete_form"]["current_password"].value())
                self.assertTrue(User.objects.filter(pk=self.user.pk).exists())
                self.assertTrue(Property.objects.filter(pk=self.property.pk).exists())

    def test_success_cascades_owned_records_and_logs_out(self):
        response = self.delete()
        self.assertRedirects(response, reverse("accounts:delete_account_complete"))
        self.assertFalse(auth.get_user(self.client).is_authenticated)
        for model, pk in (
            (User, self.user.pk),
            (Property, self.property.pk),
            (Contact, self.contact.pk),
            (ContactMethod, self.method.pk),
            (Issue, self.issue.pk),
            (Task, self.task.pk),
            (Event, self.event.pk),
            (EventContact, self.attendance.pk),
            (Note, self.note.pk),
            (Note, self.dashboard_note.pk),
        ):
            with self.subTest(model=model.__name__):
                self.assertFalse(model.objects.filter(pk=pk).exists())
        self.assertTrue(User.objects.filter(pk=self.other_user.pk).exists())
        self.assertTrue(Property.objects.filter(pk=self.other_property.pk).exists())

    def test_failure_rolls_back_and_keeps_session(self):
        for failure in (DatabaseError, RuntimeError):
            with self.subTest(failure=failure.__name__):

                def fail_during_cascade(sender, instance, **kwargs):
                    raise failure("simulated failure")

                post_delete.connect(fail_during_cascade, sender=Property, weak=False)
                try:
                    with patch("accounts.views.logger.exception") as log_failure:
                        response = self.delete()
                finally:
                    post_delete.disconnect(fail_during_cascade, sender=Property)

                log_failure.assert_called_once()
                self.assertIn("form_state=", response.url)
                page = self.client.get(response.url)
                self.assertContains(page, "Please try again later")
                self.assertEqual(page.context["open_modal"], "deleteAccountConfirmModal")
                self.assertTrue(auth.get_user(self.client).is_authenticated)
                for model, pk in (
                    (User, self.user.pk),
                    (Property, self.property.pk),
                    (Contact, self.contact.pk),
                    (Issue, self.issue.pk),
                    (Task, self.task.pk),
                    (Event, self.event.pk),
                    (Note, self.note.pk),
                ):
                    with self.subTest(model=model.__name__):
                        self.assertTrue(model.objects.filter(pk=pk).exists())
