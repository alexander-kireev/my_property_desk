"""Contact methods behaviour."""

from django.test import TestCase
from django.urls import reverse

from ..models import Contact, ContactMethod
from .support import ContactViewFixture


class ContactViewMethodsTests(ContactViewFixture, TestCase):
    def test_contacts_view_renders_owned_contacts_and_methods(self):
        contact = self.create_contact(self.user)
        method = self.create_method(contact)
        other_contact = self.create_contact(self.other_user, "Bob")

        response = self.client.get(reverse("contact:contacts"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, str(contact))
        self.assertContains(response, method.value)
        self.assertNotContains(response, str(other_contact))
        self.assertEqual(response.context["selected_contact"], contact)

    def test_contact_details_group_email_and_telephone_methods(self):
        contact = self.create_contact(self.user)
        email = self.create_method(contact, value="alice@example.com")
        telephone = self.create_method(
            contact,
            type=ContactMethod.Type.TELEPHONE,
            value="+447700900123",
        )

        response = self.client.get(reverse("contact:contacts"))

        self.assertEqual(response.context["email_methods"], [email])
        self.assertEqual(response.context["telephone_methods"], [telephone])
        self.assertContains(response, 'id="contact-emails-heading"')
        self.assertContains(response, 'id="contact-telephones-heading"')
        self.assertContains(response, 'class="contact-method-list"', count=2)
        self.assertContains(response, 'aria-label="Edit email alice@example.com"')
        self.assertContains(response, 'aria-label="Delete telephone +447700900123"')
        details_html = response.content.decode().split('id="contact-telephones-heading"', 1)[1]
        telephone_html, email_html = details_html.split('id="contact-emails-heading"', 1)
        self.assertIn("+447700900123", telephone_html)
        self.assertNotIn("alice@example.com", telephone_html)
        self.assertIn("alice@example.com", email_html)
        self.assertContains(response, 'class="contact-method-group card"', count=2)
        self.assertContains(response, 'id="contact-methods-heading">Contact methods</h3>')

    def test_long_email_is_plain_text_with_full_value_available(self):
        contact = self.create_contact(self.user)
        email = f"contact72{'2' * 90}@example.com"
        self.create_method(contact, value=email)

        response = self.client.get(reverse("contact:contacts"))

        self.assertContains(response, "contact-method-value--email")
        self.assertContains(response, f'data-email-preview="{email}"')
        self.assertContains(response, f'<span class="visually-hidden">{email}</span>', html=True)
        self.assertNotContains(response, "Show full email")
        self.assertContains(response, f'title="{email}"')
        self.assertNotContains(response, 'href="mailto:')
        self.assertNotContains(response, 'href="tel:')
        self.assertNotContains(response, "Tap a number to call")
        self.assertNotContains(response, "Tap an address to compose")

    def test_contact_list_shows_first_phone_and_email_without_remaining_count(self):
        contact = self.create_contact(self.user)
        for value in ("first@example.com", "second@example.com"):
            self.create_method(contact, value=value)
        for value in ("+447700900001", "+447700900002"):
            self.create_method(
                contact,
                type=ContactMethod.Type.TELEPHONE,
                value=value,
            )

        response = self.client.get(reverse("contact:contacts"))
        list_html = response.content.decode().split('class="contact-command-list', 1)[1]
        list_html = list_html.split('class="contact-detail-column', 1)[0]

        self.assertIn("first@example.com", list_html)
        self.assertIn("+447700900001", list_html)
        self.assertLess(list_html.index("+447700900001"), list_html.index("first@example.com"))
        self.assertNotIn("+2 more", list_html)
        self.assertNotIn("second@example.com", list_html)
        self.assertNotIn("+447700900002", list_html)
        self.assertContains(response, "second@example.com")
        self.assertContains(response, "+447700900002")

    def test_contact_list_method_summary_handles_zero_one_and_one_of_each(self):
        self.create_contact(self.user, "Empty")
        email_only = self.create_contact(self.user, "Email")
        phone_only = self.create_contact(self.user, "Phone")
        both = self.create_contact(self.user, "Both")
        self.create_method(email_only, value="email@example.com")
        self.create_method(phone_only, type=ContactMethod.Type.TELEPHONE, value="+447700900099")
        self.create_method(both, value="both@example.com")
        self.create_method(both, type=ContactMethod.Type.TELEPHONE, value="+447700900088")

        response = self.client.get(reverse("contact:contacts"))

        self.assertContains(response, "No contact details")
        self.assertContains(response, "No phone number")
        self.assertContains(response, "No email")
        self.assertContains(response, "both@example.com")
        self.assertContains(response, "+447700900088")
        self.assertNotContains(response, "+0 more")

    def test_contact_list_keeps_full_email_for_width_fitted_preview(self):
        contact = self.create_contact(self.user, "Long methods")
        phone = "+447700900123456"
        email = "averylongcontactemailaddress@example.com"
        self.create_method(contact, type=ContactMethod.Type.TELEPHONE, value=phone)
        self.create_method(contact, value=email)

        response = self.client.get(reverse("contact:contacts"))
        list_html = response.content.decode().split('class="contact-command-list', 1)[1]
        list_html = list_html.split('class="contact-detail-column', 1)[0]

        self.assertIn(f'title="{phone}">{phone}</span>', list_html)
        self.assertIn(f'title="{email}"', list_html)
        self.assertIn(f'data-email-preview="{email}"', list_html)
        self.assertNotIn("contact-command-methods--long-email", list_html)
        self.assertIn(f">{email}</span>", list_html)

    def test_deactivated_contact_list_shows_state_and_primary_method(self):
        contact = self.create_contact(
            self.user,
            state=Contact.State.DEACTIVATED,
        )
        self.create_method(contact, value="alice@example.com")

        response = self.client.get(
            reverse("contact:contacts"),
            {"state": Contact.State.DEACTIVATED},
        )
        list_html = response.content.decode().split('class="contact-command-list', 1)[1]
        list_html = list_html.split('class="contact-detail-column', 1)[0]

        self.assertIn("Deactivated", list_html)
        self.assertIn("alice@example.com", list_html)
        self.assertIn('class="contact-command-heading workspace-compact-heading"', list_html)
        self.assertContains(response, "alice@example.com")
        self.assertNotContains(response, 'class="contact-method-actions"')

    def test_add_contact_creates_contact_and_initial_methods(self):
        response = self.client.post(
            reverse("contact:add_contact"),
            {
                "first_name": "Alice",
                "last_name": "Smith",
                "email": "alice@example.com",
                "telephone": "+447700900123",
            },
        )
        contact = Contact.objects.get(first_name="Alice")

        self.assertEqual(contact.user, self.user)
        self.assertEqual(contact.contact_methods.count(), 2)
        self.assertRedirects(
            response,
            f"{reverse('contact:contacts')}?selected={contact.pk}",
        )

    def test_add_edit_and_delete_contact_method(self):
        contact = self.create_contact(self.user)

        add_response = self.client.post(
            reverse("contact:add_contact_method", args=[contact.pk]),
            {"type": ContactMethod.Type.EMAIL, "value": "alice@example.com"},
        )
        method = contact.contact_methods.get()
        self.assertEqual(add_response.status_code, 302)

        edit_response = self.client.post(
            reverse(
                "contact:edit_contact_method",
                args=[contact.pk, method.pk],
            ),
            {
                "type": ContactMethod.Type.TELEPHONE,
                "value": "+447700900123",
            },
        )
        method.refresh_from_db()
        self.assertEqual(edit_response.status_code, 302)
        self.assertEqual(method.type, ContactMethod.Type.TELEPHONE)

        delete_response = self.client.post(
            reverse(
                "contact:delete_contact_method",
                args=[contact.pk, method.pk],
            )
        )
        self.assertEqual(delete_response.status_code, 302)
        self.assertFalse(ContactMethod.objects.filter(pk=method.pk).exists())

    def test_duplicate_contact_method_reopens_add_modal(self):
        contact = self.create_contact(self.user)
        self.create_method(contact, value="alice@example.com")

        post_response = self.client.post(
            reverse("contact:add_contact_method", args=[contact.pk]),
            {"type": ContactMethod.Type.EMAIL, "value": "ALICE@example.com"},
        )
        response = self.client.get(post_response.url)

        self.assertEqual(contact.contact_methods.count(), 1)
        self.assertEqual(response.context["open_modal"], "addContactMethodModal")
        self.assertIn("value", response.context["add_contact_method_form"].errors)

    def test_edit_method_query_opens_modal_with_method_form(self):
        contact = self.create_contact(self.user)
        method = self.create_method(contact)

        response = self.client.get(
            reverse("contact:contacts"),
            {"selected": contact.pk, "edit_method": method.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["selected_contact"], contact)
        self.assertEqual(response.context["edit_contact_method"], method)
        self.assertEqual(
            response.context["edit_contact_method_form"].instance,
            method,
        )
        self.assertEqual(response.context["open_modal"], "editContactMethodModal")
        self.assertContains(
            response,
            'data-modal-clear-query="edit_method form_state"',
        )
        self.assertContains(
            response,
            'data-modal-auto-open="editContactMethodModal"',
        )
        self.assertContains(response, "data-contact-method-form", count=2)
        self.assertContains(response, "contact-method-modal", count=2)
        self.assertContains(response, "js/contact-method-form.js")
        self.assertContains(response, "Choose email or telephone")
        self.assertContains(response, "Use international format beginning with +")

    def test_invalid_method_form_reopens_correct_modal(self):
        contact = self.create_contact(self.user)

        post_response = self.client.post(
            reverse("contact:add_contact_method", args=[contact.pk]),
            {"type": ContactMethod.Type.EMAIL, "value": "invalid"},
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn(f"selected={contact.pk}", post_response.url)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["open_modal"], "addContactMethodModal")
        self.assertIn(
            "value",
            response.context["add_contact_method_form"].errors,
        )

    def test_invalid_edit_method_form_reopens_correct_modal(self):
        contact = self.create_contact(self.user)
        method = self.create_method(contact)

        post_response = self.client.post(
            reverse(
                "contact:edit_contact_method",
                args=[contact.pk, method.pk],
            ),
            {"type": ContactMethod.Type.EMAIL, "value": "invalid"},
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn(f"selected={contact.pk}", post_response.url)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)
        form = response.context["edit_contact_method_form"]
        method.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["open_modal"], "editContactMethodModal")
        self.assertEqual(response.context["edit_contact_method"], method)
        self.assertEqual(form["value"].value(), "invalid")
        self.assertIn("value", form.errors)
        self.assertEqual(method.value, "alice@example.com")

    def test_cross_user_contact_and_method_mutations_return_404(self):
        contact = self.create_contact(self.other_user, "Bob")
        method = self.create_method(contact, value="bob@example.com")
        note = self.create_note(self.other_user, contact)
        contact_urls = (
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

        for url in contact_urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.post(url, {}).status_code, 404)

    def test_method_from_different_owned_contact_cannot_be_mutated(self):
        contact = self.create_contact(self.user)
        other_contact = self.create_contact(self.user, "Other")
        method = self.create_method(other_contact)

        for route in ("edit_contact_method", "delete_contact_method"):
            with self.subTest(route=route):
                response = self.client.post(
                    reverse(f"contact:{route}", args=[contact.pk, method.pk]),
                    {"type": ContactMethod.Type.EMAIL, "value": "new@example.com"},
                )
                self.assertEqual(response.status_code, 404)
