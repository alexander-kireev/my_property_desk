"""Signed work Undo: owner, record, expiry and terminal timestamp must all match."""

from django.core import signing
from django.db import transaction
from django.http import JsonResponse


def undo_work(request, queryset, kind, record_id):
    try:
        # The UI's ten-second opportunity pauses on hover/focus; leave room
        # for that pause while the signed token remains owner/state-bound.
        original = signing.loads(request.POST.get("token", ""), salt="dashboard-undo", max_age=3600)
    except signing.BadSignature:
        return JsonResponse(
            {"error": "Undo has expired. Refresh to see the current record."}, status=409
        )
    if (
        original.get("user") != request.user.pk
        or original.get("kind") != kind
        or original.get("id") != int(record_id)
    ):
        return JsonResponse({"error": "This Undo does not match the record."}, status=409)
    with transaction.atomic():
        record = queryset.select_for_update().filter(pk=record_id).first()
        if (
            record is None
            or record.state != original.get("state")
            or not record.terminated_at
            or record.terminated_at.isoformat() != original.get("terminated_at")
        ):
            return JsonResponse(
                {"error": "This record changed again and can no longer be undone."}, status=409
            )
        record.state = original["previous_state"]
        record.terminated_at = None
        record.save(update_fields=["state", "terminated_at"])
    return JsonResponse({"ok": True, "id": record.pk, "changed": True})
