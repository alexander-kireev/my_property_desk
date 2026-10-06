"""Issue authentication behaviour."""

from django.test import TestCase
from django.urls import reverse

from .support import IssueTestMixin


class IssueAuthenticationTests(IssueTestMixin, TestCase):
    def test_issue_endpoints_require_authentication(self):
        user = self.create_user()
        issue = self.create_issue(user)
        task = self.create_task(user, issue)
        endpoints = (
            ("get", reverse("issue:issues")),
            ("post", reverse("issue:add_issue")),
            ("post", reverse("issue:edit_issue", args=[issue.pk])),
            ("post", reverse("issue:resolve_issue", args=[issue.pk])),
            ("post", reverse("issue:dismiss_issue", args=[issue.pk])),
            ("post", reverse("issue:reactivate_issue", args=[issue.pk])),
            ("post", reverse("issue:delete_issue", args=[issue.pk])),
            ("post", reverse("issue:add_issue_task", args=[issue.pk])),
            ("post", reverse("issue:edit_issue_task", args=[issue.pk, task.pk])),
        )

        for method, url in endpoints:
            with self.subTest(url=url):
                response = getattr(self.client, method)(url)
                self.assertEqual(response.status_code, 302)
