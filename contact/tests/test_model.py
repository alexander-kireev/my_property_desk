"""Contact model behaviour."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from ..models import Contact, ContactMethod
from .support import ContactTestMixin


class ContactModelTests(ContactTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()

    def test_contact_defaults_and_string_value(self):
        contact = self.create_contact(self.user, last_name="Smith")

        self.assertEqual(contact.state, Contact.State.ACTIVE)
        self.assertIsNone(contact.deleted_at)
        self.assertEqual(str(contact), "Alice Smith")

    def test_contact_string_value_handles_missing_last_name(self):
        contact = self.create_contact(self.user)

        self.assertEqual(str(contact), "Alice")

    def test_contact_method_validates_value_for_its_type(self):
        contact = self.create_contact(self.user)
        valid_email = ContactMethod(
            contact=contact,
            type=ContactMethod.Type.EMAIL,
            value="person@example.com",
        )
        valid_phone = ContactMethod(
            contact=contact,
            type=ContactMethod.Type.TELEPHONE,
            value="+447700900123",
        )

        valid_email.full_clean()
        valid_phone.full_clean()

        for type, value in (
            (ContactMethod.Type.EMAIL, "not-an-email"),
            (ContactMethod.Type.TELEPHONE, "07700 900123"),
        ):
            with self.subTest(type=type):
                method = ContactMethod(contact=contact, type=type, value=value)
                with self.assertRaises(ValidationError):
                    method.full_clean()

    def test_contact_method_normalises_email_and_rejects_same_contact_duplicate(self):
        contact = self.create_contact(self.user)
        other_contact = self.create_contact(self.user, "Bob")

        method = self.create_method(contact, value=" Alice@Example.COM ")
        same_value_other_contact = self.create_method(
            other_contact,
            value="alice@example.com",
        )

        self.assertEqual(method.value, "alice@example.com")
        self.assertEqual(same_value_other_contact.value, "alice@example.com")

        with self.assertRaises(IntegrityError), transaction.atomic():
            self.create_method(contact, value="ALICE@example.com")

    def test_hard_deleting_contact_cascades_to_methods(self):
        contact = self.create_contact(self.user)
        self.create_method(contact)

        contact.delete()

        self.assertFalse(ContactMethod.objects.exists())
