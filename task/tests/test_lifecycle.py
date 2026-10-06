"""Stale objects must not overwrite the first completed lifecycle action."""

from django.test import TestCase

from accounts.models import User
from task.models import Task
from task.services import complete_task, delete_task, dismiss_task, reactivate_task


class TaskLifecycleTests(TestCase):
    def setUp(self):
        user = User.objects.create_user(
            email="lifecycle@example.invalid", password="ValidPassword123!"
        )
        self.task = Task.objects.create(user=user, title="Lifecycle test")

    def test_stale_dismiss_retains_completed_state_and_timestamp(self):
        stale = Task.objects.get(pk=self.task.pk)
        complete_task(task=self.task)
        timestamp = self.task.terminated_at
        result = dismiss_task(task=stale)
        self.task.refresh_from_db()
        self.assertEqual(self.task.state, Task.State.COMPLETED)
        self.assertEqual(self.task.terminated_at, timestamp)
        self.assertFalse(result.action_changed)

    def test_stale_actions_cannot_change_deleted_record_or_deletion_time(self):
        stale = Task.objects.get(pk=self.task.pk)
        delete_task(task=self.task)
        timestamp = self.task.deleted_at
        for action in (complete_task, dismiss_task, reactivate_task, delete_task):
            with self.subTest(action=action.__name__):
                result = action(task=stale)
                self.assertFalse(result.action_changed)
                self.task.refresh_from_db()
                self.assertEqual(self.task.deleted_at, timestamp)
                self.assertEqual(self.task.state, Task.State.ACTIVE)
