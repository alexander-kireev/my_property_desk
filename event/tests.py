from datetime import date, datetime, time, timedelta
from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from contact.models import Contact, ContactMethod
from property.models import Property

from .templatetags.event_display import compact_email
from .forms import EventContactForm, EventForm
from .models import Event, EventContact
from .selectors import (
    calendar_events_for_user,
    event_contacts_for_event,
    events_for_user,
    filtered_events_for_user,
)
from .services import (
    add_contacts_to_event,
    cancel_event,
    create_event,
    delete_event,
    mark_event_occurred,
    reactivate_event,
    remove_contact_from_event,
    update_event,
)


class EventTestMixin:
    password = "HolidayHome123!"

    def create_user(self, email="alice@example.com"):
        return User.objects.create_user(
            email=email,
            first_name="Alice",
            last_name="Smith",
            password=self.password,
        )

    def create_property(self, user, name="Hill House", **values):
        return Property.objects.create(user=user, name=name, **values)

    def create_contact(self, user, first_name="Alex", **values):
        return Contact.objects.create(user=user, first_name=first_name, **values)

    def create_event(self, user, title="Inspection", **values):
        defaults = {
            "scheduled_date": date(2026, 9, 20),
            "all_day": True,
        }
        defaults.update(values)
        return Event.objects.create(user=user, title=title, **defaults)

    def valid_form_data(self, **values):
        data = {
            "title": "Inspection",
            "description": "Annual inspection",
            "scheduled_date": (timezone.localdate() + timedelta(days=1)).isoformat(),
            "all_day": "on",
        }
        data.update(values)
        return data


