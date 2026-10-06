"""Owner-scoped Dashboard queries and the JSON shapes consumed by the browser."""

from django.db.models import Count, Q
from django.http import JsonResponse
from django.utils import timezone

from event.models import Event
from issue.models import Issue
from note.selectors import general_notes_for_user
from property.models import Property
from task.models import Task


def records_for_user(user, kind):
    model = {"task": Task, "issue": Issue, "event": Event}.get(kind)
    return model.objects.filter(user=user, deleted_at__isnull=True) if model else None


def record_data(record, kind):
    property_record = record.property if record.property_id else None
    if kind == "task" and record.issue_id:
        property_record = record.issue.property
    data = {
        "id": record.pk,
        "kind": kind,
        "title": record.title,
        "description": record.description,
        "state": record.state,
        "property": property_record.name if property_record else "",
        "property_id": record.property_id,
        "property_deleted": bool(property_record and property_record.deleted_at),
        "date": record.scheduled_date.isoformat()
        if kind != "issue" and record.scheduled_date
        else "",
    }
    if kind == "task":
        data.update(
            priority=record.get_priority_display(),
            priority_id=record.priority,
            due=record.completion_deadline.isoformat() if record.completion_deadline else "",
            issue_id=record.issue_id,
            issue_title=record.issue.title if record.issue_id else "",
            issue_deleted=bool(record.issue_id and record.issue.deleted_at),
        )
    elif kind == "issue":
        data.update(
            priority=record.get_priority_display(),
            priority_id=record.priority,
            due=record.resolution_deadline.isoformat() if record.resolution_deadline else "",
            active_linked_tasks=getattr(record, "active_linked_tasks", 0),
            linked_tasks=getattr(record, "linked_tasks", 0),
        )
    else:
        data.update(
            all_day=record.all_day,
            start_time=record.start_time.strftime("%H:%M") if record.start_time else "",
            end_time=record.end_time.strftime("%H:%M") if record.end_time else "",
            user_participation_required=record.user_participation_required,
            user_presence_required=record.user_presence_required,
        )
    return data


def dashboard_data(request):
    records = {}
    for kind, state in (
        ("task", Task.State.ACTIVE),
        ("issue", Issue.State.ACTIVE),
        ("event", Event.State.SCHEDULED),
    ):
        queryset = records_for_user(request.user, kind).filter(state=state)
        if kind == "issue":
            queryset = queryset.annotate(
                active_linked_tasks=Count(
                    "tasks",
                    filter=Q(
                        tasks__user=request.user,
                        tasks__deleted_at__isnull=True,
                        tasks__state=Task.State.ACTIVE,
                    ),
                ),
                linked_tasks=Count(
                    "tasks", filter=Q(tasks__user=request.user, tasks__deleted_at__isnull=True)
                ),
            )
        queryset = (
            queryset.select_related("property", "issue__property")
            if kind == "task"
            else queryset.select_related("property")
        )
        records[kind] = [record_data(item, kind) for item in queryset.order_by("pk")]
    notes = [
        {
            "id": item.pk,
            "content": item.content,
            "created": timezone.localtime(item.created_at).strftime("%d %b %Y, %H:%M"),
        }
        for item in general_notes_for_user(user=request.user)
    ]
    properties = list(
        Property.objects.filter(
            user=request.user, state=Property.State.ACTIVE, deleted_at__isnull=True
        )
        .order_by("name")
        .values("id", "name")
    )
    issues = list(
        Issue.objects.filter(user=request.user, state=Issue.State.ACTIVE, deleted_at__isnull=True)
        .order_by("title")
        .values("id", "title")
    )
    return JsonResponse(
        {
            "today": timezone.localdate().isoformat(),
            "records": records,
            "notes": notes,
            "properties": properties,
            "issues": issues,
        }
    )
