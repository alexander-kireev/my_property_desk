"""Compose the Event list, participants, calendar queries and restored forms."""

from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.utils import timezone

from config.form_state import (
    deserialise_form_data,
    pop_form_state,
)
from pages.workspace_selection import resolve_selection
from property.selectors import properties_for_user

from .calendar import calendar_details, month_weeks, shift_month
from .forms import EventContactForm, EventForm
from .models import Event, EventContact
from .navigation import (
    DEFAULT_EVENT_STATE,
    _calendar_month,
    _calendar_query,
    _date_parameter,
    _list_query_parameters,
    _normalised_list_values,
    _participant_origin_parameters,
    _selected_day,
)
from .selectors import (
    calendar_events_for_user,
    event_contacts_for_event,
    events_for_user,
    filtered_events_for_user,
)

EVENTS_PER_PAGE = 20


# Rebuild rejected forms from one-use session state.
def _scheduled_event_from_form_state(request, state):
    return (
        events_for_user(user=request.user)
        .filter(
            pk=state.get("event_id"),
            state=Event.State.SCHEDULED,
        )
        .first()
    )


def _restore_add_event_forms(request, state):
    data = deserialise_form_data(state.get("data", {}))
    return {
        "add_event_form": EventForm(
            data,
            user=request.user,
            auto_id="add_event_%s",
        ),
        "initial_contacts_form": EventContactForm(
            data,
            user=request.user,
            auto_id="initial_contacts_%s",
        ),
        "open_modal": "addEventModal",
    }


def _restore_edit_event_form(request, state):
    event = _scheduled_event_from_form_state(request, state)
    if event is None:
        return {}
    data = deserialise_form_data(state.get("data", {}))
    return {
        "selected_event": event,
        "edit_event_form": EventForm(
            data,
            user=request.user,
            instance=event,
            auto_id="edit_event_%s",
        ),
        "edit_contacts_form": EventContactForm(
            data if data.get("manage_contacts") == "1" else None,
            user=request.user,
            event=event,
            include_existing=True,
            auto_id="edit_contacts_%s",
        ),
        "active_tab": "details",
        "open_modal": "editEventModal",
    }


def _restore_add_event_contacts_form(request, state):
    event = _scheduled_event_from_form_state(request, state)
    if event is None:
        return {}
    return {
        "selected_event": event,
        "add_contacts_form": EventContactForm(
            deserialise_form_data(state.get("data", {})),
            user=request.user,
            event=event,
            auto_id="event_contacts_%s",
        ),
        "active_tab": _participant_origin_parameters(request).get("tab", "details"),
        "open_modal": "addEventContactsModal",
    }


EVENT_FORM_STATE_RESTORERS = {
    "add_event": _restore_add_event_forms,
    "edit_event": _restore_edit_event_form,
    "add_event_contacts": _restore_add_event_contacts_form,
}


def _restore_event_form_context(request):
    state = pop_form_state(request)
    if not isinstance(state, dict):
        return {}
    restorer = EVENT_FORM_STATE_RESTORERS.get(state.get("action"))
    return restorer(request, state) if restorer is not None else {}


