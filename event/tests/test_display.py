"""Pure display or field contracts; no database setup required."""

from django.test import SimpleTestCase

from ..templatetags.event_display import compact_email


class EventDisplayTests(SimpleTestCase):
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
