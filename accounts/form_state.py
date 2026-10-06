"""Account PRG state stores validation feedback, never submitted passwords."""

from urllib.parse import urlencode

from django.shortcuts import redirect

from config.form_state import (
    pop_form_state,
    restore_form_errors,
    serialise_form_data,
    serialise_form_errors,
    store_form_state,
)


def redirect_with_account_form_state(
    request,
    *,
    action,
    form,
    url,
    exclude=(),
):
    token = store_form_state(
        request,
        {
            "action": action,
            "data": serialise_form_data(request.POST, exclude=exclude),
            "errors": serialise_form_errors(form),
        },
    )
    return redirect(f"{url}?{urlencode({'form_state': token})}")


def account_form_state(request, action):
    state = pop_form_state(request)
    if not isinstance(state, dict) or state.get("action") != action:
        return None
    return state


def restore_account_form(state, form):
    return restore_form_errors(form, state.get("errors", {}))
