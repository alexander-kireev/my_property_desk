"""Issue model behaviour."""

from django.test import TestCase

from ..models import Issue
from .support import IssueTestMixin


class IssueModelTests(IssueTestMixin, TestCase):
    def test_defaults_relationship_and_string_value(self):
        issue = self.create_issue(self.create_user())

        self.assertEqual(issue.state, Issue.State.ACTIVE)
        self.assertEqual(issue.priority, Issue.Priority.LOW)
        self.assertIsNone(issue.property)
        self.assertIsNone(issue.resolution_deadline)
        self.assertIsNone(issue.terminated_at)
        self.assertIsNone(issue.deleted_at)
        self.assertEqual(str(issue), "Roof leak")

    def test_issue_exposes_linked_tasks(self):
        user = self.create_user()
        issue = self.create_issue(user)
        task = self.create_task(user, issue)

        self.assertEqual(list(issue.tasks.all()), [task])
