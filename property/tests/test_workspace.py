"""Property workspace behaviour."""

import re
from datetime import timedelta
from unittest.mock import patch

from django.db.models import IntegerField, Value
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from event.models import Event
from issue.models import Issue
from task.models import Task

from ..models import Property
from .support import PropertyViewFixture


class PropertyViewWorkspaceTests(PropertyViewFixture, TestCase):
    def test_list_summary_uses_real_counts_without_join_multiplication(self):
        property_record = self.create_property()
        issue = Issue.objects.create(user=self.user, property=property_record, title="Open issue")
        Issue.objects.create(
            user=self.user, property=property_record, title="Resolved", state=Issue.State.RESOLVED
        )
        Task.objects.create(user=self.user, property=property_record, title="Direct task")
        Task.objects.create(user=self.user, issue=issue, title="Issue task")
        Task.objects.create(
            user=self.user, property=property_record, title="Done", state=Task.State.COMPLETED
        )
        tomorrow = timezone.localdate() + timedelta(days=1)
        Event.objects.create(
            user=self.user,
            property=property_record,
            title="Visit",
            scheduled_date=tomorrow,
            all_day=True,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:properties"))
        listed = response.context["page_obj"].object_list[0]

        self.assertEqual(listed.open_issues, 1)
        self.assertEqual(listed.open_direct_tasks + listed.open_issue_tasks, 2)
        self.assertContains(response, "1 issue · 2 tasks")
        self.assertNotContains(response, "Contacts</div>")

    def test_list_summary_handles_zero_and_several_issues(self):
        empty = self.create_property(name="Empty")
        busy = self.create_property(name="Busy")
        Issue.objects.bulk_create(
            Issue(user=self.user, property=busy, title=f"Issue {index}") for index in range(3)
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:properties"))
        listed = {record.pk: record for record in response.context["page_obj"].object_list}

        self.assertEqual(listed[empty.pk].open_issues, 0)
        self.assertEqual(listed[busy.pk].open_issues, 3)

    def test_mocked_summary_values_render_without_placeholder(self):
        self.create_property()
        self.client.force_login(self.user)
        for count in (0, 999, 1000, 100000):
            with (
                self.subTest(count=count),
                patch("property.workspace.with_work_summary") as summary,
            ):

                def summary_values(records):
                    return records.annotate(
                        open_issues=Value(count, output_field=IntegerField()),
                        open_direct_tasks=Value(count, output_field=IntegerField()),
                        open_issue_tasks=Value(0, output_field=IntegerField()),
                    )

                summary.side_effect = summary_values
                response = self.client.get(reverse("property:properties"))
                self.assertContains(response, f"{count} issues")

    def test_property_list_requires_login(self):
        response = self.client.get(reverse("property:properties"))

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('property:properties')}",
        )

    def test_property_list_only_contains_current_users_properties(self):
        own_property = self.create_property(name="Hill House")
        other_property = self.create_property(
            user=self.other_user,
            name="River Cottage",
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:properties"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, own_property.name)
        self.assertNotContains(response, other_property.name)

    def test_search_matches_property_name_or_address(self):
        name_match = self.create_property(name="Hill House")
        address_match = self.create_property(
            name="City Flat",
            address="22 Hill Road, London",
        )
        self.create_property(name="River Cottage", address="1 Water Lane")
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("property:properties"),
            {"search": "hill"},
        )
        properties = list(response.context["page_obj"].object_list)

        self.assertEqual(properties, [address_match, name_match])

    def test_property_list_defaults_to_all_and_can_filter_by_state(self):
        active = self.create_property(name="Active House")
        deactivated = self.create_property(
            name="Old House",
            state=Property.State.DEACTIVATED,
        )
        self.client.force_login(self.user)

        for query, expected in (
            ({}, [active, deactivated]),
            ({"state": Property.State.ACTIVE}, [active]),
            ({"state": Property.State.DEACTIVATED}, [deactivated]),
            ({"state": "all"}, [active, deactivated]),
        ):
            with self.subTest(query=query):
                response = self.client.get(reverse("property:properties"), query)
                self.assertCountEqual(response.context["page_obj"].object_list, expected)

    def test_deactivated_only_property_is_visible_by_default(self):
        deactivated = self.create_property(state=Property.State.DEACTIVATED)
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:properties"))

        self.assertEqual(list(response.context["page_obj"].object_list), [deactivated])
        self.assertContains(response, 'value="all" selected')

    def test_all_supported_sort_options_return_expected_order(self):
        alpha = self.create_property(name="Alpha House")
        zebra = self.create_property(name="Zebra House")
        earlier = timezone.now() - timedelta(days=2)
        later = timezone.now() - timedelta(days=1)
        Property.objects.filter(pk=alpha.pk).update(created_at=earlier)
        Property.objects.filter(pk=zebra.pk).update(created_at=later)
        self.client.force_login(self.user)

        expected_orders = {
            "name": [alpha.pk, zebra.pk],
            "-name": [zebra.pk, alpha.pk],
            "created_at": [alpha.pk, zebra.pk],
            "-created_at": [zebra.pk, alpha.pk],
        }

        for sort, expected_order in expected_orders.items():
            with self.subTest(sort=sort):
                response = self.client.get(
                    reverse("property:properties"),
                    {"sort": sort},
                )
                actual_order = [
                    property_record.pk
                    for property_record in response.context["page_obj"].object_list
                ]

                self.assertEqual(actual_order, expected_order)

    def test_property_list_is_paginated_at_twenty_properties(self):
        for property_number in range(21):
            self.create_property(name=f"Property {property_number:02}")
        self.client.force_login(self.user)

        first_page = self.client.get(reverse("property:properties"))
        second_page = self.client.get(
            reverse("property:properties"),
            {"page": 2},
        )

        self.assertEqual(len(first_page.context["page_obj"]), 20)
        self.assertEqual(len(second_page.context["page_obj"]), 1)

    def test_rename_keeps_property_selected_on_its_new_sorted_page(self):
        target = self.create_property(name="A House")
        for number in range(20):
            self.create_property(name=f"M House {number:02}")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("property:edit_property", args=[target.pk]) + "?return_to=list",
            {"name": "Z House", "description": "Managed property.", "address": target.address},
            follow=True,
        )
        self.assertEqual(response.context["selected_property"].pk, target.pk)
        self.assertEqual(response.context["page_obj"].number, 2)
        self.assertTrue(response.context["selected_in_page"])

    def test_deactivation_retains_explicit_active_filter_and_selection(self):
        target = self.create_property()
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("property:deactivate_property", args=[target.pk])
            + "?return_to=list&state=active",
            follow=True,
        )
        self.assertEqual(response.context["selected_property"].pk, target.pk)
        self.assertTrue(response.context["selected_outside_filters"])
        self.assertContains(response, "Selected property is outside these filters.")
        self.assertNotContains(response, "Selected property</small>")

    def test_outside_filter_detail_exposes_selected_property_recovery(self):
        target = self.create_property(name="Archived House", state=Property.State.DEACTIVATED)
        self.client.force_login(self.user)
        url = reverse("property:property_detail", args=[target.pk])

        outside = self.client.get(url, {"state": "active", "search": "__outside__"})
        self.assertTrue(outside.context["selected_outside_filters"])
        self.assertContains(outside, 'class="workspace-selection-notice property-detail-recovery"')
        self.assertContains(outside, f'href="{url}">Show all</a>')
        self.assertNotContains(outside, 'href="/properties/">Clear filters</a>')

        clear = self.client.get(url)
        self.assertFalse(clear.context["selected_outside_filters"])
        self.assertNotContains(clear, 'class="workspace-selection-notice property-detail-recovery"')

    def test_pagination_preserves_search_filter_and_sort_parameters(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("property:properties"),
            {
                "search": "House",
                "state": Property.State.ACTIVE,
                "sort": "-name",
                "page": 2,
            },
        )

        self.assertEqual(
            response.context["list_query"],
            "search=House&state=active&sort=-name",
        )

    def test_valid_creation_assigns_user_and_redirects_to_detail(self):
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("property:add_property"),
            data=self.VALID_DATA,
        )
        property_record = Property.objects.get(name=self.VALID_DATA["name"])

        self.assertEqual(property_record.user, self.user)
        self.assertRedirects(
            response,
            reverse(
                "property:property_detail",
                kwargs={"property_id": property_record.pk},
            ),
        )

    def test_property_detail_only_allows_owning_user(self):
        own_property = self.create_property(name="Hill House")
        other_property = self.create_property(
            user=self.other_user,
            name="River Cottage",
        )
        self.client.force_login(self.user)

        own_response = self.client.get(
            reverse(
                "property:property_detail",
                kwargs={"property_id": own_property.pk},
            )
        )
        other_response = self.client.get(
            reverse(
                "property:property_detail",
                kwargs={"property_id": other_property.pk},
            )
        )

        self.assertEqual(own_response.status_code, 200)
        self.assertTemplateUsed(own_response, "property/property_detail.html")
        self.assertEqual(other_response.status_code, 404)

    def test_property_work_links_are_full_rows(self):
        property_record = self.create_property()
        issue = Issue.objects.create(user=self.user, property=property_record, title="Entry phone")
        task = Task.objects.create(user=self.user, property=property_record, title="Arrange access")
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:property_detail", args=[property_record.pk]))
        self.assertContains(
            response, f'href="{reverse("issue:issues")}?selected={issue.pk}&amp;open=detail"'
        )
        self.assertContains(
            response, f'href="{reverse("task:tasks")}?selected={task.pk}&amp;open=detail"'
        )
        self.assertContains(response, 'class="navbar-nav app-mobile-menu d-lg-none"')
        self.assertContains(response, 'class="app-mobile-logout" type="submit">Log out</button>')

    def test_property_rows_show_existing_work_and_event_flags(self):
        property_record = self.create_property()
        Issue.objects.create(
            user=self.user,
            property=property_record,
            title="Urgent issue",
            priority=Issue.Priority.URGENT,
            resolution_deadline=timezone.localdate() - timedelta(days=1),
        )
        Task.objects.create(
            user=self.user,
            property=property_record,
            title="High task",
            priority=Task.Priority.HIGH,
            completion_deadline=timezone.localdate() + timedelta(days=1),
        )
        Event.objects.create(
            user=self.user,
            property=property_record,
            title="Site visit",
            scheduled_date=timezone.localdate() + timedelta(days=1),
            all_day=True,
            user_participation_required=True,
            user_presence_required=True,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:property_detail", args=[property_record.pk]))

        self.assertContains(response, 'name="records_type"')
        self.assertContains(response, 'name="records_scope"')
        self.assertContains(response, "work-pill--priority-4")
        self.assertContains(response, "property-related-date--overdue")
        self.assertContains(response, "work-pill--priority-3")
        self.assertContains(response, "property-related-date--soon")
        self.assertContains(response, 'work-pill--active">Scheduled')
        self.assertNotContains(response, 'property-presence-badge">Presence required')

    def test_issue_linked_task_summary_names_issue_not_property(self):
        property_record = self.create_property()
        issue = Issue.objects.create(user=self.user, property=property_record, title="Entry phone")
        Task.objects.create(user=self.user, issue=issue, title="Call electrician")
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:property_detail", args=[property_record.pk]))

        self.assertContains(response, "Task · Related to: Issue · Entry phone")
        self.assertNotContains(response, "Direct property task")

    def test_long_address_uses_single_line_list_preview_and_inline_header_disclosure(self):
        address = "123 Very Long Avenue " + "West " * 24
        property_record = self.create_property(address=address)
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:property_detail", args=[property_record.pk]))

        self.assertContains(response, 'class="property-command-address"')
        self.assertContains(
            response,
            'class="expandable-text expandable-text--single-line property-heading-address"',
        )
        self.assertRegex(
            response.content.decode(),
            re.escape(
                'aria-controls="property-detail-address" aria-expanded="false" hidden data-expandable-toggle'
            ).replace(r"\ ", r"\s+"),
        )
        self.assertNotContains(response, 'data-bs-target="#property-detail-address"')

    def test_creating_from_property_returns_to_its_new_record(self):
        property_record = self.create_property()
        self.client.force_login(self.user)
        cases = (
            (
                "issue:add_issue",
                Issue,
                "issue",
                {
                    "title": "Repair window",
                    "property": property_record.pk,
                    "priority": Issue.Priority.HIGH,
                },
            ),
            (
                "task:add_task",
                Task,
                "task",
                {
                    "title": "Call contractor",
                    "property": property_record.pk,
                    "relationship_type": "property",
                    "priority": Task.Priority.HIGH,
                },
            ),
            (
                "event:add_event",
                Event,
                "event",
                {
                    "title": "Site visit",
                    "property": property_record.pk,
                    "scheduled_date": (timezone.localdate() + timedelta(days=1)).isoformat(),
                    "all_day": "on",
                },
            ),
        )
        for route, model, kind, data in cases:
            with self.subTest(route=route):
                response = self.client.post(
                    reverse(route), {**data, "return_property": property_record.pk}
                )
                self.assertRedirects(
                    response,
                    reverse("property:property_detail", args=[property_record.pk])
                    + f"?records_type={kind}&records_scope=current&records_sort=recent",
                    fetch_redirect_response=False,
                )
                self.assertTrue(
                    model.objects.filter(
                        user=self.user, property=property_record, title=data["title"]
                    ).exists()
                )

    def test_property_origin_does_not_redirect_when_record_is_moved_elsewhere(self):
        origin = self.create_property(name="Origin")
        destination = self.create_property(name="Destination")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("task:add_task"),
            {
                "title": "New task",
                "property": destination.pk,
                "relationship_type": "property",
                "return_property": origin.pk,
                "priority": Task.Priority.LOW,
            },
        )
        task = Task.objects.get(title="New task")
        self.assertEqual(response.url, f"{reverse('task:tasks')}?selected={task.pk}")

    def test_deactivation_requires_post(self):
        property_record = self.create_property()
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "property:deactivate_property",
                kwargs={"property_id": property_record.pk},
            )
        )
        property_record.refresh_from_db()

        self.assertEqual(response.status_code, 405)
        self.assertEqual(property_record.state, Property.State.ACTIVE)

    def test_deactivation_preserves_property_as_history(self):
        property_record = self.create_property()
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "property:deactivate_property",
                kwargs={"property_id": property_record.pk},
            )
        )
        property_record.refresh_from_db()

        self.assertRedirects(
            response,
            reverse(
                "property:property_detail",
                kwargs={"property_id": property_record.pk},
            ),
        )
        self.assertEqual(property_record.state, Property.State.DEACTIVATED)
        self.assertIsNone(property_record.deleted_at)
        self.assertTrue(Property.objects.filter(pk=property_record.pk).exists())

    def test_user_cannot_deactivate_another_users_property(self):
        property_record = self.create_property(user=self.other_user)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "property:deactivate_property",
                kwargs={"property_id": property_record.pk},
            )
        )
        property_record.refresh_from_db()

        self.assertEqual(response.status_code, 404)
        self.assertEqual(property_record.state, Property.State.ACTIVE)

    def test_reactivation_returns_property_to_active_state(self):
        property_record = self.create_property(
            state=Property.State.DEACTIVATED,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "property:reactivate_property",
                kwargs={"property_id": property_record.pk},
            )
        )
        property_record.refresh_from_db()

        self.assertRedirects(
            response,
            reverse(
                "property:property_detail",
                kwargs={"property_id": property_record.pk},
            ),
        )
        self.assertEqual(property_record.state, Property.State.ACTIVE)

    def test_reactivation_requires_post(self):
        property_record = self.create_property(
            state=Property.State.DEACTIVATED,
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "property:reactivate_property",
                kwargs={"property_id": property_record.pk},
            )
        )
        property_record.refresh_from_db()

        self.assertEqual(response.status_code, 405)
        self.assertEqual(property_record.state, Property.State.DEACTIVATED)
