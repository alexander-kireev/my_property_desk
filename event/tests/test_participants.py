"""Event participants behaviour."""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from contact.models import Contact, ContactMethod

from ..models import Event, EventContact
from .support import EventViewFixture


class EventViewParticipantsTests(EventViewFixture, TestCase):
    def test_participant_rows_keep_full_email_in_native_title(self):
        event = self.create_event(self.user)
        contact = self.create_contact(self.user, first_name="A" * 50, last_name="B" * 50)
        email = "abcdefghijklmnopqrstuvwx@example-domain.com"
        ContactMethod.objects.create(contact=contact, type=ContactMethod.Type.EMAIL, value=email)
        ContactMethod.objects.create(
            contact=contact,
            type=ContactMethod.Type.TELEPHONE,
            value="+447700900321",
        )
        EventContact.objects.create(event=event, contact=contact)

        response = self.client.get(reverse("event:events"), {"selected": event.pk})

        self.assertContains(response, f'data-email-preview="{email}"')
        self.assertContains(response, f'title="{email}"')
        self.assertNotContains(response, "Show full email")
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
        self.assertContains(
            response,
            '<span class="event-participant-phone" title="+447700900321">+447700900321</span>',
            count=2,
            html=True,
        )

    def test_participant_without_contact_methods_has_only_one_detail_cell(self):
        event = self.create_event(self.user)
        contact = self.create_contact(self.user)
        EventContact.objects.create(event=event, contact=contact)

        response = self.client.get(reverse("event:events"), {"selected": event.pk})

        self.assertContains(
            response,
            '<span class="event-participant-no-methods">No contact details</span>',
            count=2,
        )
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

        self.assertContains(
            response, '<span class="event-participant-status">Deleted contact</span>', count=2
        )
        self.assertContains(
            response,
            '<span class="event-participant-status" title="Deactivated contact">Inactive</span>',
            count=2,
        )
        self.assertNotContains(
            response, '<span class="badge text-bg-secondary">Deleted contact</span>'
        )

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
        self.assertContains(response, "data-duration-choice")
        self.assertContains(response, 'value="all_day"')
        self.assertContains(response, 'value="timed"')
        self.assertContains(response, "Use 24-hour time (HH:MM), for example 09:30.")
        self.assertContains(response, "Requires participation.")
        self.assertContains(response, "data-contact-option")
        self.assertContains(response, "leila@example.com")
        self.assertContains(response, 'data-search-text="Leila Davies leila@example.com')
        self.assertContains(response, 'name="contacts"')
        self.assertContains(response, "data-searchable-select")
        self.assertContains(response, "js/searchable-select.js")

    def test_participant_name_links_to_active_or_deactivated_contact(self):
        event = self.create_event(self.user)
        active = self.create_contact(self.user, first_name="Active")
        inactive = self.create_contact(
            self.user,
            first_name="Inactive",
            state=Contact.State.DEACTIVATED,
        )
        EventContact.objects.create(event=event, contact=active)
        EventContact.objects.create(event=event, contact=inactive)

        response = self.client.get(
            reverse("event:events"),
            {
                "selected": event.pk,
                "tab": "details",
            },
        )

        self.assertContains(
            response,
            f"{reverse('contact:contacts')}?selected={active.pk}",
        )
        self.assertContains(
            response,
            f"{reverse('contact:contacts')}?state=all&amp;selected={inactive.pk}",
        )

    def test_create_event_with_initial_contacts(self):
        contact = self.create_contact(self.user)
        response = self.client.post(
            reverse("event:add_event"), self.valid_form_data(contacts=[contact.pk])
        )

        event = Event.objects.get(title="Inspection")
        self.assertRedirects(response, f"{reverse('event:events')}?selected={event.pk}")
        self.assertTrue(EventContact.objects.filter(event=event, contact=contact).exists())

    def test_invalid_initial_contact_creates_no_event(self):
        other_contact = self.create_contact(self.create_user("bob@example.com"), "Other")
        post_response = self.client.post(
            reverse("event:add_event"), self.valid_form_data(contacts=[other_contact.pk])
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["open_modal"], "addEventModal")
        self.assertIn("contacts", response.context["initial_contacts_form"].errors)
        self.assertFalse(Event.objects.exists())

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
        self.assertRegex(
            restored.content.decode(),
            r'id="editEventParticipantsPanel"\s+role="tabpanel"\s+aria-labelledby="editEventParticipantsTab"\s+data-event-panel="participants"\s*>',
        )

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

    def test_add_and_remove_participants(self):
        event = self.create_event(self.user)
        contact = self.create_contact(self.user)
        add_url = reverse("event:add_event_contacts_to_event", args=[event.pk])
        response = self.client.post(add_url, {"contacts": [contact.pk]})
        self.assertEqual(response.status_code, 302)
        link = EventContact.objects.get(event=event, contact=contact)

        remove_url = reverse("event:delete_event_contact_from_event", args=[event.pk, link.pk])
        response = self.client.post(remove_url)
        self.assertEqual(response.status_code, 302)
        self.assertFalse(EventContact.objects.filter(pk=link.pk).exists())

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

        response = self.client.get(
            reverse("event:events"),
            {
                "state": "all",
                "selected": event.pk,
                "tab": "details",
            },
        )

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
        other_contact = self.create_contact(self.create_user("bob@example.com"), "Other")
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


