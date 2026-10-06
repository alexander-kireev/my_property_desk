"""Property form behaviour."""

from django.test import TestCase
from django.utils import timezone

from accounts.models import User

from ..forms import PropertyForm
from ..models import Property


class PropertyFormTests(TestCase):
    TEST_PASSWORD = "HolidayHome123!"
    VALID_DATA = {
        "name": "Hill House",
        "description": "Three-bedroom managed property.",
        "address": "12 Green Lane, London",
    }

    def setUp(self):
        self.user = User.objects.create_user(
            email="alice@example.com",
            first_name="Alice",
            last_name="Smith",
            password=self.TEST_PASSWORD,
        )

    def test_duplicate_name_for_user_is_rejected_case_insensitively(self):
        Property.objects.create(user=self.user, name="Hill House")
        data = self.VALID_DATA.copy()
        data["name"] = "HILL HOUSE"

        form = PropertyForm(data=data, user=self.user)

        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)

    def test_editing_property_without_changing_its_name_is_valid(self):
        property_record = Property.objects.create(
            user=self.user,
            name=self.VALID_DATA["name"],
        )

        form = PropertyForm(
            data=self.VALID_DATA,
            user=self.user,
            instance=property_record,
        )

        self.assertTrue(form.is_valid(), form.errors)

    def test_deleted_property_name_can_be_reused(self):
        Property.objects.create(
            user=self.user,
            name="Hill House",
            deleted_at=timezone.now(),
        )
        data = self.VALID_DATA.copy()
        data["name"] = "HILL HOUSE"

        form = PropertyForm(data=data, user=self.user)

        self.assertTrue(form.is_valid(), form.errors)
