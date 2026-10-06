"""Event service behaviour."""

from datetime import date

from django.test import TestCase

from contact.models import Contact

from ..models import Event, EventContact
from ..services import (
    add_contacts_to_event,
    cancel_event,
    create_event,
    delete_event,
    mark_event_occurred,
    reactivate_event,
    remove_contact_from_event,
    update_event,
)
from .support import EventTestMixin


class EventServiceTests(EventTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.property = self.create_property(self.user)

    def test_create_update_and_soft_delete_event(self):
        event = create_event(
            user=self.user,
            title="Created",
            property=self.property,
            scheduled_date=date(2026, 9, 20),
            all_day=True,
            user_participation_required=False,
            user_presence_required=False,
        )
        update_event(
            event=event,
            title="Updated",
            description="Changed",
            property=None,
            scheduled_date=date(2026, 9, 21),
            all_day=True,
            user_participation_required=False,
            user_presence_required=False,
        )
        delete_event(event=event)

        event.refresh_from_db()
        self.assertEqual(event.title, "Updated")
        self.assertIsNone(event.property)
        self.assertIsNotNone(event.deleted_at)

    def test_create_rejects_another_users_property(self):
        other_property = self.create_property(self.create_user("bob@example.com"), "Other")
        with self.assertRaises(ValueError):
            create_event(
                user=self.user,
                title="Invalid",
                property=other_property,
                scheduled_date=date(2026, 9, 20),
                all_day=True,
                user_participation_required=False,
                user_presence_required=False,
            )

    def test_lifecycle_transitions_and_guards(self):
        occurred = self.create_event(self.user)
        mark_event_occurred(event=occurred)
        first_termination = occurred.terminated_at
        cancel_event(event=occurred)
        occurred.refresh_from_db()
        self.assertEqual(occurred.state, Event.State.OCCURRED)
        self.assertEqual(occurred.terminated_at, first_termination)

        reactivate_event(event=occurred)
        occurred.refresh_from_db()
        self.assertEqual(occurred.state, Event.State.SCHEDULED)
        self.assertIsNone(occurred.terminated_at)

    def test_create_with_contacts_is_atomic_and_owner_scoped(self):
        contact = self.create_contact(self.user)
        event = create_event(
            user=self.user,
            title="With contact",
            scheduled_date=date(2026, 9, 20),
            all_day=True,
            user_participation_required=False,
            user_presence_required=False,
            contacts=[contact],
        )
        self.assertTrue(EventContact.objects.filter(event=event, contact=contact).exists())

        other = self.create_contact(self.create_user("bob@example.com"), "Other")
        with self.assertRaises(ValueError):
            create_event(
                user=self.user,
                title="Rolled back",
                scheduled_date=date(2026, 9, 20),
                all_day=True,
                user_participation_required=False,
                user_presence_required=False,
                contacts=[other],
            )
        self.assertFalse(Event.objects.filter(title="Rolled back").exists())

    def test_add_contacts_is_idempotent_and_remove_deletes_only_link(self):
        event = self.create_event(self.user)
        contact = self.create_contact(self.user)
        add_contacts_to_event(event=event, contacts=[contact, contact])
        add_contacts_to_event(event=event, contacts=[contact])
        link = EventContact.objects.get(event=event, contact=contact)

        remove_contact_from_event(event_contact=link)

        self.assertTrue(Contact.objects.filter(pk=contact.pk).exists())
        self.assertFalse(EventContact.objects.filter(pk=link.pk).exists())

    def test_participants_cannot_change_after_termination(self):
        event = self.create_event(self.user, state=Event.State.CANCELLED)
        contact = self.create_contact(self.user)
        add_contacts_to_event(event=event, contacts=[contact])
        self.assertFalse(EventContact.objects.filter(event=event).exists())

        link = EventContact.objects.create(event=event, contact=contact)
        remove_contact_from_event(event_contact=link)
        self.assertTrue(EventContact.objects.filter(pk=link.pk).exists())
