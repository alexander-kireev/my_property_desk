"""Query normalization and safe return URLs for the issue workspace."""

from urllib.parse import urlencode

from django.shortcuts import redirect
from django.urls import reverse

from config.form_state import (
    serialise_form_data,
    store_form_state,
)

from .models import Issue
from .selectors import (
    ISSUE_DEADLINE_PERIOD_OPTIONS,
    ISSUE_SORT_OPTIONS,
)


def _normalised_list_values(request):
    search = request.GET.get("search", "").strip()
    state = request.GET.get("state", "all")
    sort = request.GET.get("sort", "resolution_deadline")
    priority_value = request.GET.get("priority", "")
    property_value = request.GET.get("property", "")
    deadline_period = request.GET.get("deadline_period", "")

    if state not in (*Issue.State.values, "all"):
        state = "all"
    if sort not in ISSUE_SORT_OPTIONS:
        sort = "resolution_deadline"
    if deadline_period not in ISSUE_DEADLINE_PERIOD_OPTIONS:
        deadline_period = ""

    try:
        priority = int(priority_value)
    except TypeError, ValueError:
        priority = ""
    if priority not in Issue.Priority.values:
        priority = ""

    try:
        property_id = int(property_value)
    except TypeError, ValueError:
        property_id = ""

    return {
        "search": search,
        "state": state,
        "priority": priority,
        "property_id": property_id,
        "deadline_period": deadline_period,
        "sort": sort,
    }


def _list_query_parameters(values):
    parameters = {}
    for name in ("search", "state", "priority", "deadline_period"):
        if values[name] and not (name == "state" and values[name] == "all"):
            parameters[name] = values[name]
    if values["property_id"]:
        parameters["property"] = values["property_id"]
    if values["sort"] != "resolution_deadline":
        parameters["sort"] = values["sort"]
    return parameters


def _issue_workspace_url(
    request,
    *,
    issue_id=None,
    tab="details",
    form_state=None,
    clear_filters=False,
):
    parameters = _list_query_parameters(_normalised_list_values(request))
    if clear_filters:
        parameters = {key: value for key, value in parameters.items() if key == "sort"}
    page = request.GET.get("page", "")
    if not clear_filters and page.isdigit() and int(page) > 1:
        parameters["page"] = page
    if issue_id is not None:
        parameters["selected"] = issue_id
    if tab == "tasks":
        parameters["tab"] = "tasks"
    if form_state is not None:
        parameters["form_state"] = form_state

    url = reverse("issue:issues")
    return f"{url}?{urlencode(parameters)}" if parameters else url


def _redirect_with_issue_form_state(
    request,
    *,
    action,
    issue_id=None,
    object_id=None,
    tab="details",
):
    token = store_form_state(
        request,
        {
            "action": action,
            "issue_id": issue_id,
            "object_id": object_id,
            "data": serialise_form_data(request.POST),
        },
    )
    return redirect(
        _issue_workspace_url(
            request,
            issue_id=issue_id,
            tab=tab,
            form_state=token,
        )
    )
