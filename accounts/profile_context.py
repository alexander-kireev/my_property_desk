"""Build the four Profile forms from one-use, password-free saved state."""

from django.utils import timezone

from config.form_state import deserialise_form_data, pop_form_state

from .form_state import restore_account_form
from .forms import AccountPasswordChangeForm, DeleteAccountForm, EmailChangeForm, ProfileForm
from .models import PendingEmailChange


def profile_context(request):
    state = pop_form_state(request)
    action = state.get("action") if isinstance(state, dict) else None
    profile_state = state if action == "profile" else None
    profile_form = ProfileForm(
        data=deserialise_form_data(profile_state["data"]) if profile_state else None,
        instance=request.user,
    )
    if profile_state:
        profile_form = restore_account_form(profile_state, profile_form)

    email_state = state if action == "change_email" else None
    email_form = EmailChangeForm(
        data=deserialise_form_data(email_state["data"]) if email_state else None,
        user=request.user,
    )
    if email_state:
        email_form = restore_account_form(email_state, email_form)

    password_state = state if action == "change_password" else None
    password_form = AccountPasswordChangeForm(
        user=request.user,
        data=deserialise_form_data(password_state["data"]) if password_state else None,
    )
    if password_state:
        password_form = restore_account_form(password_state, password_form)

    delete_state = state if action == "delete_account" else None
    delete_form = DeleteAccountForm(
        user=request.user,
        data=deserialise_form_data(delete_state["data"]) if delete_state else None,
    )
    if delete_state:
        delete_form = restore_account_form(delete_state, delete_form)

    pending = PendingEmailChange.objects.filter(
        user=request.user, expires_at__gt=timezone.now()
    ).first()
    return {
        "profile_form": profile_form,
        "email_form": email_form,
        "password_form": password_form,
        "delete_form": delete_form,
        "pending_email_change": pending,
        "open_modal": {
            "change_email": "changeEmailModal",
            "change_password": "changePasswordModal",
            "delete_account": "deleteAccountConfirmModal",
        }.get(action),
    }
