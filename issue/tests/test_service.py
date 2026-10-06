"""Issue service behaviour."""

from django.test import TestCase
from django.utils import timezone

from task.models import Task

from ..models import Issue
from ..services import (
    create_issue,
    delete_issue,
    dismiss_issue,
    reactivate_issue,
    resolve_issue,
    update_issue,
)
from .support import IssueTestMixin


class IssueServiceTests(IssueTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.property = self.create_property(self.user)

    def test_create_and_update_issue(self):
        issue = create_issue(
            user=self.user,
            property=self.property,
            priority=Issue.Priority.HIGH,
            title="Roof",
            description="Leak",
            resolution_deadline=timezone.localdate(),
        )
        update_issue(
            issue=issue,
            property=None,
            priority=Issue.Priority.LOW,
            title="Updated roof",
            description="Updated",
            resolution_deadline=None,
        )

        issue.refresh_from_db()
        self.assertEqual(issue.title, "Updated roof")
        self.assertEqual(issue.priority, Issue.Priority.LOW)
        self.assertIsNone(issue.property)

    def test_resolve_without_cascade_leaves_tasks_active(self):
        issue = self.create_issue(self.user)
        task = self.create_task(self.user, issue)

        resolve_issue(issue=issue)
        task.refresh_from_db()

        self.assertEqual(issue.state, Issue.State.RESOLVED)
        self.assertIsNotNone(issue.terminated_at)
        self.assertEqual(task.state, Task.State.ACTIVE)

    def test_resolve_with_cascade_dismisses_only_active_tasks(self):
        issue = self.create_issue(self.user)
        active = self.create_task(self.user, issue, "Active")
        completed = self.create_task(self.user, issue, "Completed", state=Task.State.COMPLETED)

        resolve_issue(issue=issue, dismiss_linked_tasks=True)
        active.refresh_from_db()
        completed.refresh_from_db()

        self.assertEqual(active.state, Task.State.DISMISSED)
        self.assertEqual(completed.state, Task.State.COMPLETED)

    def test_reactivate_does_not_reactivate_tasks(self):
        issue = self.create_issue(self.user)
        task = self.create_task(self.user, issue)

        dismiss_issue(issue=issue, dismiss_linked_tasks=True)
        reactivate_issue(issue=issue)
        task.refresh_from_db()

        self.assertEqual(issue.state, Issue.State.ACTIVE)
        self.assertIsNone(issue.terminated_at)
        self.assertEqual(task.state, Task.State.DISMISSED)

    def test_delete_optionally_soft_deletes_linked_tasks(self):
        issue = self.create_issue(self.user)
        task = self.create_task(self.user, issue)

        delete_issue(issue=issue, delete_linked_tasks=True)
        task.refresh_from_db()

        self.assertIsNotNone(issue.deleted_at)
        self.assertIsNotNone(task.deleted_at)

    def test_delete_without_cascade_leaves_task_visible(self):
        issue = self.create_issue(self.user)
        task = self.create_task(self.user, issue)

        delete_issue(issue=issue)
        task.refresh_from_db()

        self.assertIsNone(task.deleted_at)
