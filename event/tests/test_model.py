"""Event model behaviour."""

from datetime import time

from django.db import IntegrityError, transaction
from django.test import TestCase

from ..models import Event, EventContact
from .support import EventTestMixin


class EventModelTests(EventTestMixin, TestCase):
    def test_defaults_relationships_and_string_value(self):
        user = self.create_user()
        event = self.create_event(user)

        self.assertEqual(event.state, Event.State.SCHEDULED)
        self.assertFalse(event.user_participation_required)
        self.assertFalse(event.user_presence_required)
        self.assertIsNone(event.property)
        self.assertIsNone(event.terminated_at)
        self.assertIsNone(event.deleted_at)
        self.assertEqual(str(event), "Inspection")

    def test_database_rejects_invalid_timing(self):
        user = self.create_user()
        invalid_values = (
            {"all_day": True, "start_time": time(9), "end_time": time(10)},
            {"all_day": False, "start_time": None, "end_time": None},
            {"all_day": False, "start_time": time(10), "end_time": time(9)},
        )
        for values in invalid_values:
            with self.subTest(values=values), self.assertRaises(IntegrityError):
                with transaction.atomic():
                    self.create_event(user, **values)

    def test_database_allows_timed_event_without_end_time(self):
        event = self.create_event(
            self.create_user(),
            all_day=False,
            start_time=time(9),
            end_time=None,
        )

        self.assertEqual(event.start_time, time(9))
        self.assertIsNone(event.end_time)

    def test_database_rejects_presence_without_participation(self):
        user = self.create_user()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_event(
                    user,
                    user_presence_required=True,
                    user_participation_required=False,
                )

    def test_event_contact_is_unique_per_event(self):
        user = self.create_user()
        event = self.create_event(user)
        contact = self.create_contact(user)
        EventContact.objects.create(event=event, contact=contact)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EventContact.objects.create(event=event, contact=contact)
