from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from .managers import UserManager


# Keep these expiry helpers at this import path: historical migrations reference them.
def pending_registration_expiry():
    return timezone.now() + timedelta(hours=72)


def pending_email_change_expiry():
    return timezone.now() + timedelta(hours=24)


class User(AbstractUser):
    username = None
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(max_length=254, unique=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    def __str__(self):
        return self.email

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="accounts_user_email_ci_unique",
            ),
        ]


class PasswordResetRequestBucket(models.Model):
    """Keep short-lived request counts without storing email addresses or client IPs."""

    key_hash = models.CharField(max_length=64, unique=True)
    window_started_at = models.DateTimeField(db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)


class PendingRegistration(models.Model):
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    email = models.EmailField(max_length=254, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    password_hash = models.CharField(max_length=128, editable=False)
    expires_at = models.DateTimeField(default=pending_registration_expiry)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="accounts_pending_registration_email_ci_unique",
            ),
        ]

    def __str__(self):
        return self.email

    @property
    def is_expired(self):
        return self.expires_at <= timezone.now()

    def set_password(self, raw_password):
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password):
        return check_password(raw_password, self.password_hash)


class PendingEmailChange(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="pending_email_change")
    old_email = models.EmailField(max_length=254)
    new_email = models.EmailField(max_length=254)
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=pending_email_change_expiry)

    @property
    def is_expired(self):
        return self.expires_at <= timezone.now()
