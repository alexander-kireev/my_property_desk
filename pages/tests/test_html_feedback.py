"""Check form accessibility contracts without writing records or sending account emails."""

from html.parser import HTMLParser
from unittest.mock import patch

from django.forms.utils import ErrorDict
from django.template.loader import render_to_string
from django.test import SimpleTestCase

from accounts.forms import AccountPasswordChangeForm, DeleteAccountForm, EmailChangeForm
from accounts.models import User
from contact.forms import ContactCreateForm, ContactMethodForm
from event.forms import EventForm
from issue.forms import IssueForm
from issue.models import Issue
from property.forms import PropertyForm
from property.models import Property
from task.forms import TaskForm


class FormMarkup(HTMLParser):
    def __init__(self, markup):
        super().__init__()
        self.elements = []
        self.feed(markup)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class HtmlFeedbackTests(SimpleTestCase):
    def assert_references_resolve(self, markup):
        elements = FormMarkup(markup).elements
        ids = [attrs["id"] for _, attrs in elements if attrs.get("id")]
        self.assertEqual(len(ids), len(set(ids)), "Duplicate IDs in rendered form")
        for _, attrs in elements:
            for reference in attrs.get("aria-describedby", "").split():
                self.assertIn(reference, ids)

    def test_profile_password_labels_have_distinct_ids_for_bound_and_unbound_forms(self):
        for data in (None, {}):
            forms = [EmailChangeForm(user=None, data=data), DeleteAccountForm(user=None, data=data)]
            self.assertNotEqual(
                forms[0]["current_password"].id_for_label, forms[1]["current_password"].id_for_label
            )
            self.assertTrue(
                all(form["current_password"].html_name == "current_password" for form in forms)
            )

    def test_contact_error_is_described_by_its_actual_message(self):
        form = ContactCreateForm(data={"email": "invalid"}, auto_id="add_contact_%s")
        self.assertFalse(form.is_valid())
        markup = render_to_string(
            "contact/includes/contact_form_fields.html", {"contact_form": form}
        )
        self.assertIn('id="add_contact_email_error"', markup)
        self.assert_references_resolve(markup)

    def test_password_guidance_references_exist(self):
        form = AccountPasswordChangeForm(user=User())
        markup = render_to_string(
            "accounts/includes/modals/change_password_modal.html", {"password_form": form}
        )
        self.assert_references_resolve(markup)
        self.assertIn('id="id_new_password1_helptext"', markup)
        self.assertIn('id="id_new_password2_helptext"', markup)

    def test_work_form_partials_render_feedback_for_every_field(self):
        # Empty relation querysets isolate markup from owner data and database state.
        with (
            patch.object(Property.objects, "filter", return_value=Property.objects.none()),
            patch.object(Issue.objects, "filter", return_value=Issue.objects.none()),
        ):
            cases = [
                (TaskForm(user=None), "task/includes/task_form_fields.html", "task_form"),
                (IssueForm(user=None), "issue/includes/issue_form_fields.html", "issue_form"),
                (EventForm(user=None), "event/includes/event_form_fields.html", "event_form"),
                (PropertyForm(user=None), "property/includes/property_form_fields.html", "form"),
            ]
        for form, template, context_name in cases:
            with self.subTest(template=template):
                # Inject server errors without exercising unrelated model validation.
                form._errors = ErrorDict()
                form.cleaned_data = {}
                for name in form.fields:
                    form.add_error(name, "Example validation message")
                markup = render_to_string(template, {context_name: form})
                self.assert_references_resolve(markup)
                for name in form.fields:
                    self.assertIn(f'id="{form[name].auto_id}_error"', markup)

    def test_contact_method_type_keeps_native_required_validation(self):
        field = ContactMethodForm()["type"]
        self.assertIn("data-native-select", str(field))
        self.assertIn("required", str(field))
