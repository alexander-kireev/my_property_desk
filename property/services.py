"""Property cascades lock the parent. Results expose action_changed and affected_work; counts reflect the rows changed by this call."""

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import Property


def create_property(*, user, name, description="", address=""):
    return Property.objects.create(
        user=user,
        name=name,
        description=description,
        address=address,
    )


def update_property(*, property_record, name, description="", address=""):
    property_record.name = name
    property_record.description = description
    property_record.address = address
    property_record.save(update_fields=["name", "description", "address"])

    return property_record


def related_work_counts(*, property_record):
    from event.models import Event
    from issue.models import Issue
    from task.models import Task

    issues = Issue.objects.filter(
        user=property_record.user, property=property_record, deleted_at__isnull=True
    )
    tasks = (
        Task.objects.filter(user=property_record.user, deleted_at__isnull=True)
        .filter(Q(property=property_record) | Q(issue__property=property_record))
        .distinct()
    )
    events = Event.objects.filter(
        user=property_record.user, property=property_record, deleted_at__isnull=True
    )
    return {
        "issues_all": issues.count(),
        "issues_active": issues.filter(state=Issue.State.ACTIVE).count(),
        "tasks_all": tasks.count(),
        "tasks_active": tasks.filter(state=Task.State.ACTIVE).count(),
        "events_all": events.count(),
        "events_scheduled": events.filter(state=Event.State.SCHEDULED).count(),
    }


@transaction.atomic
def deactivate_property(
    *, property_record, cancel_events=False, dismiss_issues=False, dismiss_tasks=False
):
    locked = Property.objects.select_for_update().get(
        pk=property_record.pk, user=property_record.user
    )
    property_record.affected_work = {"events": 0, "issues": 0, "tasks": 0}
    property_record.action_changed = False
    if locked.deleted_at is not None or locked.state == Property.State.DEACTIVATED:
        return property_record

    from event.models import Event
    from issue.models import Issue
    from task.models import Task

    now = timezone.now()
    if cancel_events:
        property_record.affected_work["events"] = Event.objects.filter(
            user=property_record.user,
            property=property_record,
            deleted_at__isnull=True,
            state=Event.State.SCHEDULED,
        ).update(state=Event.State.CANCELLED, terminated_at=now)
    if dismiss_issues:
        property_record.affected_work["issues"] = Issue.objects.filter(
            user=property_record.user,
            property=property_record,
            deleted_at__isnull=True,
            state=Issue.State.ACTIVE,
        ).update(state=Issue.State.DISMISSED, terminated_at=now)
    if dismiss_tasks:
        task_ids = (
            Task.objects.filter(
                user=property_record.user, deleted_at__isnull=True, state=Task.State.ACTIVE
            )
            .filter(Q(property=property_record) | Q(issue__property=property_record))
            .values("pk")
        )
        property_record.affected_work["tasks"] = Task.objects.filter(pk__in=task_ids).update(
            state=Task.State.DISMISSED, terminated_at=now
        )
    property_record.state = Property.State.DEACTIVATED
    property_record.save(update_fields=["state"])
    property_record.action_changed = True

    return property_record


def reactivate_property(*, property_record):
    if property_record.state == Property.State.ACTIVE:
        return property_record

    property_record.state = Property.State.ACTIVE
    property_record.save(update_fields=["state"])

    return property_record


@transaction.atomic
def delete_property(
    *, property_record, delete_events=False, delete_issues=False, delete_tasks=False
):
    locked = Property.objects.select_for_update().get(
        pk=property_record.pk, user=property_record.user
    )
    property_record.affected_work = {"events": 0, "issues": 0, "tasks": 0}
    property_record.action_changed = False
    if locked.deleted_at is not None:
        return property_record

    from event.models import Event
    from issue.models import Issue
    from task.models import Task

    now = timezone.now()
    if delete_events:
        property_record.affected_work["events"] = Event.objects.filter(
            user=property_record.user,
            property=property_record,
            deleted_at__isnull=True,
        ).update(deleted_at=now)
    if delete_issues:
        property_record.affected_work["issues"] = Issue.objects.filter(
            user=property_record.user,
            property=property_record,
            deleted_at__isnull=True,
        ).update(deleted_at=now)
    if delete_tasks:
        task_ids = (
            Task.objects.filter(user=property_record.user, deleted_at__isnull=True)
            .filter(Q(property=property_record) | Q(issue__property=property_record))
            .values("pk")
        )
        property_record.affected_work["tasks"] = Task.objects.filter(pk__in=task_ids).update(
            deleted_at=now
        )
    property_record.deleted_at = now
    property_record.save(update_fields=["deleted_at"])
    property_record.action_changed = True

    return property_record
