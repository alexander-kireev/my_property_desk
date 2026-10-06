"""Compose Contact methods, Notes and restored forms. Writes remain in services."""

from urllib.parse import urlencode

from django.core.paginator import Paginator

from config.form_state import (
    deserialise_form_data,
    pop_form_state,
)
from note.forms import NoteForm
from note.selectors import (
    notes_for_contact,
)
from pages.workspace_selection import resolve_selection

from .forms import ContactCreateForm, ContactForm, ContactMethodForm
from .models import Contact
from .navigation import (
    CONTACT_WORKSPACE_TABS,
    CONTACTS_PER_PAGE,
    _list_query_parameters,
    _normalised_list_values,
)
from .selectors import (
    contact_methods_for_contact,
    contacts_for_user,
    filtered_contacts_for_user,
)


# Rebuild rejected forms from one-use session state.
def _active_contact_from_form_state(request, state):
    return (
        contacts_for_user(user=request.user)
        .filter(
            pk=state.get("contact_id"),
            state=Contact.State.ACTIVE,
        )
        .first()
    )


def _restore_add_contact_form(request, state):
    return {
        "add_contact_form": ContactCreateForm(
            deserialise_form_data(state.get("data", {})),
            auto_id="add_contact_%s",
        ),
        "open_modal": "addContactModal",
    }


def _restore_edit_contact_form(request, state):
    contact = _active_contact_from_form_state(request, state)
    if contact is None:
        return {}

    return {
        "selected_contact": contact,
        "edit_contact_form": ContactForm(
            deserialise_form_data(state.get("data", {})),
            instance=contact,
            auto_id="edit_contact_%s",
        ),
        "active_tab": "details",
        "open_modal": "editContactModal",
    }


def _restore_add_contact_method_form(request, state):
    contact = _active_contact_from_form_state(request, state)
    if contact is None:
        return {}

    return {
        "selected_contact": contact,
        "add_contact_method_form": ContactMethodForm(
            deserialise_form_data(state.get("data", {})),
            contact=contact,
            auto_id="add_contact_method_%s",
        ),
        "active_tab": "details",
        "open_modal": "addContactMethodModal",
    }


def _restore_edit_contact_method_form(request, state):
    contact = _active_contact_from_form_state(request, state)
    if contact is None:
        return {}

    contact_method = (
        contact_methods_for_contact(contact=contact)
        .filter(
            pk=state.get("object_id"),
        )
        .first()
    )
    if contact_method is None:
        return {}

    return {
        "selected_contact": contact,
        "edit_contact_method": contact_method,
        "edit_contact_method_form": ContactMethodForm(
            deserialise_form_data(state.get("data", {})),
            instance=contact_method,
            contact=contact,
            auto_id="edit_contact_method_%s",
        ),
        "active_tab": "details",
        "open_modal": "editContactMethodModal",
    }


def _restore_add_contact_note_form(request, state):
    contact = _active_contact_from_form_state(request, state)
    if contact is None:
        return {}

    return {
        "selected_contact": contact,
        "add_contact_note_form": NoteForm(
            deserialise_form_data(state.get("data", {})),
            auto_id="add_note_%s",
        ),
        "active_tab": "notes",
    }


def _restore_edit_contact_note_form(request, state):
    contact = _active_contact_from_form_state(request, state)
    if contact is None:
        return {}

    note = (
        notes_for_contact(
            user=request.user,
            contact=contact,
        )
        .filter(pk=state.get("object_id"))
        .first()
    )
    if note is None:
        return {}

    return {
        "selected_contact": contact,
        "edit_contact_note": note,
        "edit_contact_note_form": NoteForm(
            deserialise_form_data(state.get("data", {})),
            instance=note,
            auto_id="edit_contact_note_%s",
        ),
        "active_tab": "notes",
    }


CONTACT_FORM_STATE_RESTORERS = {
    "add_contact": _restore_add_contact_form,
    "edit_contact": _restore_edit_contact_form,
    "add_contact_method": _restore_add_contact_method_form,
    "edit_contact_method": _restore_edit_contact_method_form,
    "add_contact_note": _restore_add_contact_note_form,
    "edit_contact_note": _restore_edit_contact_note_form,
}


def _restore_contact_form_context(request):
    state = pop_form_state(request)
    if not isinstance(state, dict):
        return {}

    restorer = CONTACT_FORM_STATE_RESTORERS.get(state.get("action"))
    if restorer is None:
        return {}

    return restorer(request, state)


