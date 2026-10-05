from datetime import date, timedelta

from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from issue.models import Issue
from property.models import Property
from task.models import Task
from task.templatetags.work_status import relative_day, status_for


class WorkStatusTests(SimpleTestCase):
    today = date(2026, 9, 23)

    def test_active_task_overdue_and_due_soon(self):
        overdue = Task(completion_deadline=self.today - timedelta(days=9))
        due_today = Task(completion_deadline=self.today)
        due_soon = Task(completion_deadline=self.today + timedelta(days=3))
        later = Task(completion_deadline=self.today + timedelta(days=4))

        self.assertEqual(status_for(overdue, today=self.today).headline, "Overdue by 9 days")
        self.assertEqual(status_for(overdue, today=self.today).list_label, "Overdue")
        self.assertEqual(status_for(due_today, today=self.today).headline, "Due today")
        self.assertEqual(status_for(due_soon, today=self.today).list_label, "Due soon")
        self.assertEqual(status_for(later, today=self.today).kind, "neutral")

    def test_past_scheduled_date_is_not_a_warning(self):
        task = Task(scheduled_date=self.today - timedelta(days=2))
        self.assertEqual(status_for(task, today=self.today).kind, "neutral")

        task.completion_deadline = self.today + timedelta(days=2)
        self.assertEqual(status_for(task, today=self.today).kind, "soon")
        task.completion_deadline = self.today - timedelta(days=1)
        self.assertEqual(status_for(task, today=self.today).kind, "overdue")

    def test_terminal_records_never_show_active_date_warnings(self):
        task = Task(
            state=Task.State.COMPLETED,
            scheduled_date=self.today - timedelta(days=4),
            completion_deadline=self.today - timedelta(days=2),
        )
        issue = Issue(
            state=Issue.State.RESOLVED,
            resolution_deadline=self.today - timedelta(days=2),
        )
        self.assertEqual(status_for(task, today=self.today).kind, "terminal")
        self.assertEqual(status_for(issue, today=self.today).kind, "terminal")

    def test_issue_uses_same_urgency_rules(self):
        issue = Issue(resolution_deadline=self.today - timedelta(days=1))
        self.assertEqual(status_for(issue, today=self.today).headline, "Overdue by 1 day")

    def test_relative_day(self):
        self.assertEqual(relative_day(self.today, self.today), "Today")
        self.assertEqual(relative_day(self.today - timedelta(days=1), self.today), "Yesterday")
        self.assertEqual(relative_day(self.today + timedelta(days=2), self.today), "In 2 days")


class WorkStatusRenderingTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="status@example.com",
            first_name="Alex",
            last_name="Smith",
            password="TestPassword123!",
        )
        self.client.force_login(self.user)
        self.property = Property.objects.create(user=self.user, name="Cedar House")

    def test_task_workspace_shows_compact_status_and_no_nav_counters(self):
        Task.objects.create(
            user=self.user,
            title="Arrange roof inspection",
            property=self.property,
            priority=Task.Priority.HIGH,
            completion_deadline=timezone.localdate() - timedelta(days=2),
        )

        response = self.client.get(reverse("task:tasks"))

        self.assertContains(response, "Overdue by 2 days")
        self.assertNotContains(response, 'class="work-status-strip work-status-strip--overdue"')
        self.assertContains(response, 'class="work-pill work-pill--priority-3"')
        self.assertContains(response, 'class="task-related-link"')
        self.assertNotContains(response, 'class="badge rounded-pill text-bg-secondary">1</span>')

    def test_issue_workspace_uses_same_status_and_link_treatment(self):
        Issue.objects.create(
            user=self.user,
            title="Roof leak",
            property=self.property,
            priority=Issue.Priority.URGENT,
            resolution_deadline=timezone.localdate() - timedelta(days=1),
        )

        response = self.client.get(reverse("issue:issues"))

        self.assertContains(response, "Overdue by 1 day")
        self.assertNotContains(response, 'class="work-status-strip work-status-strip--overdue"')
        self.assertContains(response, 'class="work-pill work-pill--priority-4"')
        self.assertContains(response, 'class="task-related-link"')


class DeadlinePartialTests(SimpleTestCase):
    """Keep the shared date presentation aligned with existing urgency rules."""

    today = date(2026, 9, 23)

    def render_deadline(self, task):
        from django.template.loader import render_to_string

        return render_to_string(
            "task/includes/deadline_detail.html",
            {"task": task, "status": status_for(task, today=self.today), "today": self.today},
        )

    def test_missing_deadline_has_no_relative_date(self):
        rendered = self.render_deadline(Task())
        self.assertIn("No deadline", rendered)
        self.assertNotIn('class="work-date-relative', rendered)

    def test_overdue_deadline_explains_urgency(self):
        rendered = self.render_deadline(Task(completion_deadline=self.today - timedelta(days=2)))
        self.assertIn("21 Sep 2026", rendered)
        self.assertIn("Overdue by 2 days", rendered)
        self.assertIn("task-detail-overdue-date", rendered)

    def test_future_deadline_uses_relative_day(self):
        rendered = self.render_deadline(Task(completion_deadline=self.today + timedelta(days=4)))
        self.assertIn("27 Sep 2026", rendered)
        self.assertIn("In 4 days", rendered)
        self.assertNotIn("task-detail-overdue-date", rendered)

    def test_terminal_deadline_keeps_history_without_active_warning(self):
        task = Task(state=Task.State.COMPLETED, completion_deadline=self.today - timedelta(days=2))
        rendered = self.render_deadline(task)
        self.assertIn("21 Sep 2026", rendered)
        self.assertIn("2 days ago", rendered)
        self.assertNotIn("task-detail-overdue-date", rendered)

    def test_linked_task_labels_preserve_existing_states(self):
        from django.template.loader import render_to_string

        cases = [
            (Task(), "No deadline"),
            (Task(completion_deadline=self.today - timedelta(days=2)), "Overdue"),
            (Task(completion_deadline=self.today), "Due soon"),
            (Task(completion_deadline=self.today + timedelta(days=5)), "Due"),
            (Task(state=Task.State.COMPLETED), "Completed"),
            (Task(state=Task.State.DISMISSED), "Dismissed"),
        ]
        for task, expected in cases:
            with self.subTest(state=task.state, deadline=task.completion_deadline):
                rendered = render_to_string(
                    "issue/includes/linked_task_metadata.html",
                    {"task": task, "status": status_for(task, today=self.today)},
                )
                self.assertIn(expected, rendered)
                if task.state != Task.State.ACTIVE:
                    self.assertNotIn("task-command-deadline--overdue", rendered)
