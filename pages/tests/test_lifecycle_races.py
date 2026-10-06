"""Verify real row-lock competition and truthful Dashboard no-op responses."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from event.models import Event
from event.services import cancel_event, mark_event_occurred
from task.models import Task
from task.services import complete_task, dismiss_task


@skipUnlessDBFeature("has_select_for_update")
class LifecycleConcurrencyTests(TransactionTestCase):
    def test_competing_terminal_actions_have_one_winner(self):
        user = User.objects.create_user(email="race@example.invalid", password="ValidPassword123!")
        task = Task.objects.create(user=user, title="Race")
        event = Event.objects.create(
            user=user, title="Race", scheduled_date=timezone.localdate(), all_day=True
        )
        for record, actions, argument in (
            (task, (complete_task, dismiss_task), "task"),
            (event, (mark_event_occurred, cancel_event), "event"),
        ):
            with self.subTest(kind=argument):
                barrier = Barrier(2)

                def compete(action):
                    close_old_connections()
                    try:
                        stale = type(record).objects.get(pk=record.pk)
                        barrier.wait(timeout=10)
                        result = action(**{argument: stale})
                        return result.action_changed, result.terminated_at
                    finally:
                        close_old_connections()

                with ThreadPoolExecutor(max_workers=2) as executor:
                    results = list(executor.map(compete, actions))
                self.assertCountEqual([result[0] for result in results], [True, False])
                self.assertEqual(results[0][1], results[1][1])


class DashboardLifecycleRaceTests(TestCase):
    def test_losing_finish_does_not_offer_undo_for_winning_action(self):
        user = User.objects.create_user(email="race@example.invalid", password="ValidPassword123!")
        task = Task.objects.create(user=user, title="Race")
        self.client.force_login(user)

        def finish_after_competitor(*, task):
            competitor = Task.objects.get(pk=task.pk)
            dismiss_task(task=competitor)
            return complete_task(task=task)

        with patch("pages.dashboard.actions.complete_task", side_effect=finish_after_competitor):
            response = self.client.post(
                reverse("pages:dashboard_action"),
                {"kind": "task", "action": "finish", "id": task.pk},
            )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["changed"])
        self.assertNotIn("undo_token", response.json())
        task.refresh_from_db()
        self.assertEqual(task.state, Task.State.DISMISSED)