# Compose selection, list navigation and detail-panel context.
def _contact_list_context(
    request,
    *,
    selected_contact=None,
    add_contact_form=None,
    edit_contact_form=None,
    add_contact_method_form=None,
    edit_contact_method=None,
    edit_contact_method_form=None,
    active_tab=None,
    open_modal=None,
    add_contact_note_form=None,
    edit_contact_note=None,
    edit_contact_note_form=None,
):
    values = _normalised_list_values(request)
    contacts = filtered_contacts_for_user(
        user=request.user,
        **{**values, "state": values["state"] or "all"},
    )
    requested_contact, selected_page, outside_filters, selection_redirect = resolve_selection(
        request,
        filtered=contacts,
        owned=contacts_for_user(user=request.user),
        page_size=CONTACTS_PER_PAGE,
    )
    paginator = Paginator(contacts, CONTACTS_PER_PAGE)
    page_obj = paginator.get_page(selected_page or request.GET.get("page"))

    if selected_contact is None:
        selected_contact = requested_contact

    if selected_contact is None and page_obj.object_list:
        selected_contact = page_obj.object_list[0]

    requested_tab = active_tab or request.GET.get("tab", "details")
    if requested_tab not in CONTACT_WORKSPACE_TABS:
        requested_tab = "details"

    contact_methods = []
    email_methods = []
    telephone_methods = []
    notes = []

    selected_contact_is_active = (
        selected_contact is not None and selected_contact.state == Contact.State.ACTIVE
    )

    if selected_contact is not None:
        if requested_tab == "details":
            contact_methods = list(selected_contact.contact_methods.all())
            email_methods = [
                method for method in contact_methods if method.type == method.Type.EMAIL
            ]
            telephone_methods = [
                method for method in contact_methods if method.type == method.Type.TELEPHONE
            ]

            if add_contact_method_form is None and selected_contact_is_active:
                add_contact_method_form = ContactMethodForm(
                    contact=selected_contact,
                    auto_id="add_contact_method_%s",
                )

            if edit_contact_method is None and selected_contact.state == Contact.State.ACTIVE:
                try:
                    edit_method_id = int(request.GET.get("edit_method", ""))
                except TypeError, ValueError:
                    edit_method_id = None

                for method in contact_methods:
                    if method.pk == edit_method_id:
                        edit_contact_method = method
                        break

            if edit_contact_method_form is None and edit_contact_method is not None:
                edit_contact_method_form = ContactMethodForm(
                    instance=edit_contact_method,
                    contact=selected_contact,
                    auto_id="edit_contact_method_%s",
                )

            if edit_contact_method is not None and open_modal is None:
                open_modal = "editContactMethodModal"

        else:
            notes = list(notes_for_contact(user=request.user, contact=selected_contact))

            if add_contact_note_form is None and selected_contact_is_active:
                add_contact_note_form = NoteForm(auto_id="add_note_%s")

    list_parameters = _list_query_parameters(values)
    navigation_parameters = dict(list_parameters)
    if page_obj.number > 1:
        navigation_parameters["page"] = page_obj.number

    if add_contact_form is None:
        add_contact_form = ContactCreateForm(auto_id="add_contact_%s")

    if edit_contact_form is None and selected_contact_is_active:
        edit_contact_form = ContactForm(instance=selected_contact, auto_id="edit_contact_%s")

    return {
        "page_obj": page_obj,
        "selected_contact": selected_contact,
        "selected_outside_filters": outside_filters,
        "selection_redirect": selection_redirect,
        "contact_methods": contact_methods,
        "email_methods": email_methods,
        "telephone_methods": telephone_methods,
        "notes": notes,
        "add_contact_form": add_contact_form,
        "edit_contact_form": edit_contact_form,
        "add_contact_method_form": add_contact_method_form,
        "edit_contact_method": edit_contact_method,
        "edit_contact_method_form": edit_contact_method_form,
        "add_contact_note_form": add_contact_note_form,
        "edit_contact_note": edit_contact_note,
        "edit_contact_note_form": edit_contact_note_form,
        "active_tab": requested_tab,
        "open_modal": open_modal,
        "search": values["search"],
        "state": values["state"],
        "sort": values["sort"],
        "list_query": urlencode(list_parameters),
        "navigation_query": urlencode(navigation_parameters),
        "has_filters": bool(values["search"] or values["state"] not in ("", "all")),
        "contact_count": contacts_for_user(user=request.user).count(),
        "show_mobile_detail": bool(request.GET.get("selected"))
        or open_modal
        in (
            "editContactModal",
            "addContactMethodModal",
            "editContactMethodModal",
        ),
    }
