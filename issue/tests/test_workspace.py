"""Issue workspace behaviour."""

import re
from datetime import timedelta

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from task.models import Task

from ..models import Issue
from .support import IssueTestMixin


class IssueViewTests(IssueTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.client.force_login(self.user)
        self.property = self.create_property(self.user)
        self.issue = self.create_issue(
            self.user, property=self.property, priority=Issue.Priority.URGENT
        )

    def test_explicit_selection_enables_short_screen_detail_mode(self):
        list_response = self.client.get(reverse("issue:issues"))
        detail_response = self.client.get(reverse("issue:issues"), {"selected": self.issue.pk})

        self.assertNotContains(list_response, "show-compact-detail")
        self.assertContains(detail_response, "show-compact-detail")
        self.assertContains(detail_response, "← Back to issues")

    def test_confirmation_omits_redundant_issue_box_and_keeps_linked_task_choice(self):
        self.issue.title = "Roof " + "X" * 70
        self.issue.save(update_fields=["title"])
        self.create_task(self.user, self.issue)

        response = self.client.get(reverse("issue:issues"))

        self.assertContains(response, 'id="resolveIssueModalLabel">Resolve issue?</h2>')
        self.assertNotContains(response, 'class="modal-context')
        self.assertContains(response, 'id="resolveLinkedTasks"')
        self.assertContains(response, 'class="btn btn-danger" type="submit">Delete issue')

    def test_issue_forms_use_top_labels_and_readonly_parent_issue(self):
        self.issue.title = "Long issue " + "X" * 64
        self.issue.save(update_fields=["title"])

        response = self.client.get(reverse("issue:issues"))

        self.assertRegex(response.content.decode(), r'class="form-label" for="[^"]+">Title</label>')
        self.assertNotContains(response, 'class="col-md-4 col-form-label"')
        self.assertContains(response, 'id="issueAddTaskRelatedIssueLabel">Related issue</span>')
        self.assertRegex(
            response.content.decode(),
            rf'id="issueAddTaskRelatedIssue"\s+role="note"\s+tabindex="0"\s+aria-labelledby="issueAddTaskRelatedIssueLabel">{self.issue.title}</div>',
        )
        self.assertNotContains(response, ">Locked</span>")
        self.assertContains(
            response, "<p>The issue will be marked as resolved and retained in your history.</p>"
        )

    def test_issue_relationship_is_qualified_in_list_and_detail(self):
        response = self.client.get(reverse("issue:issues"), {"selected": self.issue.pk})

        self.assertContains(response, 'title="Hill House"')
        self.assertContains(response, "<dt>Related to</dt>")
        self.assertContains(response, '<span class="task-related-copy">Hill House</span>')
        self.assertContains(response, '<a class="task-related-link"')
        self.assertContains(response, '<h3 class="h5 mb-3">Details</h3>')
        self.assertNotContains(response, "Related to: Property ·")
        self.assertContains(
            response,
            'class="expandable-text expandable-text--fit-card expandable-text--inline-end"',
        )

    def test_issue_list_defaults_to_all_states_and_can_filter_terminal_states(self):
        resolved = self.create_issue(self.user, "Resolved issue", state=Issue.State.RESOLVED)
        dismissed = self.create_issue(self.user, "Dismissed issue", state=Issue.State.DISMISSED)

        for query, expected in (
            ({}, [self.issue, resolved, dismissed]),
            ({"state": Issue.State.RESOLVED}, [resolved]),
            ({"state": Issue.State.DISMISSED}, [dismissed]),
            ({"state": "all"}, [self.issue, resolved, dismissed]),
        ):
            with self.subTest(query=query):
                response = self.client.get(reverse("issue:issues"), query)
                self.assertCountEqual(response.context["page_obj"].object_list, expected)
                if not query:
                    html = response.content.decode()
                    for issue, label in ((resolved, "Resolved"), (dismissed, "Dismissed")):
                        row = re.search(
                            rf'<a class="issue-list-row\b[^>]*selected={issue.pk}[^>]*>.*?</a>',
                            html,
                            re.S,
                        )
                        self.assertIsNotNone(row)
                        self.assertIn(f'data-state="{issue.state}"', row.group())
                        deadline = re.search(
                            r'<span class="issue-command-deadline[^\"]*">(.*?)</span>',
                            row.group(),
                            re.S,
                        )
                        self.assertIsNotNone(deadline)
                        self.assertNotIn(label, deadline.group(1))

    def test_terminal_only_issue_list_is_visible_by_default(self):
        self.issue.state = Issue.State.RESOLVED
        self.issue.save(update_fields=["state"])

        response = self.client.get(reverse("issue:issues"))

        self.assertEqual(len(response.context["page_obj"].object_list), 1)
        self.assertEqual(response.context["selected_issue"].state, Issue.State.RESOLVED)

    def test_issue_details_count_only_active_linked_tasks(self):
        self.create_task(self.user, self.issue)
        completed = self.create_task(self.user, self.issue)
        completed.state = Task.State.COMPLETED
        completed.save(update_fields=["state"])
        deleted = self.create_task(self.user, self.issue)
        deleted.deleted_at = timezone.now()
        deleted.save(update_fields=["deleted_at"])
        response = self.client.get(reverse("issue:issues"))
        listed = response.context["page_obj"].object_list[0]
        self.assertEqual(listed.active_task_count, 1)
        self.assertContains(response, "<dt>Active tasks</dt><dd>1</dd>", html=True)

    def issue_data(self, **overrides):
        data = {
            "title": "Boiler losing pressure",
            "description": "Pressure drops overnight",
            "property": self.property.pk,
            "priority": Issue.Priority.HIGH,
            "resolution_deadline": (timezone.localdate() + timedelta(days=3)).isoformat(),
        }
        data.update(overrides)
        return data

    def task_data(self, **overrides):
        data = {
            "title": "Call contractor",
            "description": "Arrange inspection",
            "priority": Task.Priority.HIGH,
            "scheduled_date": "",
            "completion_deadline": "",
        }
        data.update(overrides)
        return data

    def test_issues_view_renders_selected_issue_and_tasks(self):
        task = self.create_task(self.user, self.issue)

        response = self.client.get(
            reverse("issue:issues"),
            {"selected": self.issue.pk, "tab": "tasks"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_issue"], self.issue)
        self.assertEqual(list(response.context["selected_tasks"]), [task])
        self.assertEqual(response.context["active_tab"], "tasks")
        self.assertContains(response, 'class="issue-task-scroll"')
        self.assertContains(response, 'class="issue-linked-tasks-card"')
        self.assertContains(response, 'class="issue-task-summary issue-linked-task-grid')

    def test_linked_task_actions_are_in_expanded_details_without_row_menu(self):
        active_task = self.create_task(self.user, self.issue)
        completed_task = self.create_task(
            self.user, self.issue, title="Completed linked task", state=Task.State.COMPLETED
        )

        response = self.client.get(
            reverse("issue:issues"), {"selected": self.issue.pk, "tab": "tasks"}
        )

        self.assertContains(response, 'class="issue-task-details-actions"', count=2)
        self.assertContains(response, 'issue-edit-task"', count=1)
        active_actions, completed_actions = [
            section.split("</div>", 1)[0]
            for section in response.content.decode().split('class="issue-task-details-actions"')[1:]
        ]
        self.assertIn('type="submit">Complete</button>', active_actions)
        self.assertIn('type="submit">Dismiss</button>', active_actions)
        self.assertIn('type="submit">Reactivate</button>', completed_actions)
        self.assertIn('type="submit">Delete</button>', active_actions)
        self.assertIn('type="submit">Delete</button>', completed_actions)
        self.assertLess(
            active_actions.index(">Complete</button>"), active_actions.index(">Edit</button>")
        )
        self.assertLess(
            active_actions.index(">Edit</button>"), active_actions.index(">Dismiss</button>")
        )
        self.assertLess(
            active_actions.index(">Dismiss</button>"), active_actions.index(">Delete</button>")
        )
        self.assertContains(response, 'issue-task-open-record"', count=2)
        self.assertContains(response, 'class="dropdown issue-task-more"', count=2)
        self.assertContains(response, "Open record →")
        self.assertContains(response, 'aria-label="More task actions"', count=2)
        self.assertContains(response, reverse("task:complete_task", args=[active_task.pk]))
        self.assertContains(response, reverse("task:reactivate_task", args=[completed_task.pk]))

    def test_selected_issue_expands_inline_until_full_record_is_requested(self):
        preview = self.client.get(reverse("issue:issues"), {"selected": self.issue.pk})
        self.assertEqual(preview.context["mobile_expanded_issue_id"], self.issue.pk)
        self.assertContains(preview, f'id="issueInlineDetails{self.issue.pk}"')
        self.assertContains(preview, "Open record →")
        self.assertContains(preview, 'class="dropdown issue-inline-more"')
        self.assertContains(preview, 'aria-label="More issue actions"')

        full_record = self.client.get(
            reverse("issue:issues"), {"selected": self.issue.pk, "open": "detail"}
        )
        self.assertIsNone(full_record.context["mobile_expanded_issue_id"])
        self.assertNotContains(full_record, f'id="issueInlineDetails{self.issue.pk}"')

    def test_genuine_empty_state_uses_full_width_onboarding(self):
        self.issue.delete()

        response = self.client.get(reverse("issue:issues"))

        self.assertContains(response, "No issues yet")
        self.assertContains(response, "Add your first issue")
        self.assertNotContains(response, "Search issues")
        self.assertNotContains(response, "No issues match your filters")

    def test_filtered_empty_state_keeps_controls_and_clear_action(self):
        response = self.client.get(
            reverse("issue:issues"),
            {"search": "nothing will match this"},
        )

        self.assertContains(response, "Search issues")
        self.assertContains(response, "No issues match your filters")
        self.assertContains(response, "Clear filters")
        self.assertNotContains(response, "Add your first issue")

    def test_issues_view_paginates_twenty_at_a_time(self):
        Issue.objects.all().delete()
        for number in range(45):
            self.create_issue(self.user, f"Issue {number:02}")

        response = self.client.get(
            reverse("issue:issues"),
            {"search": "Issue", "page": 2},
        )

        self.assertEqual(len(response.context["page_obj"]), 20)
        self.assertEqual(response.context["page_obj"].paginator.num_pages, 3)
        self.assertContains(response, "Page 2 of 3")
        self.assertContains(response, "?search=Issue&amp;page=1")
        self.assertContains(response, "?search=Issue&amp;page=3")
        self.assertContains(response, 'data-workspace-scroll-root="issues"')
        self.assertContains(response, "data-workspace-scroll-list")
        self.assertContains(response, "data-workspace-scroll-row")
        self.assertContains(response, "js/workspace-list-scroll.js")
        self.assertRegex(
            response.content.decode(),
            r'class="issue-mobile-back btn btn-sm pom-quiet mb-2"\s+href="\?search=Issue&amp;page=2"',
        )

    def test_issues_view_normalises_query_parameters(self):
        response = self.client.get(
            reverse("issue:issues"),
            {"search": "  roof  ", "state": "wrong", "sort": "wrong"},
        )

        self.assertEqual(response.context["search"], "roof")
        self.assertEqual(response.context["state"], "all")
        self.assertEqual(response.context["sort"], "resolution_deadline")
        self.assertEqual(response.context["list_query"], "search=roof")

    def test_add_issue_valid_and_invalid_flows(self):
        response = self.client.post(reverse("issue:add_issue"), self.issue_data())
        created = Issue.objects.get(title="Boiler losing pressure")
        self.assertEqual(response.status_code, 302)
        self.assertIn(f"selected={created.pk}", response.url)

        post_response = self.client.post(reverse("issue:add_issue"), self.issue_data(title=""))

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["add_issue_form"].is_bound)
        self.assertEqual(response.context["open_modal"], "addIssueModal")

    def test_add_issue_clears_stale_search_and_page(self):
        response = self.client.post(
            f"{reverse('issue:add_issue')}?search=unrelated&page=3",
            self.issue_data(),
        )
        created = Issue.objects.get(title="Boiler losing pressure")
        self.assertEqual(response.url, f"{reverse('issue:issues')}?selected={created.pk}")

    def test_edit_issue_updates_active_issue(self):
        response = self.client.post(
            reverse("issue:edit_issue", args=[self.issue.pk]),
            self.issue_data(title="Updated issue"),
        )

        self.issue.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.issue.title, "Updated issue")

    def test_invalid_edit_issue_redirects_and_restores_bound_form(self):
        original_title = self.issue.title

        post_response = self.client.post(
            reverse("issue:edit_issue", args=[self.issue.pk]),
            self.issue_data(title=""),
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn(f"selected={self.issue.pk}", post_response.url)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)
        self.issue.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_issue"], self.issue)
        self.assertEqual(response.context["open_modal"], "editIssueModal")
        self.assertIn("title", response.context["edit_issue_form"].errors)
        self.assertEqual(self.issue.title, original_title)

    def test_lifecycle_view_applies_explicit_cascade_choice(self):
        task = self.create_task(self.user, self.issue)

        response = self.client.post(
            reverse("issue:resolve_issue", args=[self.issue.pk]),
            {"affect_linked_tasks": "yes"},
        )

        self.issue.refresh_from_db()
        task.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.issue.state, Issue.State.RESOLVED)
        self.assertEqual(task.state, Task.State.DISMISSED)
        self.assertEqual(
            [str(message) for message in get_messages(response.wsgi_request)],
            ["Issue resolved. 1 linked task dismissed."],
        )

    def test_delete_issue_can_delete_linked_tasks(self):
        task = self.create_task(self.user, self.issue)

        self.client.post(
            reverse("issue:delete_issue", args=[self.issue.pk]),
            {"affect_linked_tasks": "yes"},
        )
        self.issue.refresh_from_db()
        task.refresh_from_db()

        self.assertIsNotNone(self.issue.deleted_at)
        self.assertIsNotNone(task.deleted_at)

    def test_add_issue_task_locks_parent_and_returns_to_tasks_tab(self):
        response = self.client.post(
            reverse("issue:add_issue_task", args=[self.issue.pk]),
            self.task_data(property=self.property.pk),
        )
        task = Task.objects.get(title="Call contractor")

        self.assertEqual(task.issue, self.issue)
        self.assertIsNone(task.property)
        self.assertEqual(response.status_code, 302)
        self.assertIn("tab=tasks", response.url)

    def test_invalid_issue_task_returns_bound_form_to_tasks_tab(self):
        post_response = self.client.post(
            reverse("issue:add_issue_task", args=[self.issue.pk]),
            self.task_data(title=""),
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn(f"selected={self.issue.pk}", post_response.url)
        self.assertIn("tab=tasks", post_response.url)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["add_task_form"].is_bound)
        self.assertEqual(response.context["active_tab"], "tasks")
        self.assertEqual(response.context["open_modal"], "addIssueTaskModal")
        self.assertFalse(Task.objects.exists())

    def test_add_issue_task_rejects_terminated_and_other_users_issue(self):
        other_issue = self.create_issue(self.create_user("bob@example.com"))
        self.issue.state = Issue.State.RESOLVED
        self.issue.terminated_at = timezone.now()
        self.issue.save(update_fields=["state", "terminated_at"])

        for issue in (self.issue, other_issue):
            with self.subTest(issue=issue.pk):
                response = self.client.post(
                    reverse("issue:add_issue_task", args=[issue.pk]),
                    self.task_data(),
                )
                self.assertEqual(response.status_code, 404)

    def test_edit_issue_task_keeps_parent_when_no_relink_requested(self):
        task = self.create_task(self.user, self.issue)

        response = self.client.post(
            reverse("issue:edit_issue_task", args=[self.issue.pk, task.pk]),
            self.task_data(title="Updated task"),
        )
        task.refresh_from_db()

        self.assertEqual(response.status_code, 302)
        self.assertEqual(task.title, "Updated task")
        self.assertEqual(task.issue, self.issue)
        self.assertIsNone(task.property)

    def test_cross_user_issue_mutations_return_404(self):
        other_issue = self.create_issue(self.create_user("bob@example.com"))
        endpoints = (
            "edit_issue",
            "resolve_issue",
            "dismiss_issue",
            "reactivate_issue",
            "delete_issue",
        )

        for endpoint in endpoints:
            with self.subTest(endpoint=endpoint):
                response = self.client.post(
                    reverse(f"issue:{endpoint}", args=[other_issue.pk]),
                    self.issue_data(),
                )
                self.assertEqual(response.status_code, 404)

    def test_mutation_views_reject_get_requests(self):
        task = self.create_task(self.user, self.issue)
        urls = (
            reverse("issue:add_issue"),
            reverse("issue:edit_issue", args=[self.issue.pk]),
            reverse("issue:resolve_issue", args=[self.issue.pk]),
            reverse("issue:dismiss_issue", args=[self.issue.pk]),
            reverse("issue:reactivate_issue", args=[self.issue.pk]),
            reverse("issue:delete_issue", args=[self.issue.pk]),
            reverse("issue:add_issue_task", args=[self.issue.pk]),
            reverse("issue:edit_issue_task", args=[self.issue.pk, task.pk]),
        )

        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)

    def test_soft_deleted_issue_is_not_selectable_or_mutable(self):
        self.issue.deleted_at = timezone.now()
        self.issue.save(update_fields=["deleted_at"])

        response = self.client.get(
            reverse("issue:issues"),
            {"selected": self.issue.pk},
        )
        mutation = self.client.post(reverse("issue:delete_issue", args=[self.issue.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("issue:issues"))
        self.assertIsNone(self.client.get(response.url).context["selected_issue"])
        self.assertEqual(mutation.status_code, 404)

    def test_invalid_issue_task_edit_returns_bound_form(self):
        task = self.create_task(self.user, self.issue)

        post_response = self.client.post(
            reverse("issue:edit_issue_task", args=[self.issue.pk, task.pk]),
            self.task_data(title=""),
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn(f"selected={self.issue.pk}", post_response.url)
        self.assertIn("tab=tasks", post_response.url)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["edit_task_form"].is_bound)
        self.assertEqual(response.context["edit_task"], task)
        self.assertEqual(response.context["active_tab"], "tasks")
        self.assertEqual(response.context["open_modal"], "editIssueTaskModal")
