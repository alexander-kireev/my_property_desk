"""Build the issue list, selected details and restored forms. Canonical redirects precede token consumption."""

from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.urls import reverse
from django.utils import timezone

from config.form_state import (
    deserialise_form_data,
    pop_form_state,
)
from pages.workspace_selection import resolve_selection
from property.selectors import properties_for_user
from task.forms import TaskForm
from task.models import Task
from task.selectors import tasks_for_issue

from .forms import IssueForm
from .models import Issue
from .navigation import (
    _issue_workspace_url,
    _list_query_parameters,
    _normalised_list_values,
)
from .selectors import (
    ISSUE_DEADLINE_PERIOD_OPTIONS,
    filtered_issues_for_user,
    issues_for_user,
)

ISSUES_PER_PAGE = 20


# Rebuild rejected forms from one-use session state.
def _active_issue_from_form_state(request, state):
    return (
        issues_for_user(user=request.user)
        .filter(
            pk=state.get("issue_id"),
            state=Issue.State.ACTIVE,
        )
        .first()
    )


def _restore_add_issue_form(request, state):
    return {
        "add_issue_form": IssueForm(
            deserialise_form_data(state.get("data", {})),
            user=request.user,
            auto_id="add_issue_%s",
        ),
        "open_modal": "addIssueModal",
    }


def _restore_edit_issue_form(request, state):
    issue = _active_issue_from_form_state(request, state)
    if issue is None:
        return {}
    return {
        "selected_issue": issue,
        "edit_issue_form": IssueForm(
            deserialise_form_data(state.get("data", {})),
            user=request.user,
            instance=issue,
            auto_id="edit_issue_%s",
        ),
        "active_tab": "details",
        "open_modal": "editIssueModal",
    }


def _restore_add_issue_task_form(request, state):
    issue = _active_issue_from_form_state(request, state)
    if issue is None:
        return {}
    return {
        "selected_issue": issue,
        "add_task_form": TaskForm(
            deserialise_form_data(state.get("data", {})),
            user=request.user,
            parent_issue=issue,
            auto_id="add_issue_task_%s",
        ),
        "active_tab": "tasks",
        "open_modal": "addIssueTaskModal",
    }


def _restore_edit_issue_task_form(request, state):
    issue = _active_issue_from_form_state(request, state)
    if issue is None:
        return {}
    task = (
        tasks_for_issue(user=request.user, issue=issue)
        .filter(
            pk=state.get("object_id"),
            state=Task.State.ACTIVE,
        )
        .first()
    )
    if task is None:
        return {}
    return {
        "selected_issue": issue,
        "edit_task_form": TaskForm(
            deserialise_form_data(state.get("data", {})),
            user=request.user,
            instance=task,
            auto_id="edit_issue_task_%s",
        ),
        "edit_task": task,
        "active_tab": "tasks",
        "open_modal": "editIssueTaskModal",
    }


ISSUE_FORM_STATE_RESTORERS = {
    "add_issue": _restore_add_issue_form,
    "edit_issue": _restore_edit_issue_form,
    "add_issue_task": _restore_add_issue_task_form,
    "edit_issue_task": _restore_edit_issue_task_form,
}


def _restore_issue_form_context(request):
    state = pop_form_state(request)
    if not isinstance(state, dict):
        return {}
    restorer = ISSUE_FORM_STATE_RESTORERS.get(state.get("action"))
    return restorer(request, state) if restorer is not None else {}


