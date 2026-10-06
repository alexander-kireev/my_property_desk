"""Shared test fixtures and small setup helpers; no tests are defined here."""

from django.utils import timezone

from accounts.models import User
from task.models import Task


class DashboardFixture:
    def setUp(self):
        self.user = User.objects.create_user(
            email="owner@example.com",
            password="A-strong-password-123",
            first_name="Owner",
            last_name="One",
        )
        self.other = User.objects.create_user(
            email="other@example.com",
            password="A-strong-password-123",
            first_name="Other",
            last_name="Two",
        )
        self.client.force_login(self.user)
        self.today = timezone.localdate()
        self.task = Task.objects.create(user=self.user, title="Call contractor")
        Task.objects.create(user=self.other, title="Private task")
