"""Create pending registrations and turn a valid confirmation into an account."""

from smtplib import SMTPException

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.db import IntegrityError, transaction

from .models import PendingRegistration, User
from .tokens import create_confirmation_token, decode_confirmation_token


class RegistrationUnavailable(Exception):
    """An account or an unexpired registration already owns this address."""


class RegistrationDeliveryFailed(Exception):
    """The send attempt failed; the pending change has been rolled back."""


class InvalidRegistrationLink(Exception):
    """The link is expired, consumed or no longer names a pending registration."""


def request_registration(*, first_name, last_name, email, password, confirmation_url_for_token):
    """Replace expired requests atomically; retain nothing new when delivery fails."""
    email = email.strip().lower()
    try:
        with transaction.atomic():
            pending = (
                PendingRegistration.objects.select_for_update().filter(email__iexact=email).first()
            )
            # Check again after locking: another confirmation may have just created the user.
            if User.objects.filter(email__iexact=email).exists():
                raise RegistrationUnavailable("An account already exists with this email address.")
            if pending is not None:
                if not pending.is_expired:
                    raise RegistrationUnavailable(
                        "A registration is already pending for this email address."
                    )
                # A new primary key invalidates every old confirmation token.
                pending.delete()
            pending = PendingRegistration(first_name=first_name, last_name=last_name, email=email)
            pending.set_password(password)
            pending.save()
            token = create_confirmation_token(pending)
            try:
                delivered = send_mail(
                    subject="Confirm your registration",
                    message="Confirm your My Property Desk account:\n\n"
                    + confirmation_url_for_token(token),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                )
            except (OSError, SMTPException) as error:
                raise RegistrationDeliveryFailed from error
            if delivered != 1:
                raise RegistrationDeliveryFailed
    except IntegrityError as error:
        # Concurrent first requests have no row to lock; the unique constraint decides.
        raise RegistrationUnavailable(
            "An account or registration already exists with this email address."
        ) from error


def confirm_registration(token):
    """Consume a valid pending registration once and return its newly created user."""
    try:
        data = decode_confirmation_token(token)
        pending_id = data["pending_registration_id"]
    except (signing.BadSignature, KeyError, TypeError) as error:
        raise InvalidRegistrationLink from error
    try:
        with transaction.atomic():
            pending = PendingRegistration.objects.select_for_update().filter(pk=pending_id).first()
            if pending is None or pending.is_expired:
                raise InvalidRegistrationLink
            user = User(
                first_name=pending.first_name, last_name=pending.last_name, email=pending.email
            )
            user.password = pending.password_hash
            user.save()
            pending.delete()
    except IntegrityError as error:
        raise InvalidRegistrationLink from error
    return user
