"""Event calendar behaviour."""

import re
from datetime import date, time

from django.test import TestCase
from django.urls import reverse

from .support import EventViewFixture


class EventViewCalendarTests(EventViewFixture, TestCase):
    def test_workspace_renders_calendar_and_defaults_to_details_tab(self):
        event = self.create_event(self.user, scheduled_date=date(2026, 9, 17))
        response = self.client.get(
            reverse("event:events"),
            {
                "month": 9,
                "year": 2026,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_tab"], "details")
        self.assertEqual(response.context["calendar_month_label"], "September 2026")
        self.assertEqual(response.context["calendar_event_count"], 1)
        self.assertContains(response, event.title)

    def test_crowded_day_shows_first_event_and_more_link_then_filters_list(self):
        day = date(2026, 10, 1)
        for index in range(10):
            self.create_event(self.user, f"Visit {index:02d}", scheduled_date=day)
        other = self.create_event(self.user, "Another day", scheduled_date=date(2026, 10, 2))

        response = self.client.get(reverse("event:events"), {"month": 10, "year": 2026})
        cells_by_date = {}
        for week in response.context["calendar_weeks"]:
            for cell in week:
                cells_by_date[cell["date"]] = cell
        cell = cells_by_date[day]
        self.assertEqual(cell["more_count"], 9)
        self.assertEqual(cell["first_event"].title, "Visit 00")
        self.assertContains(response, "+9 more")
        self.assertContains(
            response,
            'data-calendar-day-href="?month=10&amp;year=2026&amp;day=2026-10-01#eventResults"',
        )

        filtered = self.client.get(
            reverse("event:events"),
            {
                "month": 10,
                "year": 2026,
                "day": "2026-10-01",
            },
        )
        self.assertEqual(filtered.context["page_obj"].paginator.count, 10)
        self.assertEqual(filtered.context["calendar_event_count"], 11)
        self.assertEqual(filtered.context["selected_day"], day)
        self.assertContains(filtered, "Date: 1 Oct 2026")
        self.assertContains(filtered, 'aria-label="Clear date filter for 1 October 2026"')
        self.assertNotIn(other, filtered.context["page_obj"].object_list)
        self.assertEqual(filtered.context["mobile_agenda_day"], day)
        self.assertEqual(len(filtered.context["mobile_agenda_events"]), 10)
        self.assertContains(filtered, 'id="eventAgenda"')
        self.assertContains(
            filtered,
            'class="event-calendar-count" aria-hidden="true">10<span class="event-calendar-count-label"> events</span></span>',
        )

    def test_mobile_agenda_orders_all_day_then_timed_events(self):
        day = date(2026, 10, 1)
        late = self.create_event(
            self.user, "Late", scheduled_date=day, all_day=False, start_time=time(16)
        )
        early = self.create_event(
            self.user, "Early", scheduled_date=day, all_day=False, start_time=time(9)
        )
        all_day = self.create_event(self.user, "All day", scheduled_date=day)

        response = self.client.get(
            reverse("event:events"), {"month": 10, "year": 2026, "day": day.isoformat()}
        )
        self.assertEqual(response.context["mobile_agenda_events"], [all_day, early, late])
        self.assertContains(
            response,
            f"agenda_day=2026-10-01&amp;view=calendar&amp;selected={early.pk}&amp;tab=calendar",
        )

    def test_mobile_calendar_empty_day_stays_on_calendar_without_filtering_list(self):
        event = self.create_event(self.user, scheduled_date=date(2026, 10, 2))
        empty_day = date(2026, 10, 1)

        response = self.client.get(
            reverse("event:events"),
            {
                "month": 10,
                "year": 2026,
                "agenda_day": empty_day.isoformat(),
                "view": "calendar",
            },
        )

        self.assertTrue(response.context["mobile_calendar_view"])
        self.assertEqual(response.context["mobile_agenda_day"], empty_day)
        self.assertEqual(response.context["mobile_agenda_events"], [])
        self.assertIsNone(response.context["selected_day"])
        self.assertIn(event, response.context["page_obj"].object_list)
        self.assertContains(response, "No events planned for this day.")
        self.assertContains(
            response,
            'data-calendar-agenda-href="?month=10&amp;year=2026&amp;agenda_day=2026-10-01&amp;view=calendar#eventAgenda"',
        )

    def test_mobile_calendar_ignores_agenda_day_outside_visible_month(self):
        response = self.client.get(
            reverse("event:events"),
            {
                "month": 10,
                "year": 2026,
                "agenda_day": "2026-12-01",
                "view": "calendar",
            },
        )

        self.assertEqual(response.context["mobile_agenda_day"], date(2026, 10, 1))

    def test_mobile_agenda_rows_use_event_list_hierarchy(self):
        day = date(2026, 10, 1)
        property_record = self.create_property(self.user, name="Long property " + "P" * 50)
        event = self.create_event(
            self.user,
            title="Long event " + "E" * 60,
            property=property_record,
            scheduled_date=day,
            all_day=False,
            start_time=time(9),
            end_time=time(10),
        )

        response = self.client.get(
            reverse("event:events"), {"month": 10, "year": 2026, "day": day.isoformat()}
        )

        self.assertRegex(
            response.content.decode(),
            re.escape(
                f'class="event-mobile-agenda-title event-command-title" title="{event.title}"'
            ).replace(r"\ ", r"\s+"),
        )
        self.assertRegex(
            response.content.decode(),
            re.escape(
                f'class="event-mobile-agenda-context event-command-context" title="{property_record.name}"'
            ).replace(r"\ ", r"\s+"),
        )
        self.assertContains(response, 'class="event-command-meta"')
        self.assertContains(
            response, 'class="event-mobile-agenda-time event-command-when">09:00–10:00</span>'
        )

    def test_mobile_agenda_selection_expands_in_calendar_without_filtering_list(self):
        day = date(2026, 10, 1)
        event = self.create_event(self.user, "Heating service", scheduled_date=day)
        other = self.create_event(self.user, "Tomorrow", scheduled_date=date(2026, 10, 2))

        response = self.client.get(
            reverse("event:events"),
            {
                "month": 10,
                "year": 2026,
                "agenda_day": day.isoformat(),
                "view": "calendar",
                "selected": event.pk,
                "tab": "calendar",
            },
        )

        self.assertTrue(response.context["mobile_calendar_view"])
        self.assertIsNone(response.context["selected_day"])
        self.assertIn(other, response.context["page_obj"].object_list)
        self.assertContains(response, f'id="eventAgendaInlineDetails{event.pk}"')
        self.assertContains(response, f'aria-controls="eventAgendaInlineDetails{event.pk}"')
        self.assertContains(response, f'id="event-agenda-description-{event.pk}"')

    def test_invalid_calendar_parameters_fall_back_safely(self):
        response = self.client.get(
            reverse("event:events"),
            {
                "month": "bad",
                "year": "bad",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["calendar_weeks"])

    def test_calendar_navigation_crosses_years_and_handles_leap_february(self):
        response = self.client.get(
            reverse("event:events"),
            {
                "month": 1,
                "year": 2028,
                "search": "inspection",
            },
        )
        self.assertIn("month=12", response.context["previous_month_query"])
        self.assertIn("year=2027", response.context["previous_month_query"])
        self.assertIn("month=2", response.context["next_month_query"])
        self.assertIn("year=2028", response.context["next_month_query"])
        self.assertIn("search=inspection", response.context["next_month_query"])

        february = self.client.get(
            reverse("event:events"),
            {
                "month": 2,
                "year": 2028,
            },
        )
        dates = [day["date"] for week in february.context["calendar_weeks"] for day in week]
        self.assertIn(date(2028, 2, 29), dates)
        self.assertEqual(dates[0].weekday(), 0)

    def test_calendar_is_not_limited_by_list_pagination_and_shares_filters(self):
        for index in range(25):
            self.create_event(
                self.user,
                f"Matching {index:02d}",
                scheduled_date=date(2026, 9, 10),
                user_participation_required=True,
            )
        self.create_event(
            self.user,
            "Excluded",
            scheduled_date=date(2026, 9, 10),
            user_participation_required=False,
        )
        response = self.client.get(
            reverse("event:events"),
            {
                "month": 9,
                "year": 2026,
                "participation": "required",
            },
        )

        self.assertEqual(len(response.context["page_obj"]), 20)
        self.assertEqual(response.context["calendar_event_count"], 25)

    def test_explicit_calendar_selection_moves_to_its_natural_list_page(self):
        selected = None
        for index in range(21):
            event = self.create_event(
                self.user,
                f"Event {index:02d}",
                scheduled_date=date(2026, 9, index + 1),
            )
            if index == 20:
                selected = event
        response = self.client.get(
            reverse("event:events"),
            {
                "selected": selected.pk,
                "tab": "details",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertIn("page=2", response.url)
        corrected = self.client.get(response.url)
        self.assertIn(selected, corrected.context["page_obj"].object_list)
        self.assertEqual(corrected.context["selected_event"], selected)
        self.assertEqual(corrected.context["active_tab"], "details")
