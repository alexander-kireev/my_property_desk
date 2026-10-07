"""Property HTTP endpoints. Workspace composes pages; services own changes."""

from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from config.feedback import form_values_changed, snapshot_form_values
from config.form_state import (
    deserialise_form_data,
    pop_form_state,
    serialise_form_data,
    store_form_state,
)

from .forms import PropertyForm
from .models import Property
from .navigation import (
    _property_list_url,
    _redirect_with_property_form_state,
    _selected_property_url,
    created_record_property_url,
)
from .selectors import (
    properties_for_user,
)
from .services import (
    create_property,
    deactivate_property,
    delete_property,
    reactivate_property,
    update_property,
)
from .workspace import (
    _property_detail_context,
    _property_list_context,
    _property_record_forms,
    _restore_add_property_form,
    _restore_edit_property_form,
)


@login_required
@require_GET
def properties_view(request):
    add_property_form = None
    edit_property_form = None
    edit_property_record = None
    state = pop_form_state(request)
    if isinstance(state, dict) and state.get("action") == "add_property":
        add_property_form = _restore_add_property_form(request, state)
    elif isinstance(state, dict) and state.get("action") == "edit_property":
        edit_property_record = (
            properties_for_user(user=request.user)
            .filter(pk=state.get("property_id"), state=Property.State.ACTIVE)
            .first()
        )
        if edit_property_record:
            edit_property_form = _restore_edit_property_form(request, state, edit_property_record)

    context = _property_list_context(
        request,
        add_property_form=add_property_form,
        edit_property_form=edit_property_form,
        edit_property_record=edit_property_record,
    )
    if context["selection_redirect"]:
        return redirect(context["selection_redirect"])
    if context["selected_property"] is not None:
        context = _property_detail_context(
            request, context["selected_property"], list_context=context
        )
        if edit_property_form is None:
            context["list_edit_form"] = PropertyForm(
                user=request.user,
                instance=context["selected_property"],
                auto_id="list_edit_%s",
            )
    return render(
        request,
        "property/properties.html",
        context,
    )


@login_required
@require_POST
def add_property_view(request):
    form = PropertyForm(request.POST, user=request.user)

    if form.is_valid():
        property_record = create_property(
            user=request.user,
            **form.cleaned_data,
        )
        messages.success(request, "Property added.")

        return redirect(_selected_property_url(request, property_record, clear_filters=True))

    return _redirect_with_property_form_state(
        request,
        action="add_property",
    )


@login_required
@require_GET
def property_detail_view(request, property_id):
    property_record = get_object_or_404(
        properties_for_user(user=request.user),
        pk=property_id,
    )

    context = _property_detail_context(request, property_record)
    # Keep the one-use errors until the selected property's page is canonical.
    if context["selection_redirect"]:
        return redirect(context["selection_redirect"])
    state = pop_form_state(request)
    if isinstance(state, dict) and state.get("action") == "edit_property":
        restored = _restore_edit_property_form(request, state, property_record)
        if restored is not None:
            context["edit_property_form"] = restored
    if (
        isinstance(state, dict)
        and state.get("action") == "property_add_record"
        and state.get("property_id") == property_record.pk
        and state.get("kind") in ("task", "issue", "event")
        and property_record.state == Property.State.ACTIVE
    ):
        kind = state["kind"]
        context.update(
            _property_record_forms(
                request,
                property_record,
                data=deserialise_form_data(state.get("data", {})),
                kind=kind,
            )
        )
        context["property_record_modal"] = {
            "task": "propertyAddTaskModal",
            "issue": "propertyAddIssueModal",
            "event": "propertyAddEventModal",
        }[kind]

    return render(
        request,
        "property/property_detail.html",
        context,
    )


