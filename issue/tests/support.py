"""Shared test fixtures and small setup helpers; no tests are defined here."""

from accounts.models import User
from property.models import Property
from task.models import Task

from ..models import Issue


class IssueTestMixin:
    password = "HolidayHome123!"

    def create_user(self, email="alice@example.com"):
        return User.objects.create_user(
            email=email,
            first_name="Alice",
            last_name="Smith",
            password=self.password,
        )

    def create_property(self, user, name="Hill House", **values):
        return Property.objects.create(user=user, name=name, **values)

    def create_issue(self, user, title="Roof leak", **values):
        return Issue.objects.create(user=user, title=title, **values)

    def create_task(self, user, issue, title="Arrange contractor", **values):
        return Task.objects.create(user=user, issue=issue, title=title, **values)
