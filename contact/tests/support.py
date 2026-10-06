"""Shared test fixtures and small setup helpers; no tests are defined here."""

from accounts.models import User
from note.models import Note

from ..models import Contact, ContactMethod


class ContactTestMixin:
    TEST_PASSWORD = "HolidayHome123!"

    def create_user(self, email="alice@example.com"):
        return User.objects.create_user(
            email=email,
            first_name="Test",
            last_name="User",
            password=self.TEST_PASSWORD,
        )

    def create_contact(self, user, first_name="Alice", **values):
        return Contact.objects.create(
            user=user,
            first_name=first_name,
            **values,
        )

    def create_method(
        self,
        contact,
        type=ContactMethod.Type.EMAIL,
        value="alice@example.com",
    ):
        return ContactMethod.objects.create(
            contact=contact,
            type=type,
            value=value,
        )

    def create_note(
        self,
        user,
        contact,
        content="a note",
    ):
        return Note.objects.create(
            user=user,
            contact=contact,
            content=content,
        )


class ContactViewFixture(ContactTestMixin):
    def setUp(self):
        self.user = self.create_user()
        self.other_user = self.create_user("bob@example.com")
        self.client.force_login(self.user)
