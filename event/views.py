"""Event HTTP endpoints; workspace builds pages and services apply writes."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from config.feedback import form_values_changed, snapshot_form_values
from property.navigation import active_property_for_user, created_record_property_url

from .forms import EventContactForm, EventForm
from .models import Event, EventContact
from .navigation import _event_workspace_url, _redirect_with_event_form_state
from .selectors import (
    events_for_user,
)
from .services import (
    add_contacts_to_event,
    cancel_event,
    create_event,
    delete_event,
    mark_event_occurred,
    reactivate_event,
    remove_contact_from_event,
    set_event_contacts,
    update_event,
)
from .workspace import _event_list_context


@login_required
@require_GET
def events_view(request):
    context = _event_list_context(request)
    if context["selection_redirect"]:
        return redirect(context["selection_redirect"])
    origin = None
    if request.GET.get("open") == "add" and not context["open_modal"]:
        origin = active_property_for_user(request.user, request.GET.get("property"))
        if origin:
            context["add_event_form"].initial["property"] = origin.pk
            context["open_modal"] = "addEventModal"
    elif context["open_modal"] == "addEventModal":
        origin = active_property_for_user(
            request.user, context["add_event_form"].data.get("return_property")
        )
    context["return_property_id"] = origin.pk if origin else None
    if request.GET.get("open") == "edit" and context["edit_event_form"] is not None:
        context["open_modal"] = "editEventModal"
    return render(
        request,
        "event/events.html",
        context,
    )


@login_required
@require_POST
def add_event_view(request):
    event_form = EventForm(request.POST, user=request.user, auto_id="add_event_%s")
    contacts_form = EventContactForm(
        request.POST,
        user=request.user,
        auto_id="initial_contacts_%s",
    )
    event_is_valid = event_form.is_valid()
    contacts_are_valid = contacts_form.is_valid()
    if event_is_valid and contacts_are_valid:
        event = create_event(
            user=request.user,
            contacts=contacts_form.cleaned_data["contacts"],
            **event_form.cleaned_data,
        )
        messages.success(request, "Event added.")
        property_url = created_record_property_url(
            event, request.POST.get("return_property"), "event"
        )
        if property_url:
            return redirect(property_url)
        return redirect(_event_workspace_url(request, event_id=event.pk, clear_filters=True))
    return _redirect_with_event_form_state(
        request,
        action="add_event",
    )


@login_required
@require_POST
def delete_event_view(request, event_id):
    event = get_object_or_404(events_for_user(user=request.user), pk=event_id)
    delete_event(event=event)
    if event.action_changed:
        messages.success(request, "Event deleted.")
    return redirect(_event_workspace_url(request))


@login_required
@require_POST
def edit_event_view(request, event_id):
    event = get_object_or_404(
        events_for_user(user=request.user),
        pk=event_id,
        state=Event.State.SCHEDULED,
    )
    form = EventForm(
        request.POST,
        user=request.user,
        instance=event,
        auto_id="edit_event_%s",
    )
    managing_contacts = request.POST.get("manage_contacts") == "1"
    contacts_form = EventContactForm(
        request.POST,
        user=request.user,
        event=event,
        include_existing=True,
        auto_id="edit_contacts_%s",
    )
    before = snapshot_form_values(form)
    event_is_valid = form.is_valid()
    contacts_are_valid = not managing_contacts or contacts_form.is_valid()
    if event_is_valid and contacts_are_valid:
        event_changed = form_values_changed(before, form)
        participants_changed = False
        if managing_contacts:
            editable_ids = set(
                contacts_form.fields["contacts"].queryset.values_list("pk", flat=True)
            )
            current_ids = set(
                EventContact.objects.filter(
                    event=event,
                    contact_id__in=editable_ids,
                ).values_list("contact_id", flat=True)
            )
            chosen_ids = {contact.pk for contact in contacts_form.cleaned_data["contacts"]}
            participants_changed = chosen_ids != current_ids
        with transaction.atomic():
            if event_changed:
                update_event(event=event, **form.cleaned_data)
            if participants_changed:
                set_event_contacts(event=event, contacts=contacts_form.cleaned_data["contacts"])
        if event_changed or participants_changed:
            messages.success(request, "Event updated.")
        return redirect(_event_workspace_url(request, event_id=event.pk))
    return _redirect_with_event_form_state(
        request,
        action="edit_event",
        event_id=event.pk,
    )


@login_required
@require_POST
def mark_event_occurred_view(request, event_id):
    event = get_object_or_404(
        events_for_user(user=request.user), pk=event_id, state=Event.State.SCHEDULED
    )
    mark_event_occurred(event=event)
    if event.action_changed:
        messages.success(request, "Event marked as occurred.")
    return redirect(_event_workspace_url(request, event_id=event_id, state="all"))


@login_required
@require_POST
def cancel_event_view(request, event_id):
    event = get_object_or_404(
        events_for_user(user=request.user), pk=event_id, state=Event.State.SCHEDULED
    )
    cancel_event(event=event)
    if event.action_changed:
        messages.success(request, "Event cancelled.")
    property_url = (
        f"{reverse('property:property_detail', args=[event.property_id])}?tab=schedule"
        if event.property_id
        else None
    )
    if property_url and request.POST.get("next") == property_url:
        return redirect(property_url)
    return redirect(_event_workspace_url(request, event_id=event_id, state="all"))


@login_required
@require_POST
def reactivate_event_view(request, event_id):
    event = get_object_or_404(
        events_for_user(user=request.user),
        pk=event_id,
        state__in=(Event.State.OCCURRED, Event.State.CANCELLED),
    )
    reactivate_event(event=event)
    if event.action_changed:
        messages.success(request, "Event reactivated.")
    return redirect(_event_workspace_url(request, event_id=event_id))


@login_required
@require_POST
def add_event_contacts_to_event_view(request, event_id):
    event = get_object_or_404(
        events_for_user(user=request.user), pk=event_id, state=Event.State.SCHEDULED
    )
    form = EventContactForm(request.POST, user=request.user, event=event)
    if form.is_valid():
        before_count = EventContact.objects.filter(event=event).count()
        add_contacts_to_event(event=event, contacts=form.cleaned_data["contacts"])
        added = EventContact.objects.filter(event=event).count() - before_count
        if added:
            messages.success(request, f"{added} participant{'s' if added != 1 else ''} added.")
        return redirect(
            _event_workspace_url(request, event_id=event.pk, preserve_participant_origin=True)
        )
    return _redirect_with_event_form_state(
        request,
        action="add_event_contacts",
        event_id=event.pk,
    )


@login_required
@require_POST
def delete_event_contact_from_event_view(request, event_id, event_contact_id):
    event = get_object_or_404(
        events_for_user(user=request.user), pk=event_id, state=Event.State.SCHEDULED
    )
    event_contact = get_object_or_404(
        EventContact.objects.select_related("event"),
        pk=event_contact_id,
        event=event,
    )
    remove_contact_from_event(event_contact=event_contact)
    messages.success(request, "Participant removed.")
    return redirect(
        _event_workspace_url(request, event_id=event.pk, preserve_participant_origin=True)
    )
