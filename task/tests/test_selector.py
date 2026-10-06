"""Task selector behaviour."""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.models import User
from issue.models import Issue
from property.models import Property

from ..models import Task
from ..selectors import filtered_tasks_for_user, tasks_for_user


class TaskSelectorTests(TestCase):
    TEST_PASSWORD = "HolidayHome123!"
    TASK_DATA = [
        {
            "title": "abc active task",
            "description": "abc active task description",
            "state": Task.State.ACTIVE,
            "priority": Task.Priority.MEDIUM,
            "deleted_at": None,
        },
        {
            "title": "xyz active task",
            "description": "xyz active task description",
            "state": Task.State.ACTIVE,
            "priority": Task.Priority.MEDIUM,
            "deleted_at": None,
        },
        {
            "title": "abc completed task",
            "description": "abc completed task description",
            "state": Task.State.COMPLETED,
            "priority": Task.Priority.URGENT,
            "deleted_at": None,
        },
        {
            "title": "xyz completed task",
            "description": "xyz completed task description",
            "state": Task.State.COMPLETED,
            "priority": Task.Priority.MEDIUM,
            "deleted_at": None,
        },
        {
            "title": "abc dismissed task",
            "description": "abc dismissed task description",
            "state": Task.State.DISMISSED,
            "priority": Task.Priority.MEDIUM,
            "deleted_at": None,
        },
        {
            "title": "xyz dismissed task",
            "description": "xyz dismissed task description",
            "state": Task.State.DISMISSED,
            "priority": Task.Priority.MEDIUM,
            "deleted_at": None,
        },
    ]
    DELETED_TASK_DATA = {
        "title": "deleted task",
        "description": "deleted task description",
        "deleted_at": None,
    }
    OTHER_USER_TASK_DATA = [
        {
            "title": "other active task",
            "description": "abc active task description",
            "state": Task.State.ACTIVE,
            "priority": Task.Priority.MEDIUM,
            "deleted_at": None,
        },
        {
            "title": "other completed task",
            "description": "abc completed task description",
            "state": Task.State.COMPLETED,
            "priority": Task.Priority.MEDIUM,
            "deleted_at": None,
        },
        {
            "title": "other dismissed task",
            "description": "abc dismissed task description",
            "state": Task.State.DISMISSED,
            "priority": Task.Priority.MEDIUM,
            "deleted_at": None,
        },
        {
            "title": "other deleted task",
            "description": "deleted task description",
            "state": Task.State.ACTIVE,
            "priority": Task.Priority.MEDIUM,
            "deleted_at": None,
        },
    ]
    PROPERTY_DATA = {
        "name": "Hill House 4",
        "address": "Hill House address",
    }
    ISSUE_DATA = {"title": "Hill House issue"}

    def setUp(self):
        # Create deletion timestamps when the test runs, not when Python imports it.
        self.DELETED_TASK_DATA = self.DELETED_TASK_DATA.copy()
        self.DELETED_TASK_DATA["deleted_at"] = timezone.now()
        self.user = User.objects.create_user(
            email="alice@example.com",
            first_name="Alice",
            last_name="Smith",
            password=self.TEST_PASSWORD,
        )

        for task_data in self.TASK_DATA:
            Task.objects.create(
                user=self.user,
                **task_data,
            )

        Task.objects.create(
            user=self.user,
            **self.DELETED_TASK_DATA,
        )

    def create_tasks_user2(self, user):
        for task_data in self.OTHER_USER_TASK_DATA:
            task_data = task_data.copy()
            if task_data["title"] == "other deleted task":
                task_data["deleted_at"] = timezone.now()
            Task.objects.create(
                user=user,
                **task_data,
            )

    def create_user2(self):
        return User.objects.create_user(
            email="bob.jackson@example.com",
            first_name="Bob",
            last_name="Jackson",
            password=self.TEST_PASSWORD,
        )

    def create_issue(self, *, data, user):
        return Issue.objects.create(user=user, **data)

    def create_property(self, *, data, user):
        return Property.objects.create(user=user, **data)

    def create_task(self, *, data, user):
        return Task.objects.create(user=user, **data)

    def test_tasks_for_user_are_scopes_to_user_only(self):
        user2 = self.create_user2()
        self.create_tasks_user2(user=user2)

        tasks1 = tasks_for_user(user=self.user)
        tasks2 = tasks_for_user(user=user2)

        self.assertEqual(tasks1.count(), len(self.TASK_DATA))

        for t1 in tasks1:
            for t2 in tasks2:
                self.assertNotEqual(t1.title, t2.title)

    def test_tasks_for_user_filters_out_deleted_tasks(self):
        tasks = tasks_for_user(user=self.user)

        self.assertEqual(tasks.count(), len(self.TASK_DATA))

        deleted_task = Task.objects.get(title=self.DELETED_TASK_DATA["title"])

        for task in tasks:
            self.assertNotEqual(task.title, deleted_task.title)

    def test_filtered_tasks_for_user_scopes_on_search_by_title(self):
        tasks = list(filtered_tasks_for_user(user=self.user, search=self.TASK_DATA[1]["title"]))

        self.assertEqual(len(tasks), 1)

        self.assertEqual(tasks[0].title, self.TASK_DATA[1]["title"])

    def test_filtered_tasks_for_user_scopes_on_search_by_description(self):
        tasks = list(
            filtered_tasks_for_user(user=self.user, search=self.TASK_DATA[1]["description"])
        )

        self.assertEqual(len(tasks), 1)

        self.assertEqual(tasks[0].description, self.TASK_DATA[1]["description"])

    def test_filtered_tasks_for_user_scopes_on_search_by_issue(self):
        issue = self.create_issue(data=self.ISSUE_DATA, user=self.user)
        data = self.TASK_DATA[1].copy()
        data["issue"] = issue
        related_task = self.create_task(data=data, user=self.user)

        tasks = list(filtered_tasks_for_user(user=self.user, search=issue.title))

        self.assertEqual([related_task], tasks)

    def test_filtered_tasks_for_user_scopes_on_search_by_property_name(self):
        property_record = self.create_property(data=self.PROPERTY_DATA, user=self.user)
        data = self.TASK_DATA[1].copy()
        data["property"] = property_record
        related_task = self.create_task(data=data, user=self.user)

        tasks = list(filtered_tasks_for_user(user=self.user, search=property_record.name))

        self.assertEqual([related_task], tasks)

    def test_filtered_tasks_for_user_scopes_on_search_by_property_address(self):
        property_record = self.create_property(data=self.PROPERTY_DATA, user=self.user)
        data = self.TASK_DATA[1].copy()
        data["property"] = property_record
        related_task = self.create_task(data=data, user=self.user)

        tasks = list(filtered_tasks_for_user(user=self.user, search=property_record.address))

        self.assertEqual([related_task], tasks)

    def test_filtered_tasks_for_user_filters_by_state(self):
        tasks = list(
            filtered_tasks_for_user(
                user=self.user,
                state=Task.State.COMPLETED,
            )
        )

        self.assertEqual(
            [task.title for task in tasks],
            [
                self.TASK_DATA[2]["title"],
                self.TASK_DATA[3]["title"],
            ],
        )

    def test_filtered_tasks_for_user_filters_by_priority(self):
        tasks = list(
            filtered_tasks_for_user(
                user=self.user,
                priority=Task.Priority.URGENT,
            )
        )

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].title, self.TASK_DATA[2]["title"])

    def test_filtered_tasks_for_user_filters_by_scheduled_period(self):
        today = timezone.localdate()

        today_task = Task.objects.create(
            user=self.user,
            title="schedule fixture today",
            scheduled_date=today,
        )
        next_week_task = Task.objects.create(
            user=self.user,
            title="schedule fixture next week",
            scheduled_date=today + timedelta(days=3),
        )
        Task.objects.create(
            user=self.user,
            title="schedule fixture later",
            scheduled_date=today + timedelta(days=10),
        )
        past_task = Task.objects.create(
            user=self.user,
            title="schedule fixture past",
            scheduled_date=today - timedelta(days=1),
        )
        unscheduled_task = Task.objects.create(
            user=self.user,
            title="schedule fixture unscheduled",
        )

        expected_tasks = {
            "today": [today_task],
            "next_7_days": [today_task, next_week_task],
            "past": [past_task],
            "unscheduled": [unscheduled_task],
        }

        for scheduled_period, expected in expected_tasks.items():
            with self.subTest(scheduled_period=scheduled_period):
                tasks = list(
                    filtered_tasks_for_user(
                        user=self.user,
                        search="schedule fixture",
                        scheduled_period=scheduled_period,
                    )
                )

                self.assertCountEqual(tasks, expected)

    def test_filtered_tasks_for_user_filters_by_deadline_period(self):
        today = timezone.localdate()

        overdue_task = Task.objects.create(
            user=self.user,
            title="deadline fixture overdue",
            completion_deadline=today - timedelta(days=1),
        )
        Task.objects.create(
            user=self.user,
            title="deadline fixture completed overdue",
            state=Task.State.COMPLETED,
            completion_deadline=today - timedelta(days=1),
        )
        today_task = Task.objects.create(
            user=self.user,
            title="deadline fixture today",
            completion_deadline=today,
        )
        next_week_task = Task.objects.create(
            user=self.user,
            title="deadline fixture next week",
            completion_deadline=today + timedelta(days=3),
        )
        Task.objects.create(
            user=self.user,
            title="deadline fixture later",
            completion_deadline=today + timedelta(days=10),
        )
        no_deadline_task = Task.objects.create(
            user=self.user,
            title="deadline fixture none",
        )

        expected_tasks = {
            "overdue": [overdue_task],
            "today": [today_task],
            "next_7_days": [today_task, next_week_task],
            "no_deadline": [no_deadline_task],
        }

        for deadline_period, expected in expected_tasks.items():
            with self.subTest(deadline_period=deadline_period):
                tasks = list(
                    filtered_tasks_for_user(
                        user=self.user,
                        search="deadline fixture",
                        deadline_period=deadline_period,
                    )
                )

                self.assertCountEqual(tasks, expected)

    def test_all_supported_sort_options_return_expected_order(self):
        today = timezone.localdate()

        alpha = Task.objects.create(
            user=self.user,
            title="sort fixture alpha",
            priority=Task.Priority.LOW,
            scheduled_date=today + timedelta(days=1),
            completion_deadline=today + timedelta(days=3),
        )
        bravo = Task.objects.create(
            user=self.user,
            title="sort fixture bravo",
            priority=Task.Priority.HIGH,
            scheduled_date=None,
            completion_deadline=today + timedelta(days=1),
        )
        charlie = Task.objects.create(
            user=self.user,
            title="sort fixture charlie",
            priority=Task.Priority.MEDIUM,
            scheduled_date=today + timedelta(days=3),
            completion_deadline=None,
        )

        now = timezone.now()
        Task.objects.filter(pk=alpha.pk).update(created_at=now - timedelta(days=3))
        Task.objects.filter(pk=bravo.pk).update(created_at=now - timedelta(days=2))
        Task.objects.filter(pk=charlie.pk).update(created_at=now - timedelta(days=1))

        expected_orders = {
            "title": [alpha.pk, bravo.pk, charlie.pk],
            "-title": [charlie.pk, bravo.pk, alpha.pk],
            "created_at": [alpha.pk, bravo.pk, charlie.pk],
            "-created_at": [charlie.pk, bravo.pk, alpha.pk],
            "priority": [alpha.pk, charlie.pk, bravo.pk],
            "-priority": [bravo.pk, charlie.pk, alpha.pk],
            "scheduled_date": [alpha.pk, charlie.pk, bravo.pk],
            "-scheduled_date": [charlie.pk, alpha.pk, bravo.pk],
            "completion_deadline": [bravo.pk, alpha.pk, charlie.pk],
            "-completion_deadline": [alpha.pk, bravo.pk, charlie.pk],
        }

        for sort, expected_order in expected_orders.items():
            with self.subTest(sort=sort):
                tasks = filtered_tasks_for_user(
                    user=self.user,
                    search="sort fixture",
                    sort=sort,
                )
                actual_order = [task.pk for task in tasks]

                self.assertEqual(actual_order, expected_order)