@login_required
@require_POST
def add_property_record_view(request, property_id, kind):
    """Create a work item in property context and return to the same property."""
    if kind not in ("task", "issue", "event"):
        raise Http404
    property_record = get_object_or_404(
        properties_for_user(user=request.user),
        pk=property_id,
        state=Property.State.ACTIVE,
    )

    # The URL, not a hidden field, decides which property owns the new record.
    data = request.POST.copy()
    data["property"] = str(property_record.pk)
    if kind == "task":
        data["relationship_type"] = "property"
        data["issue"] = ""
    forms = _property_record_forms(request, property_record, data=data, kind=kind)
    form = forms[f"property_add_{kind}_form"]
    valid = form.is_valid()
    contacts_form = forms["property_event_contacts_form"]
    if kind == "event":
        valid = contacts_form.is_valid() and valid

    if valid:
        if kind == "task":
            from task.services import create_task

            record = create_task(user=request.user, **form.cleaned_data)
        elif kind == "issue":
            from issue.services import create_issue

            record = create_issue(user=request.user, **form.cleaned_data)
        else:
            from event.services import create_event

            record = create_event(
                user=request.user,
                contacts=contacts_form.cleaned_data["contacts"],
                **form.cleaned_data,
            )
        messages.success(request, f"{kind.title()} added to property.")
        return redirect(created_record_property_url(record, property_record.pk, kind))

    token = store_form_state(
        request,
        {
            "action": "property_add_record",
            "property_id": property_record.pk,
            "kind": kind,
            "data": serialise_form_data(data),
        },
    )
    detail_url = reverse("property:property_detail", args=[property_record.pk])
    return redirect(f"{detail_url}?{urlencode({'form_state': token})}")


@login_required
@require_POST
def edit_property_view(request, property_id):
    property_record = get_object_or_404(
        properties_for_user(user=request.user),
        pk=property_id,
        state=Property.State.ACTIVE,
    )
    form = PropertyForm(
        request.POST,
        user=request.user,
        instance=property_record,
    )
    before = snapshot_form_values(form)

    if form.is_valid():
        if form_values_changed(before, form):
            update_property(property_record=property_record, **form.cleaned_data)
            messages.success(request, "Property updated.")
        if request.GET.get("return_to") == "list":
            return redirect(_property_list_url(request, selected=property_record.pk))
        return redirect(_selected_property_url(request, property_record))

    return _redirect_with_property_form_state(
        request,
        action="edit_property",
        property_record=property_record,
    )


@login_required
@require_POST
def deactivate_property_view(request, property_id):
    property_record = get_object_or_404(
        properties_for_user(user=request.user),
        pk=property_id,
        state=Property.State.ACTIVE,
    )
    deactivate_property(
        property_record=property_record,
        cancel_events=request.POST.get("cancel_events") == "yes",
        dismiss_issues=request.POST.get("dismiss_issues") == "yes",
        dismiss_tasks=request.POST.get("dismiss_tasks") == "yes",
    )
    affected = property_record.affected_work
    detail = ", ".join(
        f"{count} {kind[:-1] if count == 1 else kind}" for kind, count in affected.items() if count
    )
    if property_record.action_changed:
        messages.success(
            request, f"Property deactivated.{(' Also updated ' + detail + '.') if detail else ''}"
        )
    if request.GET.get("return_to") == "list":
        return redirect(_property_list_url(request, selected=property_record.pk))
    return redirect(_selected_property_url(request, property_record))


@login_required
@require_POST
def reactivate_property_view(request, property_id):
    property_record = get_object_or_404(
        properties_for_user(user=request.user),
        pk=property_id,
        state=Property.State.DEACTIVATED,
    )
    reactivate_property(property_record=property_record)
    messages.success(request, "Property reactivated.")
    if request.GET.get("return_to") == "list":
        return redirect(_property_list_url(request, selected=property_record.pk))
    return redirect(_selected_property_url(request, property_record))


@login_required
@require_POST
def delete_property_view(request, property_id):
    property_record = get_object_or_404(
        properties_for_user(user=request.user),
        pk=property_id,
    )
    delete_property(
        property_record=property_record,
        delete_events=request.POST.get("delete_events") == "yes",
        delete_issues=request.POST.get("delete_issues") == "yes",
        delete_tasks=request.POST.get("delete_tasks") == "yes",
    )
    affected = property_record.affected_work
    detail = ", ".join(
        f"{count} {kind[:-1] if count == 1 else kind}" for kind, count in affected.items() if count
    )
    if property_record.action_changed:
        messages.success(
            request, f"Property deleted.{(' Also deleted ' + detail + '.') if detail else ''}"
        )

    if request.GET.get("return_to") == "list":
        return redirect(_property_list_url(request))
    return redirect("property:properties")
