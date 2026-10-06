"""Shared test fixtures and small setup helpers; no tests are defined here."""

from datetime import date, timedelta

from django.utils import timezone

from accounts.models import User
from contact.models import Contact
from property.models import Property

from ..models import Event


class EventTestMixin:
    password = "HolidayHome123!"

    def create_user(self, email="alice@example.com"):
        return User.objects.create_user(
            email=email,
            first_name="Alice",
            last_name="Smith",
            password=self.password,
        )

    def create_property(self, user, name="Hill House", **values):
        return Property.objects.create(user=user, name=name, **values)

    def create_contact(self, user, first_name="Alex", **values):
        return Contact.objects.create(user=user, first_name=first_name, **values)

    def create_event(self, user, title="Inspection", **values):
        defaults = {
            "scheduled_date": date(2026, 9, 20),
            "all_day": True,
        }
        defaults.update(values)
        return Event.objects.create(user=user, title=title, **defaults)

    def valid_form_data(self, **values):
        data = {
            "title": "Inspection",
            "description": "Annual inspection",
            "scheduled_date": (timezone.localdate() + timedelta(days=1)).isoformat(),
            "all_day": "on",
        }
        data.update(values)
        return data


class EventViewFixture(EventTestMixin):
    def setUp(self):
        self.user = self.create_user()
        self.client.force_login(self.user)
