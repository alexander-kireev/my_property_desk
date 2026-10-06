"""Task model behaviour."""

from django.db import IntegrityError, connection, transaction
from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from issue.models import Issue
from property.models import Property

from ..models import Task


class TaskModelTests(TestCase):
    TEST_PASSWORD = "HolidayHome123!"
    TASK_DATA = {
        "title": "call plumber about roof leak",
        "description": "Hill House 4 roof has been leaking since Friday 06.10",
    }
    ISSUE_DATA = {
        "title": "test issue",
    }
    PROPERTY_DATA = {"name": "test property"}

    def create_user(self, email):
        return User.objects.create_user(
            email=email, first_name="Alice", last_name="Smith", password=self.TEST_PASSWORD
        )

    def test_valid_data_creates_task_with_default_values(self):
        user = self.create_user("alice.smith@example.com")
        task = Task.objects.create(user=user, **self.TASK_DATA)

        self.assertEqual(task.user.pk, user.pk)
        self.assertEqual(task.property, None)
        self.assertEqual(task.issue, None)
        self.assertEqual(task.state, Task.State.ACTIVE)
        self.assertEqual(task.priority, Task.Priority.LOW)
        self.assertEqual(task.title, self.TASK_DATA["title"])
        self.assertEqual(task.description, self.TASK_DATA["description"])
        self.assertEqual(task.scheduled_date, None)
        self.assertEqual(task.completion_deadline, None)
        self.assertTrue(task.created_at < timezone.now())
        self.assertEqual(task.terminated_at, None)
        self.assertEqual(task.deleted_at, None)

    def test_task_model_requires_user(self):

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Task.objects.create(**self.TASK_DATA)

        self.assertEqual(Task.objects.count(), 0)

    def test_task_can_be_created_with_issue_relation(self):
        user = self.create_user("alice.smith@example.com")
        issue = Issue.objects.create(user=user, **self.ISSUE_DATA)
        data = self.TASK_DATA.copy()
        data["issue"] = issue

        task = Task.objects.create(user=user, **data)

        self.assertEqual(task.issue.pk, issue.pk)

    def test_task_can_be_created_with_property_relation(self):
        user = self.create_user("alice.smith@example.com")
        property_record = Property.objects.create(user=user, **self.PROPERTY_DATA)
        data = self.TASK_DATA.copy()
        data["property"] = property_record

        task = Task.objects.create(user=user, **data)

        self.assertEqual(task.property.pk, property_record.pk)

    def test_task_cannot_be_created_with_simultaneous_property_and_issue_relations(self):
        user = self.create_user("alice.smith@example.com")
        property_record = Property.objects.create(user=user, **self.PROPERTY_DATA)
        issue = Issue.objects.create(user=user, **self.ISSUE_DATA)
        data = self.TASK_DATA.copy()
        data["issue"] = issue
        data["property"] = property_record

        with self.assertRaises(IntegrityError) as raised:
            with transaction.atomic():
                Task.objects.create(user=user, **data)

        self.assertEqual(Task.objects.count(), 0)
        # PostgreSQL exposes the constraint name; SQLite only exposes the failure.
        if connection.vendor == "postgresql":
            self.assertEqual(
                raised.exception.__cause__.diag.constraint_name,
                "task_has_at_most_one_parent",
            )

    def test_str_method_returns_title(self):
        user = self.create_user("alice.smith@example.com")
        task = Task.objects.create(user=user, **self.TASK_DATA)

        title = task.__str__()

        self.assertEqual(title, task.title)

    def test_deleting_related_issue_sets_field_to_null(self):
        user = self.create_user("alice.smith@example.com")
        issue = Issue.objects.create(user=user, **self.ISSUE_DATA)
        data = self.TASK_DATA.copy()
        data["issue"] = issue

        task = Task.objects.create(user=user, **data)

        issue.delete()
        task.refresh_from_db()

        self.assertIsNone(task.issue)

    def test_deleting_related_property_sets_field_to_null(self):
        user = self.create_user("alice.smith@example.com")
        property_record = Property.objects.create(user=user, **self.PROPERTY_DATA)
        data = self.TASK_DATA.copy()
        data["property"] = property_record

        task = Task.objects.create(user=user, **data)

        property_record.delete()
        task.refresh_from_db()

        self.assertIsNone(task.property)
