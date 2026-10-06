"""Task service behaviour."""

from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from issue.models import Issue
from property.models import Property

from ..models import Task
from ..services import (
    complete_task,
    create_task,
    delete_task,
    dismiss_task,
    reactivate_task,
    update_task,
)


class TaskServiceTests(TestCase):
    TEST_PASSWORD = "HolidayHome123!"

    def setUp(self):
        self.user = User.objects.create_user(
            email="alice@example.com",
            first_name="Alice",
            last_name="Smith",
            password=self.TEST_PASSWORD,
        )
        self.other_user = User.objects.create_user(
            email="bob@example.com",
            first_name="Bob",
            last_name="Jones",
            password=self.TEST_PASSWORD,
        )

    def test_create_task_persists_all_values_and_returns_created_task(self):
        property_record = Property.objects.create(
            user=self.user,
            name="Hill House",
        )
        scheduled_date = timezone.localdate() + timedelta(days=1)
        completion_deadline = timezone.localdate() + timedelta(days=7)

        task = create_task(
            user=self.user,
            property=property_record,
            issue=None,
            priority=Task.Priority.URGENT,
            title="Arrange roof repair",
            description="Ask the roofer to inspect the west elevation.",
            scheduled_date=scheduled_date,
            completion_deadline=completion_deadline,
        )
        persisted_task = Task.objects.get(pk=task.pk)

        self.assertEqual(persisted_task, task)
        self.assertEqual(persisted_task.user, self.user)
        self.assertEqual(persisted_task.property, property_record)
        self.assertIsNone(persisted_task.issue)
        self.assertEqual(persisted_task.priority, Task.Priority.URGENT)
        self.assertEqual(persisted_task.title, "Arrange roof repair")
        self.assertEqual(
            persisted_task.description,
            "Ask the roofer to inspect the west elevation.",
        )
        self.assertEqual(persisted_task.scheduled_date, scheduled_date)
        self.assertEqual(
            persisted_task.completion_deadline,
            completion_deadline,
        )

    def test_create_task_assigns_each_supported_optional_parent(self):
        property_record = Property.objects.create(
            user=self.user,
            name="Hill House",
        )
        issue = Issue.objects.create(
            user=self.user,
            title="Roof leak",
        )
        parents = {
            "standalone": {"property": None, "issue": None},
            "property": {"property": property_record, "issue": None},
            "issue": {"property": None, "issue": issue},
        }

        for label, parent_values in parents.items():
            with self.subTest(parent=label):
                task = create_task(
                    user=self.user,
                    priority=Task.Priority.LOW,
                    title=f"{label} task",
                    description="",
                    scheduled_date=None,
                    completion_deadline=None,
                    **parent_values,
                )
                task.refresh_from_db()

                self.assertEqual(task.user, self.user)
                self.assertEqual(task.property, parent_values["property"])
                self.assertEqual(task.issue, parent_values["issue"])

    def test_update_task_persists_editable_fields_and_returns_task(self):
        original_property = Property.objects.create(
            user=self.user,
            name="Hill House",
        )
        replacement_issue = Issue.objects.create(
            user=self.user,
            title="Roof leak",
        )
        task = Task.objects.create(
            user=self.user,
            property=original_property,
            priority=Task.Priority.LOW,
            title="Original title",
            description="Original description",
        )
        scheduled_date = timezone.localdate() + timedelta(days=2)
        completion_deadline = timezone.localdate() + timedelta(days=8)

        returned_task = update_task(
            task=task,
            property=None,
            issue=replacement_issue,
            priority=Task.Priority.HIGH,
            title="Updated title",
            description="Updated description",
            scheduled_date=scheduled_date,
            completion_deadline=completion_deadline,
        )
        task.refresh_from_db()

        self.assertIs(returned_task, task)
        self.assertIsNone(task.property)
        self.assertEqual(task.issue, replacement_issue)
        self.assertEqual(task.priority, Task.Priority.HIGH)
        self.assertEqual(task.title, "Updated title")
        self.assertEqual(task.description, "Updated description")
        self.assertEqual(task.scheduled_date, scheduled_date)
        self.assertEqual(task.completion_deadline, completion_deadline)

    def test_update_task_preserves_user_and_lifecycle_fields(self):
        terminated_at = timezone.now() - timedelta(days=2)
        deleted_at = timezone.now() - timedelta(days=1)
        task = Task.objects.create(
            user=self.user,
            state=Task.State.DISMISSED,
            title="Original title",
            terminated_at=terminated_at,
            deleted_at=deleted_at,
        )
        created_at = task.created_at

        update_task(
            task=task,
            property=None,
            issue=None,
            priority=Task.Priority.MEDIUM,
            title="Updated title",
            description="Updated description",
            scheduled_date=None,
            completion_deadline=None,
        )
        task.refresh_from_db()

        self.assertEqual(task.user, self.user)
        self.assertEqual(task.state, Task.State.DISMISSED)
        self.assertEqual(task.created_at, created_at)
        self.assertEqual(task.terminated_at, terminated_at)
        self.assertEqual(task.deleted_at, deleted_at)

    def test_dismiss_task_dismisses_active_task_at_current_time(self):
        task = Task.objects.create(user=self.user, title="Active task")
        dismissed_at = timezone.now() + timedelta(minutes=1)

        with patch("task.services.timezone.now", return_value=dismissed_at):
            returned_task = dismiss_task(task=task)
        task.refresh_from_db()

        self.assertIs(returned_task, task)
        self.assertEqual(task.state, Task.State.DISMISSED)
        self.assertEqual(task.terminated_at, dismissed_at)

    def test_dismiss_task_leaves_terminated_tasks_unchanged(self):
        original_terminated_at = timezone.now() - timedelta(days=1)

        for state in (Task.State.DISMISSED, Task.State.COMPLETED):
            with self.subTest(state=state):
                task = Task.objects.create(
                    user=self.user,
                    state=state,
                    title=f"{state} task",
                    terminated_at=original_terminated_at,
                )

                dismiss_task(task=task)
                task.refresh_from_db()

                self.assertEqual(task.state, state)
                self.assertEqual(task.terminated_at, original_terminated_at)

    def test_complete_task_completes_active_task_at_current_time(self):
        task = Task.objects.create(user=self.user, title="Active task")
        completed_at = timezone.now() + timedelta(minutes=1)

        with patch("task.services.timezone.now", return_value=completed_at):
            returned_task = complete_task(task=task)
        task.refresh_from_db()

        self.assertIs(returned_task, task)
        self.assertEqual(task.state, Task.State.COMPLETED)
        self.assertEqual(task.terminated_at, completed_at)

    def test_complete_task_leaves_terminated_tasks_unchanged(self):
        original_terminated_at = timezone.now() - timedelta(days=1)

        for state in (Task.State.DISMISSED, Task.State.COMPLETED):
            with self.subTest(state=state):
                task = Task.objects.create(
                    user=self.user,
                    state=state,
                    title=f"{state} task",
                    terminated_at=original_terminated_at,
                )

                complete_task(task=task)
                task.refresh_from_db()

                self.assertEqual(task.state, state)
                self.assertEqual(task.terminated_at, original_terminated_at)

    def test_reactivate_task_reactivates_terminated_tasks(self):
        terminated_at = timezone.now() - timedelta(days=1)

        for state in (Task.State.DISMISSED, Task.State.COMPLETED):
            with self.subTest(state=state):
                task = Task.objects.create(
                    user=self.user,
                    state=state,
                    title=f"{state} task",
                    terminated_at=terminated_at,
                )

                returned_task = reactivate_task(task=task)
                task.refresh_from_db()

                self.assertIs(returned_task, task)
                self.assertEqual(task.state, Task.State.ACTIVE)
                self.assertIsNone(task.terminated_at)

    def test_reactivate_task_leaves_active_task_unchanged(self):
        task = Task.objects.create(user=self.user, title="Active task")

        reactivate_task(task=task)
        task.refresh_from_db()

        self.assertEqual(task.state, Task.State.ACTIVE)
        self.assertIsNone(task.terminated_at)

    def test_delete_task_soft_deletes_task_at_current_time(self):
        task = Task.objects.create(user=self.user, title="Task to delete")
        deleted_at = timezone.now() + timedelta(minutes=1)

        with patch("task.services.timezone.now", return_value=deleted_at):
            returned_task = delete_task(task=task)
        task.refresh_from_db()

        self.assertIs(returned_task, task)
        self.assertEqual(task.deleted_at, deleted_at)
        self.assertTrue(Task.objects.filter(pk=task.pk).exists())

    def test_delete_task_preserves_original_deletion_time_on_second_call(self):
        original_deleted_at = timezone.now() - timedelta(days=1)
        task = Task.objects.create(user=self.user, title="Task to delete")

        with patch("task.services.timezone.now", return_value=original_deleted_at):
            delete_task(task=task)
        with patch("task.services.timezone.now", return_value=timezone.now()):
            delete_task(task=task)
        task.refresh_from_db()

        self.assertEqual(task.deleted_at, original_deleted_at)
        self.assertTrue(Task.objects.filter(pk=task.pk).exists())
