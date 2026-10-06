"""Issue form behaviour."""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from property.models import Property
from task.forms import TaskForm

from ..forms import IssueForm
from ..models import Issue
from .support import IssueTestMixin


class IssueFormTests(IssueTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.property = self.create_property(self.user)

    def valid_data(self):
        return {
            "title": "Roof leak",
            "description": "Water entering upstairs",
            "property": self.property.pk,
            "priority": Issue.Priority.URGENT,
            "resolution_deadline": (timezone.localdate() + timedelta(days=4)).isoformat(),
        }

    def test_valid_form_exposes_only_editable_fields(self):
        form = IssueForm(data=self.valid_data(), user=self.user)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(
            list(form.fields),
            ["title", "description", "property", "priority", "resolution_deadline"],
        )
        self.assertEqual(form.fields["resolution_deadline"].label, "Resolve by")

    def test_title_accepts_75_characters_and_rejects_76(self):
        data = self.valid_data()
        data["title"] = "I" * 75
        self.assertTrue(IssueForm(data=data, user=self.user).is_valid())

        data["title"] = "I" * 76
        form = IssueForm(data=data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)
        self.assertEqual(form.fields["title"].widget.attrs["maxlength"], "75")

    def test_issue_forms_use_searchable_property_picker_without_target_date_copy(self):
        self.client.force_login(self.user)
        self.create_issue(self.user, property=self.property)

        response = self.client.get(reverse("issue:issues"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-searchable-select", count=4)
        self.assertContains(response, "Resolve by")
        self.assertNotContains(response, "the issue will not resolve automatically")

    def test_another_users_property_is_rejected(self):
        other_property = self.create_property(self.create_user("bob@example.com"), "Other House")
        data = self.valid_data()
        data["property"] = other_property.pk

        form = IssueForm(data=data, user=self.user)

        self.assertFalse(form.is_valid())
        self.assertIn("property", form.errors)

    def test_soft_deleted_property_is_rejected(self):
        self.property.deleted_at = timezone.now()
        self.property.save(update_fields=["deleted_at"])

        form = IssueForm(data=self.valid_data(), user=self.user)

        self.assertFalse(form.is_valid())
        self.assertIn("property", form.errors)

    def test_edit_keeps_current_inactive_property_available(self):
        issue = self.create_issue(self.user, property=self.property)
        self.property.state = Property.State.DEACTIVATED
        self.property.save(update_fields=["state"])

        form = IssueForm(data=self.valid_data(), user=self.user, instance=issue)

        self.assertTrue(form.is_valid(), form.errors)
        self.assertIn(self.property, form.fields["property"].queryset)


class LockedTaskFormTests(IssueTestMixin, TestCase):
    def test_parent_issue_mode_removes_relationship_fields(self):
        user = self.create_user()
        issue = self.create_issue(user)

        form = TaskForm(user=user, parent_issue=issue)

        self.assertNotIn("property", form.fields)
        self.assertNotIn("issue", form.fields)
