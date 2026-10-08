"""Account HTTP flows; registration and email transitions live in their service modules."""

import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordResetForm
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_POST

from config.feedback import form_values_changed, snapshot_form_values
from config.form_state import (
    deserialise_form_data,
)

from .email_change import (
    EmailAlreadyTaken,
    InvalidEmailChange,
    confirm_email_change,
    pending_change_for_token,
    request_email_change,
)
from .form_state import account_form_state, redirect_with_account_form_state, restore_account_form
from .forms import (
    AccountPasswordChangeForm,
    DeleteAccountForm,
    EmailAuthenticationForm,
    EmailChangeForm,
    PendingRegistrationForm,
    ProfileForm,
    PublicPasswordResetRequestForm,
)
from .password_reset_requests import reserve_password_reset_request
from .profile_context import profile_context
from .registration import (
    InvalidRegistrationLink,
    RegistrationDeliveryFailed,
    RegistrationUnavailable,
    confirm_registration,
    request_registration,
)

logger = logging.getLogger(__name__)


def login_view(request):

    if request.method == "POST":
        form = EmailAuthenticationForm(request, data=request.POST)

        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect("pages:dashboard")

        return redirect_with_account_form_state(
            request,
            action="login",
            form=form,
            url=reverse("accounts:login"),
            exclude=("username", "password"),
        )
    else:
        state = account_form_state(request, "login")
        form = EmailAuthenticationForm(
            request,
            data=deserialise_form_data(state["data"]) if state else None,
        )
        if state:
            form = restore_account_form(state, form)

    return render(request, "accounts/login.html", {"form": form})


def register_view(request):

    if request.method == "POST":
        form = PendingRegistrationForm(request.POST)

        if form.is_valid():

            def confirmation_url(token):
                path = reverse("accounts:confirm_registration", kwargs={"token": token})
                return request.build_absolute_uri(path)

            try:
                request_registration(
                    first_name=form.cleaned_data["first_name"],
                    last_name=form.cleaned_data["last_name"],
                    email=form.cleaned_data["email"],
                    password=form.cleaned_data["password_1"],
                    confirmation_url_for_token=confirmation_url,
                )
            except RegistrationUnavailable as error:
                form.add_error("email", str(error))
            except RegistrationDeliveryFailed:
                logger.warning("Registration confirmation delivery failed.")
                form.add_error(None, "We couldn’t send your confirmation email. Please try again.")
            else:
                return redirect("accounts:registration_pending")

        return redirect_with_account_form_state(
            request,
            action="register",
            form=form,
            url=reverse("accounts:register"),
            exclude=("email", "password_1", "password_2"),
        )

    else:
        state = account_form_state(request, "register")
        form = PendingRegistrationForm(
            data=deserialise_form_data(state["data"]) if state else None,
        )
        if state:
            form = restore_account_form(state, form)

    return render(request, "accounts/register.html", {"form": form})


def registration_pending_view(request):
    return render(request, "accounts/registration_pending.html")


@login_required
@require_POST
def logout_view(request):
    logout(request)
    return redirect("accounts:login")


def confirm_registration_view(request, token):
    try:
        user = confirm_registration(token)
    except InvalidRegistrationLink:
        return render(
            request,
            "accounts/confirm_registration.html",
            {"error": "This confirmation link is invalid or has expired."},
            status=400,
        )

    login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    messages.success(request, "Account confirmed.")

    return redirect("pages:dashboard")


@login_required
def profile_page_view(request):

    if request.method == "POST":
        profile_form = ProfileForm(data=request.POST, instance=request.user)
        before_profile = snapshot_form_values(profile_form)

        if profile_form.is_valid():
            if form_values_changed(before_profile, profile_form):
                profile_form.save()
                messages.success(request, "Profile updated.")
            return redirect("accounts:profile_page")

        return redirect_with_account_form_state(
            request,
            action="profile",
            form=profile_form,
            url=reverse("accounts:profile_page"),
        )

    else:
        return render(request, "accounts/profile_page.html", profile_context(request))


@login_required
@require_POST
def change_password_view(request):

    if request.method == "POST":
        form = AccountPasswordChangeForm(user=request.user, data=request.POST)

        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            messages.success(request, "Password changed.")
            return redirect("accounts:profile_page")

        return redirect_with_account_form_state(
            request,
            action="change_password",
            form=form,
            url=reverse("accounts:profile_page"),
            exclude=("old_password", "new_password1", "new_password2"),
        )


