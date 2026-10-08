"""Property related work behaviour."""

import re
from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from event.models import Event
from issue.models import Issue
from task.models import Task

from ..models import Property
from .support import PropertyViewFixture


class PropertyViewRelatedWorkTests(PropertyViewFixture, TestCase):
    def test_related_records_default_to_current_records(self):
        property_record = self.create_property()
        Task.objects.create(user=self.user, property=property_record, title="Book plumber")
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:property_detail", args=[property_record.pk]))

        self.assertContains(response, "1 record")
        self.assertContains(response, "Book plumber")
        self.assertRegex(
            response.content.decode(), re.escape('value="current" selected').replace(r"\ ", r"\s+")
        )

    def test_command_centre_shows_one_related_records_view(self):
        property_record = self.create_property()
        self.client.force_login(self.user)

        for url in (
            reverse("property:properties"),
            reverse("property:property_detail", args=[property_record.pk]),
        ):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.context["selected_property"], property_record)
                self.assertContains(response, "Related records")
                self.assertNotContains(response, "data-property-tab=")
                self.assertContains(response, 'data-workspace-scroll-root="properties"')

    def test_related_records_link_to_canonical_details(self):
        property_record = self.create_property()
        Issue.objects.create(
            user=self.user,
            property=property_record,
            title="Repair tap",
            description="Water is leaking.",
        )
        Task.objects.create(
            user=self.user,
            property=property_record,
            title="Book plumber",
            description="Call the contractor.",
        )
        Event.objects.create(
            user=self.user,
            property=property_record,
            title="Inspection",
            description="Meet at the entrance.",
            scheduled_date=timezone.localdate() + timedelta(days=1),
            all_day=True,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:property_detail", args=[property_record.pk]))

        self.assertContains(response, 'class="property-related-record"', count=3)
        self.assertContains(response, 'class="property-related-summary"', count=3)
        self.assertContains(response, "Open record →", count=3)
        self.assertContains(response, "Water is leaking.")
        self.assertContains(response, "Call the contractor.")
        self.assertContains(response, "Meet at the entrance.")
        self.assertNotContains(response, '<details class="property-record">')
        self.assertContains(response, "Repair tap")
        self.assertContains(response, "Book plumber")
        self.assertContains(response, "Inspection")
        self.assertContains(response, "Issue · Related to: Property · Hill House")
        self.assertContains(response, "Task · Related to: Property · Hill House")
        self.assertContains(response, "Event · Related to: Property · Hill House")

    def test_related_record_keeps_long_title_badges_and_date_in_content_sized_summary(self):
        property_record = self.create_property()
        title = "Urgent repair " + "X" * 80
        due = timezone.localdate() + timedelta(days=1)
        Issue.objects.create(
            user=self.user,
            property=property_record,
            title=title,
            priority=Issue.Priority.URGENT,
            resolution_deadline=due,
        )
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:property_detail", args=[property_record.pk]))

        self.assertContains(response, f'title="{title}"')
        self.assertContains(response, 'class="property-related-record-badges"')
        self.assertContains(response, f"Due soon {due.day} {due.strftime('%b %Y')}")

    def test_heading_shows_description_above_related_records(self):
        property_record = self.create_property()
        property_record.description = "Long property context. " * 30
        property_record.save(update_fields=["description"])
        Issue.objects.create(user=self.user, property=property_record, title="Entry phone")
        Task.objects.create(user=self.user, property=property_record, title="Arrange access")
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:property_detail", args=[property_record.pk]))

        self.assertContains(response, 'class="property-heading-description"')
        self.assertContains(response, "Related records")
        self.assertContains(response, "2 records")
        self.assertRegex(
            response.content.decode(),
            re.escape('id="property-detail-description" data-expandable-content').replace(
                r"\ ", r"\s+"
            ),
        )
        self.assertRegex(
            response.content.decode(),
            re.escape(
                'aria-controls="property-detail-description" aria-expanded="false" hidden data-expandable-toggle'
            ).replace(r"\ ", r"\s+"),
        )
        self.assertNotContains(response, 'id="propertyDescriptionModal"')
        self.assertNotContains(response, "At a glance")

    def test_related_records_list_all_current_types_without_duplicates(self):
        property_record = self.create_property()
        for number in range(3):
            Issue.objects.create(user=self.user, property=property_record, title=f"Issue {number}")
            Task.objects.create(user=self.user, property=property_record, title=f"Task {number}")
            Event.objects.create(
                user=self.user,
                property=property_record,
                title=f"Event {number}",
                scheduled_date=timezone.localdate() + timedelta(days=number + 1),
                all_day=True,
            )
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:property_detail", args=[property_record.pk]))
        html = response.content.decode()
        self.assertEqual(html.count('class="property-related-record"'), 9)
        self.assertNotIn('<details class="property-record">', html)
        for number in range(3):
            self.assertIn(f"Issue {number}", html)
            self.assertIn(f"Task {number}", html)
            self.assertIn(f"Event {number}", html)

    def test_history_contains_terminated_records_but_not_deleted_or_other_users_records(self):
        property_record = self.create_property()
        now = timezone.now()
        Issue.objects.create(
            user=self.user,
            property=property_record,
            title="Fixed leak",
            state=Issue.State.RESOLVED,
            terminated_at=now,
        )
        Task.objects.create(
            user=self.user,
            property=property_record,
            title="Finished job",
            state=Task.State.COMPLETED,
            terminated_at=now - timedelta(days=1),
        )
        Event.objects.create(
            user=self.user,
            property=property_record,
            title="Completed visit",
            scheduled_date=timezone.localdate(),
            all_day=True,
            state=Event.State.OCCURRED,
            terminated_at=now - timedelta(days=2),
        )
        Issue.objects.create(
            user=self.user,
            property=property_record,
            title="Hidden issue",
            state=Issue.State.RESOLVED,
            terminated_at=now,
            deleted_at=now,
        )
        Issue.objects.create(
            user=self.other_user,
            property=property_record,
            title="Other user issue",
            state=Issue.State.RESOLVED,
            terminated_at=now,
        )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("property:property_detail", args=[property_record.pk]),
            {"records_scope": "past"},
        )

        self.assertEqual(
            [entry["item"].title for entry in response.context["related_page"]],
            ["Completed visit", "Finished job", "Fixed leak"],
        )
        self.assertContains(response, 'class="property-related-record is-terminal"', count=3)
        for state in ("Resolved", "Completed", "Occurred"):
            self.assertContains(response, f'work-pill--terminal">{state}')
            self.assertNotContains(response, f"{state} · ")
        self.assertNotContains(response, "Hidden issue")
        self.assertNotContains(response, "Other user issue")

    def test_related_records_filter_by_type_scope_and_search(self):
        property_record = self.create_property()
        Issue.objects.create(
            user=self.user, property=property_record, title="Leaking pipe", description="Kitchen"
        )
        Task.objects.create(user=self.user, property=property_record, title="Call plumber")
        Event.objects.create(
            user=self.user,
            property=property_record,
            title="Past visit",
            scheduled_date=timezone.localdate(),
            all_day=True,
            state=Event.State.OCCURRED,
            terminated_at=timezone.now(),
        )
        self.client.force_login(self.user)
        url = reverse("property:property_detail", args=[property_record.pk])

        current = self.client.get(url)
        self.assertEqual(current.context["related_page"].paginator.count, 2)
        past = self.client.get(url, {"records_scope": "past"})
        self.assertEqual(
            [entry["item"].title for entry in past.context["related_page"]], ["Past visit"]
        )
        issues = self.client.get(url, {"records_type": "issue", "records_search": "kitchen"})
        self.assertEqual(
            [entry["item"].title for entry in issues.context["related_page"]], ["Leaking pipe"]
        )

    def test_property_add_modals_show_readonly_related_property_without_locked_badge(self):
        property_name = "A very long property name " + "W" * 45
        property_record = self.create_property(name=property_name)
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:property_detail", args=[property_record.pk]))

        html = response.content.decode()
        for kind in ("Task", "Issue", "Event"):
            with self.subTest(kind=kind):
                self.assertContains(
                    response,
                    f'<h2 class="modal-title fs-5" id="propertyAdd{kind}Title">Add {kind.lower()}</h2>',
                )
                modal_markup = html.split(f'id="propertyAdd{kind}Modal"', 1)[1].split(
                    '<div class="modal fade"', 1
                )[0]
                self.assertRegex(
                    modal_markup,
                    rf'id="propertyAdd{kind}RelatedProperty"\s+role="note"\s+tabindex="0"\s+aria-labelledby="propertyAdd{kind}RelatedPropertyLabel">{property_name}</div>',
                )
                self.assertRegex(
                    modal_markup,
                    rf'<input\s+type="hidden"\s+name="property"\s+value="{property_record.pk}">',
                )
        self.assertContains(response, 'id="propertyAddTaskRelatedProperty"', count=1)
        self.assertContains(response, 'id="propertyAddIssueRelatedProperty"', count=1)
        self.assertContains(response, 'id="propertyAddEventRelatedProperty"', count=1)
        self.assertNotContains(response, ">Locked</span>")

    def test_related_records_are_paginated_without_losing_filters(self):
        property_record = self.create_property()
        for number in range(27):
            Task.objects.create(
                user=self.user, property=property_record, title=f"Task {number:02d}"
            )
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("property:property_detail", args=[property_record.pk]),
            {
                "records_type": "task",
                "records_sort": "title",
                "records_page": "2",
            },
        )

        self.assertEqual(response.context["related_page"].paginator.count, 27)
        self.assertEqual(len(response.context["related_page"]), 2)
        self.assertContains(response, "Task 25")
        self.assertContains(response, "Task 26")
        self.assertContains(
            response,
            "records_type=task&amp;records_scope=current&amp;records_sort=title&amp;records_page=1",
        )

    def test_related_edit_links_open_existing_edit_modals(self):
        property_record = self.create_property()
        issue = Issue.objects.create(user=self.user, property=property_record, title="Repair tap")
        task = Task.objects.create(user=self.user, property=property_record, title="Book visit")
        event = Event.objects.create(
            user=self.user,
            property=property_record,
            title="Inspection",
            scheduled_date=timezone.localdate() + timedelta(days=1),
            all_day=True,
        )
        self.client.force_login(self.user)

        for route, record, modal in (
            ("issue:issues", issue, "editIssueModal"),
            ("task:tasks", task, "editTaskModal"),
            ("event:events", event, "editEventModal"),
        ):
            with self.subTest(route=route):
                response = self.client.get(reverse(route), {"selected": record.pk, "open": "edit"})
                self.assertContains(response, modal)
                self.assertEqual(response.context["open_modal"], modal)

    def test_deactivated_property_has_no_related_quick_actions(self):
        property_record = self.create_property(state=Property.State.DEACTIVATED)
        Issue.objects.create(user=self.user, property=property_record, title="Retained issue")
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("property:property_detail", args=[property_record.pk]), {"tab": "work"}
        )

        self.assertContains(response, "Retained issue")
        self.assertNotContains(response, 'data-verb="Resolve"')

    def test_related_action_cannot_return_to_another_property(self):
        source = self.create_property(name="Source House")
        other = self.create_property(name="Other House")
        task = Task.objects.create(user=self.user, property=source, title="Book visit")
        self.client.force_login(self.user)
        wrong_next = reverse("property:property_detail", args=[other.pk]) + "?tab=work"

        response = self.client.post(
            reverse("task:complete_task", args=[task.pk]), {"next": wrong_next}
        )

        self.assertRedirects(
            response, reverse("task:tasks") + f"?selected={task.pk}", fetch_redirect_response=False
        )
