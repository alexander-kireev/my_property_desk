"""Pages workspace behaviour."""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse

from event.models import Event
from issue.models import Issue
from task.models import Task

from .support import DashboardFixture


class DashboardWorkspaceTests(DashboardFixture, TestCase):
    def test_same_day_drop_returns_no_change(self):
        self.task.scheduled_date = self.today
        self.task.save(update_fields=["scheduled_date"])
        response = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "date",
                "kind": "task",
                "id": self.task.pk,
                "date": self.today.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["changed"])

    def test_issue_resolve_requires_review_when_linked_task_is_active(self):
        issue = Issue.objects.create(user=self.user, title="Review linked work")
        task = Task.objects.create(user=self.user, issue=issue, title="Linked")
        url = reverse("pages:dashboard_action")
        immediate = self.client.post(url, {"action": "finish", "kind": "issue", "id": issue.pk})
        self.assertEqual(immediate.status_code, 409)
        issue.refresh_from_db()
        self.assertEqual(issue.state, Issue.State.ACTIVE)
        confirmed = self.client.post(
            url,
            {
                "action": "finish",
                "kind": "issue",
                "id": issue.pk,
                "confirm_linked_tasks": "yes",
                "affect_linked_tasks": "yes",
            },
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.content)
        self.assertNotIn("undo_token", confirmed.json())
        task.refresh_from_db()
        self.assertEqual(task.state, Task.State.DISMISSED)

    def test_cannot_change_another_users_task(self):
        other_task = Task.objects.get(user=self.other)
        response = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "date",
                "kind": "task",
                "id": other_task.pk,
                "date": self.today.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 404)

    def test_existing_event_can_move_into_past_for_correction(self):
        event = Event.objects.create(
            user=self.user,
            title="Visit",
            scheduled_date=self.today + timedelta(days=2),
            all_day=True,
        )
        response = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "date",
                "kind": "event",
                "id": event.pk,
                "date": (self.today - timedelta(days=1)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        event.refresh_from_db()
        self.assertEqual(event.scheduled_date, self.today - timedelta(days=1))

    def test_past_scheduled_event_can_move_to_future_from_dashboard(self):
        past = self.today - timedelta(days=2)
        event = Event.objects.create(
            user=self.user,
            title="Past visit",
            scheduled_date=past,
            all_day=True,
        )
        response = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "date",
                "kind": "event",
                "id": event.pk,
                "date": (self.today + timedelta(days=1)).isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        event.refresh_from_db()
        self.assertEqual(event.scheduled_date, self.today + timedelta(days=1))
