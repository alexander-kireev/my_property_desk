"""Contact actions behaviour."""

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ..models import Contact
from .support import ContactViewFixture


class ContactViewActionsTests(ContactViewFixture, TestCase):
    def test_invalid_contact_query_values_canonicalize_once(self):
        for number in range(21):
            self.create_contact(self.user, f"Contact {number:02}")

        cases = (
            ({"state": "bogus"}, "/contacts/"),
            ({"sort": "bogus"}, "/contacts/"),
            ({"tab": "bogus"}, "/contacts/"),
            ({"selected": "abc"}, "/contacts/"),
            ({"page": "bogus"}, "/contacts/"),
            ({"page": "999999"}, "/contacts/?page=2"),
            (
                {
                    "state": "bogus",
                    "sort": "bogus",
                    "tab": "bogus",
                    "page": "999999",
                    "selected": "abc",
                },
                "/contacts/?page=2",
            ),
        )
        for query, expected in cases:
            with self.subTest(query=query):
                response = self.client.get(reverse("contact:contacts"), query, follow=True)
                self.assertEqual(response.redirect_chain, [(expected, 302)])
                self.assertEqual(response.status_code, 200)

    def test_invalid_query_redirect_preserves_form_state_until_render(self):
        post_response = self.client.post(
            reverse("contact:add_contact"),
            {"first_name": "Alice", "email": "invalid"},
        )
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(f"{post_response.url}&sort=bogus", follow=True)

        self.assertEqual(len(response.redirect_chain), 1)
        self.assertEqual(response.context["open_modal"], "addContactModal")
        self.assertIn("email", response.context["add_contact_form"].errors)

    def test_add_contact_clears_stale_search_and_page(self):
        response = self.client.post(
            f"{reverse('contact:add_contact')}?search=unrelated&page=3",
            {"first_name": "Alice", "last_name": "Smith"},
        )
        contact = Contact.objects.get(first_name="Alice")
        self.assertEqual(response.url, f"{reverse('contact:contacts')}?selected={contact.pk}")

    def test_invalid_add_contact_reopens_modal_without_partial_creation(self):
        post_response = self.client.post(
            reverse("contact:add_contact"),
            {"first_name": "Alice", "email": "invalid"},
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["open_modal"], "addContactModal")
        self.assertIn("email", response.context["add_contact_form"].errors)
        self.assertFalse(Contact.objects.exists())

    def test_edit_contact_updates_active_owned_contact(self):
        contact = self.create_contact(self.user)

        response = self.client.post(
            reverse("contact:edit_contact", args=[contact.pk]),
            {"first_name": "Alicia", "last_name": "Jones"},
        )
        contact.refresh_from_db()

        self.assertEqual(str(contact), "Alicia Jones")
        self.assertRedirects(
            response,
            f"{reverse('contact:contacts')}?selected={contact.pk}",
        )

    def test_invalid_edit_contact_redirects_and_restores_bound_form_once(self):
        contact = self.create_contact(self.user, last_name="Smith")

        post_response = self.client.post(
            reverse("contact:edit_contact", args=[contact.pk]),
            {"first_name": "", "last_name": "Changed"},
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn(reverse("contact:contacts"), post_response.url)
        self.assertIn(f"selected={contact.pk}", post_response.url)
        self.assertIn("form_state=", post_response.url)
        self.assertNotIn("first_name", post_response.url)

        response = self.client.get(post_response.url)
        form = response.context["edit_contact_form"]
        contact.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_contact"], contact)
        self.assertEqual(response.context["active_tab"], "details")
        self.assertEqual(response.context["open_modal"], "editContactModal")
        self.assertTrue(form.is_bound)
        self.assertEqual(form["first_name"].value(), "")
        self.assertEqual(form["last_name"].value(), "Changed")
        self.assertIn("first_name", form.errors)
        self.assertEqual(contact.first_name, "Alice")
        self.assertEqual(contact.last_name, "Smith")

        refreshed_response = self.client.get(post_response.url)
        self.assertFalse(refreshed_response.context["edit_contact_form"].is_bound)
        self.assertIsNone(refreshed_response.context["open_modal"])

    def test_overlong_edit_contact_name_is_rejected_with_visible_error(self):
        contact = self.create_contact(self.user)
        overlong_name = "a" * 151

        post_response = self.client.post(
            reverse("contact:edit_contact", args=[contact.pk]),
            {"first_name": overlong_name, "last_name": ""},
        )
        response = self.client.get(post_response.url)
        contact.refresh_from_db()

        self.assertEqual(post_response.status_code, 302)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["edit_contact_form"]["first_name"].value(),
            overlong_name,
        )
        self.assertIn("first_name", response.context["edit_contact_form"].errors)
        self.assertEqual(contact.first_name, "Alice")

    def test_lifecycle_views_change_state_and_soft_delete(self):
        contact = self.create_contact(self.user)

        self.client.post(reverse("contact:deactivate_contact", args=[contact.pk]))
        contact.refresh_from_db()
        self.assertEqual(contact.state, Contact.State.DEACTIVATED)

        self.client.post(reverse("contact:reactivate_contact", args=[contact.pk]))
        contact.refresh_from_db()
        self.assertEqual(contact.state, Contact.State.ACTIVE)

        self.client.post(reverse("contact:delete_contact", args=[contact.pk]))
        contact.refresh_from_db()
        self.assertIsNotNone(contact.deleted_at)
        self.assertTrue(Contact.objects.filter(pk=contact.pk).exists())

    def test_soft_deleted_contact_is_not_selectable_or_mutable(self):
        contact = self.create_contact(
            self.user,
            deleted_at=timezone.now(),
        )

        list_response = self.client.get(
            reverse("contact:contacts"),
            {"selected": contact.pk},
        )
        edit_response = self.client.post(
            reverse("contact:edit_contact", args=[contact.pk]),
            {"first_name": "Changed"},
        )

        self.assertEqual(list_response.status_code, 302)
        self.assertNotIn("selected=", list_response.url)
        self.assertIsNone(self.client.get(list_response.url).context["selected_contact"])
        self.assertEqual(edit_response.status_code, 404)
