from datetime import date

from django.core import signing
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import ensure_csrf_cookie

from event.forms import EventContactForm, EventForm
from event.models import Event
from event.services import cancel_event, create_event, delete_event, mark_event_occurred, update_event
from issue.forms import IssueForm
from issue.models import Issue
from issue.services import create_issue, delete_issue, resolve_issue, update_issue
from note.forms import NoteForm
from note.selectors import general_notes_for_user
from note.services import create_note, delete_note, remember_deleted_note, undo_deleted_note, update_note
from property.models import Property
from task.forms import TaskForm
from task.models import Task
from task.services import complete_task, create_task, delete_task, update_task


def home_view(request):
    return render(request, "pages/home.html")


def about_us_view(request):
    return render(request, "pages/about_us.html")


def contact_us_view(request):
    return render(request, "pages/contact_us.html")


@login_required
@ensure_csrf_cookie
def dashboard_view(request):
    return render(request, "pages/dashboard.html", {
        "add_event_form": EventForm(user=request.user),
        "initial_contacts_form": EventContactForm(user=request.user),
    })


def _records_for_user(user, kind):
    model = {"task": Task, "issue": Issue, "event": Event}.get(kind)
    return model.objects.filter(user=user, deleted_at__isnull=True) if model else None


def _record_data(record, kind):
    property_record = record.property if record.property_id else None
    if kind == "task" and record.issue_id:
        property_record = record.issue.property
    data = {
        "id": record.pk, "kind": kind, "title": record.title,
        "description": record.description, "state": record.state,
        "property": property_record.name if property_record else "",
        "property_id": record.property_id,
        "property_deleted": bool(property_record and property_record.deleted_at),
        "date": record.scheduled_date.isoformat() if kind != "issue" and record.scheduled_date else "",
    }
    if kind == "task":
        data.update(priority=record.get_priority_display(), priority_id=record.priority,
                    due=record.completion_deadline.isoformat() if record.completion_deadline else "",
                    issue_id=record.issue_id,
                    issue_title=record.issue.title if record.issue_id else "",
                    issue_deleted=bool(record.issue_id and record.issue.deleted_at))
    elif kind == "issue":
        data.update(priority=record.get_priority_display(), priority_id=record.priority,
                    due=record.resolution_deadline.isoformat() if record.resolution_deadline else "",
                    active_linked_tasks=getattr(record, "active_linked_tasks", 0),
                    linked_tasks=getattr(record, "linked_tasks", 0))
    else:
        data.update(all_day=record.all_day,
                    start_time=record.start_time.strftime("%H:%M") if record.start_time else "",
                    end_time=record.end_time.strftime("%H:%M") if record.end_time else "",
                    user_participation_required=record.user_participation_required,
                    user_presence_required=record.user_presence_required)
    return data


@login_required
@require_GET
def dashboard_data_view(request):
    records = {}
    for kind, state in (("task", Task.State.ACTIVE), ("issue", Issue.State.ACTIVE),
                        ("event", Event.State.SCHEDULED)):
        queryset = _records_for_user(request.user, kind).filter(state=state)
        if kind == "issue":
            queryset = queryset.annotate(
                active_linked_tasks=Count("tasks", filter=Q(tasks__user=request.user, tasks__deleted_at__isnull=True, tasks__state=Task.State.ACTIVE)),
                linked_tasks=Count("tasks", filter=Q(tasks__user=request.user, tasks__deleted_at__isnull=True)),
            )
        queryset = queryset.select_related("property", "issue__property") if kind == "task" else queryset.select_related("property")
        records[kind] = [_record_data(item, kind) for item in queryset.order_by("pk")]
    notes = [{"id": item.pk, "content": item.content,
              "created": timezone.localtime(item.created_at).strftime("%d %b %Y, %H:%M")}
             for item in general_notes_for_user(user=request.user)]
    properties = list(Property.objects.filter(user=request.user, state=Property.State.ACTIVE,
                                               deleted_at__isnull=True).order_by("name").values("id", "name"))
    issues = list(Issue.objects.filter(user=request.user, state=Issue.State.ACTIVE,
                                       deleted_at__isnull=True).order_by("title").values("id", "title"))
    return JsonResponse({"today": timezone.localdate().isoformat(), "records": records,
                         "notes": notes, "properties": properties, "issues": issues})


