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
            "pages:privacy_policy",
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
                self.assertContains(response, reverse("pages:privacy_policy"))
                self.assertContains(response, reverse("accounts:register"))

    @override_settings(DEBUG=False)
    def test_unknown_url_uses_custom_404_page(self):
        response = self.client.get("/this-page-does-not-exist/")

        self.assertEqual(response.status_code, 404)
        self.assertTemplateUsed(response, "404.html")
        self.assertContains(response, "This page isn't here.", status_code=404)
        self.assertContains(response, reverse("pages:home"), status_code=404)

    @override_settings(PMS_CLOUDFLARE_WEB_ANALYTICS_TOKEN="test-site-token")
    def test_analytics_is_limited_to_public_pages_and_respects_objection(self):
        beacon = "https://static.cloudflareinsights.com/beacon.min.js"
        for name in ("pages:home", "pages:features", "pages:faq", "pages:coming_soon", "pages:privacy_policy"):
            with self.subTest(page=name):
                self.assertContains(self.client.get(reverse(name)), beacon)

        for name in ("pages:contact_us", "accounts:login", "accounts:register", "accounts:password_reset_request"):
            with self.subTest(excluded_page=name):
                self.assertNotContains(self.client.get(reverse(name)), beacon)
        with override_settings(DEBUG=False):
            self.assertNotContains(self.client.get("/not-a-real-page/"), beacon, status_code=404)

        preference_url = reverse("pages:analytics_preference")
        response = self.client.post(preference_url, {"analytics": "off"})
        self.assertRedirects(response, f"{reverse('pages:privacy_policy')}#cookies-and-analytics")
        self.assertEqual(response.cookies["mpd_analytics_off"].value, "1")
        self.assertNotContains(self.client.get(reverse("pages:home")), beacon)
        self.assertContains(self.client.get(reverse("pages:privacy_policy")), "Turn analytics on")

        self.client.post(preference_url, {"analytics": "on"})
        self.assertContains(self.client.get(reverse("pages:home")), beacon)

    def test_analytics_preference_rejects_invalid_choice(self):
        response = self.client.post(reverse("pages:analytics_preference"), {"analytics": "unknown"})
        self.assertEqual(response.status_code, 400)

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
