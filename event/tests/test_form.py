"""Event form behaviour."""

from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from contact.models import Contact

from ..forms import EventContactForm, EventForm
from ..models import Event, EventContact
from .support import EventTestMixin


class EventFormTests(EventTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.property = self.create_property(self.user)

    def test_title_accepts_75_characters_and_rejects_76(self):
        data = self.valid_form_data(title="E" * 75)
        self.assertTrue(EventForm(data=data, user=self.user).is_valid())

        data["title"] = "E" * 76
        form = EventForm(data=data, user=self.user)
        self.assertFalse(form.is_valid())
        self.assertIn("title", form.errors)
        self.assertEqual(form.fields["title"].widget.attrs["maxlength"], "75")

    def test_valid_all_day_and_timed_forms(self):
        all_day = EventForm(data=self.valid_form_data(), user=self.user)
        timed = EventForm(
            data=self.valid_form_data(
                all_day="",
                start_time="09:00",
            ),
            user=self.user,
        )

        self.assertTrue(all_day.is_valid(), all_day.errors)
        self.assertTrue(timed.is_valid(), timed.errors)

    def test_new_event_defaults_to_local_today_without_overwriting_edits_or_bound_data(self):
        new_form = EventForm(user=self.user)
        explicit_form = EventForm(user=self.user, initial={"scheduled_date": date(2026, 12, 1)})
        bound_form = EventForm(data=self.valid_form_data(scheduled_date=""), user=self.user)
        existing = self.create_event(self.user, scheduled_date=date(2026, 12, 2))
        edit_form = EventForm(user=self.user, instance=existing)

        self.assertEqual(new_form.initial["scheduled_date"], timezone.localdate())
        self.assertEqual(explicit_form.initial["scheduled_date"], date(2026, 12, 1))
        self.assertNotIn("scheduled_date", bound_form.initial)
        self.assertEqual(edit_form["scheduled_date"].value(), date(2026, 12, 2))

    def test_timed_start_shows_only_missing_or_format_error(self):
        missing = EventForm(data=self.valid_form_data(all_day="", start_time=""), user=self.user)
        malformed = EventForm(
            data=self.valid_form_data(all_day="", start_time="1111"), user=self.user
        )

        self.assertEqual(list(missing.errors["start_time"]), ["Enter a start time."])
        self.assertEqual(list(malformed.errors["start_time"]), ["Enter a valid time."])

    def test_end_before_start_takes_precedence_over_elapsed_time(self):
        today = date(2026, 9, 23)
        with (
            patch("event.forms.timezone.localdate", return_value=today),
            patch("event.forms.timezone.localtime", return_value=datetime(2026, 9, 23, 12)),
        ):
            add = EventForm(
                data=self.valid_form_data(
                    scheduled_date=today.isoformat(),
                    all_day="",
                    start_time="10:00",
                    end_time="09:00",
                ),
                user=self.user,
            )
            existing = self.create_event(
                self.user,
                scheduled_date=today,
                all_day=False,
                start_time=time(10),
                end_time=time(11),
            )
            edit = EventForm(
                data=self.valid_form_data(
                    scheduled_date=today.isoformat(),
                    all_day="",
                    start_time="10:00",
                    end_time="09:00",
                ),
                user=self.user,
                instance=existing,
            )

            for form in (add, edit):
                with self.subTest(edit=bool(form.instance.pk)):
                    self.assertEqual(
                        list(form.errors["end_time"]), ["End time must be later than start time."]
                    )
                    self.assertNotIn("start_time", form.errors)

    def test_time_fields_use_plain_24_hour_text_inputs(self):
        form = EventForm(user=self.user)

        for field_name in ("start_time", "end_time"):
            widget = form.fields[field_name].widget
            self.assertEqual(widget.input_type, "text")
            self.assertNotIn("inputmode", widget.attrs)
            self.assertNotIn("placeholder", widget.attrs)

    def test_timing_rules_are_attached_to_time_fields(self):
        all_day_with_times = EventForm(
            data=self.valid_form_data(
                start_time="09:00",
                end_time="10:00",
            ),
            user=self.user,
        )
        timed_without_times = EventForm(data=self.valid_form_data(all_day=""), user=self.user)
        reversed_times = EventForm(
            data=self.valid_form_data(
                all_day="",
                start_time="10:00",
                end_time="09:00",
            ),
            user=self.user,
        )

        self.assertFalse(all_day_with_times.is_valid())
        self.assertIn("start_time", all_day_with_times.errors)
        self.assertIn("end_time", all_day_with_times.errors)
        self.assertFalse(timed_without_times.is_valid())
        self.assertIn("start_time", timed_without_times.errors)
        self.assertNotIn("end_time", timed_without_times.errors)
        self.assertFalse(reversed_times.is_valid())
        self.assertIn("end_time", reversed_times.errors)

    def test_scheduled_event_rejects_new_past_date_but_allows_historical_corrections(self):
        past = timezone.localdate() - timedelta(days=1)
        new_event = EventForm(
            data=self.valid_form_data(scheduled_date=past.isoformat()),
            user=self.user,
        )
        event = self.create_event(self.user, scheduled_date=past)
        unchanged = EventForm(
            data=self.valid_form_data(scheduled_date=past.isoformat(), title="Updated"),
            user=self.user,
            instance=event,
        )
        moved_earlier = EventForm(
            data=self.valid_form_data(scheduled_date=(past - timedelta(days=1)).isoformat()),
            user=self.user,
            instance=event,
        )

        self.assertIn("scheduled_date", new_event.errors)
        self.assertIn(
            "Choose today or a future date for a new event.", new_event.errors["scheduled_date"]
        )
        self.assertTrue(unchanged.is_valid(), unchanged.errors)
        self.assertTrue(moved_earlier.is_valid(), moved_earlier.errors)

    def test_past_event_allows_time_date_and_all_day_corrections(self):
        past = timezone.localdate() - timedelta(days=1)
        event = self.create_event(
            self.user,
            scheduled_date=past,
            all_day=False,
            start_time=time(9),
            end_time=time(10),
        )
        base = self.valid_form_data(
            scheduled_date=past.isoformat(),
            all_day="",
            start_time="09:00",
            end_time="10:00",
            title="Changed title",
        )
        unchanged = EventForm(data=base, user=self.user, instance=event)
        self.assertTrue(unchanged.is_valid(), unchanged.errors)
        changed_time = EventForm(
            data={**base, "start_time": "08:00"},
            user=self.user,
            instance=Event.objects.get(pk=event.pk),
        )
        self.assertTrue(changed_time.is_valid(), changed_time.errors)
        switched_all_day = EventForm(
            data={**base, "all_day": "on", "start_time": "", "end_time": ""},
            user=self.user,
            instance=Event.objects.get(pk=event.pk),
        )
        self.assertTrue(switched_all_day.is_valid(), switched_all_day.errors)
        moved_future = EventForm(
            data={
                **base,
                "scheduled_date": (timezone.localdate() + timedelta(days=2)).isoformat(),
                "start_time": "08:00",
            },
            user=self.user,
            instance=Event.objects.get(pk=event.pk),
        )
        self.assertTrue(moved_future.is_valid(), moved_future.errors)

    def test_today_timed_event_rejects_elapsed_time_and_all_day_remains_available(self):
        today = date(2026, 9, 23)
        with (
            patch("event.forms.timezone.localdate", return_value=today),
            patch("event.forms.timezone.localtime", return_value=datetime(2026, 9, 23, 12)),
        ):
            ended = EventForm(
                data=self.valid_form_data(
                    scheduled_date=today.isoformat(),
                    all_day="",
                    start_time="09:00",
                    end_time="10:00",
                ),
                user=self.user,
            )
            without_end = EventForm(
                data=self.valid_form_data(
                    scheduled_date=today.isoformat(),
                    all_day="",
                    start_time="09:00",
                ),
                user=self.user,
            )
            all_day = EventForm(
                data=self.valid_form_data(scheduled_date=today.isoformat()),
                user=self.user,
            )

            self.assertIn("end_time", ended.errors)
            self.assertIn("start_time", without_end.errors)
            self.assertTrue(all_day.is_valid(), all_day.errors)

    def test_presence_requires_participation(self):
        form = EventForm(
            data=self.valid_form_data(
                user_presence_required="on",
            ),
            user=self.user,
        )

        self.assertFalse(form.is_valid())
        self.assertIn("user_participation_required", form.errors)

    def test_property_choices_are_owner_scoped(self):
        other_property = self.create_property(self.create_user("bob@example.com"), "Other House")
        deleted = self.create_property(self.user, "Deleted", deleted_at=timezone.now())

        form = EventForm(user=self.user)

        self.assertIn(self.property, form.fields["property"].queryset)
        self.assertNotIn(other_property, form.fields["property"].queryset)
        self.assertNotIn(deleted, form.fields["property"].queryset)


class EventContactFormTests(EventTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.event = self.create_event(self.user)

    def test_accepts_multiple_owner_contacts(self):
        alpha = self.create_contact(self.user, "Alpha")
        beta = self.create_contact(self.user, "Beta")
        form = EventContactForm(
            data={"contacts": [alpha.pk, beta.pk]},
            user=self.user,
        )

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(set(form.cleaned_data["contacts"]), {alpha, beta})

    def test_rejects_other_inactive_and_deleted_contacts(self):
        other = self.create_contact(self.create_user("bob@example.com"), "Other")
        inactive = self.create_contact(self.user, "Inactive", state=Contact.State.DEACTIVATED)
        deleted = self.create_contact(self.user, "Deleted", deleted_at=timezone.now())
        for contact in (other, inactive, deleted):
            with self.subTest(contact=contact):
                form = EventContactForm(data={"contacts": [contact.pk]}, user=self.user)
                self.assertFalse(form.is_valid())

    def test_existing_event_contacts_are_excluded(self):
        existing = self.create_contact(self.user)
        available = self.create_contact(self.user, "Available")
        EventContact.objects.create(event=self.event, contact=existing)

        form = EventContactForm(user=self.user, event=self.event)

        self.assertNotIn(existing, form.fields["contacts"].queryset)
        self.assertIn(available, form.fields["contacts"].queryset)