# Compose selection, list navigation and detail-panel context.
def _event_list_context(
    request,
    *,
    selected_event=None,
    add_event_form=None,
    initial_contacts_form=None,
    edit_event_form=None,
    edit_contacts_form=None,
    add_contacts_form=None,
    active_tab=None,
    open_modal=None,
):
    values = _normalised_list_values(request)
    selected_day = _selected_day(request)
    events = filtered_events_for_user(user=request.user, **values)
    if selected_day is not None:
        events = events.filter(scheduled_date=selected_day)
        if values["sort"] == "scheduled_date":
            events = events.order_by("-all_day", "start_time", "title", "pk")
    requested_event, selected_page, outside_filters, selection_redirect = resolve_selection(
        request,
        filtered=events,
        owned=events_for_user(user=request.user),
        page_size=EVENTS_PER_PAGE,
    )
    # Redirect to the selected row's page before consuming one-use form errors.
    if selection_redirect:
        return {"selection_redirect": selection_redirect}
    restored = _restore_event_form_context(request)
    selected_event = restored.get("selected_event", selected_event)
    add_event_form = restored.get("add_event_form", add_event_form)
    initial_contacts_form = restored.get("initial_contacts_form", initial_contacts_form)
    edit_event_form = restored.get("edit_event_form", edit_event_form)
    edit_contacts_form = restored.get("edit_contacts_form", edit_contacts_form)
    add_contacts_form = restored.get("add_contacts_form", add_contacts_form)
    active_tab = restored.get("active_tab", active_tab)
    open_modal = restored.get("open_modal", open_modal)

    paginator = Paginator(events, EVENTS_PER_PAGE)
    page_obj = paginator.get_page(selected_page or request.GET.get("page"))

    if selected_event is None:
        selected_event = requested_event
        if selected_event is None and page_obj.object_list:
            selected_event = page_obj.object_list[0]

    requested_tab = active_tab or request.GET.get("tab")
    if requested_tab not in ("details", "calendar"):
        requested_tab = "details"

    list_parameters = _list_query_parameters(values)
    if selected_day is not None:
        list_parameters["day"] = selected_day.isoformat()
    navigation_parameters = dict(list_parameters)
    if page_obj.number > 1:
        navigation_parameters["page"] = page_obj.number

    displayed_month = _calendar_month(request)
    month_dates = month_weeks(displayed_month)
    calendar_events = list(
        calendar_events_for_user(
            user=request.user,
            start_date=month_dates[0][0],
            end_date=month_dates[-1][-1],
            **values,
        )
    )
    today = timezone.localdate()
    calendar_context = calendar_details(
        displayed_month,
        calendar_events,
        selected_day=selected_day,
        agenda_day=_date_parameter(request, "agenda_day"),
        today=today,
    )

    day_query_parameters = _list_query_parameters(values)
    day_query_parameters.update({"month": displayed_month.month, "year": displayed_month.year})

    navigation_parameters.update(
        {
            "month": displayed_month.month,
            "year": displayed_month.year,
        }
    )
    properties = properties_for_user(user=request.user).order_by("name", "pk")
    selected_event_is_active = (
        selected_event is not None and selected_event.state == Event.State.SCHEDULED
    )
    participants = (
        event_contacts_for_event(event=selected_event)
        if selected_event is not None
        else EventContact.objects.none()
    )

    return {
        "page_obj": page_obj,
        "selected_event": selected_event,
        "selected_outside_filters": outside_filters,
        "selection_redirect": selection_redirect,
        "show_compact_detail": (
            selected_event is not None and request.GET.get("selected") == str(selected_event.pk)
        ),
        "mobile_expanded_event_id": (
            selected_event.pk
            if selected_event is not None and request.GET.get("selected") == str(selected_event.pk)
            else None
        ),
        "participants": participants,
        "add_event_form": add_event_form
        if add_event_form is not None
        else EventForm(user=request.user, auto_id="add_event_%s"),
        "initial_contacts_form": (
            initial_contacts_form
            if initial_contacts_form is not None
            else EventContactForm(user=request.user, auto_id="initial_contacts_%s")
        ),
        "edit_event_form": (
            edit_event_form
            if edit_event_form is not None
            else EventForm(
                user=request.user,
                instance=selected_event,
                auto_id="edit_event_%s",
            )
            if selected_event_is_active
            else None
        ),
        "edit_contacts_form": (
            edit_contacts_form
            if edit_contacts_form is not None
            else EventContactForm(
                user=request.user,
                event=selected_event,
                include_existing=True,
                auto_id="edit_contacts_%s",
            )
            if selected_event_is_active
            else None
        ),
        "add_contacts_form": (
            add_contacts_form
            if add_contacts_form is not None
            else EventContactForm(
                user=request.user,
                event=selected_event,
                auto_id="event_contacts_%s",
            )
            if selected_event_is_active
            else None
        ),
        "active_tab": requested_tab,
        "mobile_calendar_view": request.GET.get("view") == "calendar",
        "open_modal": open_modal,
        "search": values["search"],
        "state": values["state"],
        "sort": values["sort"],
        "property_id": values["property_id"],
        "participation": values["participation"],
        "presence": values["presence"],
        "event_state_choices": Event.State.choices,
        "properties": properties,
        "list_query": urlencode(list_parameters),
        "selected_day": selected_day,
        "day_query_base": urlencode(day_query_parameters),
        "clear_day_query": urlencode(day_query_parameters),
        "navigation_query": urlencode(navigation_parameters),
        "participant_navigation_query": urlencode(
            {**navigation_parameters, **_participant_origin_parameters(request)}
        ),
        "calendar_month_label": displayed_month.strftime("%B %Y"),
        "calendar_month_number": displayed_month.month,
        "calendar_year": displayed_month.year,
        "calendar_weekdays": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
        **calendar_context,
        "previous_month_query": _calendar_query(values, shift_month(displayed_month, -1)),
        "next_month_query": _calendar_query(values, shift_month(displayed_month, 1)),
        "previous_year_query": _calendar_query(values, shift_month(displayed_month, -12)),
        "next_year_query": _calendar_query(values, shift_month(displayed_month, 12)),
        "today_query": _calendar_query(values, today.replace(day=1)),
        "has_filters": any(
            (
                values["search"],
                values["state"] != DEFAULT_EVENT_STATE,
                values["property_id"],
                values["participation"] != "any",
                values["presence"] != "any",
            )
        ),
        "filter_count": sum(
            bool(value)
            for value in (
                values["state"] != DEFAULT_EVENT_STATE,
                values["property_id"],
                values["participation"] != "any",
                values["presence"] != "any",
            )
        ),
        "event_count": events_for_user(user=request.user).count(),
    }
