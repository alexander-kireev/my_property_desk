"""Event workspace behaviour."""

import re
from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from ..models import Event, EventContact
from .support import EventViewFixture


class EventViewWorkspaceTests(EventViewFixture, TestCase):
    def test_terminated_event_history_copy_uses_natural_grammar(self):
        occurred = self.create_event(self.user, state=Event.State.OCCURRED)
        cancelled = self.create_event(self.user, state=Event.State.CANCELLED)

        occurred_response = self.client.get(reverse("event:events"), {"selected": occurred.pk})
        cancelled_response = self.client.get(reverse("event:events"), {"selected": cancelled.pk})

        self.assertContains(occurred_response, "This event occurred.")
        self.assertContains(cancelled_response, "This event was cancelled.")
        self.assertNotContains(occurred_response, "was occurred")

    def test_workspace_requires_login_and_post_endpoints_reject_get(self):
        self.client.logout()
        response = self.client.get(reverse("event:events"))
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.user)
        response = self.client.get(reverse("event:add_event"))
        self.assertEqual(response.status_code, 405)

    def test_event_relationship_is_qualified_in_list_and_detail(self):
        property_record = self.create_property(self.user)
        event = self.create_event(self.user, property=property_record)

        response = self.client.get(reverse("event:events"), {"selected": event.pk})

        self.assertContains(response, 'title="Hill House"')
        self.assertContains(response, "<dt>Related to</dt>")
        self.assertContains(response, '<span class="task-related-copy">Hill House</span>')
        self.assertRegex(
            response.content.decode(),
            re.escape('class="event-command-context work-summary-context" title="Hill House">Hill House</span>').replace(
                r"\ ", r"\s+"
            ),
        )
        self.assertNotContains(response, '<span aria-hidden="true">·</span>')
        self.assertContains(response, '<h3 class="h5 mb-3">Details</h3>')
        self.assertNotContains(response, "Related to: Property ·")
        self.assertContains(
            response,
            'class="expandable-text expandable-text--fit-card expandable-text--inline-end"',
        )

    def test_selected_event_renders_mobile_inline_details(self):
        event = self.create_event(self.user, "Boiler inspection", scheduled_date=date(2026, 10, 1))
        response = self.client.get(reverse("event:events"), {"selected": event.pk})

        self.assertTrue(response.context["show_compact_detail"])
        self.assertContains(response, "show-compact-detail")
        self.assertEqual(response.context["mobile_expanded_event_id"], event.pk)
        self.assertContains(response, f'id="eventInlineDetails{event.pk}"')
        self.assertContains(response, f'aria-controls="eventInlineDetails{event.pk}"')

        unselected = self.client.get(reverse("event:events"))
        self.assertFalse(unselected.context["show_compact_detail"])
        self.assertNotContains(unselected, "show-compact-detail")
        self.assertIsNone(unselected.context["mobile_expanded_event_id"])
        self.assertNotContains(unselected, f'id="eventInlineDetails{event.pk}"')

    def test_event_property_links_from_detail_and_mobile_expansion(self):
        property_name = "Property with an exceptionally long name " + "X" * 30
        property_record = self.create_property(self.user, name=property_name)
        event = self.create_event(self.user, property=property_record)

        response = self.client.get(reverse("event:events"), {"selected": event.pk})
        property_url = reverse("property:property_detail", args=[property_record.pk])

        self.assertContains(response, f'href="{property_url}"', count=2)
        self.assertContains(response, f'title="{property_name}"')
        self.assertContains(response, 'class="task-related-link"', count=2)

    def test_day_filter_orders_all_day_then_timed_events(self):
        day = date(2026, 10, 1)
        late = self.create_event(
            self.user, "Late", scheduled_date=day, all_day=False, start_time=time(16)
        )
        early = self.create_event(
            self.user, "Early", scheduled_date=day, all_day=False, start_time=time(9)
        )
        all_day = self.create_event(self.user, "All day", scheduled_date=day)
        response = self.client.get(reverse("event:events"), {"day": day.isoformat()})
        self.assertEqual(list(response.context["page_obj"].object_list), [all_day, early, late])

    def test_workspace_defaults_to_all_events_and_can_filter_scheduled(self):
        scheduled = self.create_event(self.user, "Scheduled visit")
        occurred = self.create_event(
            self.user,
            "Past visit",
            state=Event.State.OCCURRED,
        )

        default_response = self.client.get(reverse("event:events"))
        scheduled_response = self.client.get(
            reverse("event:events"),
            {"state": Event.State.SCHEDULED},
        )

        self.assertEqual(default_response.context["state"], "all")
        self.assertCountEqual(
            default_response.context["page_obj"].object_list,
            [scheduled, occurred],
        )
        self.assertEqual(list(scheduled_response.context["page_obj"].object_list), [scheduled])

    def test_selected_owned_event_can_remain_visible_outside_filters(self):
        visible = self.create_event(self.user, "Visible")
        hidden = self.create_event(self.user, "Hidden", state=Event.State.CANCELLED)
        other = self.create_event(self.create_user("bob@example.com"), "Other")

        for selected in (hidden.pk, other.pk):
            response = self.client.get(
                reverse("event:events"),
                {
                    "state": Event.State.SCHEDULED,
                    "selected": selected,
                },
            )
            if selected == hidden.pk:
                self.assertEqual(response.context["selected_event"], hidden)
                self.assertTrue(response.context["selected_outside_filters"])
            else:
                self.assertEqual(response.status_code, 302)
                self.assertEqual(self.client.get(response.url).context["selected_event"], visible)

    def test_paginates_twenty_events(self):
        last_event = None
        for index in range(21):
            last_event = self.create_event(self.user, f"Event {index:02d}")
        response = self.client.get(reverse("event:events"))
        self.assertEqual(len(response.context["page_obj"]), 20)
        self.assertEqual(response.context["page_obj"].paginator.num_pages, 2)
        self.assertContains(response, "Page 1 of 2")
        self.assertContains(response, 'aria-disabled="true">← Previous</span>')
        self.assertContains(response, "?page=2")
        selected_response = self.client.get(
            reverse("event:events"), {"page": 2, "selected": last_event.pk, "tab": "details"}
        )
        self.assertContains(selected_response, 'data-workspace-scroll-root="events"')
        self.assertContains(selected_response, "data-workspace-scroll-list")
        self.assertContains(selected_response, "data-workspace-scroll-row")
        self.assertContains(selected_response, "js/workspace-list-scroll.js")
        self.assertRegex(
            selected_response.content.decode(),
            re.escape(
                'class="event-mobile-back btn btn-sm pom-quiet mb-2" href="?page=2&amp;month='
            ).replace(r"\ ", r"\s+"),
        )

    def test_time_guidance_is_hidden_when_time_has_validation_error(self):
        post_response = self.client.post(
            reverse("event:add_event"),
            self.valid_form_data(all_day="", start_time="not-a-time"),
        )
        response = self.client.get(post_response.url)

        self.assertIn("start_time", response.context["add_event_form"].errors)
        self.assertRegex(
            response.content.decode(),
            re.escape('<p class="form-text mt-0 mb-0" hidden>Use 24-hour time (HH:MM)').replace(
                r"\ ", r"\s+"
            ),
        )

    def test_terminating_event_keeps_it_visible_in_all_states_view(self):
        event = self.create_event(self.user)

        post_response = self.client.post(reverse("event:mark_event_occurred", args=[event.pk]))

        self.assertNotIn("state=scheduled", post_response.url)
        self.assertIn(f"selected={event.pk}", post_response.url)

        response = self.client.get(post_response.url)
        event.refresh_from_db()

        self.assertEqual(event.state, Event.State.OCCURRED)
        self.assertEqual(response.context["selected_event"], event)

    def test_remove_rejects_link_belonging_to_another_event(self):
        event = self.create_event(self.user, "Target")
        other_event = self.create_event(self.user, "Other")
        contact = self.create_contact(self.user)
        link = EventContact.objects.create(event=other_event, contact=contact)

        response = self.client.post(
            reverse(
                "event:delete_event_contact_from_event",
                args=[event.pk, link.pk],
            )
        )

        self.assertEqual(response.status_code, 404)
        self.assertTrue(EventContact.objects.filter(pk=link.pk).exists())
