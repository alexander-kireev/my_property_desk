"""A stale cancellation must not replace an already recorded occurrence."""

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from event.models import Event
from event.services import cancel_event, delete_event, mark_event_occurred, reactivate_event


class EventLifecycleTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            email="lifecycle@example.invalid", password="ValidPassword123!"
        )
        self.event = Event.objects.create(
            user=user, title="Lifecycle test", scheduled_date=timezone.localdate(), all_day=True
        )

    def test_stale_cancel_retains_occurred_state_and_timestamp(self):
        stale = Event.objects.get(pk=self.event.pk)
        mark_event_occurred(event=self.event)
        timestamp = self.event.terminated_at
        result = cancel_event(event=stale)
        self.event.refresh_from_db()
        self.assertEqual(self.event.state, Event.State.OCCURRED)
        self.assertEqual(self.event.terminated_at, timestamp)
        self.assertFalse(result.action_changed)

    def test_stale_actions_cannot_change_deleted_event_or_deletion_time(self):
        stale = Event.objects.get(pk=self.event.pk)
        delete_event(event=self.event)
        timestamp = self.event.deleted_at
        for action in (mark_event_occurred, cancel_event, reactivate_event, delete_event):
            with self.subTest(action=action.__name__):
                result = action(event=stale)
                self.assertFalse(result.action_changed)
                self.event.refresh_from_db()
                self.assertEqual(self.event.deleted_at, timestamp)
                self.assertEqual(self.event.state, Event.State.SCHEDULED)
