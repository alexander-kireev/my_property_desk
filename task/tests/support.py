"""Shared test fixtures and small setup helpers; no tests are defined here."""

from django.urls import reverse

from accounts.models import User

from ..models import Task


class TaskViewFixture:
    TEST_PASSWORD = "HolidayHome123!"

    VALID_DATA = {
        "title": "Arrange roof repair",
        "description": "Ask the roofer to inspect the west elevation.",
        "property": "",
        "issue": "",
        "priority": Task.Priority.HIGH,
        "scheduled_date": "",
        "completion_deadline": "",
    }

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

    def create_task(
        self,
        *,
        user=None,
        title="Arrange roof repair",
        state=Task.State.ACTIVE,
        terminated_at=None,
        deleted_at=None,
        property_record=None,
        issue=None,
    ):
        return Task.objects.create(
            user=user or self.user,
            title=title,
            description="Ask the roofer to inspect the west elevation.",
            priority=Task.Priority.MEDIUM,
            state=state,
            terminated_at=terminated_at,
            deleted_at=deleted_at,
            property=property_record,
            issue=issue,
        )

    def task_url(self, name, task):
        return reverse(f"task:{name}", kwargs={"task_id": task.pk})
