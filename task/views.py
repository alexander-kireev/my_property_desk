"""HTTP endpoints for task work. Page composition lives in workspace; writes use services."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from config.feedback import form_values_changed, snapshot_form_values
from pages.workspace_selection import amended_query_url
from property.navigation import active_property_for_user, created_record_property_url

from .forms import TaskForm
from .models import Task
from .navigation import _redirect_with_task_form_state, _task_action_redirect, _task_workspace_url
from .selectors import (
    tasks_for_user,
)
from .services import (
    complete_task,
    create_task,
    delete_task,
    dismiss_task,
    reactivate_task,
    update_task,
)
from .workspace import _task_list_context


@login_required
@require_GET
def tasks_view(request):
    stale = tuple(
        name
        for name in ("scheduled_period", "deadline_period")
        if request.GET.get(name) == "upcoming"
    )
    if stale:
        return redirect(amended_query_url(request, remove=stale))
    context = _task_list_context(request)
    if context["selection_redirect"]:
        return redirect(context["selection_redirect"])
    origin = None
    if request.GET.get("open") == "add" and not context["open_modal"]:
        origin = active_property_for_user(request.user, request.GET.get("property"))
        if origin:
            context["add_task_form"].initial["property"] = origin.pk
            context["open_modal"] = "addTaskModal"
    elif context["open_modal"] == "addTaskModal":
        origin = active_property_for_user(
            request.user, context["add_task_form"].data.get("return_property")
        )
    context["return_property_id"] = origin.pk if origin else None
    if request.GET.get("open") == "edit" and context["edit_task_form"] is not None:
        context["open_modal"] = "editTaskModal"
        context["show_mobile_detail"] = True
    return render(
        request,
        "task/tasks.html",
        context,
    )


@login_required
@require_POST
def add_task_view(request):
    form = TaskForm(
        request.POST,
        user=request.user,
        auto_id="add_task_%s",
    )
    if form.is_valid():
        task = create_task(user=request.user, **form.cleaned_data)
        messages.success(request, "Task added.")
        property_url = created_record_property_url(
            task, request.POST.get("return_property"), "task"
        )
        if property_url:
            return redirect(property_url)
        return redirect(_task_workspace_url(request, task_id=task.pk, clear_filters=True))
    return _redirect_with_task_form_state(
        request,
        action="add_task",
    )


@login_required
@require_POST
def edit_task_view(request, task_id):
    task = get_object_or_404(
        tasks_for_user(user=request.user),
        pk=task_id,
        state=Task.State.ACTIVE,
    )
    form = TaskForm(
        request.POST,
        user=request.user,
        instance=task,
        auto_id="edit_task_%s",
    )
    before = snapshot_form_values(form)
    if form.is_valid():
        if form_values_changed(before, form):
            update_task(task=task, **form.cleaned_data)
            messages.success(request, "Task updated.")
        return redirect(_task_workspace_url(request, task_id=task.pk))
    return _redirect_with_task_form_state(
        request,
        action="edit_task",
        task_id=task.pk,
    )


@login_required
@require_POST
def dismiss_task_view(request, task_id):
    task = get_object_or_404(
        tasks_for_user(user=request.user),
        pk=task_id,
        state=Task.State.ACTIVE,
    )
    dismiss_task(task=task)
    if task.action_changed:
        messages.success(request, "Task dismissed.")
    return _task_action_redirect(request, task=task)


@login_required
@require_POST
def complete_task_view(request, task_id):
    task = get_object_or_404(
        tasks_for_user(user=request.user),
        pk=task_id,
        state=Task.State.ACTIVE,
    )
    complete_task(task=task)
    if task.action_changed:
        messages.success(request, "Task completed.")
    return _task_action_redirect(request, task=task)


@login_required
@require_POST
def reactivate_task_view(request, task_id):
    task = get_object_or_404(
        tasks_for_user(user=request.user),
        pk=task_id,
        state__in=[Task.State.DISMISSED, Task.State.COMPLETED],
    )
    reactivate_task(task=task)
    if task.action_changed:
        messages.success(request, "Task reactivated.")
    return _task_action_redirect(request, task=task)


@login_required
@require_POST
def delete_task_view(request, task_id):
    task = get_object_or_404(tasks_for_user(user=request.user), pk=task_id)
    delete_task(task=task)
    if task.action_changed:
        messages.success(request, "Task deleted.")
    return _task_action_redirect(request, task=task, deleted=True)