class EventModelTests(EventTestMixin, TestCase):
    def test_defaults_relationships_and_string_value(self):
        user = self.create_user()
        event = self.create_event(user)

        self.assertEqual(event.state, Event.State.SCHEDULED)
        self.assertFalse(event.user_participation_required)
        self.assertFalse(event.user_presence_required)
        self.assertIsNone(event.property)
        self.assertIsNone(event.terminated_at)
        self.assertIsNone(event.deleted_at)
        self.assertEqual(str(event), "Inspection")

    def test_database_rejects_invalid_timing(self):
        user = self.create_user()
        invalid_values = (
            {"all_day": True, "start_time": time(9), "end_time": time(10)},
            {"all_day": False, "start_time": None, "end_time": None},
            {"all_day": False, "start_time": time(10), "end_time": time(9)},
        )
        for values in invalid_values:
            with self.subTest(values=values), self.assertRaises(IntegrityError):
                with transaction.atomic():
                    self.create_event(user, **values)

    def test_database_allows_timed_event_without_end_time(self):
        event = self.create_event(
            self.create_user(),
            all_day=False,
            start_time=time(9),
            end_time=None,
        )

        self.assertEqual(event.start_time, time(9))
        self.assertIsNone(event.end_time)

    def test_database_rejects_presence_without_participation(self):
        user = self.create_user()
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                self.create_event(
                    user,
                    user_presence_required=True,
                    user_participation_required=False,
                )

    def test_event_contact_is_unique_per_event(self):
        user = self.create_user()
        event = self.create_event(user)
        contact = self.create_contact(user)
        EventContact.objects.create(event=event, contact=contact)

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                EventContact.objects.create(event=event, contact=contact)


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
        timed = EventForm(data=self.valid_form_data(
            all_day="",
            start_time="09:00",
        ), user=self.user)

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
        malformed = EventForm(data=self.valid_form_data(all_day="", start_time="1111"), user=self.user)

        self.assertEqual(list(missing.errors["start_time"]), ["Enter a start time."])
        self.assertEqual(list(malformed.errors["start_time"]), ["Enter a valid time."])

    def test_end_before_start_takes_precedence_over_elapsed_time(self):
        today = date(2026, 9, 23)
        with (
            patch("event.forms.timezone.localdate", return_value=today),
            patch("event.forms.timezone.localtime", return_value=datetime(2026, 9, 23, 12)),
        ):
            add = EventForm(data=self.valid_form_data(
                scheduled_date=today.isoformat(), all_day="",
                start_time="10:00", end_time="09:00",
            ), user=self.user)
            existing = self.create_event(
                self.user, scheduled_date=today, all_day=False,
                start_time=time(10), end_time=time(11),
            )
            edit = EventForm(data=self.valid_form_data(
                scheduled_date=today.isoformat(), all_day="",
                start_time="10:00", end_time="09:00",
            ), user=self.user, instance=existing)

            for form in (add, edit):
                with self.subTest(edit=bool(form.instance.pk)):
                    self.assertEqual(list(form.errors["end_time"]), ["End time must be later than start time."])
                    self.assertNotIn("start_time", form.errors)

    def test_time_fields_use_plain_24_hour_text_inputs(self):
        form = EventForm(user=self.user)

        for field_name in ("start_time", "end_time"):
            widget = form.fields[field_name].widget
            self.assertEqual(widget.input_type, "text")
            self.assertNotIn("inputmode", widget.attrs)
            self.assertNotIn("placeholder", widget.attrs)

    def test_timing_rules_are_attached_to_time_fields(self):
        all_day_with_times = EventForm(data=self.valid_form_data(
            start_time="09:00",
            end_time="10:00",
        ), user=self.user)
        timed_without_times = EventForm(data=self.valid_form_data(all_day=""), user=self.user)
        reversed_times = EventForm(data=self.valid_form_data(
            all_day="",
            start_time="10:00",
            end_time="09:00",
        ), user=self.user)

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
        self.assertIn("Choose today or a future date for a new event.", new_event.errors["scheduled_date"])
        self.assertTrue(unchanged.is_valid(), unchanged.errors)
        self.assertTrue(moved_earlier.is_valid(), moved_earlier.errors)

    def test_past_event_allows_time_date_and_all_day_corrections(self):
        past = timezone.localdate() - timedelta(days=1)
        event = self.create_event(
            self.user, scheduled_date=past, all_day=False,
            start_time=time(9), end_time=time(10),
        )
        base = self.valid_form_data(
            scheduled_date=past.isoformat(), all_day="",
            start_time="09:00", end_time="10:00", title="Changed title",
        )
        unchanged = EventForm(data=base, user=self.user, instance=event)
        self.assertTrue(unchanged.is_valid(), unchanged.errors)
        changed_time = EventForm(
            data={**base, "start_time": "08:00"}, user=self.user,
            instance=Event.objects.get(pk=event.pk),
        )
        self.assertTrue(changed_time.is_valid(), changed_time.errors)
        switched_all_day = EventForm(
            data={**base, "all_day": "on", "start_time": "", "end_time": ""},
            user=self.user, instance=Event.objects.get(pk=event.pk),
        )
        self.assertTrue(switched_all_day.is_valid(), switched_all_day.errors)
        moved_future = EventForm(
            data={**base, "scheduled_date": (timezone.localdate() + timedelta(days=2)).isoformat(), "start_time": "08:00"},
            user=self.user, instance=Event.objects.get(pk=event.pk),
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
                    scheduled_date=today.isoformat(), all_day="",
                    start_time="09:00", end_time="10:00",
                ),
                user=self.user,
            )
            without_end = EventForm(
                data=self.valid_form_data(
                    scheduled_date=today.isoformat(), all_day="", start_time="09:00",
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
        form = EventForm(data=self.valid_form_data(
            user_presence_required="on",
        ), user=self.user)

        self.assertFalse(form.is_valid())
        self.assertIn("user_participation_required", form.errors)

    def test_property_choices_are_owner_scoped(self):
        other_property = self.create_property(
            self.create_user("bob@example.com"), "Other House"
        )
        deleted = self.create_property(
            self.user, "Deleted", deleted_at=timezone.now()
        )

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

    def test_contact_choices_use_shared_checkbox_style(self):
        self.create_contact(self.user, "Alpha")

        form = EventContactForm(user=self.user)

        self.assertIn('class="form-check-input"', str(form["contacts"]))

    def test_rejects_other_inactive_and_deleted_contacts(self):
        other = self.create_contact(self.create_user("bob@example.com"), "Other")
        inactive = self.create_contact(
            self.user, "Inactive", state=Contact.State.DEACTIVATED
        )
        deleted = self.create_contact(
            self.user, "Deleted", deleted_at=timezone.now()
        )
        for contact in (other, inactive, deleted):
            with self.subTest(contact=contact):
                form = EventContactForm(
                    data={"contacts": [contact.pk]}, user=self.user
                )
                self.assertFalse(form.is_valid())

    def test_existing_event_contacts_are_excluded(self):
        existing = self.create_contact(self.user)
        available = self.create_contact(self.user, "Available")
        EventContact.objects.create(event=self.event, contact=existing)

        form = EventContactForm(user=self.user, event=self.event)

        self.assertNotIn(existing, form.fields["contacts"].queryset)
        self.assertIn(available, form.fields["contacts"].queryset)


class EventSelectorTests(EventTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.other_user = self.create_user("bob@example.com")
        self.property = self.create_property(
            self.user, address="12 Hill Road"
        )

    def test_events_for_user_scopes_owner_and_soft_deletion(self):
        visible = self.create_event(self.user)
        self.create_event(self.other_user, "Other")
        self.create_event(self.user, "Deleted", deleted_at=timezone.now())

        self.assertEqual(list(events_for_user(user=self.user)), [visible])

    def test_search_and_filters(self):
        wanted = self.create_event(
            self.user,
            "Unrelated title",
            property=self.property,
            state=Event.State.CANCELLED,
            user_participation_required=True,
            user_presence_required=True,
        )
        self.create_event(self.user, "Other")

        result = filtered_events_for_user(
            user=self.user,
            search="Hill Road",
            state=Event.State.CANCELLED,
            property_id=self.property.pk,
            participation="required",
            presence="required",
        )

        self.assertEqual(list(result), [wanted])

    def test_calendar_selector_uses_visible_date_range(self):
        inside = self.create_event(
            self.user, scheduled_date=date(2026, 9, 12)
        )
        self.create_event(self.user, "Outside", scheduled_date=date(2026, 10, 1))

        result = calendar_events_for_user(
            user=self.user,
            start_date=date(2026, 9, 1),
            end_date=date(2026, 9, 30),
        )

        self.assertEqual(list(result), [inside])

    def test_event_contacts_are_ordered_and_include_historical_contacts(self):
        event = self.create_event(self.user)
        zed = self.create_contact(self.user, "Zed")
        amy = self.create_contact(self.user, "Amy", state=Contact.State.DEACTIVATED)
        zed_link = EventContact.objects.create(event=event, contact=zed)
        amy_link = EventContact.objects.create(event=event, contact=amy)
        first_email = ContactMethod.objects.create(
            contact=amy,
            type=ContactMethod.Type.EMAIL,
            value="first@example.com",
        )
        ContactMethod.objects.create(
            contact=amy,
            type=ContactMethod.Type.EMAIL,
            value="second@example.com",
        )
        first_telephone = ContactMethod.objects.create(
            contact=amy,
            type=ContactMethod.Type.TELEPHONE,
            value="+447700900123",
        )

        participants = list(event_contacts_for_event(event=event))

        self.assertEqual(participants, [amy_link, zed_link])
        self.assertEqual(participants[0].contact_email, first_email.value)
        self.assertEqual(
            participants[0].contact_telephone,
            first_telephone.value,
        )


class EventServiceTests(EventTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.property = self.create_property(self.user)

    def test_create_update_and_soft_delete_event(self):
        event = create_event(
            user=self.user,
            title="Created",
            property=self.property,
            scheduled_date=date(2026, 9, 20),
            all_day=True,
            user_participation_required=False,
            user_presence_required=False,
        )
        update_event(
            event=event,
            title="Updated",
            description="Changed",
            property=None,
            scheduled_date=date(2026, 9, 21),
            all_day=True,
            user_participation_required=False,
            user_presence_required=False,
        )
        delete_event(event=event)

        event.refresh_from_db()
        self.assertEqual(event.title, "Updated")
        self.assertIsNone(event.property)
        self.assertIsNotNone(event.deleted_at)

    def test_create_rejects_another_users_property(self):
        other_property = self.create_property(
            self.create_user("bob@example.com"), "Other"
        )
        with self.assertRaises(ValueError):
            create_event(
                user=self.user,
                title="Invalid",
                property=other_property,
                scheduled_date=date(2026, 9, 20),
                all_day=True,
                user_participation_required=False,
                user_presence_required=False,
            )

    def test_lifecycle_transitions_and_guards(self):
        occurred = self.create_event(self.user)
        mark_event_occurred(event=occurred)
        first_termination = occurred.terminated_at
        cancel_event(event=occurred)
        occurred.refresh_from_db()
        self.assertEqual(occurred.state, Event.State.OCCURRED)
        self.assertEqual(occurred.terminated_at, first_termination)

        reactivate_event(event=occurred)
        occurred.refresh_from_db()
        self.assertEqual(occurred.state, Event.State.SCHEDULED)
        self.assertIsNone(occurred.terminated_at)

    def test_create_with_contacts_is_atomic_and_owner_scoped(self):
        contact = self.create_contact(self.user)
        event = create_event(
            user=self.user,
            title="With contact",
            scheduled_date=date(2026, 9, 20),
            all_day=True,
            user_participation_required=False,
            user_presence_required=False,
            contacts=[contact],
        )
        self.assertTrue(
            EventContact.objects.filter(event=event, contact=contact).exists()
        )

        other = self.create_contact(self.create_user("bob@example.com"), "Other")
        with self.assertRaises(ValueError):
            create_event(
                user=self.user,
                title="Rolled back",
                scheduled_date=date(2026, 9, 20),
                all_day=True,
                user_participation_required=False,
                user_presence_required=False,
                contacts=[other],
            )
        self.assertFalse(Event.objects.filter(title="Rolled back").exists())

    def test_add_contacts_is_idempotent_and_remove_deletes_only_link(self):
        event = self.create_event(self.user)
        contact = self.create_contact(self.user)
        add_contacts_to_event(event=event, contacts=[contact, contact])
        add_contacts_to_event(event=event, contacts=[contact])
        link = EventContact.objects.get(event=event, contact=contact)

        remove_contact_from_event(event_contact=link)

        self.assertTrue(Contact.objects.filter(pk=contact.pk).exists())
        self.assertFalse(EventContact.objects.filter(pk=link.pk).exists())

    def test_participants_cannot_change_after_termination(self):
        event = self.create_event(self.user, state=Event.State.CANCELLED)
        contact = self.create_contact(self.user)
        add_contacts_to_event(event=event, contacts=[contact])
        self.assertFalse(EventContact.objects.filter(event=event).exists())

        link = EventContact.objects.create(event=event, contact=contact)
        remove_contact_from_event(event_contact=link)
        self.assertTrue(EventContact.objects.filter(pk=link.pk).exists())


class EventViewTests(EventTestMixin, TestCase):
    def setUp(self):
        self.user = self.create_user()
        self.client.force_login(self.user)

    def test_terminated_event_history_copy_uses_natural_grammar(self):
        occurred = self.create_event(self.user, state=Event.State.OCCURRED)
        cancelled = self.create_event(self.user, state=Event.State.CANCELLED)

        occurred_response = self.client.get(reverse("event:events"), {"selected": occurred.pk})
        cancelled_response = self.client.get(reverse("event:events"), {"selected": cancelled.pk})

        self.assertContains(occurred_response, "This event occurred.")
        self.assertContains(cancelled_response, "This event was cancelled.")
        self.assertNotContains(occurred_response, "was occurred")

    def test_participant_email_middle_truncation_keeps_both_ends(self):
        short_email = "someone@example.com"
        long_email = "abcdefghijklmnopqrstuvwx@example-domain.com"
        self.assertEqual(compact_email(short_email), short_email)
        self.assertEqual(compact_email("a" * 35), "a" * 35)
        self.assertEqual(
            compact_email(long_email),
            f"{long_email[:16]}...{long_email[-16:]}",
        )
        self.assertEqual(len(compact_email(long_email)), 35)

    def test_participant_rows_show_compact_email_with_full_hover_text(self):
        event = self.create_event(self.user)
        contact = self.create_contact(
            self.user, first_name="A" * 50, last_name="B" * 50
        )
        email = "abcdefghijklmnopqrstuvwx@example-domain.com"
        ContactMethod.objects.create(
            contact=contact, type=ContactMethod.Type.EMAIL, value=email
        )
        ContactMethod.objects.create(
            contact=contact,
            type=ContactMethod.Type.TELEPHONE,
            value="+447700900321",
        )
        EventContact.objects.create(event=event, contact=contact)

        response = self.client.get(reverse("event:events"), {"selected": event.pk})

        self.assertContains(response, f'title="{email}"', count=2)
        self.assertContains(response, compact_email(email), count=2)
        self.assertContains(response, 'class="event-participant-email"', count=2)
        self.assertContains(response, 'class="event-participant-phone"', count=2)
        self.assertContains(response, f'title="{contact}"')

    def test_phone_only_participant_has_no_email_content_before_phone(self):
        event = self.create_event(self.user)
        contact = self.create_contact(self.user)
        ContactMethod.objects.create(
            contact=contact,
            type=ContactMethod.Type.TELEPHONE,
            value="+447700900321",
        )
        EventContact.objects.create(event=event, contact=contact)

        response = self.client.get(reverse("event:events"), {"selected": event.pk})

        self.assertNotContains(response, '<span class="event-participant-email"></span>')
        self.assertContains(response, '<span class="event-participant-phone" title="+447700900321">+447700900321</span>', count=2)

    def test_participant_without_contact_methods_has_only_one_detail_cell(self):
        event = self.create_event(self.user)
        contact = self.create_contact(self.user)
        EventContact.objects.create(event=event, contact=contact)

        response = self.client.get(reverse("event:events"), {"selected": event.pk})

        self.assertContains(response, '<span class="event-participant-no-methods">No contact details</span>', count=2)
        self.assertNotContains(response, '<span class="event-participant-email"')
        self.assertNotContains(response, '<span class="event-participant-phone"')

    def test_historical_participants_have_compact_inline_status_labels(self):
        event = self.create_event(self.user)
        deleted = self.create_contact(self.user, first_name="A" * 50)
        deleted.deleted_at = timezone.now()
        deleted.save(update_fields=["deleted_at"])
        inactive = self.create_contact(
            self.user, first_name="B" * 50, state=Contact.State.DEACTIVATED
        )
        EventContact.objects.create(event=event, contact=deleted)
        EventContact.objects.create(event=event, contact=inactive)

        response = self.client.get(reverse("event:events"), {"selected": event.pk})

        self.assertContains(response, '<span class="event-participant-status">Deleted contact</span>', count=2)
        self.assertContains(response, '<span class="event-participant-status" title="Deactivated contact">Inactive</span>', count=2)
        self.assertNotContains(response, '<span class="badge text-bg-secondary">Deleted contact</span>')

    def test_workspace_requires_login_and_post_endpoints_reject_get(self):
        self.client.logout()
        response = self.client.get(reverse("event:events"))
        self.assertEqual(response.status_code, 302)

        self.client.force_login(self.user)
        response = self.client.get(reverse("event:add_event"))
        self.assertEqual(response.status_code, 405)

    def test_workspace_renders_calendar_and_defaults_to_details_tab(self):
        event = self.create_event(self.user, scheduled_date=date(2026, 9, 17))
        response = self.client.get(reverse("event:events"), {
            "month": 9,
            "year": 2026,
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_tab"], "details")
        self.assertEqual(response.context["calendar_month_label"], "September 2026")
        self.assertEqual(response.context["calendar_event_count"], 1)
        self.assertContains(response, event.title)

    def test_event_relationship_is_qualified_in_list_and_detail(self):
        property_record = self.create_property(self.user)
        event = self.create_event(self.user, property=property_record)

        response = self.client.get(reverse("event:events"), {"selected": event.pk})

        self.assertContains(response, 'title="Hill House"')
        self.assertContains(response, '<dt>Related to</dt>')
        self.assertContains(response, '<span class="task-related-copy">Hill House</span>')
        self.assertContains(response, 'class="event-command-context" title="Hill House">Hill House</span>')
        self.assertNotContains(response, '<span aria-hidden="true">·</span>')
        self.assertContains(response, '<h3 class="h5 mb-3">Details</h3>')
        self.assertNotContains(response, 'Related to: Property ·')
        self.assertContains(response, 'class="expandable-text expandable-text--fit-card expandable-text--inline-end"')

    def test_crowded_day_shows_first_event_and_more_link_then_filters_list(self):
        day = date(2026, 10, 1)
        for index in range(10):
            self.create_event(self.user, f"Visit {index:02d}", scheduled_date=day)
        other = self.create_event(self.user, "Another day", scheduled_date=date(2026, 10, 2))

        response = self.client.get(reverse("event:events"), {"month": 10, "year": 2026})
        cell = next(item for week in response.context["calendar_weeks"] for item in week if item["date"] == day)
        self.assertEqual(cell["more_count"], 9)
        self.assertEqual(cell["first_event"].title, "Visit 00")
        self.assertContains(response, "+9 more")
        self.assertContains(response, 'data-calendar-day-href="?month=10&amp;year=2026&amp;day=2026-10-01#eventResults"')

        filtered = self.client.get(reverse("event:events"), {
            "month": 10, "year": 2026, "day": "2026-10-01",
        })
        self.assertEqual(filtered.context["page_obj"].paginator.count, 10)
        self.assertEqual(filtered.context["calendar_event_count"], 11)
        self.assertEqual(filtered.context["selected_day"], day)
        self.assertContains(filtered, "Date: 1 Oct 2026")
        self.assertContains(filtered, 'aria-label="Clear date filter for 1 October 2026"')
        self.assertNotIn(other, filtered.context["page_obj"].object_list)
        self.assertEqual(filtered.context["mobile_agenda_day"], day)
        self.assertEqual(len(filtered.context["mobile_agenda_events"]), 10)
        self.assertContains(filtered, 'id="eventAgenda"')
        self.assertContains(filtered, 'class="event-calendar-count" aria-hidden="true">10<span class="event-calendar-count-label"> events</span></span>')

    def test_mobile_agenda_orders_all_day_then_timed_events(self):
        day = date(2026, 10, 1)
        late = self.create_event(self.user, "Late", scheduled_date=day, all_day=False, start_time=time(16))
        early = self.create_event(self.user, "Early", scheduled_date=day, all_day=False, start_time=time(9))
        all_day = self.create_event(self.user, "All day", scheduled_date=day)

        response = self.client.get(reverse("event:events"), {"month": 10, "year": 2026, "day": day.isoformat()})
        self.assertEqual(response.context["mobile_agenda_events"], [all_day, early, late])
        self.assertContains(response, f'agenda_day=2026-10-01&amp;view=calendar&amp;selected={early.pk}&amp;tab=calendar')

    def test_mobile_calendar_empty_day_stays_on_calendar_without_filtering_list(self):
        event = self.create_event(self.user, scheduled_date=date(2026, 10, 2))
        empty_day = date(2026, 10, 1)

        response = self.client.get(reverse("event:events"), {
            "month": 10, "year": 2026, "agenda_day": empty_day.isoformat(),
            "view": "calendar",
        })

        self.assertTrue(response.context["mobile_calendar_view"])
        self.assertEqual(response.context["mobile_agenda_day"], empty_day)
        self.assertEqual(response.context["mobile_agenda_events"], [])
        self.assertIsNone(response.context["selected_day"])
        self.assertIn(event, response.context["page_obj"].object_list)
        self.assertContains(response, "No events planned for this day.")
        self.assertContains(response, 'data-calendar-agenda-href="?month=10&amp;year=2026&amp;agenda_day=2026-10-01&amp;view=calendar#eventAgenda"')

    def test_mobile_calendar_ignores_agenda_day_outside_visible_month(self):
        response = self.client.get(reverse("event:events"), {
            "month": 10, "year": 2026, "agenda_day": "2026-12-01",
            "view": "calendar",
        })

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

        response = self.client.get(reverse("event:events"), {"month": 10, "year": 2026, "day": day.isoformat()})

        self.assertContains(response, f'class="event-mobile-agenda-title event-command-title" title="{event.title}"')
        self.assertContains(response, f'class="event-mobile-agenda-context event-command-context" title="{property_record.name}"')
        self.assertContains(response, 'class="event-command-meta"')
        self.assertContains(response, 'class="event-mobile-agenda-time event-command-when">09:00–10:00</span>')

    def test_mobile_agenda_selection_expands_in_calendar_without_filtering_list(self):
        day = date(2026, 10, 1)
        event = self.create_event(self.user, "Heating service", scheduled_date=day)
        other = self.create_event(self.user, "Tomorrow", scheduled_date=date(2026, 10, 2))

        response = self.client.get(reverse("event:events"), {
            "month": 10, "year": 2026, "agenda_day": day.isoformat(),
            "view": "calendar", "selected": event.pk, "tab": "calendar",
        })

        self.assertTrue(response.context["mobile_calendar_view"])
        self.assertIsNone(response.context["selected_day"])
        self.assertIn(other, response.context["page_obj"].object_list)
        self.assertContains(response, f'id="eventAgendaInlineDetails{event.pk}"')
        self.assertContains(response, f'aria-controls="eventAgendaInlineDetails{event.pk}"')
        self.assertContains(response, f'id="event-agenda-description-{event.pk}"')

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

    def test_day_filter_orders_all_day_then_timed_events(self):
        day = date(2026, 10, 1)
        late = self.create_event(self.user, "Late", scheduled_date=day, all_day=False, start_time=time(16))
        early = self.create_event(self.user, "Early", scheduled_date=day, all_day=False, start_time=time(9))
        all_day = self.create_event(self.user, "All day", scheduled_date=day)
        response = self.client.get(reverse("event:events"), {"day": day.isoformat()})
        self.assertEqual(list(response.context["page_obj"].object_list), [all_day, early, late])

    def test_add_event_modal_renders_tabbed_contact_cards(self):
        contact = self.create_contact(self.user, first_name="Leila", last_name="Davies")
        ContactMethod.objects.create(
            contact=contact,
            type=ContactMethod.Type.EMAIL,
            value="leila@example.com",
        )

        response = self.client.get(reverse("event:events"))

        self.assertContains(response, 'data-event-tab="details"')
        self.assertContains(response, 'data-event-tab="participants"')
        self.assertContains(response, 'data-duration-choice')
        self.assertContains(response, 'value="all_day"')
        self.assertContains(response, 'value="timed"')
        self.assertContains(response, "Use 24-hour time (HH:MM), for example 09:30.")
        self.assertContains(response, "Requires participation.")
        self.assertContains(response, 'data-contact-option')
        self.assertContains(response, 'leila@example.com')
        self.assertContains(response, 'data-search-text="Leila Davies leila@example.com')
        self.assertContains(response, 'name="contacts"')
        self.assertContains(response, 'data-searchable-select')
        self.assertContains(response, 'js/searchable-select.js')

    def test_add_event_modal_defaults_date_to_local_today(self):
        response = self.client.get(reverse("event:events"))

        self.assertEqual(
            response.context["add_event_form"]["scheduled_date"].value(),
            timezone.localdate(),
        )
        self.assertContains(response, '>Date</label>')

    def test_participant_name_links_to_active_or_deactivated_contact(self):
        event = self.create_event(self.user)
        active = self.create_contact(self.user, first_name="Active")
        inactive = self.create_contact(
            self.user, first_name="Inactive", state=Contact.State.DEACTIVATED,
        )
        EventContact.objects.create(event=event, contact=active)
        EventContact.objects.create(event=event, contact=inactive)

        response = self.client.get(reverse("event:events"), {
            "selected": event.pk, "tab": "details",
        })

        self.assertContains(
            response,
            f'{reverse("contact:contacts")}?selected={active.pk}',
        )
        self.assertContains(
            response,
            f'{reverse("contact:contacts")}?state=all&amp;selected={inactive.pk}',
        )

    def test_add_and_edit_event_modals_use_the_same_property_picker(self):
        self.create_event(self.user)

        response = self.client.get(reverse("event:events"))

        self.assertContains(response, 'data-searchable-select', count=2)

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

    def test_invalid_calendar_parameters_fall_back_safely(self):
        response = self.client.get(reverse("event:events"), {
            "month": "bad",
            "year": "bad",
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["calendar_weeks"])

    def test_calendar_navigation_crosses_years_and_handles_leap_february(self):
        response = self.client.get(reverse("event:events"), {
            "month": 1,
            "year": 2028,
            "search": "inspection",
        })
        self.assertIn("month=12", response.context["previous_month_query"])
        self.assertIn("year=2027", response.context["previous_month_query"])
        self.assertIn("month=2", response.context["next_month_query"])
        self.assertIn("year=2028", response.context["next_month_query"])
        self.assertIn("search=inspection", response.context["next_month_query"])

        february = self.client.get(reverse("event:events"), {
            "month": 2,
            "year": 2028,
        })
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
        response = self.client.get(reverse("event:events"), {
            "month": 9,
            "year": 2026,
            "participation": "required",
        })

        self.assertEqual(len(response.context["page_obj"]), 20)
        self.assertEqual(response.context["calendar_event_count"], 25)

    def test_selected_owned_event_can_remain_visible_outside_filters(self):
        visible = self.create_event(self.user, "Visible")
        hidden = self.create_event(self.user, "Hidden", state=Event.State.CANCELLED)
        other = self.create_event(self.create_user("bob@example.com"), "Other")

        for selected in (hidden.pk, other.pk):
            response = self.client.get(reverse("event:events"), {
                "state": Event.State.SCHEDULED,
                "selected": selected,
            })
            if selected == hidden.pk:
                self.assertEqual(response.context["selected_event"], hidden)
                self.assertTrue(response.context["selected_outside_filters"])
            else:
                self.assertEqual(response.status_code, 302)
                self.assertEqual(self.client.get(response.url).context["selected_event"], visible)

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
        response = self.client.get(reverse("event:events"), {
            "selected": selected.pk,
            "tab": "details",
        })

        self.assertEqual(response.status_code, 302)
        self.assertIn("page=2", response.url)
        corrected = self.client.get(response.url)
        self.assertIn(selected, corrected.context["page_obj"].object_list)
        self.assertEqual(corrected.context["selected_event"], selected)
        self.assertEqual(corrected.context["active_tab"], "details")

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
        selected_response = self.client.get(reverse("event:events"), {"page": 2, "selected": last_event.pk, "tab": "details"})
        self.assertContains(selected_response, 'data-workspace-scroll-root="events"')
        self.assertContains(selected_response, 'data-workspace-scroll-list')
        self.assertContains(selected_response, 'data-workspace-scroll-row')
        self.assertContains(selected_response, 'js/workspace-list-scroll.js')
        self.assertContains(selected_response, 'class="event-mobile-back btn btn-sm pom-quiet mb-2" href="?page=2&amp;month=')

    def test_create_event_with_initial_contacts(self):
        contact = self.create_contact(self.user)
        response = self.client.post(reverse("event:add_event"), self.valid_form_data(
            contacts=[contact.pk]
        ))

        event = Event.objects.get(title="Inspection")
        self.assertRedirects(response, f"{reverse('event:events')}?selected={event.pk}")
        self.assertTrue(
            EventContact.objects.filter(event=event, contact=contact).exists()
        )

    def test_add_event_clears_stale_search_day_and_page(self):
        response = self.client.post(
            f"{reverse('event:add_event')}?search=unrelated&day=2026-01-01&page=3",
            self.valid_form_data(),
        )
        event = Event.objects.get(title="Inspection")
        self.assertEqual(response.url, f"{reverse('event:events')}?selected={event.pk}")

    def test_invalid_create_rerenders_open_add_modal(self):
        post_response = self.client.post(reverse("event:add_event"), self.valid_form_data(
            title=""
        ))

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

    def test_time_guidance_is_hidden_when_time_has_validation_error(self):
        post_response = self.client.post(
            reverse("event:add_event"),
            self.valid_form_data(all_day="", start_time="not-a-time"),
        )
        response = self.client.get(post_response.url)

        self.assertIn("start_time", response.context["add_event_form"].errors)
        self.assertContains(
            response,
            '<p class="form-text mt-0 mb-0" hidden>Use 24-hour time (HH:MM)',
        )

    def test_add_event_shows_only_order_error_for_elapsed_end_time(self):
        today = date(2026, 9, 23)
        with (
            patch("event.forms.timezone.localdate", return_value=today),
            patch("event.forms.timezone.localtime", return_value=datetime(2026, 9, 23, 12)),
        ):
            post_response = self.client.post(reverse("event:add_event"), self.valid_form_data(
                scheduled_date=today.isoformat(), all_day="",
                start_time="10:00", end_time="09:00",
            ))
            response = self.client.get(post_response.url)

        self.assertEqual(
            list(response.context["add_event_form"].errors["end_time"]),
            ["End time must be later than start time."],
        )

    def test_invalid_initial_contact_creates_no_event(self):
        other_contact = self.create_contact(
            self.create_user("bob@example.com"), "Other"
        )
        post_response = self.client.post(reverse("event:add_event"), self.valid_form_data(
            contacts=[other_contact.pk]
        ))

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["open_modal"], "addEventModal")
        self.assertIn("contacts", response.context["initial_contacts_form"].errors)
        self.assertFalse(Event.objects.exists())

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

    def test_edit_modal_preselects_participants_and_saves_changes(self):
        event = self.create_event(self.user)
        retained = self.create_contact(self.user, first_name="Amir")
        removed = self.create_contact(self.user, first_name="Bea")
        added = self.create_contact(self.user, first_name="Cora")
        EventContact.objects.create(event=event, contact=retained)
        EventContact.objects.create(event=event, contact=removed)

        response = self.client.get(reverse("event:events"), {"selected": event.pk, "open": "edit"})
        self.assertContains(response, 'id="editEventParticipantsTab"')
        self.assertContains(response, 'id="editEventParticipantsPanel"')
        self.assertContains(response, 'name="manage_contacts" value="1"')
        self.assertEqual(
            set(response.context["edit_contacts_form"].initial["contacts"]),
            {retained.pk, removed.pk},
        )

        response = self.client.post(
            reverse("event:edit_event", args=[event.pk]),
            self.valid_form_data(
                title="Updated with participants",
                manage_contacts="1",
                contacts=[retained.pk, added.pk],
            ),
        )
        self.assertEqual(response.status_code, 302)
        event.refresh_from_db()
        self.assertEqual(event.title, "Updated with participants")
        self.assertSetEqual(
            set(EventContact.objects.filter(event=event).values_list("contact_id", flat=True)),
            {retained.pk, added.pk},
        )

    def test_edit_modal_can_clear_active_participants_but_preserves_inactive_links(self):
        event = self.create_event(self.user)
        active = self.create_contact(self.user, first_name="Amir")
        inactive = self.create_contact(self.user, first_name="Bea", state=Contact.State.DEACTIVATED)
        EventContact.objects.create(event=event, contact=active)
        EventContact.objects.create(event=event, contact=inactive)

        response = self.client.post(
            reverse("event:edit_event", args=[event.pk]),
            self.valid_form_data(manage_contacts="1"),
        )
        self.assertEqual(response.status_code, 302)
        self.assertSetEqual(
            set(EventContact.objects.filter(event=event).values_list("contact_id", flat=True)),
            {inactive.pk},
        )

    def test_invalid_participant_selection_keeps_event_unchanged_and_reopens_tab(self):
        event = self.create_event(self.user)
        other = self.create_contact(self.create_user("bob@example.com"))
        response = self.client.post(
            reverse("event:edit_event", args=[event.pk]),
            self.valid_form_data(title="Should not save", manage_contacts="1", contacts=[other.pk]),
        )
        self.assertEqual(response.status_code, 302)
        event.refresh_from_db()
        self.assertEqual(event.title, "Inspection")

        restored = self.client.get(response.url)
        self.assertEqual(restored.context["open_modal"], "editEventModal")
        self.assertIn("contacts", restored.context["edit_contacts_form"].errors)
        self.assertContains(restored, 'id="editEventParticipantsTab"')
        self.assertContains(restored, 'id="editEventParticipantsPanel" role="tabpanel" aria-labelledby="editEventParticipantsTab" data-event-panel="participants">')

    def test_invalid_event_details_do_not_change_participants(self):
        event = self.create_event(self.user)
        current = self.create_contact(self.user)
        replacement = self.create_contact(self.user, first_name="Bea")
        EventContact.objects.create(event=event, contact=current)

        response = self.client.post(
            reverse("event:edit_event", args=[event.pk]),
            self.valid_form_data(title="", manage_contacts="1", contacts=[replacement.pk]),
        )
        self.assertEqual(response.status_code, 302)
        self.assertSetEqual(
            set(EventContact.objects.filter(event=event).values_list("contact_id", flat=True)),
            {current.pk},
        )

    def test_legacy_edit_post_without_participant_marker_keeps_links(self):
        event = self.create_event(self.user)
        contact = self.create_contact(self.user)
        EventContact.objects.create(event=event, contact=contact)

        response = self.client.post(
            reverse("event:edit_event", args=[event.pk]),
            self.valid_form_data(title="Legacy edit"),
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(EventContact.objects.filter(event=event, contact=contact).exists())

    def test_edit_and_lifecycle_views_are_owner_scoped(self):
        event = self.create_event(self.user)
        other = self.create_event(self.create_user("bob@example.com"), "Other")
        edit_data = self.valid_form_data(title="Changed", scheduled_date=event.scheduled_date.isoformat())
        response = self.client.post(reverse("event:edit_event", args=[event.pk]), edit_data)
        self.assertEqual(response.status_code, 302)
        event.refresh_from_db()
        self.assertEqual(event.title, "Changed")

        response = self.client.post(reverse("event:cancel_event", args=[other.pk]))
        self.assertEqual(response.status_code, 404)

    def test_terminating_event_keeps_it_visible_in_all_states_view(self):
        event = self.create_event(self.user)

        post_response = self.client.post(
            reverse("event:mark_event_occurred", args=[event.pk])
        )

        self.assertNotIn("state=scheduled", post_response.url)
        self.assertIn(f"selected={event.pk}", post_response.url)

        response = self.client.get(post_response.url)
        event.refresh_from_db()

        self.assertEqual(event.state, Event.State.OCCURRED)
        self.assertEqual(response.context["selected_event"], event)

    def test_add_and_remove_participants(self):
        event = self.create_event(self.user)
        contact = self.create_contact(self.user)
        add_url = reverse("event:add_event_contacts_to_event", args=[event.pk])
        response = self.client.post(add_url, {"contacts": [contact.pk]})
        self.assertEqual(response.status_code, 302)
        link = EventContact.objects.get(event=event, contact=contact)

        remove_url = reverse(
            "event:delete_event_contact_from_event", args=[event.pk, link.pk]
        )
        response = self.client.post(remove_url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(EventContact.objects.filter(pk=link.pk).exists())

    def test_remove_rejects_link_belonging_to_another_event(self):
        event = self.create_event(self.user, "Target")
        other_event = self.create_event(self.user, "Other")
        contact = self.create_contact(self.user)
        link = EventContact.objects.create(event=other_event, contact=contact)

        response = self.client.post(reverse(
            "event:delete_event_contact_from_event",
            args=[event.pk, link.pk],
        ))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(EventContact.objects.filter(pk=link.pk).exists())

    def test_terminal_event_hides_participant_mutations(self):
        event = self.create_event(self.user, state=Event.State.CANCELLED)
        contact = self.create_contact(self.user)
        method = ContactMethod.objects.create(
            contact=contact,
            type=ContactMethod.Type.EMAIL,
            value="alex@example.com",
        )
        hidden_method = ContactMethod.objects.create(
            contact=contact,
            type=ContactMethod.Type.EMAIL,
            value="other@example.com",
        )
        telephone = ContactMethod.objects.create(
            contact=contact,
            type=ContactMethod.Type.TELEPHONE,
            value="+447700900321",
        )
        EventContact.objects.create(event=event, contact=contact)

        response = self.client.get(reverse("event:events"), {
            "state": "all",
            "selected": event.pk,
            "tab": "details",
        })

        self.assertContains(response, contact.first_name)
        self.assertContains(response, method.value)
        self.assertContains(response, telephone.value)
        self.assertNotContains(response, hidden_method.value)
        self.assertContains(response, 'class="event-participant-row"')
        self.assertNotContains(response, "Add participants")
        self.assertNotContains(
            response,
            reverse(
                "event:delete_event_contact_from_event",
                args=[event.pk, event.event_contacts.get().pk],
            ),
        )

    def test_add_participants_modal_has_one_short_instruction(self):
        event = self.create_event(self.user, title="Pest-control follow-up")
        response = self.client.get(reverse("event:events"), {"selected": event.pk})
        self.assertContains(response, "Select one or more contacts to add to the event.")
        self.assertNotContains(response, "Choose from active contacts. You can update this later.")
        self.assertNotContains(response, "Select one or more active contacts to add to")

    def test_participant_views_reject_other_users_objects_and_terminated_events(self):
        event = self.create_event(self.user)
        other_contact = self.create_contact(
            self.create_user("bob@example.com"), "Other"
        )
        post_response = self.client.post(
            reverse("event:add_event_contacts_to_event", args=[event.pk]),
            {"contacts": [other_contact.pk]},
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn(f"selected={event.pk}", post_response.url)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["open_modal"], "addEventContactsModal")
        self.assertIn("contacts", response.context["add_contacts_form"].errors)
        self.assertFalse(EventContact.objects.filter(event=event).exists())

        event.state = Event.State.OCCURRED
        event.save(update_fields=["state"])
        response = self.client.post(
            reverse("event:add_event_contacts_to_event", args=[event.pk]),
            {"contacts": []},
        )
        self.assertEqual(response.status_code, 404)

    def test_deleted_events_are_not_accessible_to_mutation_views(self):
        event = self.create_event(self.user, deleted_at=timezone.now())
        response = self.client.post(reverse("event:reactivate_event", args=[event.pk]))
        self.assertEqual(response.status_code, 404)
