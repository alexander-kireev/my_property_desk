"""HTTP endpoints for issue work. Page composition lives in workspace; writes use services."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from config.feedback import form_values_changed, snapshot_form_values
from pages.workspace_selection import amended_query_url
from property.navigation import active_property_for_user, created_record_property_url
from task.forms import TaskForm
from task.models import Task
from task.selectors import tasks_for_issue
from task.services import create_task, update_task

from .forms import IssueForm
from .models import Issue
from .navigation import _issue_workspace_url, _redirect_with_issue_form_state
from .selectors import (
    issues_for_user,
)
from .services import (
    create_issue,
    delete_issue,
    dismiss_issue,
    reactivate_issue,
    resolve_issue,
    update_issue,
)
from .workspace import _issue_list_context


@login_required
@require_GET
def issues_view(request):
    if request.GET.get("deadline_period") == "upcoming":
        return redirect(amended_query_url(request, remove=("deadline_period",)))
    context = _issue_list_context(request)
    if context["selection_redirect"]:
        return redirect(context["selection_redirect"])
    origin = None
    if request.GET.get("open") == "add" and not context["open_modal"]:
        origin = active_property_for_user(request.user, request.GET.get("property"))
        if origin:
            context["add_issue_form"].initial["property"] = origin.pk
            context["open_modal"] = "addIssueModal"
    elif context["open_modal"] == "addIssueModal":
        origin = active_property_for_user(
            request.user, context["add_issue_form"].data.get("return_property")
        )
    context["return_property_id"] = origin.pk if origin else None
    if request.GET.get("open") == "edit" and context["edit_issue_form"] is not None:
        context["open_modal"] = "editIssueModal"
    return render(
        request,
        "issue/issues.html",
        context,
    )


@login_required
@require_POST
def add_issue_view(request):
    form = IssueForm(
        request.POST,
        user=request.user,
        auto_id="add_issue_%s",
    )
    if form.is_valid():
        issue = create_issue(user=request.user, **form.cleaned_data)
        messages.success(request, "Issue added.")
        property_url = created_record_property_url(
            issue, request.POST.get("return_property"), "issue"
        )
        if property_url:
            return redirect(property_url)
        return redirect(_issue_workspace_url(request, issue_id=issue.pk, clear_filters=True))
    return _redirect_with_issue_form_state(
        request,
        action="add_issue",
    )


@login_required
@require_POST
def edit_issue_view(request, issue_id):
    issue = get_object_or_404(
        issues_for_user(user=request.user), pk=issue_id, state=Issue.State.ACTIVE
    )
    form = IssueForm(
        request.POST,
        user=request.user,
        instance=issue,
        auto_id="edit_issue_%s",
    )
    before = snapshot_form_values(form)
    if form.is_valid():
        if form_values_changed(before, form):
            update_issue(issue=issue, **form.cleaned_data)
            messages.success(request, "Issue updated.")
        return redirect(_issue_workspace_url(request, issue_id=issue.pk))
    return _redirect_with_issue_form_state(
        request,
        action="edit_issue",
        issue_id=issue.pk,
    )


@login_required
@require_POST
def resolve_issue_view(request, issue_id):
    issue = get_object_or_404(
        issues_for_user(user=request.user), pk=issue_id, state=Issue.State.ACTIVE
    )
    resolve_issue(
        issue=issue,
        dismiss_linked_tasks=request.POST.get("affect_linked_tasks") == "yes",
    )
    count = issue.affected_linked_tasks
    detail = f" {count} linked task{'s' if count != 1 else ''} dismissed." if count else ""
    if issue.action_changed:
        messages.success(request, f"Issue resolved.{detail}")
    property_url = (
        f"{reverse('property:property_detail', args=[issue.property_id])}?tab=work"
        if issue.property_id
        else None
    )
    if property_url and request.POST.get("next") == property_url:
        return redirect(property_url)
    return redirect(_issue_workspace_url(request, issue_id=issue.pk))


@login_required
@require_POST
def dismiss_issue_view(request, issue_id):
    issue = get_object_or_404(
        issues_for_user(user=request.user), pk=issue_id, state=Issue.State.ACTIVE
    )
    dismiss_issue(
        issue=issue,
        dismiss_linked_tasks=request.POST.get("affect_linked_tasks") == "yes",
    )
    count = issue.affected_linked_tasks
    detail = f" {count} linked task{'s' if count != 1 else ''} dismissed." if count else ""
    if issue.action_changed:
        messages.success(request, f"Issue dismissed.{detail}")
    return redirect(_issue_workspace_url(request, issue_id=issue.pk))


@login_required
@require_POST
def reactivate_issue_view(request, issue_id):
    issue = get_object_or_404(
        issues_for_user(user=request.user),
        pk=issue_id,
        state__in=[Issue.State.RESOLVED, Issue.State.DISMISSED],
    )
    reactivate_issue(issue=issue)
    messages.success(request, "Issue reactivated.")
    return redirect(_issue_workspace_url(request, issue_id=issue.pk))


@login_required
@require_POST
def delete_issue_view(request, issue_id):
    issue = get_object_or_404(issues_for_user(user=request.user), pk=issue_id)
    delete_issue(
        issue=issue,
        delete_linked_tasks=request.POST.get("affect_linked_tasks") == "yes",
    )
    count = issue.affected_linked_tasks
    detail = f" {count} linked task{'s' if count != 1 else ''} deleted." if count else ""
    if issue.action_changed:
        messages.success(request, f"Issue deleted.{detail}")
    return redirect(_issue_workspace_url(request))


@login_required
@require_POST
def add_issue_task_view(request, issue_id):
    issue = get_object_or_404(
        issues_for_user(user=request.user), pk=issue_id, state=Issue.State.ACTIVE
    )
    form = TaskForm(
        request.POST,
        user=request.user,
        parent_issue=issue,
        auto_id="add_issue_task_%s",
    )
    if form.is_valid():
        create_task(
            user=request.user,
            property=None,
            issue=issue,
            **form.cleaned_data,
        )
        messages.success(request, "Task added to issue.")
        return redirect(_issue_workspace_url(request, issue_id=issue.pk, tab="tasks"))
    return _redirect_with_issue_form_state(
        request,
        action="add_issue_task",
        issue_id=issue.pk,
        tab="tasks",
    )


@login_required
@require_POST
def edit_issue_task_view(request, issue_id, task_id):
    issue = get_object_or_404(
        issues_for_user(user=request.user), pk=issue_id, state=Issue.State.ACTIVE
    )
    task = get_object_or_404(
        tasks_for_issue(user=request.user, issue=issue),
        pk=task_id,
        state=Task.State.ACTIVE,
    )
    form = TaskForm(
        request.POST,
        user=request.user,
        instance=task,
        auto_id="edit_issue_task_%s",
    )
    before = snapshot_form_values(form)
    if form.is_valid():
        if form_values_changed(before, form):
            update_task(task=task, **form.cleaned_data)
            messages.success(request, "Task updated.")
        if task.issue_id != issue.pk:
            return redirect(f"{reverse('task:tasks')}?selected={task.pk}&moved=1")
        return redirect(_issue_workspace_url(request, issue_id=issue.pk, tab="tasks"))
    return _redirect_with_issue_form_state(
        request,
        action="edit_issue_task",
        issue_id=issue.pk,
        object_id=task.pk,
        tab="tasks",
    )
