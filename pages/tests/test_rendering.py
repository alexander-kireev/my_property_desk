"""Pages rendering behaviour."""

import re
from datetime import timedelta

from django.test import Client, TestCase
from django.urls import reverse

from issue.models import Issue

from .support import DashboardFixture


class DashboardRenderingTests(DashboardFixture, TestCase):
    def test_dashboard_data_is_private(self):
        response = self.client.get(reverse("pages:dashboard_data"))
        self.assertEqual(response.status_code, 200)
        titles = [item["title"] for item in response.json()["records"]["task"]]
        self.assertEqual(titles, ["Call contractor"])

    def test_dashboard_data_exposes_task_and_issue_deadlines(self):
        deadline = self.today + timedelta(days=2)
        self.task.completion_deadline = deadline
        self.task.save(update_fields=["completion_deadline"])
        issue = Issue.objects.create(
            user=self.user, title="Faulty lock", resolution_deadline=deadline
        )
        response = self.client.get(reverse("pages:dashboard_data"))
        records = response.json()["records"]
        self.assertEqual(records["task"][0]["due"], deadline.isoformat())
        self.assertEqual(records["issue"][0]["id"], issue.pk)
        self.assertEqual(records["issue"][0]["due"], deadline.isoformat())

    def test_dashboard_sets_csrf_cookie_for_actions(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        response = client.get(reverse("pages:dashboard"))
        self.assertIn("csrftoken", response.cookies)
        token = response.cookies["csrftoken"].value
        response = client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "add",
                "kind": "note",
                "content": "Check access",
            },
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)

    def test_dashboard_uses_month_and_year_controls_without_week_view(self):
        response = self.client.get(reverse("pages:dashboard"))
        self.assertContains(response, 'id="calendarMonth"')
        self.assertContains(response, 'id="calendarYear"')
        self.assertContains(response, 'id="selectedDayHeading"')
        self.assertNotContains(response, 'id="selectedDayNumber"')
        self.assertNotContains(response, 'data-view="week"')

    def test_dashboard_has_selected_day_tabs_and_toast(self):
        response = self.client.get(reverse("pages:dashboard"))
        for tab in ("tasks", "deadlines", "events"):
            self.assertContains(response, f'data-day-tab="{tab}"')
        self.assertContains(response, 'id="dashboardToast"')
        for kind in ("tasks", "issues", "events"):
            self.assertRegex(
                response.content.decode(),
                re.escape(f'data-calendar-filter="{kind}" checked').replace(r"\ ", r"\s+"),
            )
        for panel in ("operations", "calendar", "day", "notes"):
            self.assertContains(response, f'data-dashboard-panel="{panel}"')

    def test_dashboard_dialogs_are_named_and_keep_neutral_escape_action(self):
        response = self.client.get(reverse("pages:dashboard"))
        self.assertRegex(
            response.content.decode(),
            re.escape('id="workDialog" class="dashboard-dialog modal fade"').replace(r"\ ", r"\s+"),
        )
        self.assertRegex(
            response.content.decode(),
            re.escape('id="confirmDialog" class="dashboard-dialog modal fade"').replace(
                r"\ ", r"\s+"
            ),
        )
        self.assertRegex(
            response.content.decode(),
            re.escape('id="confirmCancel" data-close-dialog>Cancel</button>').replace(
                r"\ ", r"\s+"
            ),
        )

    def test_dashboard_uses_mpd_branding(self):
        response = self.client.get(reverse("pages:dashboard"))
        self.assertContains(response, "Dashboard | My Property Desk")
        self.assertContains(response, "brand/mpd-wordmark-dark.svg")
        self.assertContains(response, "brand/mpd-favicon-light.svg")
        self.assertContains(response, "brand/mpd-favicon-dark.svg")
        self.assertNotContains(response, "PoM")

    def test_brand_link_targets_dashboard_when_signed_in_and_home_when_signed_out(self):
        response = self.client.get(reverse("pages:dashboard"))
        self.assertRegex(
            response.content.decode(),
            re.escape(
                f'class="navbar-brand" href="{reverse("pages:dashboard")}" aria-label="My Property Desk dashboard"'
            ).replace(r"\ ", r"\s+"),
        )
        anonymous_response = Client().get(reverse("pages:home"))
        self.assertRegex(
            anonymous_response.content.decode(),
            re.escape(
                f'class="navbar-brand" href="{reverse("pages:home")}" aria-label="My Property Desk home"'
            ).replace(r"\ ", r"\s+"),
        )

    def test_authenticated_global_navigation_marks_only_matching_destination(self):
        destinations = {
            "pages:dashboard": "pages:dashboard",
            "task:tasks": "task:tasks",
            "issue:issues": "issue:issues",
            "event:events": "event:events",
            "property:properties": "property:properties",
            "contact:contacts": "contact:contacts",
            "accounts:profile_page": "accounts:profile_page",
        }
        for route_name, current_name in destinations.items():
            with self.subTest(route=route_name):
                response = self.client.get(reverse(route_name))
                self.assertEqual(response.status_code, 200)
                navbar = (
                    response.content.decode()
                    .split('<nav class="app-navbar ', 1)[1]
                    .split("</nav>", 1)[0]
                )
                self.assertEqual(navbar.count('aria-current="page"'), 2)
                current_links = re.findall(r'<a\b[^>]*aria-current="page"[^>]*>', navbar)
                self.assertEqual(len(current_links), 2)
                self.assertTrue(
                    all(f'href="{reverse(current_name)}"' in link for link in current_links)
                )
                self.assertNotIn(
                    'aria-current="page"',
                    navbar.split('class="my-work-menu-toggle', 1)[1].split("</button>", 1)[0],
                )

    def test_dashboard_event_filters_use_date_only(self):
        response = self.client.get(reverse("pages:dashboard"))
        self.assertContains(response, 'id="workFilter"')
        self.assertContains(response, 'id="workSecondaryWrap"')
        self.assertNotContains(response, 'id="workPresenceFilter"')
        self.assertNotContains(response, 'id="workPresenceWrap"')

    def test_dashboard_switches_between_day_and_notes_with_add_control_in_operations(self):
        response = self.client.get(reverse("pages:dashboard"))
        html = response.content.decode()
        self.assertLess(html.index('id="dashboardAddToggle"'), html.index('id="calendarGrid"'))
        self.assertContains(response, 'id="dayViewToggle"')
        self.assertContains(response, 'id="notesViewToggle"')
        self.assertRegex(
            response.content.decode(),
            re.escape(
                'id="notesView" role="tabpanel" aria-labelledby="notesViewToggle" hidden'
            ).replace(r"\ ", r"\s+"),
        )
        self.assertContains(response, 'id="notesList"')
        self.assertNotContains(response, 'id="notesToggle"')
