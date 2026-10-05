from unittest.mock import patch

from django.test import SimpleTestCase

from issue.models import Issue
from property.models import Property
from task.forms import TaskForm
from task.models import Task


class RelationshipDisplayTests(SimpleTestCase):
    def selection(self, **kwargs):
        with (
            patch.object(Property.objects, "filter", return_value=Property.objects.none()),
            patch.object(Issue.objects, "filter", return_value=Issue.objects.none()),
        ):
            form = TaskForm(user=None, **kwargs)
        return {name for name, selected in form.relationship_selection.items() if selected}

    def test_bound_choice_is_preserved_instead_of_existing_parent(self):
        for choice in ("standalone", "property", "issue"):
            with self.subTest(choice=choice):
                self.assertEqual(
                    self.selection(data={"relationship_type": choice}, instance=Task(issue_id=2)),
                    {choice},
                )

    def test_empty_and_incomplete_submissions_preserve_existing_markers(self):
        self.assertEqual(self.selection(data={}), {"standalone"})
        self.assertEqual(self.selection(data={"property": "1"}), set())
        self.assertEqual(self.selection(data={"issue": "2"}), set())
        self.assertEqual(self.selection(data={"relationship_type": "invalid"}), set())

    def test_unbound_initial_and_instance_parents(self):
        self.assertEqual(self.selection(), {"standalone"})
        self.assertEqual(self.selection(initial={"property": 1}), {"property"})
        self.assertEqual(self.selection(instance=Task(property_id=1)), {"property"})
        self.assertEqual(self.selection(instance=Task(issue_id=2)), {"issue"})

    def test_conflicting_initial_and_instance_values_are_not_silently_normalised(self):
        self.assertEqual(
            self.selection(initial={"property": 1}, instance=Task(issue_id=2)),
            {"property", "issue"},
        )
