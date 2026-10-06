"""Task actions behaviour."""

from datetime import timedelta
from unittest.mock import patch

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from issue.models import Issue
from property.models import Property

from ..forms import TaskForm
from ..models import Task
from .support import TaskViewFixture


class TaskViewActionsTests(TaskViewFixture, TestCase):
    def test_task_modal_form_uses_top_labels_and_named_confirmation_actions(self):
        self.client.force_login(self.user)
        self.create_task()

        response = self.client.get(reverse("task:tasks"))

        html = response.content.decode()
        self.assertRegex(html, r'class="form-label" for="[^"]+">Title</label>')
        self.assertRegex(html, r'class="form-label" for="[^"]+">Description</label>')
        self.assertRegex(html, r'class="task-relationship-label"\s+id="[^"]+">Related to</span>')
        self.assertNotContains(response, 'class="col-md-4 col-form-label"')
        self.assertRegex(html, r'type="button"\s+data-bs-dismiss="modal">Keep task</button>')
        self.assertContains(
            response, 'class="btn theme-action" type="submit">Dismiss task</button>'
        )

    def test_deleted_parent_names_keep_boxed_non_linked_markup(self):
        self.client.force_login(self.user)
        property_record = Property.objects.create(
            user=self.user,
            name="Former property " + "W" * 55,
            deleted_at=timezone.now(),
        )
        issue = Issue.objects.create(
            user=self.user,
            title="Former issue " + "I" * 55,
            deleted_at=timezone.now(),
        )
        for task in (
            self.create_task(property_record=property_record),
            self.create_task(issue=issue),
        ):
            with self.subTest(task=task.pk):
                response = self.client.get(
                    reverse("task:tasks"),
                    {"selected": task.pk, "open": "detail"},
                )
                self.assertContains(response, 'class="task-related-deleted"')
                self.assertContains(response, 'class="task-related-copy"')
                self.assertNotContains(response, "Deleted property")
                self.assertNotContains(response, "Deleted issue")
                mobile_response = self.client.get(
                    reverse("task:tasks"),
                    {"selected": task.pk},
                )
                self.assertContains(mobile_response, 'class="task-related-copy"')

    def test_tasks_view_displays_ten_owned_non_deleted_tasks_only(self):
        own_tasks = [self.create_task(title=f"Owned task {number:02}") for number in range(10)]
        other_task = self.create_task(
            user=self.other_user,
            title="Another user's task",
        )
        deleted_task = self.create_task(
            title="Soft-deleted task",
            deleted_at=timezone.now(),
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("task:tasks"))
        displayed_tasks = list(response.context["page_obj"].object_list)

        self.assertEqual(displayed_tasks, own_tasks)
        for task in own_tasks:
            self.assertContains(response, task.title)
        self.assertNotContains(response, other_task.title)
        self.assertNotContains(response, deleted_task.title)

    def test_tasks_view_supplies_clean_unbound_add_form(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("task:tasks"))
        form = response.context["add_task_form"]

        self.assertIsInstance(form, TaskForm)
        self.assertFalse(form.is_bound)
        self.assertEqual(form.errors, {})

    def test_unchanged_edit_does_not_write_or_claim_success(self):
        task = self.create_task()
        self.client.force_login(self.user)
        data = {
            **self.VALID_DATA,
            "title": f"  {task.title}  ",
            "priority": task.priority,
        }
        with patch("task.views.update_task") as update:
            response = self.client.post(reverse("task:edit_task", args=[task.pk]), data)
        self.assertEqual(response.status_code, 302)
        update.assert_not_called()
        self.assertEqual(list(get_messages(response.wsgi_request)), [])

    def test_tasks_view_normalises_invalid_and_default_list_parameters(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("task:tasks"),
            {
                "search": "  roof  ",
                "state": "invalid",
                "priority": "invalid",
                "scheduled_period": "invalid",
                "deadline_period": "invalid",
                "sort": "invalid",
                "page": 4,
            },
        )

        self.assertEqual(response.context["search"], "roof")
        self.assertEqual(response.context["state"], "all")
        self.assertEqual(response.context["priority"], "")
        self.assertEqual(response.context["scheduled_period"], "")
        self.assertEqual(response.context["deadline_period"], "")
        self.assertEqual(response.context["sort"], "completion_deadline")
        self.assertEqual(response.context["list_query"], "search=roof")

    def test_tasks_view_selects_first_task_and_supplies_clean_edit_form(self):
        task = self.create_task(title="First task")
        self.create_task(title="Second task")
        self.client.force_login(self.user)

        response = self.client.get(reverse("task:tasks"))
        form = response.context["edit_task_form"]

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "task/tasks.html")
        self.assertEqual(response.context["selected_task"], task)
        self.assertContains(response, task.title)
        self.assertIsInstance(form, TaskForm)
        self.assertFalse(form.is_bound)
        self.assertEqual(form.instance, task)
        self.assertEqual(form.errors, {})

    def test_edit_task_view_updates_active_task_and_redirects_to_workspace(self):
        task = self.create_task(title="Original title")
        property_record = Property.objects.create(
            user=self.user,
            name="Hill House",
        )
        scheduled_date = timezone.localdate() + timedelta(days=1)
        completion_deadline = timezone.localdate() + timedelta(days=7)
        data = {
            "title": "Updated title",
            "description": "Updated description",
            "property": property_record.pk,
            "issue": "",
            "priority": Task.Priority.URGENT,
            "scheduled_date": scheduled_date.isoformat(),
            "completion_deadline": completion_deadline.isoformat(),
        }
        self.client.force_login(self.user)

        response = self.client.post(
            self.task_url("edit_task", task),
            data=data,
        )
        task.refresh_from_db()

        self.assertRedirects(
            response,
            f"{reverse('task:tasks')}?selected={task.pk}",
        )
        self.assertEqual(task.title, data["title"])
        self.assertEqual(task.description, data["description"])
        self.assertEqual(task.property, property_record)
        self.assertIsNone(task.issue)
        self.assertEqual(task.priority, Task.Priority.URGENT)
        self.assertEqual(task.scheduled_date, scheduled_date)
        self.assertEqual(task.completion_deadline, completion_deadline)

    def test_edit_task_view_rerenders_bound_form_without_partial_update(self):
        task = self.create_task(title="Original title")
        original_values = (
            task.title,
            task.description,
            task.priority,
            task.scheduled_date,
            task.completion_deadline,
        )
        data = self.VALID_DATA.copy()
        data["title"] = ""
        data["description"] = "Attempted update"
        data["priority"] = Task.Priority.URGENT
        self.client.force_login(self.user)

        post_response = self.client.post(
            self.task_url("edit_task", task),
            data=data,
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn(f"selected={task.pk}", post_response.url)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)
        task.refresh_from_db()
        form = response.context["edit_task_form"]

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "task/tasks.html")
        self.assertEqual(response.context["selected_task"], task)
        self.assertEqual(response.context["open_modal"], "editTaskModal")
        self.assertTrue(form.is_bound)
        self.assertEqual(form.data["title"], data["title"])
        self.assertEqual(form.data["description"], data["description"])
        self.assertEqual(
            form.data["priority"],
            str(data["priority"]),
        )
        self.assertIn("title", form.errors)
        self.assertEqual(
            (
                task.title,
                task.description,
                task.priority,
                task.scheduled_date,
                task.completion_deadline,
            ),
            original_values,
        )

    def test_edit_task_view_returns_404_for_terminated_tasks(self):
        terminated_at = timezone.now() - timedelta(days=1)
        self.client.force_login(self.user)

        for state in (Task.State.DISMISSED, Task.State.COMPLETED):
            with self.subTest(state=state):
                task = self.create_task(
                    title=f"{state} task",
                    state=state,
                    terminated_at=terminated_at,
                )
                response = self.client.post(
                    self.task_url("edit_task", task),
                    data=self.VALID_DATA,
                )

                self.assertEqual(response.status_code, 404)

    def test_dismiss_task_view_dismisses_active_task_and_redirects(self):
        task = self.create_task()
        dismissed_at = timezone.now() + timedelta(minutes=1)
        self.client.force_login(self.user)

        with patch("task.services.timezone.now", return_value=dismissed_at):
            response = self.client.post(self.task_url("dismiss_task", task))
        task.refresh_from_db()

        self.assertRedirects(
            response,
            f"{reverse('task:tasks')}?selected={task.pk}",
        )
        self.assertEqual(task.state, Task.State.DISMISSED)
        self.assertEqual(task.terminated_at, dismissed_at)

    def test_dismiss_task_view_returns_404_for_terminated_tasks(self):
        terminated_at = timezone.now() - timedelta(days=1)
        self.client.force_login(self.user)

        for state in (Task.State.DISMISSED, Task.State.COMPLETED):
            with self.subTest(state=state):
                task = self.create_task(
                    title=f"{state} task",
                    state=state,
                    terminated_at=terminated_at,
                )
                response = self.client.post(self.task_url("dismiss_task", task))

                self.assertEqual(response.status_code, 404)

    def test_complete_task_view_completes_active_task_and_redirects(self):
        task = self.create_task()
        completed_at = timezone.now() + timedelta(minutes=1)
        self.client.force_login(self.user)

        with patch("task.services.timezone.now", return_value=completed_at):
            response = self.client.post(self.task_url("complete_task", task))
        task.refresh_from_db()

        self.assertRedirects(
            response,
            f"{reverse('task:tasks')}?selected={task.pk}",
        )
        self.assertEqual(task.state, Task.State.COMPLETED)
        self.assertEqual(task.terminated_at, completed_at)

    def test_complete_task_view_returns_404_for_terminated_tasks(self):
        terminated_at = timezone.now() - timedelta(days=1)
        self.client.force_login(self.user)

        for state in (Task.State.COMPLETED, Task.State.DISMISSED):
            with self.subTest(state=state):
                task = self.create_task(
                    title=f"{state} task",
                    state=state,
                    terminated_at=terminated_at,
                )
                response = self.client.post(self.task_url("complete_task", task))

                self.assertEqual(response.status_code, 404)

    def test_reactivate_task_view_reactivates_terminated_tasks_and_redirects(self):
        terminated_at = timezone.now() - timedelta(days=1)
        self.client.force_login(self.user)

        for state in (Task.State.DISMISSED, Task.State.COMPLETED):
            with self.subTest(state=state):
                task = self.create_task(
                    title=f"{state} task",
                    state=state,
                    terminated_at=terminated_at,
                )
                response = self.client.post(self.task_url("reactivate_task", task))
                task.refresh_from_db()

                self.assertRedirects(
                    response,
                    f"{reverse('task:tasks')}?selected={task.pk}",
                )
                self.assertEqual(task.state, Task.State.ACTIVE)
                self.assertIsNone(task.terminated_at)

    def test_reactivate_task_view_returns_404_for_active_task(self):
        task = self.create_task()
        self.client.force_login(self.user)

        response = self.client.post(self.task_url("reactivate_task", task))

        self.assertEqual(response.status_code, 404)

    def test_delete_task_view_soft_deletes_each_lifecycle_state_and_redirects(self):
        terminated_at = timezone.now() - timedelta(days=1)
        deleted_at = timezone.now() + timedelta(minutes=1)
        self.client.force_login(self.user)

        for state in Task.State.values:
            with self.subTest(state=state):
                task = self.create_task(
                    title=f"{state} task",
                    state=state,
                    terminated_at=(None if state == Task.State.ACTIVE else terminated_at),
                )
                with patch(
                    "task.services.timezone.now",
                    return_value=deleted_at,
                ):
                    response = self.client.post(self.task_url("delete_task", task))
                task.refresh_from_db()

                self.assertRedirects(response, reverse("task:tasks"))
                self.assertEqual(task.deleted_at, deleted_at)
                self.assertTrue(Task.objects.filter(pk=task.pk).exists())

    def test_soft_deleted_tasks_are_inaccessible_from_task_endpoints(self):
        deleted_at = timezone.now()
        active_task = self.create_task(deleted_at=deleted_at)
        dismissed_task = self.create_task(
            title="Soft-deleted dismissed task",
            state=Task.State.DISMISSED,
            terminated_at=timezone.now() - timedelta(days=1),
            deleted_at=deleted_at,
        )
        self.client.force_login(self.user)
        endpoints = (
            ("edit_task", active_task, self.VALID_DATA),
            ("dismiss_task", active_task, None),
            ("complete_task", active_task, None),
            ("reactivate_task", dismissed_task, None),
            ("delete_task", active_task, None),
        )

        for view_name, task, data in endpoints:
            with self.subTest(view=view_name):
                response = self.client.post(
                    self.task_url(view_name, task),
                    data=data,
                )
                self.assertEqual(response.status_code, 404)

    def test_add_task_view_with_valid_data_creates_task_and_assigns_to_correct_user(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("task:add_task"),
            data=self.VALID_DATA,
        )

        task = Task.objects.get(title=self.VALID_DATA["title"])

        self.assertEqual(task.user, self.user)
        self.assertRedirects(
            response,
            f"{reverse('task:tasks')}?selected={task.pk}",
        )

    def test_add_task_clears_stale_search_and_page(self):
        self.client.force_login(self.user)
        response = self.client.post(
            f"{reverse('task:add_task')}?search=unrelated&page=3",
            data=self.VALID_DATA,
        )
        task = Task.objects.get(title=self.VALID_DATA["title"])
        self.assertEqual(response.url, f"{reverse('task:tasks')}?selected={task.pk}")

    def test_add_task_view_with_invalid_data_returns_bound_form_with_error_and_does_not_create_task(
        self,
    ):
        data = self.VALID_DATA.copy()
        data["title"] = ""

        self.client.force_login(self.user)

        url = f"{reverse('task:add_task')}?search=call_plumber&sort=-created_at"

        post_response = self.client.post(url, data=data)

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("search=call_plumber", post_response.url)
        self.assertIn("sort=-created_at", post_response.url)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("title", response.context["add_task_form"].errors)
        self.assertTrue(response.context["add_task_form"].is_bound)
        self.assertEqual(response.context["search"], "call_plumber")
        self.assertEqual(response.context["sort"], "-created_at")
        self.assertEqual(response.context["open_modal"], "addTaskModal")
        self.assertEqual(Task.objects.count(), 0)
        self.assertEqual(response.context["list_query"], "search=call_plumber&sort=-created_at")

    def test_linked_task_action_accepts_its_issue_workspace_return(self):
        issue = Issue.objects.create(user=self.user, title="Roof leak")
        task = self.create_task(issue=issue)
        next_url = f"{reverse('issue:issues')}?selected={issue.pk}&tab=tasks"
        self.client.force_login(self.user)

        response = self.client.post(
            self.task_url("complete_task", task),
            {"next": next_url},
        )

        self.assertRedirects(response, next_url)

    def test_task_action_rejects_external_and_forged_issue_returns(self):
        issue = Issue.objects.create(user=self.user, title="Roof leak")
        other_issue = Issue.objects.create(user=self.user, title="Boiler fault")
        linked_task = self.create_task(issue=issue)
        unlinked_task = self.create_task(title="Standalone task")
        self.client.force_login(self.user)

        for task, next_url in (
            (linked_task, "https://example.com/steal"),
            (
                linked_task,
                f"{reverse('issue:issues')}?selected={other_issue.pk}&tab=tasks",
            ),
            (
                unlinked_task,
                f"{reverse('issue:issues')}?selected={issue.pk}&tab=tasks",
            ),
        ):
            task.state = Task.State.ACTIVE
            task.terminated_at = None
            task.save(update_fields=["state", "terminated_at"])
            with self.subTest(next=next_url):
                response = self.client.post(
                    self.task_url("complete_task", task),
                    {"next": next_url},
                )
                self.assertRedirects(
                    response,
                    f"{reverse('task:tasks')}?selected={task.pk}",
                )
