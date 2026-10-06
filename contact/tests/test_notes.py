"""Contact notes behaviour."""

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from note.models import Note

from .support import ContactViewFixture


class ContactViewNotesTests(ContactViewFixture, TestCase):
    def test_add_edit_and_delete_contact_note_works_and_redirects_back_to_selected_contacts_notes_tab(
        self,
    ):
        contact = self.create_contact(self.user)

        expected_url = f"{reverse('contact:contacts')}?selected={contact.pk}&tab=notes"

        add_response = self.client.post(
            reverse("contact:add_contact_note", args=[contact.pk]), {"content": "note"}
        )
        note = contact.notes.get()
        self.assertRedirects(add_response, expected_url)

        edit_content = "edit"
        edit_response = self.client.post(
            reverse("contact:edit_contact_note", args=[contact.pk, note.pk]),
            {"content": edit_content},
        )
        note.refresh_from_db()
        self.assertRedirects(edit_response, expected_url)
        self.assertEqual(note.content, edit_content)

        delete_response = self.client.post(
            reverse(
                "contact:delete_contact_note",
                args=[contact.pk, note.pk],
            )
        )
        self.assertRedirects(delete_response, expected_url)
        self.assertFalse(Note.objects.filter(pk=note.pk).exists())

    def test_contact_note_delete_offers_undo_and_restores_note(self):
        contact = self.create_contact(self.user)
        note = self.create_note(self.user, contact)
        original_time = note.created_at
        deleted = self.client.post(
            reverse("contact:delete_contact_note", args=[contact.pk, note.pk]), follow=True
        )
        self.assertContains(deleted, "data-note-undo-toast")
        token = deleted.context["note_undo_token"]
        undone = self.client.post(
            reverse("contact:undo_contact_note", args=[contact.pk]), {"token": token}
        )
        self.assertEqual(undone.status_code, 200)
        note.refresh_from_db()
        self.assertEqual(note.created_at, original_time)
        self.assertEqual(
            self.client.post(
                reverse("contact:undo_contact_note", args=[contact.pk]), {"token": token}
            ).status_code,
            409,
        )

    def test_note_from_different_owned_contact_cannot_be_mutated(self):
        contact = self.create_contact(self.user)
        other_contact = self.create_contact(self.user, "Other")
        note = self.create_note(self.user, other_contact)

        for route in ("edit_contact_note", "delete_contact_note"):
            with self.subTest(route=route):
                response = self.client.post(reverse(f"contact:{route}", args=[contact.pk, note.pk]))
                self.assertEqual(response.status_code, 404)

    def test_invalid_add_note_form_returns_errors(self):
        contact = self.create_contact(self.user)

        post_response = self.client.post(
            reverse("contact:add_contact_note", args=[contact.pk]),
            {"content": ""},
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn(f"selected={contact.pk}", post_response.url)
        self.assertIn("tab=notes", post_response.url)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_tab"], "notes")
        self.assertEqual(response.context["selected_contact"], contact)
        form = response.context["add_contact_note_form"]
        self.assertEqual(form["content"].value(), "")
        self.assertIn(
            "content",
            response.context["add_contact_note_form"].errors,
        )
        self.assertEqual(Note.objects.filter(user=self.user).count(), 0)

    def test_invalid_edit_note_form_returns_errors(self):
        contact = self.create_contact(self.user)
        note = self.create_note(self.user, contact)
        original_content = note.content

        post_response = self.client.post(
            reverse("contact:edit_contact_note", args=[contact.pk, note.pk]),
            {"content": ""},
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn(reverse("contact:contacts"), post_response.url)
        self.assertIn(f"selected={contact.pk}", post_response.url)
        self.assertIn("tab=notes", post_response.url)
        self.assertIn("form_state=", post_response.url)
        self.assertNotIn("content", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["active_tab"], "notes")
        self.assertEqual(response.context["selected_contact"], contact)
        self.assertEqual(response.context["edit_contact_note"], note)
        form = response.context["edit_contact_note_form"]
        note.refresh_from_db()

        self.assertEqual(note.content, original_content)
        self.assertEqual(form["content"].value(), "")
        self.assertIn("content", form.errors)

        refreshed_response = self.client.get(post_response.url)
        self.assertIsNone(refreshed_response.context["edit_contact_note_form"])

    def test_contacts_notes_tab_renders_owned_notes_in_correct_order(self):
        contact = self.create_contact(self.user)
        data = [["newest", 0], ["middle", 1], ["oldest", 2]]

        for content, days in data:
            note = self.create_note(self.user, contact, content)
            note.created_at = timezone.now() - timedelta(days=days)
            note.save(update_fields=["created_at"])

        response = self.client.get(reverse("contact:contacts"), {"tab": "notes"})
        self.assertEqual(response.status_code, 200)
        notes = response.context["notes"]

        for i, note in enumerate(notes):
            self.assertEqual(note.content, data[i][0])

    def test_contacts_notes_tab_is_contact_and_user_scoped(self):
        contact1 = self.create_contact(self.user)
        contact2 = self.create_contact(self.user)
        note1 = self.create_note(self.user, contact1)
        self.create_note(self.user, contact2)
        self.create_note(self.other_user, self.create_contact(self.other_user))

        response = self.client.get(
            reverse("contact:contacts"), {"tab": "notes", "selected": contact1.pk}
        )
        self.assertEqual(list(response.context["notes"]), [note1])