@login_required
@require_POST
def change_email_view(request):

    if request.method == "POST":
        form = EmailChangeForm(request.POST, user=request.user)

        if form.is_valid():
            current_password = form.cleaned_data["current_password"]

            if not request.user.check_password(current_password):
                form.add_error("current_password", "Your current password is incorrect.")
            else:

                def confirmation_url(token):
                    path = reverse("accounts:confirm_email_change", kwargs={"token": token})
                    return request.build_absolute_uri(path)

                request_email_change(
                    user=request.user,
                    new_email=form.cleaned_data["new_email"],
                    confirmation_url_for_token=confirmation_url,
                )

                messages.success(
                    request,
                    "Verification email sent. Your current sign-in email remains active until you confirm the new address.",
                )
                return redirect("accounts:profile_page")

        return redirect_with_account_form_state(
            request,
            action="change_email",
            form=form,
            url=reverse("accounts:profile_page"),
            exclude=("current_password",),
        )


def confirm_email_change_view(request, token):
    pending = pending_change_for_token(token)
    if pending is None:
        return render(
            request,
            "accounts/confirm_email_change.html",
            {"error": "This verification link is invalid or has expired."},
            status=400,
        )
    if request.method == "POST":
        try:
            confirm_email_change(token)
        except InvalidEmailChange:
            return render(
                request,
                "accounts/confirm_email_change.html",
                {"error": "This verification link is invalid or has expired."},
                status=400,
            )
        except EmailAlreadyTaken:
            return render(
                request,
                "accounts/confirm_email_change.html",
                {
                    "error": "This email address is already in use. Request a different address from your profile."
                },
                status=409,
            )
        return redirect("accounts:email_change_complete")
    return render(request, "accounts/confirm_email_change.html", {"pending": pending})


def email_change_complete_view(request):
    return render(request, "accounts/email_change_complete.html")


@login_required
@require_POST
def delete_account_view(request):
    form = DeleteAccountForm(request.POST, user=request.user)
    if form.is_valid():
        try:
            with transaction.atomic():
                request.user.delete()
        except Exception:
            logger.exception("Account deletion failed for user %s", request.user.pk)
            form.add_error(None, "We couldn't delete your account. Please try again later.")
        else:
            logout(request)
            request.session["account_deleted"] = True
            return redirect("accounts:delete_account_complete")

    return redirect_with_account_form_state(
        request,
        action="delete_account",
        form=form,
        url=reverse("accounts:profile_page"),
        exclude=("current_password", "confirmation"),
    )


def delete_account_complete_view(request):
    if not request.session.pop("account_deleted", False):
        return redirect("accounts:login")
    return render(request, "accounts/delete_account_complete.html")


def _send_reset_email(request, form):
    # A production link must use HTTPS even when TLS terminates before Django.
    form.save(
        request=request,
        use_https=request.is_secure() or not settings.DEBUG,
        from_email=settings.DEFAULT_FROM_EMAIL,
        email_template_name="accounts/password_reset_email.txt",
        subject_template_name="accounts/password_reset_subject.txt",
    )


@require_http_methods(["GET", "POST"])
def password_reset_request_view(request):
    form = PublicPasswordResetRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if reserve_password_reset_request(
            form.cleaned_data["email"], request.META.get("REMOTE_ADDR")
        ):
            try:
                _send_reset_email(request, form)
            except Exception:
                # Account existence and mail delivery stay private in the public response.
                logger.exception("Public password reset delivery failed.")
        return redirect("accounts:password_reset_sent")
    return render(request, "accounts/password_reset_request.html", {"form": form})


@login_required
@require_POST
def reset_password_protected_view(request):
    form = PasswordResetForm({"email": request.user.email})
    if form.is_valid() and reserve_password_reset_request(
        request.user.email, request.META.get("REMOTE_ADDR")
    ):
        try:
            _send_reset_email(request, form)
        except Exception:
            logger.exception("Signed-in password reset delivery failed.")
    messages.success(request, "If available, a password reset link has been sent.")
    return redirect("accounts:profile_page")


class PasswordResetConfirmPRGView(auth_views.PasswordResetConfirmView):
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        if self.request.method == "GET":
            state = account_form_state(self.request, "password_reset_confirm")
            if state:
                form = self.get_form_class()(
                    user=self.user,
                    data=deserialise_form_data(state["data"]),
                )
                form = restore_account_form(state, form)
        return form

    def form_invalid(self, form):
        return redirect_with_account_form_state(
            self.request,
            action="password_reset_confirm",
            form=form,
            url=self.request.path,
            exclude=("new_password1", "new_password2"),
        )
