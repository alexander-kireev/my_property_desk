"""Limit public and signed-in reset emails using one database-backed policy."""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac

from .models import PasswordResetRequestBucket

WINDOW = timedelta(hours=1)
EMAIL_LIMIT = 3
SOURCE_LIMIT = 20


def _bucket_key(kind, value):
    # Only a keyed digest reaches the database; neither addresses nor IPs are stored.
    return salted_hmac(
        "accounts.password-reset-request", f"{kind}:{value}", algorithm="sha256"
    ).hexdigest()


def _reserve_bucket(key, limit, now):
    bucket, _ = PasswordResetRequestBucket.objects.select_for_update().get_or_create(
        key_hash=key,
        defaults={"window_started_at": now},
    )
    if bucket.window_started_at <= now - WINDOW:
        bucket.window_started_at = now
        bucket.attempts = 0

    allowed = bucket.attempts < limit
    if allowed:
        bucket.attempts += 1
    bucket.save(update_fields=("window_started_at", "attempts"))
    return allowed


def reserve_password_reset_request(email, source):
    """Count every valid request and allow an email only within both hourly limits."""
    now = timezone.now()
    email_key = _bucket_key("email", email.strip().casefold())
    source_key = _bucket_key("source", source or "unknown")

    # Old windows carry no security value and can be removed without a scheduler.
    PasswordResetRequestBucket.objects.filter(window_started_at__lt=now - 2 * WINDOW).delete()
    with transaction.atomic():
        source_allowed = _reserve_bucket(source_key, SOURCE_LIMIT, now)
        if not source_allowed:
            return False
        email_allowed = _reserve_bucket(email_key, EMAIL_LIMIT, now)
    return email_allowed and source_allowed