@login_required
@require_POST
def dashboard_action_view(request):
    action, kind = request.POST.get("action"), request.POST.get("kind")
    record_id = request.POST.get("id", "")
    if action != "add" and (not record_id.isdecimal() or int(record_id) < 1):
        return JsonResponse({"error": "Record not found."}, status=404)
    if kind == "note":
        if action == "undo":
            restored = undo_deleted_note(request=request, token=request.POST.get("token", ""), general_only=True, note_id=int(record_id))
            if restored is None:
                return JsonResponse({"error": "This note can no longer be undone."}, status=409)
            return JsonResponse({"ok": True, "id": restored.pk, "changed": True})
        if action == "add":
            form = NoteForm(request.POST)
            if not form.is_valid():
                return JsonResponse({"errors": form.errors}, status=400)
            note = create_note(user=request.user, content=form.cleaned_data["content"])
        else:
            note = general_notes_for_user(user=request.user).filter(pk=record_id).first()
            if note is None:
                return JsonResponse({"error": "Note not found."}, status=404)
            if action == "delete":
                token = remember_deleted_note(request=request, note=note)
                delete_note(note=note)
                return JsonResponse({"ok": True, "undo_token": token})
            if action != "edit":
                return JsonResponse({"error": "Unknown action."}, status=400)
            previous_content = note.content
            form = NoteForm(request.POST, instance=note)
            if not form.is_valid():
                return JsonResponse({"errors": form.errors}, status=400)
            if form.cleaned_data["content"] == previous_content:
                return JsonResponse({"ok": True, "id": note.pk, "changed": False})
            update_note(note=note, content=form.cleaned_data["content"])
        return JsonResponse({"ok": True, "id": note.pk, "changed": True})

    queryset = _records_for_user(request.user, kind)
    if queryset is None:
        return JsonResponse({"error": "Unknown record type."}, status=400)
    record = None
    if action == "undo":
        try:
            # The UI's ten-second opportunity pauses on hover/focus; leave room
            # for that pause while the signed token remains owner/state-bound.
            original = signing.loads(request.POST.get("token", ""), salt="dashboard-undo", max_age=3600)
        except signing.BadSignature:
            return JsonResponse({"error": "Undo has expired. Refresh to see the current record."}, status=409)
        if (original.get("user") != request.user.pk or original.get("kind") != kind
                or original.get("id") != int(record_id)):
            return JsonResponse({"error": "This Undo does not match the record."}, status=409)
        with transaction.atomic():
            record = queryset.select_for_update().filter(pk=record_id).first()
            if (record is None or record.state != original.get("state")
                    or not record.terminated_at
                    or record.terminated_at.isoformat() != original.get("terminated_at")):
                return JsonResponse({"error": "This record changed again and can no longer be undone."}, status=409)
            record.state = original["previous_state"]
            record.terminated_at = None
            record.save(update_fields=["state", "terminated_at"])
        return JsonResponse({"ok": True, "id": record.pk, "changed": True})
    if action != "add":
        record = queryset.filter(pk=record_id).first()
        if record is None:
            return JsonResponse({"error": "Record not found."}, status=404)

    if action == "unschedule":
        if kind != "task" or record.state != Task.State.ACTIVE:
            return JsonResponse({"error": "This task cannot be unscheduled."}, status=400)
        if record.scheduled_date is None:
            return JsonResponse({"ok": True, "id": record.pk, "changed": False})
        record.scheduled_date = None
        record.save(update_fields=["scheduled_date"])
    elif action == "clear_deadline":
        if kind not in ("task", "issue") or record.state != "active":
            return JsonResponse({"error": "This deadline cannot be removed."}, status=400)
        field = "completion_deadline" if kind == "task" else "resolution_deadline"
        if getattr(record, field) is None:
            return JsonResponse({"ok": True, "id": record.pk, "changed": False})
        setattr(record, field, None)
        record.save(update_fields=[field])
    elif action == "date":
        if kind not in ("task", "event") or record.state not in ("active", "scheduled"):
            return JsonResponse({"error": "This record cannot be scheduled."}, status=400)
        try:
            new_date = date.fromisoformat(request.POST.get("date", ""))
        except (TypeError, ValueError):
            return JsonResponse({"error": "Choose a valid date."}, status=400)
        if new_date == record.scheduled_date:
            return JsonResponse({"ok": True, "id": record.pk, "changed": False})
        if kind == "event":
            data = {"title": record.title, "description": record.description,
                    "property": record.property_id or "", "scheduled_date": new_date.isoformat(),
                    "all_day": "on" if record.all_day else "",
                    "start_time": record.start_time.strftime("%H:%M") if record.start_time else "",
                    "end_time": record.end_time.strftime("%H:%M") if record.end_time else "",
                    "user_participation_required": "on" if record.user_participation_required else "",
                    "user_presence_required": "on" if record.user_presence_required else ""}
            form = EventForm(data, user=request.user, instance=record)
            if not form.is_valid():
                return JsonResponse({"errors": form.errors}, status=400)
        record.scheduled_date = new_date
        record.save(update_fields=["scheduled_date"])
    elif action == "deadline":
        if kind not in ("task", "issue") or record.state != "active":
            return JsonResponse({"error": "This deadline cannot be moved."}, status=400)
        try:
            new_date = date.fromisoformat(request.POST.get("date", ""))
        except (TypeError, ValueError):
            return JsonResponse({"error": "Choose a valid date."}, status=400)
        field = "completion_deadline" if kind == "task" else "resolution_deadline"
        if new_date == getattr(record, field):
            return JsonResponse({"ok": True, "id": record.pk, "changed": False})
        setattr(record, field, new_date)
        record.save(update_fields=[field])
    elif action in ("add", "edit"):
        form_class = {"task": TaskForm, "issue": IssueForm, "event": EventForm}[kind]
        tracked_fields = {
            "task": ("property", "issue", "priority", "title", "description", "scheduled_date", "completion_deadline"),
            "issue": ("property", "priority", "title", "description", "resolution_deadline"),
            "event": ("property", "title", "description", "scheduled_date", "all_day", "start_time", "end_time",
                      "user_participation_required", "user_presence_required"),
        }[kind]
        previous_values = {name: getattr(record, name) for name in tracked_fields} if record else None
        form = form_class(request.POST, user=request.user, instance=record)
        if not form.is_valid():
            return JsonResponse({"errors": form.errors}, status=400)
        contacts_form = EventContactForm(request.POST, user=request.user) if kind == "event" and action == "add" else None
        if contacts_form is not None and not contacts_form.is_valid():
            return JsonResponse({"errors": contacts_form.errors}, status=400)
        values = form.cleaned_data
        if kind == "task":
            fields = {name: values[name] for name in tracked_fields}
            if record and all(previous_values[name] == value for name, value in fields.items()):
                return JsonResponse({"ok": True, "id": record.pk, "changed": False})
            record = update_task(task=record, **fields) if record else create_task(user=request.user, **fields)
        elif kind == "issue":
            fields = {name: values[name] for name in tracked_fields}
            if record and all(previous_values[name] == value for name, value in fields.items()):
                return JsonResponse({"ok": True, "id": record.pk, "changed": False})
            record = update_issue(issue=record, **fields) if record else create_issue(user=request.user, **fields)
        else:
            fields = {name: values[name] for name in tracked_fields}
            if record and all(previous_values[name] == value for name, value in fields.items()):
                return JsonResponse({"ok": True, "id": record.pk, "changed": False})
            record = update_event(event=record, **fields) if record else create_event(
                user=request.user, contacts=contacts_form.cleaned_data["contacts"], **fields,
            )
    elif action == "finish":
        expected = {"task": Task.State.ACTIVE, "issue": Issue.State.ACTIVE,
                    "event": Event.State.SCHEDULED}[kind]
        if record.state != expected:
            return JsonResponse({"error": "This record is no longer available for that action."}, status=409)
        if kind == "task":
            complete_task(task=record)
        elif kind == "issue":
            confirmed = request.POST.get("confirm_linked_tasks") == "yes"
            with transaction.atomic():
                record = queryset.select_for_update().get(pk=record_id)
                if record.state != Issue.State.ACTIVE:
                    return JsonResponse({"error": "This issue is no longer active."}, status=409)
                active_linked = Task.objects.filter(user=request.user, issue=record, deleted_at__isnull=True, state=Task.State.ACTIVE).exists()
                if active_linked and not confirmed:
                    return JsonResponse({"error": "Linked tasks need review before resolving this issue."}, status=409)
                resolve_issue(issue=record, dismiss_linked_tasks=confirmed and request.POST.get("affect_linked_tasks") == "yes")
        else:
            mark_event_occurred(event=record)
    elif action == "cancel" and kind == "event":
        if record.state != Event.State.SCHEDULED:
            return JsonResponse({"error": "This event is no longer scheduled."}, status=409)
        cancel_event(event=record)
    elif action == "delete":
        if kind == "task":
            delete_task(task=record)
        elif kind == "issue":
            delete_issue(issue=record, delete_linked_tasks=request.POST.get("affect_linked_tasks") == "yes")
        else:
            delete_event(event=record)
    else:
        return JsonResponse({"error": "Unknown action."}, status=400)
    result = {"ok": True, "id": record.pk, "changed": True}
    if action == "finish" and not (kind == "issue" and request.POST.get("confirm_linked_tasks") == "yes"):
        result["undo_token"] = signing.dumps({
            "user": request.user.pk, "kind": kind, "id": record.pk,
            "previous_state": expected, "state": record.state,
            "terminated_at": record.terminated_at.isoformat(),
        }, salt="dashboard-undo")
    return JsonResponse(result)
