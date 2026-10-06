"""Issue selector behaviour."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from task.models import Task
from task.selectors import tasks_for_issue

from ..models import Issue
from ..selectors import filtered_issues_for_user, issues_for_user
from .support import IssueTestMixin


class IssueSelectorTests(IssueTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.other_user = self.create_user("bob@example.com")
        self.property = self.create_property(self.user, address="12 Hill Road")

    def test_issues_for_user_scopes_owner_and_soft_deletion(self):
        visible = self.create_issue(self.user, "Visible")
        self.create_issue(self.other_user, "Other user")
        self.create_issue(self.user, "Deleted", deleted_at=timezone.now())

        self.assertEqual(list(issues_for_user(user=self.user)), [visible])

    def test_search_covers_issue_and_property_text(self):
        title_match = self.create_issue(self.user, "Broken gutter")
        property_match = self.create_issue(self.user, "Unrelated title", property=self.property)

        self.assertEqual(
            list(filtered_issues_for_user(user=self.user, search="gutter")),
            [title_match],
        )
        self.assertEqual(
            list(filtered_issues_for_user(user=self.user, search="Hill Road")),
            [property_match],
        )

    def test_filters_state_priority_and_property(self):
        wanted = self.create_issue(
            self.user,
            property=self.property,
            state=Issue.State.RESOLVED,
            priority=Issue.Priority.HIGH,
        )
        self.create_issue(self.user, "Other")

        result = filtered_issues_for_user(
            user=self.user,
            state=Issue.State.RESOLVED,
            priority=Issue.Priority.HIGH,
            property_id=self.property.pk,
        )

        self.assertEqual(list(result), [wanted])

    def test_deadline_filters_and_null_last_sort(self):
        overdue = self.create_issue(
            self.user,
            "Overdue",
            resolution_deadline=timezone.localdate() - timedelta(days=1),
        )
        no_deadline = self.create_issue(self.user, "No deadline")

        self.assertEqual(
            list(filtered_issues_for_user(user=self.user, deadline_period="overdue")),
            [overdue],
        )
        self.assertEqual(
            list(filtered_issues_for_user(user=self.user, sort="resolution_deadline")),
            [overdue, no_deadline],
        )

    def test_tasks_for_issue_includes_states_but_excludes_deleted(self):
        issue = self.create_issue(self.user)
        active = self.create_task(self.user, issue, "Active")
        completed = self.create_task(self.user, issue, "Completed", state=Task.State.COMPLETED)
        self.create_task(self.user, issue, "Deleted", deleted_at=timezone.now())
        self.create_task(self.other_user, issue, "Wrong owner")

        self.assertEqual(
            list(tasks_for_issue(user=self.user, issue=issue)),
            [active, completed],
        )
