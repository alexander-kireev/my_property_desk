"""Property cascade behaviour."""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from event.models import Event
from issue.models import Issue
from task.models import Task

from ..models import Property
from ..services import deactivate_property, delete_property, related_work_counts


class PropertyCascadeDecisionTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="cascade@example.com", first_name="Cascade", last_name="Test"
        )
        self.property = Property.objects.create(user=self.user, name="Cascade House")
        self.issue = Issue.objects.create(user=self.user, property=self.property, title="Leak")
        self.direct_task = Task.objects.create(
            user=self.user, property=self.property, title="Direct"
        )
        self.issue_task = Task.objects.create(user=self.user, issue=self.issue, title="Via issue")
        self.event = Event.objects.create(
            user=self.user,
            property=self.property,
            title="Visit",
            scheduled_date=timezone.localdate(),
            all_day=True,
        )

    def test_deactivate_choices_are_independent_and_default_to_parent_only(self):
        self.assertEqual(related_work_counts(property_record=self.property)["tasks_active"], 2)
        deactivate_property(property_record=self.property, dismiss_tasks=True)
        self.issue.refresh_from_db()
        self.event.refresh_from_db()
        self.direct_task.refresh_from_db()
        self.issue_task.refresh_from_db()
        self.assertEqual(self.issue.state, Issue.State.ACTIVE)
        self.assertEqual(self.event.state, Event.State.SCHEDULED)
        self.assertEqual(self.direct_task.state, Task.State.DISMISSED)
        self.assertEqual(self.issue_task.state, Task.State.DISMISSED)

    def test_deactivate_can_cancel_event_and_dismiss_issue_without_touching_task(self):
        deactivate_property(property_record=self.property, cancel_events=True, dismiss_issues=True)
        self.issue.refresh_from_db()
        self.event.refresh_from_db()
        self.direct_task.refresh_from_db()
        self.issue_task.refresh_from_db()
        self.assertEqual(self.issue.state, Issue.State.DISMISSED)
        self.assertEqual(self.event.state, Event.State.CANCELLED)
        self.assertEqual(self.direct_task.state, Task.State.ACTIVE)
        self.assertEqual(self.issue_task.state, Task.State.ACTIVE)
        self.assertEqual(self.property.affected_work, {"events": 1, "issues": 1, "tasks": 0})

    def test_deactivate_without_choices_keeps_all_child_states(self):
        deactivate_property(property_record=self.property)
        self.issue.refresh_from_db()
        self.event.refresh_from_db()
        self.direct_task.refresh_from_db()
        self.assertEqual(self.issue.state, Issue.State.ACTIVE)
        self.assertEqual(self.event.state, Event.State.SCHEDULED)
        self.assertEqual(self.direct_task.state, Task.State.ACTIVE)

    def test_delete_choices_include_terminal_tasks_through_issue_once(self):
        self.issue_task.state = Task.State.COMPLETED
        self.issue_task.save(update_fields=["state"])
        delete_property(property_record=self.property, delete_tasks=True)
        self.issue.refresh_from_db()
        self.event.refresh_from_db()
        self.direct_task.refresh_from_db()
        self.issue_task.refresh_from_db()
        self.assertIsNone(self.issue.deleted_at)
        self.assertIsNone(self.event.deleted_at)
        self.assertIsNotNone(self.direct_task.deleted_at)
        self.assertIsNotNone(self.issue_task.deleted_at)
        self.assertEqual(self.property.affected_work["tasks"], 2)

    def test_delete_parent_alone_keeps_linked_work(self):
        delete_property(property_record=self.property)
        self.issue.refresh_from_db()
        self.direct_task.refresh_from_db()
        self.assertIsNone(self.issue.deleted_at)
        self.assertIsNone(self.direct_task.deleted_at)

    def test_delete_issue_and_event_choices_leave_tasks_with_parent_tombstone(self):
        delete_property(property_record=self.property, delete_events=True, delete_issues=True)
        self.issue.refresh_from_db()
        self.event.refresh_from_db()
        self.issue_task.refresh_from_db()
        self.assertIsNotNone(self.issue.deleted_at)
        self.assertIsNotNone(self.event.deleted_at)
        self.assertIsNone(self.issue_task.deleted_at)
        self.assertEqual(self.issue_task.issue.title, "Leak")
        self.assertEqual(self.property.affected_work, {"events": 1, "issues": 1, "tasks": 0})
        self.client.force_login(self.user)
        response = self.client.get(reverse("task:tasks"), {"selected": self.issue_task.pk})
        self.assertContains(response, "Leak")
        self.assertNotContains(response, "Deleted issue")

    def test_cascade_uses_live_child_set_not_old_modal_count(self):
        shown_count = related_work_counts(property_record=self.property)["tasks_active"]
        Task.objects.create(
            user=self.user, property=self.property, title="Added after modal opened"
        )
        deactivate_property(property_record=self.property, dismiss_tasks=True)
        self.assertEqual(shown_count, 2)
        self.assertEqual(self.property.affected_work["tasks"], 3)
