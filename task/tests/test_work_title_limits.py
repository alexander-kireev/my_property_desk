"""Pure display or field contracts; no database setup required."""

from django.core.exceptions import ValidationError
from django.test import SimpleTestCase

from event.models import Event
from issue.models import Issue
from task.models import Task


class WorkTitleLimitTests(SimpleTestCase):
    def test_all_work_models_enforce_the_dashboard_title_limit(self):
        for model in (Task, Issue, Event):
            with self.subTest(model=model.__name__):
                title = model._meta.get_field("title")
                title.clean("A" * 75, model())
                with self.assertRaises(ValidationError):
                    title.clean("A" * 76, model())