# Compose selection, list navigation and detail-panel context.
def _issue_list_context(
    request,
    *,
    selected_issue=None,
    add_issue_form=None,
    edit_issue_form=None,
    add_task_form=None,
    edit_task_form=None,
    edit_task=None,
    active_tab=None,
    open_modal=None,
):
    values = _normalised_list_values(request)
    issues = filtered_issues_for_user(
        user=request.user,
        **values,
    )
    requested_issue, selected_page, outside_filters, selection_redirect = resolve_selection(
        request,
        filtered=issues,
        owned=issues_for_user(user=request.user),
        page_size=ISSUES_PER_PAGE,
    )
    # Redirect to the selected row's page before consuming one-use form errors.
    if selection_redirect:
        return {"selection_redirect": selection_redirect}
    restored = _restore_issue_form_context(request)
    selected_issue = restored.get("selected_issue", selected_issue)
    add_issue_form = restored.get("add_issue_form", add_issue_form)
    edit_issue_form = restored.get("edit_issue_form", edit_issue_form)
    add_task_form = restored.get("add_task_form", add_task_form)
    edit_task_form = restored.get("edit_task_form", edit_task_form)
    edit_task = restored.get("edit_task", edit_task)
    active_tab = restored.get("active_tab", active_tab)
    open_modal = restored.get("open_modal", open_modal)

    paginator = Paginator(issues, ISSUES_PER_PAGE)
    page_obj = paginator.get_page(selected_page or request.GET.get("page"))

    if selected_issue is None:
        selected_issue = requested_issue

    if selected_issue is None and page_obj.object_list:
        selected_issue = page_obj.object_list[0]

    selected_tasks = (
        tasks_for_issue(user=request.user, issue=selected_issue)
        if selected_issue is not None
        else Task.objects.none()
    )

    requested_tab = active_tab or request.GET.get("tab", "details")
    if requested_tab not in ("details", "tasks"):
        requested_tab = "details"

    list_parameters = _list_query_parameters(values)
    navigation_parameters = dict(list_parameters)
    if page_obj.number > 1:
        navigation_parameters["page"] = page_obj.number

    properties = properties_for_user(user=request.user).order_by("name", "pk")
    return {
        "page_obj": page_obj,
        "selected_issue": selected_issue,
        "selected_outside_filters": outside_filters,
        "selection_redirect": selection_redirect,
        "show_compact_detail": (
            selected_issue is not None and request.GET.get("selected") == str(selected_issue.pk)
        ),
        "show_mobile_detail": request.GET.get("open") in ("detail", "edit")
        or open_modal == "editIssueModal",
        "mobile_expanded_issue_id": (
            selected_issue.pk
            if selected_issue is not None
            and request.GET.get("selected") == str(selected_issue.pk)
            and request.GET.get("open") not in ("detail", "edit")
            else None
        ),
        "selected_tasks": selected_tasks,
        "active_task_count": selected_tasks.filter(state=Task.State.ACTIVE).count(),
        "linked_task_count": selected_tasks.count(),
        "add_issue_form": add_issue_form
        or IssueForm(
            user=request.user,
            auto_id="add_issue_%s",
        ),
        "edit_issue_form": edit_issue_form
        or (
            IssueForm(
                user=request.user,
                instance=selected_issue,
                auto_id="edit_issue_%s",
            )
            if selected_issue and selected_issue.state == Issue.State.ACTIVE
            else None
        ),
        "add_task_form": add_task_form
        or (
            TaskForm(
                user=request.user,
                parent_issue=selected_issue,
                auto_id="add_issue_task_%s",
            )
            if selected_issue and selected_issue.state == Issue.State.ACTIVE
            else None
        ),
        "edit_task_form": edit_task_form
        or (
            TaskForm(
                user=request.user,
                auto_id="edit_issue_task_%s",
            )
            if selected_issue and selected_issue.state == Issue.State.ACTIVE
            else None
        ),
        "edit_task": edit_task,
        "active_tab": requested_tab,
        "open_modal": open_modal,
        "search": values["search"],
        "state": values["state"],
        "priority": values["priority"],
        "property_id": values["property_id"],
        "deadline_period": values["deadline_period"],
        "sort": values["sort"],
        "deadline_period_options": ISSUE_DEADLINE_PERIOD_OPTIONS,
        "issue_state_choices": Issue.State.choices,
        "deadline_period_label": ISSUE_DEADLINE_PERIOD_OPTIONS.get(values["deadline_period"], ""),
        "properties": properties,
        "list_query": urlencode(list_parameters),
        "navigation_query": urlencode(navigation_parameters),
        "has_filters": any(
            (
                values["search"],
                values["state"] != "all",
                values["priority"],
                values["property_id"],
                values["deadline_period"],
            )
        ),
        "filter_count": sum(
            bool(value)
            for value in (
                values["state"] != "all",
                values["priority"],
                values["property_id"],
                values["deadline_period"],
            )
        ),
        "today": timezone.localdate(),
        "issue_count": issues_for_user(user=request.user).count(),
        "task_workspace_url": (
            _issue_workspace_url(
                request,
                issue_id=selected_issue.pk,
                tab="tasks",
            )
            if selected_issue
            else reverse("issue:issues")
        ),
    }
