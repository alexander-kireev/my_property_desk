"""Property model behaviour."""

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone

from accounts.models import User

from ..models import Property


class PropertyModelTests(TestCase):
    TEST_PASSWORD = "HolidayHome123!"

    def create_user(self, email):
        return User.objects.create_user(
            email=email,
            first_name="Test",
            last_name="User",
            password=self.TEST_PASSWORD,
        )

    def test_property_name_is_case_insensitively_unique_per_user(self):
        user = self.create_user("alice@example.com")
        Property.objects.create(user=user, name="Hill House")

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Property.objects.create(user=user, name="HILL HOUSE")

    def test_different_users_can_use_the_same_property_name(self):
        user_1 = self.create_user("alice@example.com")
        user_2 = self.create_user("bob@example.com")

        Property.objects.create(user=user_1, name="Hill House")
        Property.objects.create(user=user_2, name="HILL HOUSE")

        self.assertEqual(Property.objects.count(), 2)

    def test_deleted_property_name_can_be_reused_by_same_user(self):
        user = self.create_user("alice@example.com")
        deleted_property = Property.objects.create(user=user, name="Hill House")
        deleted_property.deleted_at = timezone.now()
        deleted_property.save(update_fields=["deleted_at"])

        Property.objects.create(user=user, name="HILL HOUSE")

        self.assertEqual(Property.objects.count(), 2)
