"""Dashboard action families. Keep JSON responses stable for the browser controller."""

from datetime import date

from django.core import signing
from django.db import transaction
from django.http import JsonResponse

from config.feedback import form_values_changed, snapshot_form_values
from event.forms import EventContactForm, EventForm
from event.models import Event
from event.services import (
    cancel_event,
    create_event,
    delete_event,
    mark_event_occurred,
    update_event,
)
from issue.forms import IssueForm
from issue.models import Issue
from issue.services import create_issue, delete_issue, resolve_issue, update_issue
from note.forms import NoteForm
from note.selectors import general_notes_for_user
from note.services import (
    create_note,
    delete_note,
    remember_deleted_note,
    undo_deleted_note,
    update_note,
)
from task.forms import TaskForm
from task.models import Task
from task.services import complete_task, create_task, delete_task, update_task

from .data import records_for_user
from .undo import undo_work


def dashboard_action(request):
    action, kind = request.POST.get("action"), request.POST.get("kind")
    record_id = request.POST.get("id", "")
    if action != "add" and (not record_id.isdecimal() or int(record_id) < 1):
        return JsonResponse({"error": "Record not found."}, status=404)
    if kind == "note":
        return _note_action(request, action, record_id)

    queryset = records_for_user(request.user, kind)
    if queryset is None:
        return JsonResponse({"error": "Unknown record type."}, status=400)
    record = None
    if action == "undo":
        return undo_work(request, queryset, kind, record_id)
    if action != "add":
        record = queryset.filter(pk=record_id).first()
        if record is None:
            return JsonResponse({"error": "Record not found."}, status=404)

    if action in ("unschedule", "clear_deadline", "date", "deadline"):
        return _change_dates(request, action, kind, record)
    elif action in ("add", "edit"):
        return _save_record(request, action, kind, record)
    elif action == "finish":
        expected = {
            "task": Task.State.ACTIVE,
            "issue": Issue.State.ACTIVE,
            "event": Event.State.SCHEDULED,
        }[kind]
        if record.state != expected:
            return JsonResponse(
                {"error": "This record is no longer available for that action."}, status=409
            )
        if kind == "task":
            complete_task(task=record)
        elif kind == "issue":
            confirmed = request.POST.get("confirm_linked_tasks") == "yes"
            with transaction.atomic():
                record = queryset.select_for_update().get(pk=record_id)
                if record.state != Issue.State.ACTIVE:
                    return JsonResponse({"error": "This issue is no longer active."}, status=409)
                active_linked = Task.objects.filter(
                    user=request.user,
                    issue=record,
                    deleted_at__isnull=True,
                    state=Task.State.ACTIVE,
                ).exists()
                if active_linked and not confirmed:
                    return JsonResponse(
                        {"error": "Linked tasks need review before resolving this issue."},
                        status=409,
                    )
                resolve_issue(
                    issue=record,
                    dismiss_linked_tasks=confirmed
                    and request.POST.get("affect_linked_tasks") == "yes",
                )
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
            delete_issue(
                issue=record, delete_linked_tasks=request.POST.get("affect_linked_tasks") == "yes"
            )
        else:
            delete_event(event=record)
    else:
        return JsonResponse({"error": "Unknown action."}, status=400)
    # A concurrent lifecycle action may win after the initial lookup.
    # In that case do not issue an Undo token for somebody else's transition.
    if not record.action_changed:
        return JsonResponse({"ok": True, "id": record.pk, "changed": False})
    result = {"ok": True, "id": record.pk, "changed": True}
    if action == "finish" and not (
        kind == "issue" and request.POST.get("confirm_linked_tasks") == "yes"
    ):
        result["undo_token"] = signing.dumps(
            {
                "user": request.user.pk,
                "kind": kind,
                "id": record.pk,
                "previous_state": expected,
                "state": record.state,
                "terminated_at": record.terminated_at.isoformat(),
            },
            salt="dashboard-undo",
        )
    return JsonResponse(result)


def _note_action(request, action, record_id):
    if action == "undo":
        restored = undo_deleted_note(
            request=request,
            token=request.POST.get("token", ""),
            general_only=True,
            note_id=int(record_id),
        )
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


def _change_dates(request, action, kind, record):
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
        except TypeError, ValueError:
            return JsonResponse({"error": "Choose a valid date."}, status=400)
        if new_date == record.scheduled_date:
            return JsonResponse({"ok": True, "id": record.pk, "changed": False})
        if kind == "event":
            data = {
                "title": record.title,
                "description": record.description,
                "property": record.property_id or "",
                "scheduled_date": new_date.isoformat(),
                "all_day": "on" if record.all_day else "",
                "start_time": record.start_time.strftime("%H:%M") if record.start_time else "",
                "end_time": record.end_time.strftime("%H:%M") if record.end_time else "",
                "user_participation_required": "on" if record.user_participation_required else "",
                "user_presence_required": "on" if record.user_presence_required else "",
            }
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
        except TypeError, ValueError:
            return JsonResponse({"error": "Choose a valid date."}, status=400)
        field = "completion_deadline" if kind == "task" else "resolution_deadline"
        if new_date == getattr(record, field):
            return JsonResponse({"ok": True, "id": record.pk, "changed": False})
        setattr(record, field, new_date)
        record.save(update_fields=[field])
    return JsonResponse({"ok": True, "id": record.pk, "changed": True})


def _save_record(request, action, kind, record):
    form_class = {"task": TaskForm, "issue": IssueForm, "event": EventForm}[kind]
    form = form_class(request.POST, user=request.user, instance=record)
    # ModelForm validation mutates the instance, so take the snapshot first.
    before = snapshot_form_values(form)
    if not form.is_valid():
        return JsonResponse({"errors": form.errors}, status=400)
    contacts_form = None
    if kind == "event" and action == "add":
        contacts_form = EventContactForm(request.POST, user=request.user)
        if not contacts_form.is_valid():
            return JsonResponse({"errors": contacts_form.errors}, status=400)
    if record is not None and not form_values_changed(before, form):
        return JsonResponse({"ok": True, "id": record.pk, "changed": False})

    values = form.cleaned_data
    if kind == "task":
        if record is None:
            record = create_task(user=request.user, **values)
        else:
            record = update_task(task=record, **values)
    elif kind == "issue":
        if record is None:
            record = create_issue(user=request.user, **values)
        else:
            record = update_issue(issue=record, **values)
    else:
        if record is None:
            record = create_event(
                user=request.user, contacts=contacts_form.cleaned_data["contacts"], **values
            )
        else:
            record = update_event(event=record, **values)
    return JsonResponse({"ok": True, "id": record.pk, "changed": True})
