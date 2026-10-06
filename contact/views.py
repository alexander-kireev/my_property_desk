"""Contact, method and Note HTTP endpoints. Canonicalize before consuming saved errors."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from config.feedback import form_values_changed, snapshot_form_values
from note.forms import NoteForm
from note.selectors import (
    notes_for_contact,
)
from note.services import (
    create_note,
    delete_note,
    remember_deleted_note,
    undo_deleted_note,
    update_note,
)

from .forms import ContactCreateForm, ContactForm, ContactMethodForm
from .models import Contact
from .navigation import (
    _canonical_contacts_url,
    _contact_workspace_url,
    _redirect_with_contact_form_state,
)
from .selectors import (
    contact_methods_for_contact,
    contacts_for_user,
)
from .services import (
    create_contact,
    create_contact_method,
    deactivate_contact,
    delete_contact,
    delete_contact_method,
    reactivate_contact,
    update_contact,
    update_contact_method,
)
from .workspace import _contact_list_context, _restore_contact_form_context


@login_required
@require_GET
def contacts_view(request):
    canonical_url = _canonical_contacts_url(request)
    if canonical_url:
        return redirect(canonical_url)
    context_overrides = _restore_contact_form_context(request)
    context = _contact_list_context(request, **context_overrides)
    if context["selection_redirect"]:
        return redirect(context["selection_redirect"])
    token = request.session.pop("note_undo_display", None)
    original = request.session.get("note_undo")
    if (
        token
        and original
        and token == original.get("token")
        and context["selected_contact"]
        and original.get("contact_id") == context["selected_contact"].pk
    ):
        context["note_undo_token"] = token
    return render(
        request,
        "contact/contacts.html",
        context,
    )


@login_required
@require_POST
def add_contact_view(request):
    form = ContactCreateForm(request.POST, auto_id="add_contact_%s")
    if form.is_valid():
        contact = create_contact(user=request.user, **form.cleaned_data)
        messages.success(request, "Contact added.")
        return redirect(_contact_workspace_url(request, contact_id=contact.pk, clear_filters=True))

    return _redirect_with_contact_form_state(
        request,
        action="add_contact",
    )


@login_required
@require_POST
def edit_contact_view(request, contact_id):
    contact = get_object_or_404(
        contacts_for_user(user=request.user),
        pk=contact_id,
        state=Contact.State.ACTIVE,
    )
    form = ContactForm(
        request.POST,
        instance=contact,
        auto_id="edit_contact_%s",
    )
    before = snapshot_form_values(form)
    if form.is_valid():
        if form_values_changed(before, form):
            update_contact(contact=contact, **form.cleaned_data)
            messages.success(request, "Contact updated.")
        return redirect(_contact_workspace_url(request, contact_id=contact.pk))

    return _redirect_with_contact_form_state(
        request,
        action="edit_contact",
        contact_id=contact.pk,
    )


@login_required
@require_POST
def deactivate_contact_view(request, contact_id):
    contact = get_object_or_404(
        contacts_for_user(user=request.user),
        pk=contact_id,
        state=Contact.State.ACTIVE,
    )
    deactivate_contact(contact=contact)
    messages.success(request, "Contact deactivated.")
    return redirect(_contact_workspace_url(request, contact_id=contact.pk))


@login_required
@require_POST
def reactivate_contact_view(request, contact_id):
    contact = get_object_or_404(
        contacts_for_user(user=request.user),
        pk=contact_id,
        state=Contact.State.DEACTIVATED,
    )
    reactivate_contact(contact=contact)
    messages.success(request, "Contact reactivated.")
    return redirect(_contact_workspace_url(request, contact_id=contact.pk))


@login_required
@require_POST
def delete_contact_view(request, contact_id):
    contact = get_object_or_404(
        contacts_for_user(user=request.user),
        pk=contact_id,
    )
    delete_contact(contact=contact)
    messages.success(request, "Contact deleted.")
    return redirect(_contact_workspace_url(request))


@login_required
@require_POST
def add_contact_method_view(request, contact_id):
    contact = get_object_or_404(
        contacts_for_user(user=request.user),
        pk=contact_id,
        state=Contact.State.ACTIVE,
    )
    form = ContactMethodForm(
        request.POST,
        contact=contact,
        auto_id="add_contact_method_%s",
    )
    if form.is_valid():
        create_contact_method(contact=contact, **form.cleaned_data)
        messages.success(
            request,
            f"{form.cleaned_data['type'].title()} {'number' if form.cleaned_data['type'] == 'telephone' else 'address'} added.",
        )
        return redirect(_contact_workspace_url(request, contact_id=contact.pk))

    return _redirect_with_contact_form_state(
        request,
        action="add_contact_method",
        contact_id=contact.pk,
    )


@login_required
@require_POST
def edit_contact_method_view(request, contact_id, method_id):
    contact = get_object_or_404(
        contacts_for_user(user=request.user),
        pk=contact_id,
        state=Contact.State.ACTIVE,
    )
    contact_method = get_object_or_404(
        contact_methods_for_contact(contact=contact),
        pk=method_id,
    )
    form = ContactMethodForm(
        request.POST,
        instance=contact_method,
        contact=contact,
        auto_id="edit_contact_method_%s",
    )
    before = snapshot_form_values(form)
    if form.is_valid():
        if form_values_changed(before, form):
            update_contact_method(contact_method=contact_method, **form.cleaned_data)
            messages.success(request, "Contact detail updated.")
        return redirect(_contact_workspace_url(request, contact_id=contact.pk))

    return _redirect_with_contact_form_state(
        request,
        action="edit_contact_method",
        contact_id=contact.pk,
        object_id=contact_method.pk,
    )


@login_required
@require_POST
def delete_contact_method_view(request, contact_id, method_id):
    contact = get_object_or_404(
        contacts_for_user(user=request.user),
        pk=contact_id,
        state=Contact.State.ACTIVE,
    )
    contact_method = get_object_or_404(
        contact_methods_for_contact(contact=contact),
        pk=method_id,
    )
    delete_contact_method(contact_method=contact_method)
    messages.success(request, "Contact detail deleted.")
    return redirect(_contact_workspace_url(request, contact_id=contact.pk))


@login_required
@require_POST
def add_contact_note_view(request, contact_id):
    contact = get_object_or_404(
        contacts_for_user(user=request.user),
        pk=contact_id,
        state=Contact.State.ACTIVE,
    )

    form = NoteForm(
        request.POST,
        auto_id="add_note_%s",
    )
    if form.is_valid():
        create_note(user=request.user, contact=contact, **form.cleaned_data)
        messages.success(request, "Note added.")
        return redirect(_contact_workspace_url(request, contact_id=contact.pk, tab="notes"))

    return _redirect_with_contact_form_state(
        request,
        action="add_contact_note",
        contact_id=contact.pk,
        tab="notes",
    )


@login_required
@require_POST
def edit_contact_note_view(request, contact_id, note_id):
    contact = get_object_or_404(
        contacts_for_user(user=request.user),
        pk=contact_id,
        state=Contact.State.ACTIVE,
    )

    note = get_object_or_404(
        notes_for_contact(user=request.user, contact=contact).filter(pk=note_id)
    )

    form = NoteForm(
        request.POST,
        instance=note,
        auto_id="edit_contact_note_%s",
    )
    before = snapshot_form_values(form)
    if form.is_valid():
        if form_values_changed(before, form):
            update_note(note=note, **form.cleaned_data)
            messages.success(request, "Note updated.")
        return redirect(_contact_workspace_url(request, contact_id=contact.pk, tab="notes"))

    return _redirect_with_contact_form_state(
        request,
        action="edit_contact_note",
        contact_id=contact.pk,
        object_id=note.pk,
        tab="notes",
    )


@login_required
@require_POST
def delete_contact_note_view(request, contact_id, note_id):
    contact = get_object_or_404(
        contacts_for_user(user=request.user),
        pk=contact_id,
        state=Contact.State.ACTIVE,
    )
    note = get_object_or_404(
        notes_for_contact(user=request.user, contact=contact),
        pk=note_id,
    )
    token = remember_deleted_note(request=request, note=note)
    request.session["note_undo_display"] = token
    delete_note(note=note)
    return redirect(_contact_workspace_url(request, contact_id=contact.pk, tab="notes"))


@login_required
@require_POST
def undo_contact_note_view(request, contact_id):
    contact = get_object_or_404(contacts_for_user(user=request.user), pk=contact_id)
    note = undo_deleted_note(
        request=request, token=request.POST.get("token", ""), contact_id=contact.pk
    )
    if note is None:
        return JsonResponse({"error": "This note can no longer be undone."}, status=409)
    return JsonResponse({"ok": True, "id": note.pk})
