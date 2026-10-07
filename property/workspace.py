"""Compose Property list/detail forms and related work without performing writes."""

from urllib.parse import urlencode

from django.core.paginator import Paginator

from config.form_state import (
    deserialise_form_data,
)
from pages.workspace_selection import amended_query_url, page_for_record, resolve_selection

from .forms import PropertyForm
from .models import Property
from .navigation import (
    _list_query_parameters,
    _normalised_list_values,
)
from .related_records import related_records_context
from .selectors import (
    filtered_properties_for_user,
    properties_for_user,
    with_work_summary,
)
from .services import (
    related_work_counts,
)

PROPERTIES_PER_PAGE = 20


def _property_record_forms(request, property_record, *, data=None, kind=None):
    """The three add forms share the property page, not the My work workspace."""
    from event.forms import EventContactForm, EventForm
    from issue.forms import IssueForm
    from task.forms import TaskForm

    def form_data(form_kind):
        return data if kind == form_kind else None

    return {
        "property_add_task_form": TaskForm(
            form_data("task"),
            user=request.user,
            auto_id="property_add_task_%s",
            initial={"property": property_record.pk},
        ),
        "property_add_issue_form": IssueForm(
            form_data("issue"),
            user=request.user,
            auto_id="property_add_issue_%s",
            initial={"property": property_record.pk},
        ),
        "property_add_event_form": EventForm(
            form_data("event"),
            user=request.user,
            auto_id="property_add_event_%s",
            initial={"property": property_record.pk},
        ),
        "property_event_contacts_form": EventContactForm(
            form_data("event"),
            user=request.user,
            auto_id="property_event_contacts_%s",
        ),
    }


def _restore_add_property_form(request, state):
    return PropertyForm(
        deserialise_form_data(state.get("data", {})),
        user=request.user,
        auto_id="add_property_%s",
    )


def _restore_edit_property_form(request, state, property_record):
    if (
        state.get("property_id") != property_record.pk
        or property_record.state != Property.State.ACTIVE
    ):
        return None
    return PropertyForm(
        deserialise_form_data(state.get("data", {})),
        user=request.user,
        instance=property_record,
        auto_id="edit_property_%s",
    )


def _property_list_context(
    request,
    *,
    add_property_form=None,
    edit_property_form=None,
    edit_property_record=None,
    page_override=None,
):
    values = _normalised_list_values(request)
    properties = filtered_properties_for_user(
        user=request.user,
        **{**values, "state": values["state"] or "all"},
    )
    requested_property, selected_page, outside_filters, selection_redirect = resolve_selection(
        request,
        filtered=properties,
        owned=properties_for_user(user=request.user),
        page_size=PROPERTIES_PER_PAGE,
    )

    paginator = Paginator(with_work_summary(properties), PROPERTIES_PER_PAGE)
    page_obj = paginator.get_page(page_override or selected_page or request.GET.get("page"))

    query_parameters = _list_query_parameters(values)
    return_parameters = query_parameters.copy()
    return_parameters["return_to"] = "list"
    if page_obj.number > 1:
        return_parameters["page"] = page_obj.number
    navigation_parameters = query_parameters.copy()
    if page_obj.number > 1:
        navigation_parameters["page"] = page_obj.number

    selected_property = edit_property_record or requested_property
    requested_id = request.GET.get("selected", "")
    if selected_property is None and page_obj.object_list:
        selected_property = page_obj.object_list[0]
    return {
        "add_property_form": (
            add_property_form
            if add_property_form is not None
            else PropertyForm(user=request.user, auto_id="add_property_%s")
        ),
        "page_obj": page_obj,
        "list_edit_form": edit_property_form
        or PropertyForm(user=request.user, auto_id="list_edit_%s"),
        "list_return_query": urlencode(return_parameters),
        "navigation_query": urlencode(navigation_parameters),
        "search": values["search"],
        "state": values["state"],
        "sort": values["sort"],
        "list_query": urlencode(query_parameters),
        "has_filters": bool(values["search"] or values["state"] not in ("", "all")),
        "property_count": properties_for_user(user=request.user).count(),
        "selected_property": selected_property,
        "mobile_expanded_property_id": (
            selected_property.pk
            if selected_property is not None
            and requested_id == str(selected_property.pk)
            and not outside_filters
            else None
        ),
        "selected_in_page": selected_page is not None or requested_property is None,
        "selected_outside_filters": outside_filters,
        "selection_redirect": None if request.GET.get("form_state") else selection_redirect,
        "is_detail_route": False,
    }


def _property_detail_context(
    request, property_record, *, edit_property_form=None, list_context=None
):
    related_context = related_records_context(request, property_record)

    selection_redirect = None
    if list_context is None:
        values = _normalised_list_values(request)
        filtered = filtered_properties_for_user(
            user=request.user,
            **{**values, "state": values["state"] or "all"},
        )
        natural_page = page_for_record(filtered, property_record.pk, PROPERTIES_PER_PAGE)
        if natural_page is not None:
            wanted = str(natural_page) if natural_page > 1 else ""
            if request.GET.get("page", "") != wanted:
                selection_redirect = amended_query_url(
                    request,
                    changes={"page": natural_page if natural_page > 1 else None},
                )
        context = _property_list_context(request, page_override=natural_page)
    else:
        context = list_context
    linked_counts = related_work_counts(property_record=property_record)
    context.update(
        {
            "property": property_record,
            "selected_property": property_record,
            "related_work_counts": linked_counts,
            "linked_work_option_count": sum(
                bool(linked_counts[key])
                for key in ("events_scheduled", "issues_active", "tasks_active")
            ),
            "selected_in_page": any(
                item.pk == property_record.pk for item in context["page_obj"].object_list
            ),
            "selected_outside_filters": (
                natural_page is None
                if list_context is None
                else context["selected_outside_filters"]
            ),
            "selection_redirect": selection_redirect,
            "is_detail_route": list_context is None,
            **related_context,
            "edit_property_form": (
                edit_property_form
                if edit_property_form is not None
                else PropertyForm(
                    user=request.user, instance=property_record, auto_id="edit_property_%s"
                )
            ),
        }
    )
    if property_record.state == Property.State.ACTIVE:
        context.update(_property_record_forms(request, property_record))
    return context
