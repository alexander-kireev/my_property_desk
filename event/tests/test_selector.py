"""Event selector behaviour."""

from datetime import date

from django.test import TestCase
from django.utils import timezone

from contact.models import Contact, ContactMethod

from ..models import Event, EventContact
from ..selectors import (
    calendar_events_for_user,
    event_contacts_for_event,
    events_for_user,
    filtered_events_for_user,
)
from .support import EventTestMixin


class EventSelectorTests(EventTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.other_user = self.create_user("bob@example.com")
        self.property = self.create_property(self.user, address="12 Hill Road")

    def test_events_for_user_scopes_owner_and_soft_deletion(self):
        visible = self.create_event(self.user)
        self.create_event(self.other_user, "Other")
        self.create_event(self.user, "Deleted", deleted_at=timezone.now())

        self.assertEqual(list(events_for_user(user=self.user)), [visible])

    def test_search_and_filters(self):
        wanted = self.create_event(
            self.user,
            "Unrelated title",
            property=self.property,
            state=Event.State.CANCELLED,
            user_participation_required=True,
            user_presence_required=True,
        )
        self.create_event(self.user, "Other")

        result = filtered_events_for_user(
            user=self.user,
            search="Hill Road",
            state=Event.State.CANCELLED,
            property_id=self.property.pk,
            participation="required",
            presence="required",
        )

        self.assertEqual(list(result), [wanted])

    def test_calendar_selector_uses_visible_date_range(self):
        inside = self.create_event(self.user, scheduled_date=date(2026, 9, 12))
        self.create_event(self.user, "Outside", scheduled_date=date(2026, 10, 1))

        result = calendar_events_for_user(
            user=self.user,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
        )

        self.assertEqual(list(result), [inside])

    def test_event_contacts_are_ordered_and_include_historical_contacts(self):
        event = self.create_event(self.user)
        zed = self.create_contact(self.user, "Zed")
        amy = self.create_contact(self.user, "Amy", state=Contact.State.DEACTIVATED)
        zed_link = EventContact.objects.create(event=event, contact=zed)
        amy_link = EventContact.objects.create(event=event, contact=amy)
        first_email = ContactMethod.objects.create(
            contact=amy,
            type=ContactMethod.Type.EMAIL,
            value="first@example.com",
        )
        ContactMethod.objects.create(
            contact=amy,
            type=ContactMethod.Type.EMAIL,
            value="second@example.com",
        )
        first_telephone = ContactMethod.objects.create(
            contact=amy,
            type=ContactMethod.Type.TELEPHONE,
            value="+447700900123",
        )

        participants = list(event_contacts_for_event(event=event))

        self.assertEqual(participants, [amy_link, zed_link])
        self.assertEqual(participants[0].contact_email, first_email.value)
        self.assertEqual(
            participants[0].contact_telephone,
            first_telephone.value,
        )
