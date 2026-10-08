"""Application settings loaded from MPD/PMS environment variables and .env."""

import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# Paths and environment
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def app_env(name, default=None):
    """Prefer the public MPD name while accepting existing PMS deployment keys."""
    return os.environ.get(f"MPD_{name}", os.environ.get(f"PMS_{name}", default))


def required_app_env(name):
    value = app_env(name)
    if value is None:
        raise ImproperlyConfigured(f"MPD_{name} or PMS_{name} is required")
    return value


# Deployment identity and allowed hosts
SECRET_KEY = required_app_env("SECRET_KEY")

DEBUG = app_env("DEBUG", "False").lower() == "true"
PMS_PRODUCTION = app_env("PRODUCTION", "False").lower() == "true"

if PMS_PRODUCTION and DEBUG:
    raise ImproperlyConfigured("PMS_DEBUG must be False in production")

ALLOWED_HOSTS = [
    host.strip() for host in app_env("ALLOWED_HOSTS", "").split(",") if host.strip()
]
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in app_env("CSRF_TRUSTED_ORIGINS", "").split(",")
    if origin.strip()
]

if PMS_PRODUCTION and (not ALLOWED_HOSTS or not CSRF_TRUSTED_ORIGINS):
    raise ImproperlyConfigured(
        "PMS_ALLOWED_HOSTS and PMS_CSRF_TRUSTED_ORIGINS are required in production"
    )

if PMS_PRODUCTION:
    # Render terminates TLS and forwards the original scheme in this header.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    SECURE_REDIRECT_EXEMPT = [r"^health/$"]
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(app_env("HSTS_SECONDS", "3600"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False


# Installed apps, middleware and template discovery
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts.apps.AccountsConfig",
    "pages.apps.PagesConfig",
    "property.apps.PropertyConfig",
    "issue.apps.IssueConfig",
    "task.apps.TaskConfig",
    "contact.apps.ContactConfig",
    "event.apps.EventConfig",
    "note.apps.NoteConfig",
]

AUTH_USER_MODEL = "accounts.User"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "pages.context_processors.public_analytics",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Cloudflare Web Analytics is manually embedded on selected public pages only.
# Set this to the site token from Cloudflare's Web Analytics dashboard at deploy time.
PMS_CLOUDFLARE_WEB_ANALYTICS_TOKEN = app_env("CLOUDFLARE_WEB_ANALYTICS_TOKEN", "")
PMS_REGISTRATION_MODE = app_env("REGISTRATION_MODE", "pending").lower()
if PMS_REGISTRATION_MODE not in {"instant", "pending"}:
    raise ImproperlyConfigured("PMS_REGISTRATION_MODE must be instant or pending")


# PostgreSQL connection
PMS_DB_SSLMODE = app_env("DB_SSLMODE", "require" if PMS_PRODUCTION else "prefer")
if PMS_PRODUCTION and PMS_DB_SSLMODE not in {"require", "verify-ca", "verify-full"}:
    raise ImproperlyConfigured("Production PostgreSQL connections must use TLS")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": required_app_env("DB_NAME"),
        "USER": required_app_env("DB_USER"),
        "PASSWORD": required_app_env("DB_PASSWORD"),
        "HOST": app_env("DB_HOST", "127.0.0.1"),
        "PORT": app_env("DB_PORT", "5433"),
        "OPTIONS": {"sslmode": PMS_DB_SSLMODE},
    }
}


# Account password rules
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Public reset links expire after one hour, as stated in the reset email.
PASSWORD_RESET_TIMEOUT = 3600


# Language and time handling
LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static assets and default model keys
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]
if PMS_PRODUCTION:
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Console delivery is useful locally; set the SMTP values below for real delivery.
EMAIL_BACKEND = app_env("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = app_env("EMAIL_HOST", "localhost")
EMAIL_PORT = int(app_env("EMAIL_PORT", "587"))
EMAIL_HOST_USER = app_env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = app_env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = app_env("EMAIL_USE_TLS", "False").lower() == "true"
EMAIL_USE_SSL = app_env("EMAIL_USE_SSL", "False").lower() == "true"
DEFAULT_FROM_EMAIL = app_env("DEFAULT_FROM_EMAIL", "noreply@property-operations-manager.local")
# Public contact messages use the same delivery backend as account email.
PMS_CONTACT_EMAIL = app_env("CONTACT_EMAIL", DEFAULT_FROM_EMAIL)

if PMS_PRODUCTION:
    if EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
        raise ImproperlyConfigured("A real email backend is required in production")
    if EMAIL_BACKEND == "django.core.mail.backends.smtp.EmailBackend" and (
        not EMAIL_HOST
        or EMAIL_HOST == "localhost"
        or not EMAIL_HOST_USER
        or not EMAIL_HOST_PASSWORD
    ):
        raise ImproperlyConfigured("SMTP host and credentials are required in production")
    if DEFAULT_FROM_EMAIL.endswith(".local") or PMS_CONTACT_EMAIL.endswith(".local"):
        raise ImproperlyConfigured("Public sender and contact email addresses are required")

    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {"console": {"class": "logging.StreamHandler"}},
        "loggers": {
            "django.request": {
                "handlers": ["console"],
                "level": "ERROR",
                "propagate": False,
            },
            "accounts": {"handlers": ["console"], "level": "WARNING"},
            "pages": {"handlers": ["console"], "level": "WARNING"},
        },
    }
