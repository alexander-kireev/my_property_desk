"""Property work: combine direct and Issue-linked records, then filter, order and page."""

from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone

RELATED_RECORDS_PER_PAGE = 25


def _title_order(entry):
    return (entry["item"].title.casefold(), entry["kind"], entry["item"].pk)


def _recent_order(entry):
    item = entry["item"]
    return (item.terminated_at or item.created_at, item.pk)


def _past_order(entry):
    item = entry["item"]
    return (timezone.localdate(item.terminated_at or item.created_at), entry["kind"], item.pk)


def related_records_context(request, property_record):
    from event.models import Event
    from issue.models import Issue
    from task.models import Task

    issues = Issue.objects.filter(
        user=request.user,
        property=property_record,
        deleted_at__isnull=True,
    )
    tasks = (
        Task.objects.filter(
            user=request.user,
            deleted_at__isnull=True,
        )
        .filter(Q(property=property_record) | Q(issue__property=property_record))
        .select_related("issue")
        .distinct()
    )
    events = Event.objects.filter(
        user=request.user,
        property=property_record,
        deleted_at__isnull=True,
    )

    record_type = request.GET.get("records_type", "all")
    if record_type not in ("all", "issue", "task", "event"):
        record_type = "all"
    record_scope = request.GET.get("records_scope", "current")
    if record_scope not in ("current", "past", "all"):
        record_scope = "current"
    record_sort = request.GET.get("records_sort", "date")
    if record_sort not in ("date", "recent", "title"):
        record_sort = "date"
    record_search = request.GET.get("records_search", "").strip()

    today = timezone.localdate()
    records = []
    for kind, queryset, active_state in (
        ("issue", issues, Issue.State.ACTIVE),
        ("task", tasks, Task.State.ACTIVE),
        ("event", events, Event.State.SCHEDULED),
    ):
        if record_type not in ("all", kind):
            continue
        if record_scope == "current":
            queryset = queryset.filter(state=active_state)
        elif record_scope == "past":
            queryset = queryset.exclude(state=active_state)
        if record_search:
            queryset = queryset.filter(
                Q(title__icontains=record_search) | Q(description__icontains=record_search)
            )
        for item in queryset:
            current = item.state == active_state
            if kind == "issue":
                date = item.resolution_deadline
            elif kind == "task":
                date = item.completion_deadline
            else:
                date = item.scheduled_date
            records.append({"kind": kind, "item": item, "current": current, "date": date})

    def date_order(entry):
        return (entry["date"] is None, entry["date"] or today, entry["kind"], entry["item"].pk)

    if record_sort == "title":
        records.sort(key=_title_order)
    elif record_sort == "recent":
        records.sort(key=_recent_order, reverse=True)
    elif record_scope == "past":
        records.sort(key=_past_order)
    else:
        records.sort(key=date_order)

    record_parameters = {
        "records_type": record_type,
        "records_scope": record_scope,
        "records_sort": record_sort,
    }
    if record_search:
        record_parameters["records_search"] = record_search
    record_page = Paginator(records, RELATED_RECORDS_PER_PAGE).get_page(
        request.GET.get("records_page")
    )

    return {
        "related_page": record_page,
        "related_type": record_type,
        "related_scope": record_scope,
        "related_sort": record_sort,
        "related_search": record_search,
        "related_has_filters": bool(
            record_type != "all" or record_scope != "current" or record_search
        ),
        "related_query": urlencode(record_parameters),
    }
