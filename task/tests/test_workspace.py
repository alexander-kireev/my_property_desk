"""Task workspace behaviour."""

import re
from datetime import timedelta

from django.test import TestCase
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from issue.models import Issue

from ..models import Task
from .support import TaskViewFixture


class TaskViewWorkspaceTests(TaskViewFixture, TestCase):
    def test_linked_task_relationship_is_qualified_in_list_and_detail(self):
        issue = Issue.objects.create(user=self.user, title="Water ingress")
        task = self.create_task(issue=issue)
        self.client.force_login(self.user)

        response = self.client.get(reverse("task:tasks"), {"selected": task.pk})

        self.assertContains(response, 'title="Water ingress"')
        self.assertContains(response, '<dt class="fw-normal text-body-secondary">Related to</dt>')
        self.assertContains(response, '<span class="task-related-copy">Water ingress</span>')
        self.assertContains(response, '<h3 class="h5 mb-3">Details</h3>')
        self.assertNotContains(response, "Related to: Issue ·")
        self.assertContains(
            response,
            'class="expandable-text expandable-text--fit-card expandable-text--inline-end"',
        )

    def test_task_list_defaults_to_all_states_and_can_filter_terminal_states(self):
        active = self.create_task(title="Active task")
        completed = self.create_task(title="Completed task", state=Task.State.COMPLETED)
        dismissed = self.create_task(title="Dismissed task", state=Task.State.DISMISSED)
        self.client.force_login(self.user)

        for query, expected in (
            ({}, [active, completed, dismissed]),
            ({"state": Task.State.COMPLETED}, [completed]),
            ({"state": Task.State.DISMISSED}, [dismissed]),
            ({"state": "all"}, [active, completed, dismissed]),
        ):
            with self.subTest(query=query):
                response = self.client.get(reverse("task:tasks"), query)
                self.assertCountEqual(response.context["page_obj"].object_list, expected)
                if not query:
                    html = response.content.decode()
                    for task, label in ((completed, "Completed"), (dismissed, "Dismissed")):
                        row = re.search(
                            rf'<a class="task-command-row\b[^>]*selected={task.pk}[^>]*>.*?</a>',
                            html,
                            re.S,
                        )
                        self.assertIsNotNone(row)
                        self.assertIn(f'data-state="{task.state}"', row.group())
                        deadline = re.search(
                            r'<span class="task-command-deadline[^\"]*">(.*?)</span>',
                            row.group(),
                            re.S,
                        )
                        self.assertIsNotNone(deadline)
                        self.assertNotIn(label, deadline.group(1))

    def test_workspace_wires_shared_list_scroll_restoration(self):
        task = self.create_task()
        self.client.force_login(self.user)

        response = self.client.get(reverse("task:tasks"), {"selected": task.pk})

        self.assertContains(response, 'data-workspace-scroll-root="tasks"')
        self.assertContains(response, "data-workspace-scroll-list")
        self.assertContains(response, "data-workspace-scroll-row")
        self.assertContains(response, "js/workspace-list-scroll.js")

    def test_explicit_selection_enables_short_screen_detail_mode(self):
        task = self.create_task()
        self.client.force_login(self.user)

        list_response = self.client.get(reverse("task:tasks"))
        detail_response = self.client.get(reverse("task:tasks"), {"selected": task.pk})

        self.assertNotContains(list_response, "show-compact-detail")
        self.assertContains(detail_response, "show-compact-detail")
        self.assertContains(detail_response, "← Back to tasks")

    def test_terminal_only_task_list_is_visible_by_default(self):
        self.create_task(state=Task.State.COMPLETED)
        self.client.force_login(self.user)

        response = self.client.get(reverse("task:tasks"))

        self.assertEqual(len(response.context["page_obj"].object_list), 1)
        self.assertEqual(response.context["selected_task"].state, Task.State.COMPLETED)

    def test_task_endpoints_require_login_without_mutating_task(self):
        task = self.create_task()
        original_values = (
            task.title,
            task.state,
            task.terminated_at,
            task.deleted_at,
        )
        endpoints = (
            ("get", reverse("task:tasks"), None),
            ("post", reverse("task:add_task"), self.VALID_DATA),
            ("post", self.task_url("edit_task", task), self.VALID_DATA),
            ("post", self.task_url("dismiss_task", task), None),
            ("post", self.task_url("complete_task", task), None),
            ("post", self.task_url("reactivate_task", task), None),
            ("post", self.task_url("delete_task", task), None),
        )

        for method, url, data in endpoints:
            with self.subTest(method=method, url=url):
                if method == "get":
                    response = self.client.get(url, data=data)
                else:
                    response = self.client.post(url, data=data)
                task.refresh_from_db()

                self.assertRedirects(
                    response,
                    f"{reverse('accounts:login')}?next={url}",
                )
                self.assertEqual(
                    (
                        task.title,
                        task.state,
                        task.terminated_at,
                        task.deleted_at,
                    ),
                    original_values,
                )
                self.assertEqual(Task.objects.count(), 1)

    def test_task_views_reject_unsupported_http_methods(self):
        task = self.create_task()
        self.client.force_login(self.user)
        endpoints = (
            ("post", reverse("task:tasks")),
            ("get", reverse("task:add_task")),
            ("get", self.task_url("edit_task", task)),
            ("get", self.task_url("dismiss_task", task)),
            ("get", self.task_url("complete_task", task)),
            ("get", self.task_url("reactivate_task", task)),
            ("get", self.task_url("delete_task", task)),
        )

        for method, url in endpoints:
            with self.subTest(method=method, url=url):
                if method == "get":
                    response = self.client.get(url)
                else:
                    response = self.client.post(url)

                self.assertEqual(response.status_code, 405)

        task.refresh_from_db()
        self.assertEqual(task.state, Task.State.ACTIVE)
        self.assertIsNone(task.deleted_at)

    def test_tasks_view_displays_zero_task_state(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("task:tasks"))

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "task/tasks.html")
        self.assertEqual(response.context["page_obj"].paginator.count, 0)
        self.assertContains(response, "No tasks yet")

    def test_tasks_view_paginates_fifty_one_tasks_as_twenty_twenty_eleven(self):
        for number in range(51):
            self.create_task(title=f"Task {number:02}")
        self.client.force_login(self.user)

        page_sizes = {1: 20, 2: 20, 3: 11}

        for page_number, expected_size in page_sizes.items():
            with self.subTest(page=page_number):
                response = self.client.get(
                    reverse("task:tasks"),
                    {"page": page_number},
                )

                self.assertEqual(response.status_code, 200)
                self.assertEqual(
                    len(response.context["page_obj"]),
                    expected_size,
                )
                self.assertEqual(
                    response.context["page_obj"].paginator.count,
                    51,
                )
                self.assertContains(response, f"Page {page_number} of 3")

        first_page = self.client.get(reverse("task:tasks"))
        last_page = self.client.get(reverse("task:tasks"), {"page": 3})
        self.assertContains(first_page, 'aria-disabled="true">← Previous</span>')
        self.assertContains(last_page, 'aria-disabled="true">Next →</span>')

    def test_tasks_view_preserves_valid_list_parameters_for_pagination(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("task:tasks"),
            {
                "search": "roof",
                "state": Task.State.ACTIVE,
                "priority": Task.Priority.HIGH,
                "scheduled_period": "next_7_days",
                "deadline_period": "overdue",
                "sort": "-created_at",
                "page": 2,
            },
        )

        self.assertEqual(
            response.context["list_query"],
            "search=roof&state=active&priority=3&scheduled_period="
            "next_7_days&deadline_period=overdue&sort=-created_at",
        )

    def test_upcoming_url_is_canonicalised_without_losing_other_context(self):
        self.client.force_login(self.user)
        response = self.client.get(
            reverse("task:tasks"),
            {
                "search": "roof",
                "scheduled_period": "upcoming",
                "sort": "-created_at",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("search=roof", response.url)
        self.assertIn("sort=-created_at", response.url)
        self.assertNotIn("upcoming", response.url)

    def test_tasks_view_honours_selected_task_on_displayed_page(self):
        self.create_task(title="First task")
        selected_task = self.create_task(title="Selected task")
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("task:tasks"),
            {"selected": selected_task.pk},
        )

        self.assertEqual(response.context["selected_task"], selected_task)
        self.assertContains(response, 'aria-current="true"')
        self.assertContains(
            response, "task-command-row work-summary-row list-group-item list-group-item-action is-selected"
        )

    def test_selected_task_expands_inline_until_full_record_is_requested(self):
        task = self.create_task(title="Mobile preview")
        task.scheduled_date = timezone.localdate() - timedelta(days=60)
        task.completion_deadline = task.scheduled_date
        task.save(update_fields=["scheduled_date", "completion_deadline"])
        self.client.force_login(self.user)

        preview = self.client.get(reverse("task:tasks"), {"selected": task.pk})
        self.assertEqual(preview.context["mobile_expanded_task_id"], task.pk)
        self.assertFalse(preview.context["show_mobile_detail"])
        self.assertContains(preview, f'id="taskInlineDetails{task.pk}"')
        self.assertContains(preview, '<h3 class="task-inline-section-title">Description</h3>')
        self.assertContains(preview, '<h3 class="task-inline-section-title">Details</h3>')
        self.assertContains(preview, "<dt>Status</dt>")
        self.assertContains(preview, "<dt>Priority</dt>")
        self.assertContains(preview, "<dt>Created</dt>")
        self.assertContains(preview, "60 days ago")
        self.assertContains(preview, "Overdue by 60 days")
        self.assertContains(preview, "Open record →")

        full_record = self.client.get(
            reverse("task:tasks"), {"selected": task.pk, "open": "detail"}
        )
        self.assertTrue(full_record.context["show_mobile_detail"])
        self.assertIsNone(full_record.context["mobile_expanded_task_id"])

    def test_tasks_view_rejects_inaccessible_selected_task(self):
        visible_task = self.create_task(title="Visible task")
        other_task = self.create_task(user=self.other_user, title="Other task")
        deleted_task = self.create_task(
            title="Deleted task",
            deleted_at=timezone.now(),
        )
        self.client.force_login(self.user)

        for selected_id in (other_task.pk, deleted_task.pk, "invalid"):
            with self.subTest(selected=selected_id):
                response = self.client.get(
                    reverse("task:tasks"),
                    {"selected": selected_id},
                )
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, reverse("task:tasks"))
                fallback = self.client.get(response.url)
                self.assertEqual(fallback.context["selected_task"], visible_task)
                self.assertNotContains(fallback, other_task.title)
                self.assertNotContains(fallback, deleted_task.title)

    def test_tasks_view_corrects_page_to_selected_task(self):
        tasks = [self.create_task(title=f"Task {number:02}") for number in range(21)]
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("task:tasks"),
            {"page": 1, "selected": tasks[-1].pk},
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("page=2", response.url)
        corrected = self.client.get(response.url)
        self.assertEqual(corrected.context["selected_task"], tasks[-1])

        linked_response = self.client.get(
            reverse("task:tasks"),
            {"page": 1, "selected": tasks[-1].pk, "open": "detail"},
        )
        self.assertEqual(linked_response.status_code, 302)
        self.assertEqual(self.client.get(linked_response.url).context["selected_task"], tasks[-1])

    def test_task_detail_route_has_been_removed(self):
        with self.assertRaises(NoReverseMatch):
            reverse("task:task_detail", kwargs={"task_id": 1})

    def test_mutation_views_return_404_for_another_users_task(self):
        active_task = self.create_task(user=self.other_user)
        dismissed_task = self.create_task(
            user=self.other_user,
            title="Another user's dismissed task",
            state=Task.State.DISMISSED,
            terminated_at=timezone.now(),
        )
        self.client.force_login(self.user)
        endpoints = (
            ("edit_task", active_task),
            ("dismiss_task", active_task),
            ("complete_task", active_task),
            ("reactivate_task", dismissed_task),
            ("delete_task", active_task),
        )

        for view_name, task in endpoints:
            with self.subTest(view=view_name):
                response = self.client.post(
                    self.task_url(view_name, task),
                    data=self.VALID_DATA if view_name == "edit_task" else None,
                )

                self.assertEqual(response.status_code, 404)

        active_task.refresh_from_db()
        dismissed_task.refresh_from_db()
        self.assertEqual(active_task.state, Task.State.ACTIVE)
        self.assertIsNone(active_task.deleted_at)
        self.assertEqual(dismissed_task.state, Task.State.DISMISSED)

    def test_tasks_view_supplies_own_count_and_no_notes_ui(self):
        self.create_task()
        Issue.objects.create(user=self.user, title="Roof leak")
        self.client.force_login(self.user)

        response = self.client.get(reverse("task:tasks"))

        self.assertEqual(response.context["task_count"], 1)
        self.assertNotContains(response, "Task notes")
        self.assertNotContains(response, "NotesBoard")

    def test_tasks_view_distinguishes_filtered_empty_from_first_use(self):
        self.create_task(title="Existing task")
        self.client.force_login(self.user)

        response = self.client.get(reverse("task:tasks"), {"search": "missing"})

        self.assertEqual(response.context["task_count"], 1)
        self.assertIsNone(response.context["selected_task"])
        self.assertContains(response, "No matching tasks")
        self.assertNotContains(response, "Add your first task")
