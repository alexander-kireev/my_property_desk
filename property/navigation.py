"""Property URLs and origin checks shared by workspaces and actions."""

from urllib.parse import urlencode

from django.shortcuts import redirect
from django.urls import reverse

from config.form_state import (
    serialise_form_data,
    store_form_state,
)

from .models import Property
from .selectors import (
    PROPERTY_SORT_OPTIONS,
)


def active_property_for_user(user, value):
    """Only accept a property that the user can still add records to."""
    if not str(value).isdigit():
        return None
    return Property.objects.filter(
        pk=value,
        user=user,
        state=Property.State.ACTIVE,
        deleted_at__isnull=True,
    ).first()


def created_record_property_url(record, value, record_type):
    """Return to the origin only if the new record actually belongs there."""
    if not str(value).isdigit():
        return None
    property_id = record.property_id
    if property_id is None and record_type == "task" and record.issue_id:
        property_id = record.issue.property_id
    if str(property_id) != str(value):
        return None
    query = urlencode(
        {
            "records_type": record_type,
            "records_scope": "current",
            "records_sort": "recent",
        }
    )
    return f"{reverse('property:property_detail', args=[property_id])}?{query}"


def _normalised_list_values(request):
    search = request.GET.get("search", "").strip()
    state = request.GET.get("state", "")
    sort = request.GET.get("sort", "name")

    if state not in (*Property.State.values, "all"):
        state = ""

    if sort not in PROPERTY_SORT_OPTIONS:
        sort = "name"

    return {"search": search, "state": state, "sort": sort}


def _list_query_parameters(values):
    parameters = {}
    for name in ("search", "state"):
        if values[name]:
            parameters[name] = values[name]
    if values["sort"] != "name":
        parameters["sort"] = values["sort"]
    return parameters


def _property_list_url(request, *, form_state=None, selected=None):
    parameters = _list_query_parameters(_normalised_list_values(request))
    page = request.GET.get("page", "")
    if page.isdigit() and int(page) > 1:
        parameters["page"] = page
    if form_state is not None:
        parameters["form_state"] = form_state
    if selected is not None:
        parameters["selected"] = selected

    url = reverse("property:properties")
    return f"{url}?{urlencode(parameters)}" if parameters else url


def _property_detail_url(property_record, *, form_state=None):
    url = reverse(
        "property:property_detail",
        kwargs={"property_id": property_record.pk},
    )
    return f"{url}?{urlencode({'form_state': form_state})}" if form_state else url


def _selected_property_url(request, property_record, *, clear_filters=False):
    """Keep a changed property selected while retaining explicit list filters."""
    parameters = _list_query_parameters(_normalised_list_values(request))
    if clear_filters:
        parameters = {key: value for key, value in parameters.items() if key == "sort"}
    url = _property_detail_url(property_record)
    return f"{url}?{urlencode(parameters)}" if parameters else url


def _redirect_with_property_form_state(
    request,
    *,
    action,
    property_record=None,
):
    token = store_form_state(
        request,
        {
            "action": action,
            "property_id": property_record.pk if property_record else None,
            "data": serialise_form_data(request.POST),
        },
    )
    if property_record is not None and request.GET.get("return_to") != "list":
        return redirect(_property_detail_url(property_record, form_state=token))
    return redirect(
        _property_list_url(
            request,
            form_state=token,
            selected=property_record.pk if property_record else None,
        )
    )
