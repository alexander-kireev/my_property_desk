"""Pages actions behaviour."""

from datetime import time, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from contact.models import Contact
from event.models import Event, EventContact
from issue.models import Issue
from note.models import Note
from task.models import Task

from .support import DashboardFixture


class DashboardActionsTests(DashboardFixture, TestCase):
    def test_dashboard_edit_preserves_task_link_to_historical_issue(self):
        issue = Issue.objects.create(
            user=self.user,
            title="Test activity reported",
            state=Issue.State.RESOLVED,
        )
        self.task.issue = issue
        self.task.save(update_fields=["issue"])

        data = self.client.get(reverse("pages:dashboard_data")).json()
        tasks_by_id = {item["id"]: item for item in data["records"]["task"]}
        task_data = tasks_by_id[self.task.pk]
        self.assertEqual(task_data["issue_id"], issue.pk)
        self.assertEqual(task_data["issue_title"], issue.title)
        self.assertNotIn(issue.pk, [item["id"] for item in data["issues"]])

        response = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "edit",
                "kind": "task",
                "id": self.task.pk,
                "title": "Collect landlord approval",
                "description": "",
                "relationship_type": "issue",
                "property": "",
                "issue": issue.pk,
                "priority": self.task.priority,
                "scheduled_date": "",
                "completion_deadline": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.title, "Collect landlord approval")
        self.assertEqual(self.task.issue_id, issue.pk)

    def test_dashboard_edit_can_clear_task_schedule_and_task_or_issue_deadline(self):
        yesterday = self.today - timedelta(days=1)
        self.task.scheduled_date = yesterday
        self.task.completion_deadline = yesterday
        self.task.save(update_fields=["scheduled_date", "completion_deadline"])
        issue = Issue.objects.create(
            user=self.user, title="Roof leak", resolution_deadline=yesterday
        )
        task_response = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "edit",
                "kind": "task",
                "id": self.task.pk,
                "title": self.task.title,
                "description": "",
                "relationship_type": "standalone",
                "property": "",
                "issue": "",
                "priority": self.task.priority,
                "scheduled_date": "",
                "completion_deadline": "",
            },
        )
        issue_response = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "edit",
                "kind": "issue",
                "id": issue.pk,
                "title": issue.title,
                "description": "",
                "property": "",
                "priority": issue.priority,
                "resolution_deadline": "",
            },
        )
        self.assertEqual(task_response.status_code, 200)
        self.assertEqual(issue_response.status_code, 200)
        self.task.refresh_from_db()
        issue.refresh_from_db()
        self.assertIsNone(self.task.scheduled_date)
        self.assertIsNone(self.task.completion_deadline)
        self.assertIsNone(issue.resolution_deadline)

    def test_unchanged_note_edit_does_not_write(self):
        note = Note.objects.create(user=self.user, content="Call back tomorrow")
        with patch("pages.dashboard.actions.update_note") as update:
            response = self.client.post(
                reverse("pages:dashboard_action"),
                {
                    "action": "edit",
                    "kind": "note",
                    "id": note.pk,
                    "content": "  Call back tomorrow  ",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["changed"])
        update.assert_not_called()

    def test_schedule_task_and_keep_its_deadline(self):
        self.task.completion_deadline = self.today + timedelta(days=5)
        self.task.save(update_fields=["completion_deadline"])
        date = self.today + timedelta(days=2)
        response = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "date",
                "kind": "task",
                "id": self.task.pk,
                "date": date.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.scheduled_date, date)
        self.assertEqual(self.task.completion_deadline, self.today + timedelta(days=5))

    def test_complete_undo_is_owner_and_state_safe(self):
        completed = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "finish",
                "kind": "task",
                "id": self.task.pk,
            },
        )
        self.assertEqual(completed.status_code, 200)
        token = completed.json()["undo_token"]
        repeated = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "finish",
                "kind": "task",
                "id": self.task.pk,
            },
        )
        self.assertEqual(repeated.status_code, 409)
        restored = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "undo",
                "kind": "task",
                "id": self.task.pk,
                "token": token,
            },
        )
        self.assertEqual(restored.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.state, Task.State.ACTIVE)
        self.assertIsNone(self.task.terminated_at)
        stale = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "undo",
                "kind": "task",
                "id": self.task.pk,
                "token": token,
            },
        )
        self.assertEqual(stale.status_code, 409)

    def test_issue_and_event_quick_actions_can_be_undone(self):
        issue = Issue.objects.create(user=self.user, title="Leaky pipe")
        event = Event.objects.create(
            user=self.user,
            title="Visit",
            scheduled_date=self.today + timedelta(days=1),
            all_day=True,
        )
        for kind, record, active_state in (
            ("issue", issue, Issue.State.ACTIVE),
            ("event", event, Event.State.SCHEDULED),
        ):
            with self.subTest(kind=kind):
                finished = self.client.post(
                    reverse("pages:dashboard_action"),
                    {
                        "action": "finish",
                        "kind": kind,
                        "id": record.pk,
                    },
                )
                self.assertEqual(finished.status_code, 200)
                undone = self.client.post(
                    reverse("pages:dashboard_action"),
                    {
                        "action": "undo",
                        "kind": kind,
                        "id": record.pk,
                        "token": finished.json()["undo_token"],
                    },
                )
                self.assertEqual(undone.status_code, 200)
                record.refresh_from_db()
                self.assertEqual(record.state, active_state)

    def test_move_task_deadline_without_rescheduling_task(self):
        scheduled = self.today + timedelta(days=1)
        deadline = self.today + timedelta(days=4)
        self.task.scheduled_date = scheduled
        self.task.completion_deadline = self.today + timedelta(days=2)
        self.task.save(update_fields=["scheduled_date", "completion_deadline"])
        response = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "deadline",
                "kind": "task",
                "id": self.task.pk,
                "date": deadline.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        self.task.refresh_from_db()
        self.assertEqual(self.task.scheduled_date, scheduled)
        self.assertEqual(self.task.completion_deadline, deadline)

    def test_move_issue_deadline(self):
        issue = Issue.objects.create(
            user=self.user, title="Faulty lock", resolution_deadline=self.today
        )
        deadline = self.today + timedelta(days=3)
        response = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "deadline",
                "kind": "issue",
                "id": issue.pk,
                "date": deadline.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 200)
        issue.refresh_from_db()
        self.assertEqual(issue.resolution_deadline, deadline)

    def test_unschedule_task_preserves_its_deadline(self):
        deadline = self.today + timedelta(days=3)
        self.task.scheduled_date = self.today
        self.task.completion_deadline = deadline
        self.task.save(update_fields=["scheduled_date", "completion_deadline"])
        url = reverse("pages:dashboard_action")
        response = self.client.post(
            url, {"action": "unschedule", "kind": "task", "id": self.task.pk}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["changed"])
        self.task.refresh_from_db()
        self.assertIsNone(self.task.scheduled_date)
        self.assertEqual(self.task.completion_deadline, deadline)
        repeated = self.client.post(
            url, {"action": "unschedule", "kind": "task", "id": self.task.pk}
        )
        self.assertFalse(repeated.json()["changed"])

    def test_remove_task_or_issue_deadline_preserves_other_dates(self):
        self.task.scheduled_date = self.today
        self.task.completion_deadline = self.today + timedelta(days=2)
        self.task.save(update_fields=["scheduled_date", "completion_deadline"])
        issue = Issue.objects.create(
            user=self.user, title="Faulty lock", resolution_deadline=self.today
        )
        url = reverse("pages:dashboard_action")
        for kind, record in (("task", self.task), ("issue", issue)):
            with self.subTest(kind=kind):
                response = self.client.post(
                    url, {"action": "clear_deadline", "kind": kind, "id": record.pk}
                )
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json()["changed"])
                record.refresh_from_db()
                self.assertIsNone(
                    record.completion_deadline if kind == "task" else record.resolution_deadline
                )
                repeated = self.client.post(
                    url, {"action": "clear_deadline", "kind": kind, "id": record.pk}
                )
                self.assertFalse(repeated.json()["changed"])
        self.assertEqual(self.task.scheduled_date, self.today)

    def test_clear_date_actions_reject_events_and_other_users_records(self):
        event = Event.objects.create(
            user=self.user, title="Visit", scheduled_date=self.today, all_day=True
        )
        other_task = Task.objects.get(user=self.other)
        url = reverse("pages:dashboard_action")
        for action in ("unschedule", "clear_deadline"):
            with self.subTest(action=action):
                forbidden = self.client.post(
                    url, {"action": action, "kind": "event", "id": event.pk}
                )
                self.assertEqual(forbidden.status_code, 400)
                private = self.client.post(
                    url, {"action": action, "kind": "task", "id": other_task.pk}
                )
                self.assertEqual(private.status_code, 404)

    def test_deadline_rejects_invalid_date_and_other_users_record(self):
        invalid = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "deadline",
                "kind": "task",
                "id": self.task.pk,
                "date": "not-a-date",
            },
        )
        self.assertEqual(invalid.status_code, 400)
        other_task = Task.objects.get(user=self.other)
        private = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "deadline",
                "kind": "task",
                "id": other_task.pk,
                "date": self.today.isoformat(),
            },
        )
        self.assertEqual(private.status_code, 404)

    def test_event_cannot_use_deadline_action(self):
        event = Event.objects.create(
            user=self.user,
            title="Visit",
            scheduled_date=self.today + timedelta(days=2),
            all_day=True,
        )
        response = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "deadline",
                "kind": "event",
                "id": event.pk,
                "date": self.today.isoformat(),
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_timed_event_edit_preserves_time_when_date_changes(self):
        event = Event.objects.create(
            user=self.user,
            title="Visit",
            scheduled_date=self.today + timedelta(days=2),
            all_day=False,
            start_time=time(14, 0),
            end_time=time(15, 0),
        )
        target = self.today + timedelta(days=3)
        response = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "edit",
                "kind": "event",
                "id": event.pk,
                "title": event.title,
                "description": "",
                "property": "",
                "scheduled_date": target.isoformat(),
                "start_time": "14:00",
                "end_time": "15:00",
            },
        )
        self.assertEqual(response.status_code, 200)
        event.refresh_from_db()
        self.assertEqual(event.scheduled_date, target)
        self.assertEqual(event.start_time, time(14, 0))
        self.assertEqual(event.end_time, time(15, 0))

    def test_cancel_event_from_dashboard(self):
        event = Event.objects.create(
            user=self.user,
            title="Visit",
            scheduled_date=self.today + timedelta(days=2),
            all_day=True,
        )
        response = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "cancel",
                "kind": "event",
                "id": event.pk,
            },
        )
        self.assertEqual(response.status_code, 200)
        event.refresh_from_db()
        self.assertEqual(event.state, Event.State.CANCELLED)
        self.assertIsNotNone(event.terminated_at)
        active_titles = [
            item["title"]
            for item in self.client.get(reverse("pages:dashboard_data")).json()["records"]["event"]
        ]
        self.assertNotIn("Visit", active_titles)

    def test_cannot_cancel_another_users_event(self):
        event = Event.objects.create(
            user=self.other,
            title="Private visit",
            scheduled_date=self.today + timedelta(days=2),
            all_day=True,
        )
        response = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "cancel",
                "kind": "event",
                "id": event.pk,
            },
        )
        self.assertEqual(response.status_code, 404)
        event.refresh_from_db()
        self.assertEqual(event.state, Event.State.SCHEDULED)

    def test_add_note_is_general_and_private(self):
        response = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "add",
                "kind": "note",
                "content": "Check access",
            },
        )
        self.assertEqual(response.status_code, 200)
        note = Note.objects.get(pk=response.json()["id"])
        self.assertEqual(note.user, self.user)
        self.assertIsNone(note.contact)

    def test_note_delete_undo_restores_only_latest_note(self):
        first = Note.objects.create(user=self.user, content="First")
        second = Note.objects.create(user=self.user, content="Second")
        action_url = reverse("pages:dashboard_action")
        first_delete = self.client.post(
            action_url, {"action": "delete", "kind": "note", "id": first.pk}
        )
        second_delete = self.client.post(
            action_url, {"action": "delete", "kind": "note", "id": second.pk}
        )
        stale = self.client.post(
            action_url,
            {
                "action": "undo",
                "kind": "note",
                "id": first.pk,
                "token": first_delete.json()["undo_token"],
            },
        )
        self.assertEqual(stale.status_code, 409)
        restored = self.client.post(
            action_url,
            {
                "action": "undo",
                "kind": "note",
                "id": second.pk,
                "token": second_delete.json()["undo_token"],
            },
        )
        self.assertEqual(restored.status_code, 200)
        self.assertTrue(Note.objects.filter(pk=second.pk, content="Second").exists())
        self.assertFalse(Note.objects.filter(pk=first.pk).exists())

    def test_add_issue_uses_model_form_validation(self):
        response = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "add",
                "kind": "issue",
                "title": "Tap leak",
                "description": "",
                "property": "",
                "priority": Issue.Priority.HIGH,
                "resolution_deadline": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Issue.objects.filter(user=self.user, title="Tap leak").exists())

    def test_add_task_and_event(self):
        task_response = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "add",
                "kind": "task",
                "title": "Book visit",
                "description": "",
                "relationship_type": "standalone",
                "property": "",
                "issue": "",
                "priority": Task.Priority.MEDIUM,
                "scheduled_date": "",
                "completion_deadline": "",
            },
        )
        self.assertEqual(task_response.status_code, 200)
        self.assertTrue(Task.objects.filter(user=self.user, title="Book visit").exists())
        event_response = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "add",
                "kind": "event",
                "title": "Access visit",
                "description": "",
                "property": "",
                "scheduled_date": (self.today + timedelta(days=1)).isoformat(),
                "all_day": "on",
                "start_time": "",
                "end_time": "",
            },
        )
        self.assertEqual(event_response.status_code, 200)
        self.assertTrue(Event.objects.filter(user=self.user, title="Access visit").exists())

    def test_dashboard_add_event_offers_and_saves_owned_active_participants(self):
        participant = Contact.objects.create(user=self.user, first_name="Ada", last_name="Lovelace")
        Contact.objects.create(
            user=self.user, first_name="Inactive", state=Contact.State.DEACTIVATED
        )
        Contact.objects.create(user=self.other, first_name="Private")
        response = self.client.get(reverse("pages:dashboard"))
        self.assertContains(response, 'id="dashboardAddEventModal"')
        self.assertContains(response, 'id="dashboardAddEventParticipantsTab"')
        self.assertContains(response, 'class="modal-event-field-grid"')
        self.assertContains(response, 'class="event-contact-option"')
        self.assertContains(response, "Ada Lovelace")
        self.assertNotContains(response, "Inactive")
        self.assertNotContains(response, "Private")
        response = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "add",
                "kind": "event",
                "title": "Visit with Ada",
                "description": "",
                "property": "",
                "scheduled_date": self.today.isoformat(),
                "all_day": "on",
                "start_time": "",
                "end_time": "",
                "contacts": [participant.pk],
            },
        )
        self.assertEqual(response.status_code, 200)
        event = Event.objects.get(user=self.user, title="Visit with Ada")
        self.assertTrue(EventContact.objects.filter(event=event, contact=participant).exists())

    def test_dashboard_add_event_rejects_another_users_participant(self):
        private = Contact.objects.create(user=self.other, first_name="Private")
        response = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "add",
                "kind": "event",
                "title": "Invalid participant",
                "description": "",
                "property": "",
                "scheduled_date": self.today.isoformat(),
                "all_day": "on",
                "start_time": "",
                "end_time": "",
                "contacts": [private.pk],
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("contacts", response.json()["errors"])
        self.assertFalse(Event.objects.filter(user=self.user, title="Invalid participant").exists())

    def test_dashboard_edit_event_participants_without_changing_details(self):
        previous = Contact.objects.create(user=self.user, first_name="Previous")
        replacement = Contact.objects.create(user=self.user, first_name="Replacement")
        historical = Contact.objects.create(
            user=self.user, first_name="Historical", state=Contact.State.DEACTIVATED
        )
        event = Event.objects.create(
            user=self.user, title="Inspection", scheduled_date=self.today, all_day=True
        )
        EventContact.objects.bulk_create(
            [EventContact(event=event, contact=contact) for contact in (previous, historical)]
        )
        page = self.client.get(reverse("pages:dashboard"))
        self.assertContains(page, 'id="workParticipantsTab"')
        data = self.client.get(reverse("pages:dashboard_data")).json()
        record = next(item for item in data["records"]["event"] if item["id"] == event.pk)
        self.assertEqual(record["contact_ids"], [previous.pk])

        response = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "edit",
                "kind": "event",
                "id": event.pk,
                "title": event.title,
                "description": event.description,
                "property": "",
                "scheduled_date": self.today.isoformat(),
                "all_day": "on",
                "start_time": "",
                "end_time": "",
                "manage_contacts": "1",
                "contacts": [replacement.pk],
            },
        )
        self.assertEqual(response.status_code, 200, response.content)
        self.assertTrue(response.json()["changed"])
        self.assertEqual(
            set(event.event_contacts.values_list("contact_id", flat=True)),
            {replacement.pk, historical.pk},
        )

    def test_dashboard_edit_event_rejects_private_participant(self):
        private = Contact.objects.create(user=self.other, first_name="Private")
        event = Event.objects.create(
            user=self.user, title="Inspection", scheduled_date=self.today, all_day=True
        )
        response = self.client.post(
            reverse("pages:dashboard_action"),
            {
                "action": "edit",
                "kind": "event",
                "id": event.pk,
                "title": event.title,
                "description": event.description,
                "property": "",
                "scheduled_date": self.today.isoformat(),
                "all_day": "on",
                "start_time": "",
                "end_time": "",
                "manage_contacts": "1",
                "contacts": [private.pk],
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("contacts", response.json()["errors"])
