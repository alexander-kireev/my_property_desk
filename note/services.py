import secrets

from django.db import transaction
from django.utils.dateparse import parse_datetime

from .models import Note


def create_note(*, user, content, contact=None):
    return Note.objects.create(
        user=user,
        content=content,
        contact=contact,
    )


def update_note(*, note, content):
    note.content = content
    note.save(update_fields=["content"])
    return note


def delete_note(*, note):
    note.delete()


def remember_deleted_note(*, request, note):
    """Keep only the latest deleted note available for a short UI Undo."""
    token = secrets.token_urlsafe(18)
    request.session["note_undo"] = {
        "token": token,
        "user_id": request.user.pk,
        "id": note.pk,
        "contact_id": note.contact_id,
        "content": note.content,
        "created_at": note.created_at.isoformat(),
    }
    return token


def undo_deleted_note(*, request, token, contact_id=None, general_only=False, note_id=None):
    original = request.session.get("note_undo")
    if not original or original.get("token") != token or original.get("user_id") != request.user.pk:
        return None
    if contact_id is not None and original.get("contact_id") != contact_id:
        return None
    if note_id is not None and original.get("id") != note_id:
        return None
    if general_only and original.get("contact_id") is not None:
        return None
    with transaction.atomic():
        if Note.objects.filter(pk=original["id"]).exists():
            return None
        note = Note.objects.create(
            pk=original["id"],
            user=request.user,
            contact_id=original["contact_id"],
            content=original["content"],
        )
        Note.objects.filter(pk=note.pk).update(created_at=parse_datetime(original["created_at"]))
    request.session.pop("note_undo", None)
    return note
