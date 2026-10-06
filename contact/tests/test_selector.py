"""Contact selector behaviour."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from ..models import Contact, ContactMethod
from ..selectors import (
    contact_methods_for_contact,
    contacts_for_user,
    filtered_contacts_for_user,
)
from .support import ContactTestMixin


class ContactSelectorTests(ContactTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.other_user = self.create_user("bob@example.com")

    def test_contacts_for_user_scopes_owner_and_soft_deletion(self):
        visible = self.create_contact(self.user)
        self.create_contact(self.other_user, "Bob")
        self.create_contact(self.user, "Deleted", deleted_at=timezone.now())

        self.assertEqual(list(contacts_for_user(user=self.user)), [visible])

    def test_contacts_for_user_prefetches_methods(self):
        contact = self.create_contact(self.user)
        method = self.create_method(contact)

        with self.assertNumQueries(2):
            contacts = list(contacts_for_user(user=self.user))
            self.assertEqual(list(contacts[0].contact_methods.all()), [method])

    def test_contacts_for_user_summarises_first_email_and_telephone(self):
        contact = self.create_contact(self.user)
        self.create_method(contact, value="first@example.com")
        self.create_method(contact, value="second@example.com")
        self.create_method(
            contact,
            type=ContactMethod.Type.TELEPHONE,
            value="+447700900001",
        )
        self.create_method(
            contact,
            type=ContactMethod.Type.TELEPHONE,
            value="+447700900002",
        )

        summary = contacts_for_user(user=self.user).get(pk=contact.pk)

        self.assertEqual(summary.first_email, "first@example.com")
        self.assertEqual(summary.first_telephone, "+447700900001")

    def test_primary_methods_include_methods_outside_search_match(self):
        contact = self.create_contact(self.user)
        self.create_method(contact, value="findme@example.com")
        self.create_method(contact, value="other@example.com")
        self.create_method(contact, type=ContactMethod.Type.TELEPHONE, value="+447700900001")

        summary = filtered_contacts_for_user(user=self.user, search="findme").get(pk=contact.pk)

        self.assertEqual(summary.first_email, "findme@example.com")
        self.assertEqual(summary.first_telephone, "+447700900001")

    def test_search_matches_names_and_contact_method_values(self):
        first_name_match = self.create_contact(self.user, "Alex")
        last_name_match = self.create_contact(
            self.user,
            "Morgan",
            last_name="Alexander",
        )
        email_match = self.create_contact(self.user, "Email")
        phone_match = self.create_contact(self.user, "Phone")
        self.create_method(email_match, value="alex@example.com")
        self.create_method(
            phone_match,
            type=ContactMethod.Type.TELEPHONE,
            value="+441234567890",
        )

        result = filtered_contacts_for_user(user=self.user, search="alex")
        self.assertEqual(
            set(result),
            {first_name_match, last_name_match, email_match},
        )
        self.assertEqual(
            list(filtered_contacts_for_user(user=self.user, search="123456")),
            [phone_match],
        )

    def test_search_returns_each_contact_once(self):
        contact = self.create_contact(self.user, "Alice")
        self.create_method(contact, value="alice@example.com")
        self.create_method(
            contact,
            type=ContactMethod.Type.TELEPHONE,
            value="+441111111111",
        )

        self.assertEqual(
            list(filtered_contacts_for_user(user=self.user, search="Alice")),
            [contact],
        )

    def test_state_filter_and_supported_sort_options(self):
        alpha = self.create_contact(self.user, "Alpha")
        zebra = self.create_contact(
            self.user,
            "Zebra",
            state=Contact.State.DEACTIVATED,
        )
        earlier = timezone.now() - timedelta(days=2)
        later = timezone.now() - timedelta(days=1)
        Contact.objects.filter(pk=alpha.pk).update(created_at=earlier)
        Contact.objects.filter(pk=zebra.pk).update(created_at=later)

        self.assertEqual(
            list(
                filtered_contacts_for_user(
                    user=self.user,
                    state=Contact.State.DEACTIVATED,
                )
            ),
            [zebra],
        )

        expected = {
            "name": [alpha, zebra],
            "-name": [zebra, alpha],
            "created_at": [alpha, zebra],
            "-created_at": [zebra, alpha],
        }
        for sort, contacts in expected.items():
            with self.subTest(sort=sort):
                self.assertEqual(
                    list(filtered_contacts_for_user(user=self.user, sort=sort)),
                    contacts,
                )

    def test_contact_methods_for_contact_only_returns_its_methods(self):
        contact = self.create_contact(self.user)
        other_contact = self.create_contact(self.user, "Other")
        wanted = self.create_method(contact)
        self.create_method(other_contact, value="other@example.com")

        self.assertEqual(
            list(contact_methods_for_contact(contact=contact)),
            [wanted],
        )
