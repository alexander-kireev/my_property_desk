"""Event filter and calendar URLs. Month bounds use pure calendar helpers."""

from datetime import date
from urllib.parse import urlencode

from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from config.form_state import (
    serialise_form_data,
    store_form_state,
)

from .calendar import renderable_month
from .models import Event
from .selectors import (
    EVENT_SORT_OPTIONS,
    USER_PARTICIPATION_REQUIRED_OPTIONS,
    USER_PRESENCE_REQUIRED_OPTIONS,
)

DEFAULT_EVENT_STATE = "all"


def _normalised_list_values(request):
    search = request.GET.get("search", "").strip()
    state = request.GET.get("state", DEFAULT_EVENT_STATE)
    sort = request.GET.get("sort", "scheduled_date")
    property_value = request.GET.get("property", "")
    participation = request.GET.get("participation", "any").lower()
    presence = request.GET.get("presence", "any").lower()

    if state not in (*Event.State.values, "all"):
        state = DEFAULT_EVENT_STATE
    if sort not in EVENT_SORT_OPTIONS:
        sort = "scheduled_date"
    if participation not in USER_PARTICIPATION_REQUIRED_OPTIONS:
        participation = "any"
    if presence not in USER_PRESENCE_REQUIRED_OPTIONS:
        presence = "any"
    try:
        property_id = int(property_value)
    except TypeError, ValueError:
        property_id = ""

    return {
        "search": search,
        "state": state,
        "sort": sort,
        "property_id": property_id,
        "participation": participation,
        "presence": presence,
    }


def _list_query_parameters(values):
    parameters = {}
    if values["search"]:
        parameters["search"] = values["search"]
    if values["state"] != DEFAULT_EVENT_STATE:
        parameters["state"] = values["state"]
    for name in ("participation", "presence"):
        if values[name] != "any":
            parameters[name] = values[name]
    if values["property_id"]:
        parameters["property"] = values["property_id"]
    if values["sort"] != "scheduled_date":
        parameters["sort"] = values["sort"]
    return parameters


def _calendar_month(request):
    return renderable_month(
        request.GET.get("year"), request.GET.get("month"), timezone.localdate().replace(day=1)
    )


def _calendar_query(values, month):
    parameters = _list_query_parameters(values)
    parameters.update(
        {"month": month.month, "year": month.year, "tab": "calendar", "view": "calendar"}
    )
    return urlencode(parameters)


def _date_parameter(request, name):
    try:
        return date.fromisoformat(request.GET.get(name, ""))
    except TypeError, ValueError:
        return None


def _selected_day(request):
    return _date_parameter(request, "day")


def _event_workspace_url(
    request,
    *,
    event_id=None,
    tab="details",
    form_state=None,
    state=None,
    clear_filters=False,
):
    parameters = _list_query_parameters(_normalised_list_values(request))
    if clear_filters:
        parameters = {key: value for key, value in parameters.items() if key == "sort"}
    selected_day = None if clear_filters else _selected_day(request)
    if selected_day is not None:
        parameters["day"] = selected_day.isoformat()
    if state is not None:
        if state == DEFAULT_EVENT_STATE:
            parameters.pop("state", None)
        else:
            parameters["state"] = state
    try:
        page = int(request.GET.get("page", ""))
    except TypeError, ValueError:
        page = None
    if not clear_filters and page is not None and page > 1:
        parameters["page"] = page
    if not clear_filters and request.GET.get("month") and request.GET.get("year"):
        displayed_month = _calendar_month(request)
        parameters["month"] = displayed_month.month
        parameters["year"] = displayed_month.year
    if event_id is not None:
        parameters["selected"] = event_id
    if tab == "calendar":
        parameters["tab"] = "calendar"
    if form_state is not None:
        parameters["form_state"] = form_state
    url = reverse("event:events")
    return f"{url}?{urlencode(parameters)}" if parameters else url


def _redirect_with_event_form_state(
    request,
    *,
    action,
    event_id=None,
):
    token = store_form_state(
        request,
        {
            "action": action,
            "event_id": event_id,
            "data": serialise_form_data(request.POST),
        },
    )
    return redirect(
        _event_workspace_url(
            request,
            event_id=event_id,
            form_state=token,
        )
    )