class ParticipantOriginTests(EventViewFixture, TestCase):
    def test_add_and_invalid_retry_preserve_calendar_agenda_origin(self):
        from urllib.parse import parse_qs, urlencode, urlsplit

        event = self.create_event(self.user)
        contact = self.create_contact(self.user)
        origin = {
            "view": "calendar",
            "tab": "calendar",
            "agenda_day": "2026-10-06",
            "month": "10",
            "year": "2026",
            "search": "Inspection",
        }
        endpoint = reverse("event:add_event_contacts_to_event", args=[event.pk])
        response = self.client.post(f"{endpoint}?{urlencode(origin)}", {"contacts": [contact.pk]})
        result = parse_qs(urlsplit(response.url).query)
        for key, value in origin.items():
            self.assertEqual(result[key], [value])
        self.assertEqual(result["selected"], [str(event.pk)])
        self.assertEqual(result["focus"], ["participants"])

        invalid = self.client.post(f"{endpoint}?{urlencode(origin)}", {"contacts": [999999]})
        retry = parse_qs(urlsplit(invalid.url).query)
        for key in ("view", "tab", "agenda_day"):
            self.assertEqual(retry[key], [origin[key]])
        page = self.client.get(invalid.url)
        self.assertEqual(page.context["open_modal"], "addEventContactsModal")
        self.assertTrue(page.context["mobile_calendar_view"])
        self.assertEqual(page.context["active_tab"], "calendar")

    def test_list_origin_stays_list_and_untrusted_origin_is_not_reflected(self):
        from urllib.parse import parse_qs, urlsplit

        event = self.create_event(self.user)
        contact = self.create_contact(self.user)
        endpoint = reverse("event:add_event_contacts_to_event", args=[event.pk])
        response = self.client.post(
            endpoint + "?view=other&tab=other&agenda_day=bad&next=https://example.com",
            {"contacts": [contact.pk]},
        )
        result = parse_qs(urlsplit(response.url).query)
        for key in ("view", "tab", "agenda_day", "next"):
            self.assertNotIn(key, result)
        self.assertEqual(result["selected"], [str(event.pk)])

    def test_explicit_detail_origin_remains_explicit_after_add(self):
        event = self.create_event(self.user)
        contact = self.create_contact(self.user)
        endpoint = reverse("event:add_event_contacts_to_event", args=[event.pk])
        response = self.client.post(endpoint + "?open=detail", {"contacts": [contact.pk]})
        self.assertIn("open=detail", response.url)
