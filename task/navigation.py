"""Query normalization and safe return URLs for the task workspace."""

from urllib.parse import parse_qs, urlencode, urlsplit

from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme

from config.form_state import (
    serialise_form_data,
    store_form_state,
)

from .models import Task
from .selectors import (
    TASK_DEADLINE_PERIOD_OPTIONS,
    TASK_SCHEDULE_PERIOD_OPTIONS,
    TASK_SORT_OPTIONS,
)


def _normalised_list_values(request):
    search = request.GET.get("search", "").strip()
    state = request.GET.get("state", "all")
    sort = request.GET.get("sort", "completion_deadline")
    priority_value = request.GET.get("priority", "")
    scheduled_period = request.GET.get("scheduled_period", "")
    deadline_period = request.GET.get("deadline_period", "")

    if state not in (*Task.State.values, "all"):
        state = "all"
    if sort not in TASK_SORT_OPTIONS:
        sort = "completion_deadline"
    if scheduled_period not in TASK_SCHEDULE_PERIOD_OPTIONS:
        scheduled_period = ""
    if deadline_period not in TASK_DEADLINE_PERIOD_OPTIONS:
        deadline_period = ""

    try:
        priority = int(priority_value)
    except TypeError, ValueError:
        priority = ""
    if priority not in Task.Priority.values:
        priority = ""

    return {
        "search": search,
        "state": state,
        "priority": priority,
        "scheduled_period": scheduled_period,
        "deadline_period": deadline_period,
        "sort": sort,
    }


def _list_query_parameters(values):
    parameters = {}
    for name in (
        "search",
        "state",
        "priority",
        "scheduled_period",
        "deadline_period",
    ):
        if values[name] and not (name == "state" and values[name] == "all"):
            parameters[name] = values[name]
    if values["sort"] != "completion_deadline":
        parameters["sort"] = values["sort"]
    return parameters


def _task_workspace_url(request, *, task_id=None, form_state=None, clear_filters=False):
    parameters = _list_query_parameters(_normalised_list_values(request))
    if clear_filters:
        parameters = {key: value for key, value in parameters.items() if key == "sort"}
    page = request.GET.get("page", "")
    if not clear_filters and page.isdigit() and int(page) > 1:
        parameters["page"] = page
    if task_id is not None:
        parameters["selected"] = task_id
    if form_state is not None:
        parameters["form_state"] = form_state

    url = reverse("task:tasks")
    return f"{url}?{urlencode(parameters)}" if parameters else url


def _redirect_with_task_form_state(request, *, action, task_id=None):
    token = store_form_state(
        request,
        {
            "action": action,
            "task_id": task_id,
            "data": serialise_form_data(request.POST),
        },
    )
    return redirect(
        _task_workspace_url(
            request,
            task_id=task_id,
            form_state=token,
        )
    )


def _task_action_redirect(request, *, task, deleted=False):
    next_url = request.POST.get("next", "")
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        parsed_next = urlsplit(next_url)
        next_path = parsed_next.path
        is_task_workspace = next_path == reverse("task:tasks")
        is_own_issue_workspace = (
            task.issue_id
            and next_path == reverse("issue:issues")
            and parse_qs(parsed_next.query).get("selected") == [str(task.issue_id)]
        )
        property_id = task.property_id or (task.issue.property_id if task.issue_id else None)
        is_own_property_workspace = (
            property_id
            and next_url == f"{reverse('property:property_detail', args=[property_id])}?tab=work"
        )
        if is_task_workspace or is_own_issue_workspace or is_own_property_workspace:
            return redirect(next_url)

    return redirect(
        _task_workspace_url(
            request,
            task_id=None if deleted else task.pk,
        )
    )
