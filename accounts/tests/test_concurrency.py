"""Real database races; row-lock behaviour cannot be established with SQLite."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.db import close_old_connections
from django.test import TransactionTestCase, skipUnlessDBFeature

from accounts.models import PendingRegistration
from accounts.registration import RegistrationUnavailable, request_registration


@skipUnlessDBFeature("has_select_for_update")
class RegistrationConcurrencyTests(TransactionTestCase):
    def test_competing_requests_create_one_pending_registration_and_one_email(self):
        barrier = Barrier(2)

        def attempt_registration(attempt_number):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                request_registration(
                    first_name="Race",
                    last_name="Check",
                    email="race@example.invalid",
                    password="ValidPassword123!",
                    confirmation_url_for_token=str,
                )
                return "created"
            except RegistrationUnavailable:
                return "unavailable"
            finally:
                close_old_connections()

        with patch("accounts.registration.send_mail", return_value=1) as delivery:
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(attempt_registration, range(2)))
        self.assertCountEqual(results, ["created", "unavailable"])
        self.assertEqual(PendingRegistration.objects.count(), 1)
        self.assertEqual(delivery.call_count, 1)
