"""Public routes and contact delivery contracts."""

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, override_settings
from django.urls import reverse


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    PMS_CONTACT_EMAIL="feedback@example.test",
)
class PublicSiteTests(SimpleTestCase):
    def test_public_pages_and_account_entry_points_render(self):
        names = (
            "pages:home",
            "pages:features",
            "pages:faq",
            "pages:contact_us",
            "pages:coming_soon",
            "accounts:login",
            "accounts:register",
            "accounts:password_reset_request",
            "accounts:password_reset_sent",
            "accounts:password_reset_complete",
        )
        for name in names:
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, reverse("pages:features"))
                self.assertContains(response, reverse("accounts:register"))

    def test_anonymous_problem_report_attaches_screenshot(self):
        screenshot = SimpleUploadedFile(
            "example.png", b"\x89PNG\r\n\x1a\n" + b"capture", content_type="image/png"
        )
        response = self.client.post(
            reverse("pages:contact_us"),
            {
                "form_type": "report",
                "report-description": "The calendar did not move my task.",
                "report-steps": "Drag the task to Friday.",
                "report-area": "Dashboard",
                "report-screenshots": screenshot,
                "report-email": "",
            },
        )
        self.assertRedirects(response, f"{reverse('pages:contact_us')}?sent=report")
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["feedback@example.test"])
        self.assertEqual(mail.outbox[0].reply_to, [])
        self.assertEqual(len(mail.outbox[0].attachments), 1)

    def test_rejects_non_image_upload_before_delivery(self):
        response = self.client.post(
            reverse("pages:contact_us"),
            {
                "form_type": "report",
                "report-description": "A problem occurred.",
                "report-screenshots": SimpleUploadedFile(
                    "not-image.png", b"plain text", content_type="image/png"
                ),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Attach PNG, JPG or WebP screenshots only.")
        self.assertEqual(len(mail.outbox), 0)

    def test_message_can_request_reply(self):
        response = self.client.post(
            reverse("pages:contact_us"),
            {
                "form_type": "message",
                "message-topic": "Suggestion",
                "message-body": "Please add a reminder for inspections.",
                "message-email": "manager@example.test",
            },
        )
        self.assertRedirects(response, f"{reverse('pages:contact_us')}?sent=message")
        self.assertEqual(mail.outbox[0].reply_to, ["manager@example.test"])
        self.assertIn("Please add a reminder", mail.outbox[0].body)

    def test_removed_diagnostics_fields_are_ignored(self):
        self.client.post(
            reverse("pages:contact_us"),
            {
                "form_type": "report",
                "report-description": "A problem occurred.",
                "report-page_url": "https://example.test/private/",
                "report-browser_info": "Example browser",
            },
        )
        self.assertNotIn("/private/", mail.outbox[0].body)
        self.assertNotIn("Example browser", mail.outbox[0].body)
