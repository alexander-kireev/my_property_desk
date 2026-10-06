"""One-use form errors survive navigation to the selected Issue's page."""

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from issue.models import Issue


class IssuePaginationStateTests(TestCase):
    def test_rejected_edit_survives_page_correction_and_is_consumed_once(self):
        user = User.objects.create_user(
            email="pagination@example.invalid", password="TestPassword123!"
        )
        records = [
            Issue.objects.create(user=user, title=f"Issue {index:02}") for index in range(21)
        ]
        selected = records[-1]
        self.client.force_login(user)
        response = self.client.post(
            reverse("issue:edit_issue", args=[selected.pk]) + "?sort=created_at",
            {"title": "", "priority": "1"},
        )
        self.assertEqual(response.status_code, 302)
        correction = self.client.get(response.url)
        self.assertEqual(correction.status_code, 302)
        final = self.client.get(correction.url)
        self.assertEqual(final.context["page_obj"].number, 2)
        self.assertEqual(final.context["selected_issue"].pk, selected.pk)
        self.assertTrue(final.context["edit_issue_form"].is_bound)
        self.assertIn("title", final.context["edit_issue_form"].errors)
        replay = self.client.get(correction.url)
        self.assertFalse(replay.context["edit_issue_form"].is_bound)
