"""Verified email-change lifecycle. Raw verification secrets are never stored."""

import hashlib
import logging
import secrets
from datetime import timedelta
from smtplib import SMTPException

from django.conf import settings
from django.core.mail import send_mail
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import PendingEmailChange, PendingRegistration, User

logger = logging.getLogger(__name__)


class InvalidEmailChange(Exception):
    pass


class EmailAlreadyTaken(Exception):
    pass


def token_digest(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def request_email_change(*, user, new_email, confirmation_url_for_token):
    token = secrets.token_urlsafe(32)
    with transaction.atomic():
        PendingEmailChange.objects.update_or_create(
            user=user,
            defaults={
                "old_email": user.email,
                "new_email": new_email,
                "token_hash": token_digest(token),
                "expires_at": timezone.now() + timedelta(hours=24),
            },
        )
        delivered = send_mail(
            subject="Verify your new email address",
            message=(
                "Confirm your new My Property Desk email address by opening this link:\n\n"
                f"{confirmation_url_for_token(token)}\n\n"
                "This link expires in 24 hours. Your existing sign-in email remains active until you confirm."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[new_email],
        )
        if delivered != 1:
            raise RuntimeError("Verification email was not sent.")


def pending_change_for_token(token):
    pending = (
        PendingEmailChange.objects.select_related("user")
        .filter(token_hash=token_digest(token))
        .first()
    )
    if pending is None or pending.is_expired or pending.user.email != pending.old_email:
        return None
    return pending


def confirm_email_change(token):
    try:
        with transaction.atomic():
            pending = (
                PendingEmailChange.objects.select_for_update()
                .select_related("user")
                .filter(token_hash=token_digest(token))
                .first()
            )
            if pending is None or pending.is_expired:
                raise InvalidEmailChange
            user = User.objects.select_for_update().get(pk=pending.user_id)
            if user.email != pending.old_email:
                raise InvalidEmailChange
            if (
                User.objects.filter(email__iexact=pending.new_email).exclude(pk=user.pk).exists()
                or PendingRegistration.objects.filter(
                    email__iexact=pending.new_email, expires_at__gt=timezone.now()
                ).exists()
            ):
                raise EmailAlreadyTaken
            old_email = user.email
            user.email = pending.new_email
            user.save(update_fields=["email"])
            pending.delete()

            def notify_previous_address():
                # The address change is already committed. A failed notification
                # must not make that successful change appear to have failed.
                try:
                    delivered = send_mail(
                        subject="Your sign-in email address changed",
                        message=(
                            "The sign-in email address for your My Property Desk account "
                            f"was changed to {user.email}. If you did not request this, contact support immediately."
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[old_email],
                    )
                except OSError, SMTPException:
                    logger.warning("Email change committed, but notification delivery failed.")
                else:
                    if delivered != 1:
                        logger.warning("Email change committed, but no notification was sent.")

            transaction.on_commit(notify_previous_address)
    except IntegrityError as error:
        raise EmailAlreadyTaken from error
