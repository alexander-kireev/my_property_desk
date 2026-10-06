"""Build the task list, selected details and restored forms. Canonical redirects precede token consumption."""

from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.utils import timezone

from config.form_state import (
    deserialise_form_data,
    pop_form_state,
)
from pages.workspace_selection import resolve_selection

from .forms import TaskForm
from .models import Task
from .navigation import _list_query_parameters, _normalised_list_values, _task_workspace_url
from .selectors import (
    TASK_DEADLINE_PERIOD_OPTIONS,
    TASK_SCHEDULE_PERIOD_OPTIONS,
    filtered_tasks_for_user,
    tasks_for_user,
)

TASKS_PER_PAGE = 20


# Rebuild rejected forms from one-use session state.
def _restore_add_task_form(request, state):
    return {
        "add_task_form": TaskForm(
            deserialise_form_data(state.get("data", {})),
            user=request.user,
            auto_id="add_task_%s",
        ),
        "open_modal": "addTaskModal",
    }


def _restore_edit_task_form(request, state):
    task = (
        tasks_for_user(user=request.user)
        .filter(
            pk=state.get("task_id"),
            state=Task.State.ACTIVE,
        )
        .first()
    )
    if task is None:
        return {}
    return {
        "selected_task": task,
        "edit_task_form": TaskForm(
            deserialise_form_data(state.get("data", {})),
            user=request.user,
            instance=task,
            auto_id="edit_task_%s",
        ),
        "open_modal": "editTaskModal",
    }


TASK_FORM_STATE_RESTORERS = {
    "add_task": _restore_add_task_form,
    "edit_task": _restore_edit_task_form,
}


def _restore_task_form_context(request):
    state = pop_form_state(request)
    if not isinstance(state, dict):
        return {}
    restorer = TASK_FORM_STATE_RESTORERS.get(state.get("action"))
    return restorer(request, state) if restorer is not None else {}


# Compose selection, list navigation and detail-panel context.
def _task_list_context(
    request,
    *,
    selected_task=None,
    add_task_form=None,
    edit_task_form=None,
    open_modal=None,
):
    values = _normalised_list_values(request)
    tasks = filtered_tasks_for_user(
        user=request.user,
        **values,
    )
    requested_task, selected_page, outside_filters, selection_redirect = resolve_selection(
        request,
        filtered=tasks,
        owned=tasks_for_user(user=request.user),
        page_size=TASKS_PER_PAGE,
    )
    # Redirect to the selected row's page before consuming one-use form errors.
    if selection_redirect:
        return {"selection_redirect": selection_redirect}
    restored = _restore_task_form_context(request)
    selected_task = restored.get("selected_task", selected_task)
    add_task_form = restored.get("add_task_form", add_task_form)
    edit_task_form = restored.get("edit_task_form", edit_task_form)
    open_modal = restored.get("open_modal", open_modal)

    paginator = Paginator(tasks, TASKS_PER_PAGE)
    page_obj = paginator.get_page(selected_page or request.GET.get("page"))

    if selected_task is None:
        selected_task = requested_task

    if selected_task is None and page_obj.object_list:
        selected_task = page_obj.object_list[0]

    list_parameters = _list_query_parameters(values)
    navigation_parameters = dict(list_parameters)
    if page_obj.number > 1:
        navigation_parameters["page"] = page_obj.number

    return {
        "page_obj": page_obj,
        "selected_task": selected_task,
        "selected_outside_filters": outside_filters,
        "selection_redirect": selection_redirect,
        "add_task_form": (
            add_task_form
            if add_task_form is not None
            else TaskForm(user=request.user, auto_id="add_task_%s")
        ),
        "edit_task_form": (
            edit_task_form
            if edit_task_form is not None
            else (
                TaskForm(
                    user=request.user,
                    instance=selected_task,
                    auto_id="edit_task_%s",
                )
                if selected_task and selected_task.state == Task.State.ACTIVE
                else None
            )
        ),
        "open_modal": open_modal,
        "search": values["search"],
        "state": values["state"],
        "priority": values["priority"],
        "scheduled_period": values["scheduled_period"],
        "deadline_period": values["deadline_period"],
        "sort": values["sort"],
        "schedule_period_options": TASK_SCHEDULE_PERIOD_OPTIONS,
        "deadline_period_options": TASK_DEADLINE_PERIOD_OPTIONS,
        "scheduled_period_label": TASK_SCHEDULE_PERIOD_OPTIONS.get(values["scheduled_period"], ""),
        "deadline_period_label": TASK_DEADLINE_PERIOD_OPTIONS.get(values["deadline_period"], ""),
        "list_query": urlencode(list_parameters),
        "navigation_query": urlencode(navigation_parameters),
        "today": timezone.localdate(),
        "has_filters": any(
            (
                values["search"],
                values["state"] != "all",
                values["priority"],
                values["scheduled_period"],
                values["deadline_period"],
            )
        ),
        "filter_count": sum(
            bool(value)
            for value in (
                values["state"] != "all",
                values["priority"],
                values["scheduled_period"],
                values["deadline_period"],
            )
        ),
        "task_count": tasks_for_user(user=request.user).count(),
        "task_workspace_url": (
            _task_workspace_url(request, task_id=selected_task.pk)
            if selected_task
            else _task_workspace_url(request)
        ),
        "task_list_url": _task_workspace_url(request),
        "show_mobile_detail": request.GET.get("open") in ("detail", "edit")
        or open_modal == "editTaskModal",
        "show_compact_detail": (
            selected_task is not None and request.GET.get("selected") == str(selected_task.pk)
        ),
        "mobile_expanded_task_id": (
            selected_task.pk
            if selected_task is not None
            and request.GET.get("selected") == str(selected_task.pk)
            and request.GET.get("open") not in ("detail", "edit")
            else None
        ),
        "relationship_moved": (
            request.GET.get("moved") == "1"
            and selected_task is not None
            and request.GET.get("selected") == str(selected_task.pk)
        ),
    }
