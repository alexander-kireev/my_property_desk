"""Property detail pagination must not discard a rejected edit."""

from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from property.models import Property


class PropertyPaginationStateTests(TestCase):
    def test_rejected_edit_survives_page_correction_once(self):
        user = User.objects.create_user(
            email="pagination@example.invalid", password="TestPassword123!"
        )
        records = [
            Property.objects.create(user=user, name=f"Property {index:02}") for index in range(21)
        ]
        selected = records[-1]
        self.client.force_login(user)
        response = self.client.post(
            reverse("property:edit_property", args=[selected.pk]), {"name": ""}
        )
        correction = self.client.get(response.url)
        self.assertEqual(correction.status_code, 302)
        final = self.client.get(correction.url)
        self.assertTrue(final.context["edit_property_form"].is_bound)
        self.assertIn("name", final.context["edit_property_form"].errors)
        self.assertFalse(self.client.get(correction.url).context["edit_property_form"].is_bound)
