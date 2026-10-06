"""Contact workspace behaviour."""

import re

from django.test import TestCase
from django.urls import reverse

from ..models import Contact, ContactMethod
from .support import ContactViewFixture


class ContactViewWorkspaceTests(ContactViewFixture, TestCase):
    def test_contacts_view_requires_login(self):
        self.client.logout()

        response = self.client.get(reverse("contact:contacts"))

        self.assertRedirects(
            response,
            f"{reverse('accounts:login')}?next={reverse('contact:contacts')}",
        )

    def test_confirmation_dialogs_omit_redundant_record_boxes(self):
        long_name = "A" * 50
        contact = self.create_contact(self.user, first_name=long_name)
        long_email = f"contact{'2' * 85}@example.com"
        self.create_method(contact, value=long_email)

        response = self.client.get(reverse("contact:contacts"))

        self.assertContains(response, 'id="editContactModalLabel">Edit contact</h2>')
        self.assertContains(response, 'id="deleteContactModalLabel">Delete contact?</h2>')
        self.assertNotContains(response, 'class="modal-context')
        self.assertContains(response, long_name)
        self.assertContains(response, long_email)
        self.assertContains(response, 'class="btn btn-danger" type="submit">Delete contact')
        self.assertContains(response, 'class="btn btn-danger" type="submit">Delete detail')

    def test_mobile_back_link_keeps_contact_list_page(self):
        for index in range(21):
            self.create_contact(self.user, f"Contact {index:02d}")

        response = self.client.get(
            reverse("contact:contacts"),
            {"page": 2, "selected": Contact.objects.order_by("pk").last().pk},
        )

        self.assertRegex(
            response.content.decode(),
            re.escape(
                'class="workspace-mobile-back btn btn-sm pom-quiet mb-3" href="/contacts/?page=2"'
            ).replace(r"\ ", r"\s+"),
        )
        self.assertContains(response, "js/workspace-list-scroll.js")
        self.assertContains(response, 'data-workspace-scroll-root="contacts"')

    def test_contact_list_defaults_to_all_and_can_filter_by_state(self):
        active = self.create_contact(self.user, "Active")
        deactivated = self.create_contact(
            self.user,
            "Deactivated",
            state=Contact.State.DEACTIVATED,
        )

        for query, expected in (
            ({}, [active, deactivated]),
            ({"state": Contact.State.ACTIVE}, [active]),
            ({"state": Contact.State.DEACTIVATED}, [deactivated]),
            ({"state": "all"}, [active, deactivated]),
        ):
            with self.subTest(query=query):
                response = self.client.get(reverse("contact:contacts"), query)
                self.assertCountEqual(response.context["page_obj"].object_list, expected)

    def test_deactivated_only_contact_is_visible_by_default(self):
        deactivated = self.create_contact(self.user, state=Contact.State.DEACTIVATED)

        response = self.client.get(reverse("contact:contacts"))

        self.assertEqual(list(response.context["page_obj"].object_list), [deactivated])
        self.assertContains(response, 'value="all" selected')

    def test_contacts_view_paginates_twenty_at_a_time(self):
        for number in range(21):
            self.create_contact(self.user, f"Contact {number:02}")

        first_page = self.client.get(reverse("contact:contacts"))
        second_page = self.client.get(reverse("contact:contacts"), {"page": 2})

        self.assertEqual(len(first_page.context["page_obj"]), 20)
        self.assertEqual(len(second_page.context["page_obj"]), 1)
        self.assertContains(first_page, "Page 1 of 2")
        self.assertContains(second_page, "Page 2 of 2")
        self.assertContains(second_page, 'aria-disabled="true">Next →</span>')

    def test_contacts_view_normalises_list_parameters(self):
        self.create_contact(self.user)

        response = self.client.get(
            reverse("contact:contacts"),
            {"search": " Alice ", "state": "invalid", "sort": "invalid"},
            follow=True,
        )

        self.assertEqual(len(response.redirect_chain), 1)
        self.assertEqual(response.redirect_chain[0][0], "/contacts/?search=+Alice+")
        self.assertEqual(response.context["search"], "Alice")
        self.assertEqual(response.context["state"], "")
        self.assertEqual(response.context["sort"], "name")
        self.assertEqual(response.context["list_query"], "search=Alice")

    def test_contacts_view_normalises_workspace_tab(self):
        contact = self.create_contact(self.user)

        notes_response = self.client.get(
            reverse("contact:contacts"),
            {"selected": contact.pk, "tab": "notes"},
        )
        invalid_response = self.client.get(
            reverse("contact:contacts"),
            {"selected": contact.pk, "tab": "invalid"},
            follow=True,
        )

        self.assertEqual(notes_response.context["active_tab"], "notes")
        self.assertContains(notes_response, 'class="notes-board-shell"')
        self.assertEqual(len(invalid_response.redirect_chain), 1)
        self.assertEqual(invalid_response.redirect_chain[0][0], f"/contacts/?selected={contact.pk}")
        self.assertEqual(invalid_response.context["active_tab"], "details")

    def test_valid_contact_deep_link_is_not_redirected(self):
        for number in range(21):
            self.create_contact(self.user, f"Contact {number:02}")
        contact = Contact.objects.get(first_name="Contact 00")

        response = self.client.get(
            reverse("contact:contacts"),
            {"selected": contact.pk, "page": 2, "tab": "notes", "sort": "-name"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_contact"], contact)
        self.assertEqual(response.context["active_tab"], "notes")

    def test_deactivated_contact_is_read_only(self):
        contact = self.create_contact(
            self.user,
            state=Contact.State.DEACTIVATED,
        )

        self.assertEqual(
            self.client.post(
                reverse("contact:edit_contact", args=[contact.pk]),
                {"first_name": "Changed"},
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse("contact:add_contact_method", args=[contact.pk]),
                {"type": ContactMethod.Type.EMAIL, "value": "a@example.com"},
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                reverse("contact:add_contact_note", args=[contact.pk]),
            ).status_code,
            404,
        )

    def test_mutation_views_reject_get_requests(self):
        contact = self.create_contact(self.user)
        method = self.create_method(contact)
        note = self.create_note(self.user, contact)
        urls = (
            reverse("contact:add_contact"),
            reverse("contact:edit_contact", args=[contact.pk]),
            reverse("contact:deactivate_contact", args=[contact.pk]),
            reverse("contact:reactivate_contact", args=[contact.pk]),
            reverse("contact:delete_contact", args=[contact.pk]),
            reverse("contact:add_contact_method", args=[contact.pk]),
            reverse("contact:edit_contact_method", args=[contact.pk, method.pk]),
            reverse("contact:delete_contact_method", args=[contact.pk, method.pk]),
            reverse("contact:add_contact_note", args=[contact.pk]),
            reverse("contact:edit_contact_note", args=[contact.pk, note.pk]),
            reverse("contact:delete_contact_note", args=[contact.pk, note.pk]),
        )

        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)
