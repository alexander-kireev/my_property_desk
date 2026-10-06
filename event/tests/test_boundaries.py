"""Calendar range and one-use validation state at pagination boundaries."""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from event.models import Event


class EventBoundaryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="boundary@example.invalid", password="TestPassword123!"
        )
        self.client.force_login(self.user)

    def test_calendar_extremes_render_and_navigation_remains_renderable(self):
        for year, month in ((1, 1), (9999, 12), (9999, 11)):
            with self.subTest(year=year, month=month):
                response = self.client.get(reverse("event:events"), {"year": year, "month": month})
                self.assertEqual(response.status_code, 200)
                for key in (
                    "previous_month_query",
                    "next_month_query",
                    "previous_year_query",
                    "next_year_query",
                ):
                    linked = self.client.get(reverse("event:events") + "?" + response.context[key])
                    self.assertEqual(linked.status_code, 200)

    def test_rejected_edit_survives_page_correction_once(self):
        records = [
            Event.objects.create(
                user=self.user,
                title=f"Event {index:02}",
                scheduled_date=timezone.localdate(),
                all_day=True,
            )
            for index in range(21)
        ]
        selected = records[-1]
        response = self.client.post(
            reverse("event:edit_event", args=[selected.pk]) + "?sort=created_at",
            {"title": "", "scheduled_date": timezone.localdate().isoformat(), "all_day": "on"},
        )
        correction = self.client.get(response.url)
        self.assertEqual(correction.status_code, 302)
        final = self.client.get(correction.url)
        self.assertTrue(final.context["edit_event_form"].is_bound)
        self.assertIn("title", final.context["edit_event_form"].errors)
        self.assertFalse(self.client.get(correction.url).context["edit_event_form"].is_bound)
