"""Property actions behaviour."""

from datetime import datetime, timedelta
from datetime import timezone as datetime_timezone

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from event.models import Event
from issue.models import Issue
from task.models import Task

from ..models import Property
from .support import PropertyViewFixture


class PropertyViewActionsTests(PropertyViewFixture, TestCase):
    def test_list_edit_and_state_actions_preserve_filters_and_page(self):
        property_record = self.create_property(name="Oak House")
        self.client.force_login(self.user)
        query = "?return_to=list&search=Oak&state=all&sort=-name&page=2"
        expected = (
            f"{reverse('property:properties')}?search=Oak&state=all&sort=-name"
            f"&page=2&selected={property_record.pk}"
        )

        response = self.client.post(
            reverse("property:edit_property", args=[property_record.pk]) + query,
            {
                "name": "Oak House",
                "description": "Updated",
                "address": "10 Oak Road",
            },
        )
        self.assertRedirects(response, expected, fetch_redirect_response=False)
        response = self.client.post(
            reverse("property:deactivate_property", args=[property_record.pk]) + query
        )
        self.assertRedirects(response, expected, fetch_redirect_response=False)
        response = self.client.post(
            reverse("property:reactivate_property", args=[property_record.pk]) + query
        )
        self.assertRedirects(response, expected, fetch_redirect_response=False)

    def test_invalid_list_edit_reopens_shared_modal(self):
        property_record = self.create_property(name="Oak House")
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("property:edit_property", args=[property_record.pk])
            + "?return_to=list&search=Oak",
            {
                "name": "",
                "description": "Updated",
                "address": "10 Oak Road",
            },
            follow=True,
        )

        self.assertContains(response, 'data-modal-auto-open="listEditPropertyModal"')
        self.assertContains(response, "This field is required")

    def test_deleted_property_is_excluded_from_property_list(self):
        visible_property = self.create_property(name="Hill House")
        deleted_property = self.create_property(name="Deleted House")
        deleted_property.deleted_at = timezone.now()
        deleted_property.save(update_fields=["deleted_at"])
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:properties"))

        self.assertContains(response, visible_property.name)
        self.assertNotContains(response, deleted_property.name)

    def test_add_property_clears_stale_search_and_page(self):
        self.client.force_login(self.user)
        response = self.client.post(
            f"{reverse('property:add_property')}?search=unrelated&page=3",
            data=self.VALID_DATA,
        )
        property_record = Property.objects.get(name=self.VALID_DATA["name"])
        self.assertEqual(
            response.url,
            reverse("property:property_detail", kwargs={"property_id": property_record.pk}),
        )

    def test_invalid_creation_reopens_modal_and_preserves_list_state(self):
        self.create_property(name="Hill House")
        self.client.force_login(self.user)
        url = f"{reverse('property:add_property')}?search=Hill&sort=-name"
        data = self.VALID_DATA.copy()
        data["name"] = "HILL HOUSE"

        post_response = self.client.post(url, data=data)

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("search=Hill", post_response.url)
        self.assertIn("sort=-name", post_response.url)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)

        self.assertEqual(response.status_code, 200)
        self.assertIn("name", response.context["add_property_form"].errors)
        self.assertEqual(response.context["search"], "Hill")
        self.assertEqual(response.context["sort"], "-name")
        self.assertContains(
            response,
            'data-modal-auto-open="addPropertyModal"',
        )
        self.assertEqual(Property.objects.count(), 1)

    def test_mobile_property_header_keeps_long_name_status_and_actions_together(self):
        name = "Northgate Mews and Gardens Residential Building"
        property_record = self.create_property(name=name)
        self.client.force_login(self.user)

        response = self.client.get(reverse("property:property_detail", args=[property_record.pk]))

        self.assertContains(response, 'class="property-command-header workspace-detail-header"')
        self.assertNotContains(response, 'class="property-detail-header"')
        self.assertContains(response, 'class="workspace-mobile-back btn btn-sm pom-quiet mb-3"')
        self.assertContains(
            response, f'<h2 class="property-heading-title workspace-detail-title h3">{name}</h2>'
        )
        self.assertContains(response, 'class="work-pill work-pill--active"')
        self.assertContains(response, 'class="property-heading-description"')
        self.assertContains(response, 'class="property-heading-actions workspace-detail-actions"')
        self.assertContains(response, 'aria-label="Property actions"')

    def test_past_date_sort_uses_displayed_local_date_then_kind_and_pk(self):
        property_record = self.create_property()
        utc = datetime_timezone.utc
        issue = Issue.objects.create(
            user=self.user,
            property=property_record,
            title="Zulu issue",
            state=Issue.State.RESOLVED,
            terminated_at=datetime(2026, 9, 26, 13, tzinfo=utc),
        )
        first_task = Task.objects.create(
            user=self.user,
            property=property_record,
            title="Bravo task",
            state=Task.State.COMPLETED,
            terminated_at=datetime(2026, 9, 26, 23, 30, tzinfo=utc),
        )
        second_task = Task.objects.create(
            user=self.user,
            property=property_record,
            title="Alpha task",
            state=Task.State.COMPLETED,
            terminated_at=datetime(2026, 9, 27, 10, tzinfo=utc),
        )
        event = Event.objects.create(
            user=self.user,
            property=property_record,
            title="Charlie event",
            scheduled_date=timezone.localdate(),
            all_day=True,
            state=Event.State.OCCURRED,
            terminated_at=datetime(2026, 9, 27, 13, tzinfo=utc),
        )
        self.client.force_login(self.user)
        url = reverse("property:property_detail", args=[property_record.pk])

        with timezone.override("Pacific/Auckland"):
            date_response = self.client.get(url, {"records_scope": "past", "records_sort": "date"})
            recent_response = self.client.get(
                url, {"records_scope": "past", "records_sort": "recent"}
            )
            title_response = self.client.get(
                url, {"records_scope": "past", "records_sort": "title"}
            )

        self.assertEqual(
            [entry["item"].pk for entry in date_response.context["related_page"]],
            [issue.pk, first_task.pk, second_task.pk, event.pk],
        )
        self.assertEqual(
            [entry["kind"] for entry in date_response.context["related_page"]],
            ["issue", "task", "task", "event"],
        )
        self.assertContains(date_response, "27 Sep 2026")
        self.assertContains(date_response, "28 Sep 2026")
        self.assertEqual(
            [entry["item"].title for entry in recent_response.context["related_page"]],
            ["Charlie event", "Alpha task", "Bravo task", "Zulu issue"],
        )
        self.assertEqual(
            [entry["item"].title for entry in title_response.context["related_page"]],
            ["Alpha task", "Bravo task", "Charlie event", "Zulu issue"],
        )

    def test_add_buttons_open_forms_on_the_property_page(self):
        property_record = self.create_property()
        self.client.force_login(self.user)
        response = self.client.get(reverse("property:property_detail", args=[property_record.pk]))
        for kind, modal in (
            ("issue", "propertyAddIssueModal"),
            ("task", "propertyAddTaskModal"),
            ("event", "propertyAddEventModal"),
        ):
            with self.subTest(kind=kind):
                self.assertContains(response, f'data-bs-target="#{modal}"')
                self.assertContains(
                    response,
                    reverse("property:add_property_record", args=[property_record.pk, kind]),
                )
                self.assertEqual(
                    response.context[f"property_add_{kind}_form"].initial["property"],
                    property_record.pk,
                )

    def test_property_add_creates_each_record_without_leaving_property(self):
        property_record = self.create_property()
        self.client.force_login(self.user)
        cases = (
            ("issue", Issue, {"title": "Repair window", "priority": Issue.Priority.HIGH}),
            ("task", Task, {"title": "Call contractor", "priority": Task.Priority.HIGH}),
            (
                "event",
                Event,
                {
                    "title": "Site visit",
                    "scheduled_date": (timezone.localdate() + timedelta(days=1)).isoformat(),
                    "all_day": "on",
                },
            ),
        )
        for kind, model, data in cases:
            with self.subTest(kind=kind):
                response = self.client.post(
                    reverse("property:add_property_record", args=[property_record.pk, kind]),
                    data,
                )
                self.assertRedirects(
                    response,
                    reverse("property:property_detail", args=[property_record.pk])
                    + f"?records_type={kind}&records_scope=current&records_sort=recent",
                    fetch_redirect_response=False,
                )
                self.assertTrue(
                    model.objects.filter(
                        user=self.user, property=property_record, title=data["title"]
                    ).exists()
                )

    def test_invalid_property_add_reopens_same_modal_with_entered_values(self):
        property_record = self.create_property()
        self.client.force_login(self.user)
        for kind, modal in (
            ("issue", "propertyAddIssueModal"),
            ("task", "propertyAddTaskModal"),
            ("event", "propertyAddEventModal"),
        ):
            with self.subTest(kind=kind):
                response = self.client.post(
                    reverse("property:add_property_record", args=[property_record.pk, kind]),
                    {"title": "", "description": "Keep this text"},
                )
                restored = self.client.get(response.url)
                self.assertIn(f"/properties/{property_record.pk}/?form_state=", response.url)
                self.assertEqual(restored.context["property_record_modal"], modal)
                self.assertEqual(
                    restored.context[f"property_add_{kind}_form"].data["description"],
                    "Keep this text",
                )

    def test_property_add_ignores_tampered_property_field(self):
        origin = self.create_property(name="Origin")
        destination = self.create_property(name="Destination")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("property:add_property_record", args=[origin.pk, "task"]),
            {
                "title": "Stay here",
                "property": destination.pk,
                "relationship_type": "standalone",
                "priority": Task.Priority.LOW,
            },
        )
        self.assertEqual(response.status_code, 302)
        task = Task.objects.get(title="Stay here")
        self.assertEqual(task.property, origin)
        self.assertIsNone(task.issue)

    def test_invalid_property_origin_form_keeps_return_destination(self):
        property_record = self.create_property()
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("issue:add_issue"),
            {
                "title": "",
                "property": property_record.pk,
                "return_property": property_record.pk,
            },
        )
        restored = self.client.get(response.url)
        self.assertEqual(restored.context["open_modal"], "addIssueModal")
        self.assertEqual(restored.context["return_property_id"], property_record.pk)
        self.assertContains(restored, f'name="return_property" value="{property_record.pk}"')

    def test_property_task_quick_action_returns_to_property_workspace(self):
        property_record = self.create_property()
        task = Task.objects.create(user=self.user, property=property_record, title="Book visit")
        self.client.force_login(self.user)
        next_url = reverse("property:property_detail", args=[property_record.pk]) + "?tab=work"

        response = self.client.post(
            reverse("task:complete_task", args=[task.pk]), {"next": next_url}
        )

        self.assertRedirects(response, next_url, fetch_redirect_response=False)
        task.refresh_from_db()
        self.assertEqual(task.state, Task.State.COMPLETED)

    def test_property_issue_and_event_quick_actions_return_to_property(self):
        property_record = self.create_property()
        issue = Issue.objects.create(user=self.user, property=property_record, title="Repair tap")
        event = Event.objects.create(
            user=self.user,
            property=property_record,
            title="Inspection",
            scheduled_date=timezone.localdate() + timedelta(days=1),
            all_day=True,
        )
        self.client.force_login(self.user)

        for action_url, next_tab in (
            (reverse("issue:resolve_issue", args=[issue.pk]), "work"),
            (reverse("event:cancel_event", args=[event.pk]), "schedule"),
        ):
            with self.subTest(action_url=action_url):
                next_url = (
                    reverse("property:property_detail", args=[property_record.pk])
                    + f"?tab={next_tab}"
                )
                response = self.client.post(action_url, {"next": next_url})
                self.assertRedirects(response, next_url, fetch_redirect_response=False)

    def test_property_detail_query_actions_mark_the_correct_modal_to_open(self):
        property_record = self.create_property()
        self.client.force_login(self.user)
        url = reverse(
            "property:property_detail",
            kwargs={"property_id": property_record.pk},
        )

        for parameter, modal_id in (
            ("edit", "editPropertyModal"),
            ("deactivate", "deactivatePropertyModal"),
            ("confirm_delete", "deletePropertyModal"),
        ):
            with self.subTest(parameter=parameter):
                response = self.client.get(url, {parameter: "1"})
                self.assertContains(
                    response,
                    f'data-modal-auto-open="{modal_id}"',
                )

    def test_deleted_property_detail_returns_404(self):
        property_record = self.create_property()
        property_record.deleted_at = timezone.now()
        property_record.save(update_fields=["deleted_at"])
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "property:property_detail",
                kwargs={"property_id": property_record.pk},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_valid_edit_updates_property(self):
        property_record = self.create_property()
        self.client.force_login(self.user)
        updated_data = {
            "name": "Updated House",
            "description": "Updated description.",
            "address": "20 Updated Road",
        }

        response = self.client.post(
            reverse(
                "property:edit_property",
                kwargs={"property_id": property_record.pk},
            ),
            data=updated_data,
        )
        property_record.refresh_from_db()

        self.assertRedirects(
            response,
            reverse(
                "property:property_detail",
                kwargs={"property_id": property_record.pk},
            ),
        )
        self.assertEqual(property_record.name, updated_data["name"])
        self.assertEqual(property_record.description, updated_data["description"])
        self.assertEqual(property_record.address, updated_data["address"])

    def test_duplicate_name_edit_is_rejected(self):
        property_record = self.create_property(name="Hill House")
        self.create_property(name="River Cottage")
        self.client.force_login(self.user)
        data = self.VALID_DATA.copy()
        data["name"] = "RIVER COTTAGE"

        post_response = self.client.post(
            reverse(
                "property:edit_property",
                kwargs={"property_id": property_record.pk},
            ),
            data=data,
        )

        self.assertEqual(post_response.status_code, 302)
        self.assertIn("form_state=", post_response.url)

        response = self.client.get(post_response.url)
        property_record.refresh_from_db()

        self.assertEqual(response.status_code, 200)
        self.assertIn("name", response.context["edit_property_form"].errors)
        self.assertContains(
            response,
            'data-modal-auto-open="editPropertyModal"',
        )
        self.assertEqual(property_record.name, "Hill House")

    def test_user_cannot_edit_another_users_property(self):
        property_record = self.create_property(user=self.other_user)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "property:edit_property",
                kwargs={"property_id": property_record.pk},
            ),
            data=self.VALID_DATA,
        )

        self.assertEqual(response.status_code, 404)

    def test_deactivated_property_cannot_be_edited(self):
        property_record = self.create_property(
            state=Property.State.DEACTIVATED,
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "property:edit_property",
                kwargs={"property_id": property_record.pk},
            ),
            data=self.VALID_DATA,
        )

        self.assertEqual(response.status_code, 404)

    def test_delete_soft_deletes_property_and_redirects_to_list(self):
        property_record = self.create_property()
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "property:delete_property",
                kwargs={"property_id": property_record.pk},
            )
        )
        property_record.refresh_from_db()

        self.assertRedirects(response, reverse("property:properties"))
        self.assertIsNotNone(property_record.deleted_at)
        self.assertTrue(Property.objects.filter(pk=property_record.pk).exists())

    def test_delete_requires_post(self):
        property_record = self.create_property()
        self.client.force_login(self.user)

        response = self.client.get(
            reverse(
                "property:delete_property",
                kwargs={"property_id": property_record.pk},
            )
        )
        property_record.refresh_from_db()

        self.assertEqual(response.status_code, 405)
        self.assertIsNone(property_record.deleted_at)

    def test_user_cannot_delete_another_users_property(self):
        property_record = self.create_property(user=self.other_user)
        self.client.force_login(self.user)

        response = self.client.post(
            reverse(
                "property:delete_property",
                kwargs={"property_id": property_record.pk},
            )
        )
        property_record.refresh_from_db()

        self.assertEqual(response.status_code, 404)
        self.assertIsNone(property_record.deleted_at)
