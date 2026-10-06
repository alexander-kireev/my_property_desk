"""Task writes. Lifecycle actions refresh the passed object and set action_changed for callers."""

from django.db import transaction
from django.utils import timezone

from .models import Task


def create_task(
    *, user, property, issue, priority, title, description, scheduled_date, completion_deadline
):
    return Task.objects.create(
        user=user,
        property=property,
        issue=issue,
        priority=priority,
        title=title,
        description=description,
        scheduled_date=scheduled_date,
        completion_deadline=completion_deadline,
    )


def update_task(
    *, task, property, issue, priority, title, description, scheduled_date, completion_deadline
):
    task.property = property
    task.issue = issue
    task.priority = priority
    task.title = title
    task.description = description
    task.scheduled_date = scheduled_date
    task.completion_deadline = completion_deadline
    task.save(
        update_fields=[
            "property",
            "issue",
            "priority",
            "title",
            "description",
            "scheduled_date",
            "completion_deadline",
        ]
    )

    return task


def _refresh_lifecycle(task):
    """Refresh the passed object under a row lock; callers own the transaction."""
    current = Task.objects.select_for_update().get(pk=task.pk, user_id=task.user_id)
    task.state = current.state
    task.terminated_at = current.terminated_at
    task.deleted_at = current.deleted_at
    task.action_changed = False


@transaction.atomic
def dismiss_task(*, task):
    _refresh_lifecycle(task)
    if task.deleted_at is not None or task.state != Task.State.ACTIVE:
        return task

    task.state = Task.State.DISMISSED
    task.terminated_at = timezone.now()
    task.save(update_fields=["state", "terminated_at"])

    task.action_changed = True
    return task


@transaction.atomic
def complete_task(*, task):
    _refresh_lifecycle(task)
    if task.deleted_at is not None or task.state != Task.State.ACTIVE:
        return task

    task.state = Task.State.COMPLETED
    task.terminated_at = timezone.now()
    task.save(update_fields=["state", "terminated_at"])

    task.action_changed = True
    return task


@transaction.atomic
def reactivate_task(*, task):
    _refresh_lifecycle(task)
    if task.deleted_at is not None or task.state == Task.State.ACTIVE:
        return task

    task.state = Task.State.ACTIVE
    task.terminated_at = None
    task.save(update_fields=["state", "terminated_at"])

    task.action_changed = True
    return task


@transaction.atomic
def delete_task(*, task):
    _refresh_lifecycle(task)
    if task.deleted_at is not None:
        return task

    task.deleted_at = timezone.now()
    task.save(update_fields=["deleted_at"])

    task.action_changed = True
    return task


def dismiss_active_tasks_for_issue(*, issue, terminated_at=None):
    return Task.objects.filter(
        user=issue.user,
        issue=issue,
        state=Task.State.ACTIVE,
        deleted_at__isnull=True,
    ).update(
        state=Task.State.DISMISSED,
        terminated_at=terminated_at or timezone.now(),
    )


def delete_tasks_for_issue(*, issue, deleted_at=None):
    return Task.objects.filter(
        user=issue.user,
        issue=issue,
        deleted_at__isnull=True,
    ).update(deleted_at=deleted_at or timezone.now())
