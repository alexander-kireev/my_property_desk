"""Shared test fixtures and small setup helpers; no tests are defined here."""

from accounts.models import User

from ..models import Property


class PropertyViewFixture:
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
        self.other_user = User.objects.create_user(
            email="bob@example.com",
            first_name="Bob",
            last_name="Jones",
            password=self.TEST_PASSWORD,
        )

    def create_property(
        self,
        *,
        user=None,
        name="Hill House",
        state=Property.State.ACTIVE,
        address="12 Green Lane, London",
    ):
        return Property.objects.create(
            user=user or self.user,
            name=name,
            description="Managed property.",
            address=address,
            state=state,
        )
