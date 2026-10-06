"""Task form behaviour."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from issue.models import Issue
from property.models import Property

from ..forms import TaskForm
from ..models import Task


class TaskFormTests(TestCase):
    TEST_PASSWORD = "HolidayHome123!"
    TASK_DATA = {
        "title": "call plumber about roof leak",
        "description": "Hill House 4 roof has been leaking since Friday 06.10",
        "priority": Task.Priority.LOW,
    }
    PROPERTY_DATA = {"name": "Hill House 4"}
    ISSUE_DATA = {"title": "Hill House issue"}

    def setUp(self):
        self.user = User.objects.create_user(
            email="alice@example.com",
            first_name="Alice",
            last_name="Smith",
            password=self.TEST_PASSWORD,
        )

    def create_user2(self):
        return User.objects.create_user(
            email="bob.jackson@example.com",
            first_name="Bob",
            last_name="Jackson",
            password=self.TEST_PASSWORD,
        )

    def create_issue(self, *, data, user):
        return Issue.objects.create(user=user, title=data["title"])

    def create_property(self, *, data, user):
        return Property.objects.create(user=user, name=data["name"])

    def create_task(self, *, data, user):
        form = TaskForm(data=data, user=user)
        self.assertTrue(form.is_valid(), form.errors)

        task = form.save(commit=False)
        task.user = user
        form.save()

        return Task.objects.get(pk=task.pk)

    def test_valid_form_can_create_standalone_task(self):
        task = self.create_task(data=self.TASK_DATA, user=self.user)

        self.assertIsNone(task.property)
        self.assertIsNone(task.issue)

    def test_not_linked_edit_clears_existing_issue_without_posting_disabled_picker(self):
        issue = self.create_issue(data=self.ISSUE_DATA, user=self.user)
        task = self.create_task(data={**self.TASK_DATA, "issue": issue.pk}, user=self.user)

        form = TaskForm(
            data={**self.TASK_DATA, "relationship_type": "standalone"},
            user=self.user,
            instance=task,
        )

        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        task.refresh_from_db()
        self.assertIsNone(task.issue_id)

    def test_title_accepts_75_characters_and_rejects_76(self):
        data = {**self.TASK_DATA, "title": "T" * 75}
        self.assertTrue(TaskForm(data=data, user=self.user).is_valid())

        data["title"] = "T" * 76
        form = TaskForm(data=data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)
        self.assertEqual(form.fields["title"].widget.attrs["maxlength"], "75")

    def test_duplicate_name_for_tasks_is_allowed(self):
        self.create_task(data=self.TASK_DATA, user=self.user)
        self.create_task(data=self.TASK_DATA, user=self.user)

        self.assertEqual(Task.objects.filter(title=self.TASK_DATA["title"]).count(), 2)

    def test_valid_form_can_create_task_with_issue_relation(self):
        data = self.TASK_DATA.copy()
        issue = self.create_issue(data=self.ISSUE_DATA, user=self.user)
        data["issue"] = issue
        task = self.create_task(data=data, user=self.user)

        self.assertEqual(task.issue.pk, issue.pk)

    def test_valid_form_can_create_task_with_property_relation(self):
        data = self.TASK_DATA.copy()
        property_record = self.create_property(data=self.PROPERTY_DATA, user=self.user)
        data["property"] = property_record
        task = self.create_task(data=data, user=self.user)

        self.assertEqual(task.property.pk, property_record.pk)

    def test_invalid_form_cannot_create_task_with_issue_and_property_simultaneously(self):
        data = self.TASK_DATA.copy()
        property_record = self.create_property(data=self.PROPERTY_DATA, user=self.user)
        issue = self.create_issue(data=self.ISSUE_DATA, user=self.user)
        data["property"] = property_record
        data["issue"] = issue

        form = TaskForm(data=data, user=self.user)

        self.assertFalse(form.is_valid(), form.errors)
        self.assertIn(
            "A task cannot be related to both a property and an issue simultaneously.",
            form.non_field_errors(),
        )

        self.assertEqual(Task.objects.count(), 0)

    def test_task_can_be_edited_via_form_with_valid_data(self):
        task = self.create_task(data=self.TASK_DATA, user=self.user)
        original_pk = task.pk

        new_data = {
            "title": "amended title",
            "description": "amended description",
            "priority": Task.Priority.HIGH,
        }

        form = TaskForm(data=new_data, user=self.user, instance=task)

        self.assertTrue(form.is_valid())
        updated_task = form.save()
        updated_task.refresh_from_db()

        self.assertEqual(updated_task.pk, original_pk)
        self.assertEqual(updated_task.title, new_data["title"])
        self.assertEqual(updated_task.description, new_data["description"])
        self.assertEqual(updated_task.priority, new_data["priority"])
        self.assertEqual(updated_task.user, self.user)
        self.assertEqual(Task.objects.count(), 1)

    def test_deadline_before_scheduled_date_is_allowed_for_warning(self):
        data = self.TASK_DATA.copy()
        data["scheduled_date"] = timezone.localdate() + timedelta(days=7)
        data["completion_deadline"] = timezone.localdate() + timedelta(days=5)

        form = TaskForm(data=data, user=self.user)

        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_form_with_another_users_issue_relation_is_rejected(self):
        user2 = self.create_user2()
        issue2 = self.create_issue(data=self.ISSUE_DATA, user=user2)
        data = self.TASK_DATA.copy()
        data["issue"] = issue2
        form = TaskForm(data=data, user=self.user)

        self.assertFalse(form.is_valid())
        self.assertIn("issue", form.errors)

    def test_invalid_form_with_another_users_property_relation_is_rejected(self):
        user2 = self.create_user2()
        property2 = self.create_property(data=self.PROPERTY_DATA, user=user2)
        data = self.TASK_DATA.copy()
        data["property"] = property2
        form = TaskForm(data=data, user=self.user)

        self.assertFalse(form.is_valid())
        self.assertIn("property", form.errors)

    def test_property_choices_only_include_users_active_non_deleted_properties(self):
        active_property = Property.objects.create(user=self.user, name="Active property")

        Property.objects.create(
            user=self.user, name="Deactivated property", state=Property.State.DEACTIVATED
        )
        Property.objects.create(user=self.user, name="Deleted property", deleted_at=timezone.now())

        user2 = self.create_user2()

        Property.objects.create(user=user2, name="Another user's active property")

        form = TaskForm(user=self.user)

        available_properties = list(form.fields["property"].queryset)

        self.assertEqual([active_property], available_properties)

    def test_issue_choices_only_include_users_active_non_deleted_properties(self):
        active_issue = Issue.objects.create(user=self.user, title="Active issue")

        Issue.objects.create(user=self.user, title="Dismissed issue", state=Issue.State.DISMISSED)
        Issue.objects.create(user=self.user, title="Resolved issue", state=Issue.State.RESOLVED)
        Issue.objects.create(user=self.user, title="Deleted issue", deleted_at=timezone.now())

        user2 = self.create_user2()

        Issue.objects.create(user=user2, title="Another user's active issue")

        form = TaskForm(user=self.user)

        available_issues = list(form.fields["issue"].queryset)

        self.assertEqual([active_issue], available_issues)

    def test_schedule_and_deadline_accept_past_today_and_future(self):
        today = timezone.localdate()
        for field in ("scheduled_date", "completion_deadline"):
            for offset in (-1, 0, 1):
                with self.subTest(field=field, days_from_today=offset):
                    data = self.TASK_DATA.copy()
                    data[field] = today + timedelta(days=offset)
                    form = TaskForm(data=data, user=self.user)
                    self.assertTrue(form.is_valid(), form.errors)
