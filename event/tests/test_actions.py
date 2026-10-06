"""Event actions behaviour."""

from datetime import date, datetime, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ..models import Event
from .support import EventViewFixture


class EventViewActionsTests(EventViewFixture, TestCase):
    def test_deleted_event_property_is_not_linked(self):
        property_record = self.create_property(
            self.user, name="Former property", deleted_at=timezone.now()
        )
        event = self.create_event(self.user, property=property_record)

        response = self.client.get(reverse("event:events"), {"selected": event.pk})

        self.assertNotContains(
            response, f'href="{reverse("property:property_detail", args=[property_record.pk])}"'
        )
        self.assertContains(response, "Former property")
        self.assertNotContains(response, "Deleted property")

    def test_invalid_day_is_ignored(self):
        self.create_event(self.user)
        response = self.client.get(reverse("event:events"), {"day": "not-a-date"})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["selected_day"])

    def test_add_event_modal_defaults_date_to_local_today(self):
        response = self.client.get(reverse("event:events"))

        self.assertEqual(
            response.context["add_event_form"]["scheduled_date"].value(),
            timezone.localdate(),
        )
        self.assertContains(response, ">Date</label>")

    def test_add_and_edit_event_modals_use_the_same_property_picker(self):
        self.create_event(self.user)

        response = self.client.get(reverse("event:events"))

        self.assertContains(response, "data-searchable-select", count=2)

    def test_add_event_clears_stale_search_day_and_page(self):
        response = self.client.post(
            f"{reverse('event:add_event')}?search=unrelated&day=2026-01-01&page=3",
            self.valid_form_data(),
        )
        event = Event.objects.get(title="Inspection")
        self.assertEqual(response.url, f"{reverse('event:events')}?selected={event.pk}")

    def test_invalid_create_rerenders_open_add_modal(self):
        post_response = self.client.post(reverse("event:add_event"), self.valid_form_data(title=""))

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["open_modal"], "addEventModal")
        self.assertIn("title", response.context["add_event_form"].errors)
        self.assertFalse(Event.objects.exists())

    def test_past_scheduled_date_returns_field_error_in_add_modal(self):
        past = timezone.localdate() - timedelta(days=1)
        post_response = self.client.post(
            reverse("event:add_event"),
            self.valid_form_data(scheduled_date=past.isoformat()),
        )

        response = self.client.get(post_response.url)

        self.assertEqual(response.context["open_modal"], "addEventModal")
        self.assertIn("scheduled_date", response.context["add_event_form"].errors)
        self.assertFalse(Event.objects.exists())

    def test_add_event_shows_only_order_error_for_elapsed_end_time(self):
        today = date(2026, 9, 23)
        with (
            patch("event.forms.timezone.localdate", return_value=today),
            patch("event.forms.timezone.localtime", return_value=datetime(2026, 9, 23, 12)),
        ):
            post_response = self.client.post(
                reverse("event:add_event"),
                self.valid_form_data(
                    scheduled_date=today.isoformat(),
                    all_day="",
                    start_time="10:00",
                    end_time="09:00",
                ),
            )
            response = self.client.get(post_response.url)

        self.assertEqual(
            list(response.context["add_event_form"].errors["end_time"]),
            ["End time must be later than start time."],
        )

    def test_invalid_edit_redirects_and_restores_bound_form(self):
        event = self.create_event(self.user)

        post_response = self.client.post(
            reverse("event:edit_event", args=[event.pk]),
            self.valid_form_data(title=""),
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn(f"selected={event.pk}", post_response.url)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)
        event.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_event"], event)
        self.assertEqual(response.context["open_modal"], "editEventModal")
        self.assertIn("title", response.context["edit_event_form"].errors)
        self.assertEqual(event.title, "Inspection")

    def test_edit_and_lifecycle_views_are_owner_scoped(self):
        event = self.create_event(self.user)
        other = self.create_event(self.create_user("bob@example.com"), "Other")
        edit_data = self.valid_form_data(
            title="Changed", scheduled_date=event.scheduled_date.isoformat()
        )
        response = self.client.post(reverse("event:edit_event", args=[event.pk]), edit_data)
        self.assertEqual(response.status_code, 302)
        event.refresh_from_db()
        self.assertEqual(event.title, "Changed")

        response = self.client.post(reverse("event:cancel_event", args=[other.pk]))
        self.assertEqual(response.status_code, 404)

    def test_deleted_events_are_not_accessible_to_mutation_views(self):
        event = self.create_event(self.user, deleted_at=timezone.now())
        response = self.client.post(reverse("event:reactivate_event", args=[event.pk]))
        self.assertEqual(response.status_code, 404)
