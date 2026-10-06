"""Contact form behaviour."""

from django.test import TestCase

from ..forms import ContactCreateForm, ContactForm, ContactMethodForm
from ..models import ContactMethod
from .support import ContactTestMixin


class ContactFormTests(ContactTestMixin, TestCase):
    def test_contact_form_only_exposes_name_fields(self):
        form = ContactForm()

        self.assertEqual(list(form.fields), ["first_name", "last_name"])

    def test_create_and_edit_forms_apply_browser_name_length_limits(self):
        contact = self.create_contact(self.create_user())
        edit_form = ContactForm(instance=contact)
        create_form = ContactCreateForm()

        for name in ("first_name", "last_name"):
            with self.subTest(name=name):
                self.assertEqual(edit_form.fields[name].widget.attrs["maxlength"], "50")
                self.assertEqual(
                    create_form.fields[name].widget.attrs["maxlength"],
                    "50",
                )

    def test_overlong_names_receive_field_specific_errors(self):
        form = ContactForm(data={"first_name": "A" * 51, "last_name": "B" * 52})

        self.assertFalse(form.is_valid())
        self.assertEqual(
            list(form.errors["first_name"]),
            ["First name must be 50 characters or fewer. You entered 51."],
        )
        self.assertEqual(
            list(form.errors["last_name"]),
            ["Last name must be 50 characters or fewer. You entered 52."],
        )

    def test_contact_method_form_uses_clear_choices_and_value_label(self):
        form = ContactMethodForm()

        self.assertEqual(form.fields["type"].label, "Contact method")
        self.assertEqual(form.fields["value"].label, "Contact information")
        self.assertEqual(form.fields["type"].choices[0], ("", "Choose email or telephone"))

    def test_create_form_uses_the_same_friendly_name_error(self):
        form = ContactCreateForm(data={"first_name": "A" * 51})

        self.assertFalse(form.is_valid())
        self.assertEqual(
            list(form.errors["first_name"]),
            ["First name must be 50 characters or fewer. You entered 51."],
        )

    def test_create_form_accepts_optional_initial_methods(self):
        form = ContactCreateForm(
            data={
                "first_name": "Alice",
                "last_name": "Smith",
                "email": "alice@example.com",
                "telephone": "+447700900123",
            }
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_create_form_allows_contact_without_methods(self):
        form = ContactCreateForm(data={"first_name": "Alice"})

        self.assertTrue(form.is_valid(), form.errors)

    def test_create_form_rejects_invalid_initial_methods(self):
        form = ContactCreateForm(
            data={
                "first_name": "Alice",
                "email": "invalid",
                "telephone": "07700 900123",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)
        self.assertIn("telephone", form.errors)

    def test_contact_method_form_applies_type_specific_validation(self):
        email_form = ContactMethodForm(data={"type": ContactMethod.Type.EMAIL, "value": "invalid"})
        phone_form = ContactMethodForm(
            data={"type": ContactMethod.Type.TELEPHONE, "value": "+441234567890"}
        )

        self.assertFalse(email_form.is_valid())
        self.assertIn("value", email_form.errors)
        self.assertTrue(phone_form.is_valid(), phone_form.errors)

    def test_contact_method_form_rejects_duplicate_for_same_contact(self):
        contact = self.create_contact(self.create_user())
        self.create_method(contact, value="alice@example.com")

        form = ContactMethodForm(
            data={
                "type": ContactMethod.Type.EMAIL,
                "value": "ALICE@example.com",
            },
            contact=contact,
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(
            list(form.errors["value"]),
            ["This email address is already saved for this contact."],
        )

    def test_contact_method_form_shows_only_duplicate_telephone_error(self):
        contact = self.create_contact(self.create_user())
        self.create_method(
            contact,
            type=ContactMethod.Type.TELEPHONE,
            value="+447700900123",
        )

        form = ContactMethodForm(
            data={"type": ContactMethod.Type.TELEPHONE, "value": "+447700900123"},
            contact=contact,
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(
            list(form.errors["value"]),
            ["This telephone number is already saved for this contact."],
        )

    def test_contact_method_form_prioritises_format_over_duplicate(self):
        contact = self.create_contact(self.create_user())
        self.create_method(
            contact,
            type=ContactMethod.Type.TELEPHONE,
            value="+447700900123",
        )

        form = ContactMethodForm(
            data={"type": ContactMethod.Type.EMAIL, "value": "+447700900123"},
            contact=contact,
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(list(form.errors["value"]), ["Enter a valid email address."])

    def test_changing_email_to_invalid_phone_shows_one_format_error(self):
        contact = self.create_contact(self.create_user())
        method = self.create_method(contact)
        form = ContactMethodForm(
            data={"type": ContactMethod.Type.TELEPHONE, "value": "alice@example.com"},
            contact=contact,
            instance=method,
        )

        self.assertFalse(form.is_valid())
        self.assertEqual(
            list(form.errors["value"]),
            ["Enter an international number, for example +447700900123."],
        )
