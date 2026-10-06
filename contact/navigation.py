"""Contact filter normalization, canonical pages and return URLs."""

from urllib.parse import urlencode, urlsplit

from django.core.paginator import Paginator
from django.http import QueryDict
from django.shortcuts import redirect
from django.urls import reverse

from config.form_state import (
    serialise_form_data,
    store_form_state,
)
from pages.workspace_selection import resolve_selection

from .models import Contact
from .selectors import (
    CONTACT_SORT_OPTIONS,
    contacts_for_user,
    filtered_contacts_for_user,
)

CONTACTS_PER_PAGE = 20


CONTACT_WORKSPACE_TABS = ("details", "notes")


def _normalised_list_values(request):
    search = request.GET.get("search", "").strip()
    state = request.GET.get("state", "")
    sort = request.GET.get("sort", "name")

    if state not in (*Contact.State.values, "all"):
        state = ""
    if sort not in CONTACT_SORT_OPTIONS:
        sort = "name"

    return {"search": search, "state": state, "sort": sort}


def _canonical_contacts_url(request):
    """Make invalid list choices agree with the state rendered by the workspace."""
    invalid_choice = any(
        name in request.GET and request.GET.get(name) not in accepted
        for name, accepted in (
            ("state", (*Contact.State.values, "all", "")),
            ("sort", CONTACT_SORT_OPTIONS),
            ("tab", CONTACT_WORKSPACE_TABS),
        )
    )
    if not invalid_choice and "page" not in request.GET:
        return None

    parameters = request.GET.copy()
    values = _normalised_list_values(request)
    contacts = filtered_contacts_for_user(
        user=request.user,
        **{**values, "state": values["state"] or "all"},
    )
    _, _, _, selection_redirect = resolve_selection(
        request,
        filtered=contacts,
        owned=contacts_for_user(user=request.user),
        page_size=CONTACTS_PER_PAGE,
    )
    if selection_redirect:
        parameters = QueryDict(urlsplit(selection_redirect).query, mutable=True)

    for name, accepted in (
        ("state", (*Contact.State.values, "all", "")),
        ("sort", CONTACT_SORT_OPTIONS),
        ("tab", CONTACT_WORKSPACE_TABS),
    ):
        if name in parameters and parameters.get(name) not in accepted:
            parameters.pop(name)

    if "page" in parameters:
        actual_page = Paginator(contacts, CONTACTS_PER_PAGE).get_page(parameters.get("page")).number
        if parameters.get("page") != str(actual_page):
            if actual_page == 1:
                parameters.pop("page")
            else:
                parameters["page"] = str(actual_page)

    if parameters == request.GET:
        return None
    query = parameters.urlencode()
    url = reverse("contact:contacts")
    return f"{url}?{query}" if query else url


def _list_query_parameters(values):
    parameters = {}
    for name in ("search", "state"):
        if values[name]:
            parameters[name] = values[name]
    if values["sort"] != "name":
        parameters["sort"] = values["sort"]
    return parameters


def _contact_workspace_url(
    request,
    *,
    contact_id=None,
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
    if contact_id is not None:
        parameters["selected"] = contact_id
    if tab == "notes":
        parameters["tab"] = "notes"
    if form_state is not None:
        parameters["form_state"] = form_state

    url = reverse("contact:contacts")
    return f"{url}?{urlencode(parameters)}" if parameters else url


def _redirect_with_contact_form_state(
    request,
    *,
    action,
    contact_id=None,
    object_id=None,
    tab="details",
):
    state = {
        "action": action,
        "contact_id": contact_id,
        "object_id": object_id,
        "data": serialise_form_data(request.POST),
    }
    token = store_form_state(request, state)
    return redirect(
        _contact_workspace_url(
            request,
            contact_id=contact_id,
            tab=tab,
            form_state=token,
        )
    )
