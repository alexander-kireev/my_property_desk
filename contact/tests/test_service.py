"""Contact service behaviour."""

from django.test import TestCase

from ..models import Contact, ContactMethod
from ..services import (
    create_contact,
    create_contact_method,
    deactivate_contact,
    delete_contact,
    delete_contact_method,
    reactivate_contact,
    update_contact,
    update_contact_method,
)
from .support import ContactTestMixin


class ContactServiceTests(ContactTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()

    def test_create_contact_persists_initial_methods(self):
        contact = create_contact(
            user=self.user,
            first_name="Alice",
            last_name="Smith",
            email="alice@example.com",
            telephone="+447700900123",
        )

        self.assertEqual(contact.user, self.user)
        self.assertEqual(contact.contact_methods.count(), 2)
        self.assertSetEqual(
            set(contact.contact_methods.values_list("type", "value")),
            {
                (ContactMethod.Type.EMAIL, "alice@example.com"),
                (ContactMethod.Type.TELEPHONE, "+447700900123"),
            },
        )

    def test_create_contact_allows_no_initial_methods(self):
        contact = create_contact(user=self.user, first_name="Alice")

        self.assertFalse(contact.contact_methods.exists())

    def test_update_contact_preserves_owner_and_lifecycle(self):
        contact = self.create_contact(self.user)

        update_contact(contact=contact, first_name="Alicia", last_name="Jones")
        contact.refresh_from_db()

        self.assertEqual(str(contact), "Alicia Jones")
        self.assertEqual(contact.user, self.user)
        self.assertEqual(contact.state, Contact.State.ACTIVE)

    def test_contact_lifecycle_services_are_idempotent(self):
        contact = self.create_contact(self.user)

        deactivate_contact(contact=contact)
        deactivate_contact(contact=contact)
        self.assertEqual(contact.state, Contact.State.DEACTIVATED)

        reactivate_contact(contact=contact)
        reactivate_contact(contact=contact)
        self.assertEqual(contact.state, Contact.State.ACTIVE)

        delete_contact(contact=contact)
        original_deleted_at = contact.deleted_at
        delete_contact(contact=contact)
        self.assertEqual(contact.deleted_at, original_deleted_at)

    def test_contact_method_services_create_update_and_delete(self):
        contact = self.create_contact(self.user)
        method = create_contact_method(
            contact=contact,
            type=ContactMethod.Type.EMAIL,
            value="alice@example.com",
        )

        update_contact_method(
            contact_method=method,
            type=ContactMethod.Type.TELEPHONE,
            value="+447700900123",
        )
        method.refresh_from_db()
        self.assertEqual(method.type, ContactMethod.Type.TELEPHONE)

        delete_contact_method(contact_method=method)
        self.assertFalse(ContactMethod.objects.filter(pk=method.pk).exists())
