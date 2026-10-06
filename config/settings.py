"""Application settings loaded from PMS environment variables and the local .env file."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Paths and environment
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

# Deployment identity and allowed hosts
SECRET_KEY = os.environ["PMS_SECRET_KEY"]

DEBUG = os.environ.get("PMS_DEBUG", "False").lower() == "true"

ALLOWED_HOSTS = [
    host.strip() for host in os.environ.get("PMS_ALLOWED_HOSTS", "").split(",") if host.strip()
]


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
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# PostgreSQL connection
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ["PMS_DB_NAME"],
        "USER": os.environ["PMS_DB_USER"],
        "PASSWORD": os.environ["PMS_DB_PASSWORD"],
        "HOST": os.environ.get("PMS_DB_HOST", "127.0.0.1"),
        "PORT": os.environ.get("PMS_DB_PORT", "5433"),
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


# Language and time handling
LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# Static assets and default model keys
STATIC_URL = "static/"

STATICFILES_DIRS = [
    BASE_DIR / "static",
]


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# Console delivery is useful locally; set the SMTP values below for real delivery.
EMAIL_BACKEND = os.environ.get(
    "PMS_EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)
EMAIL_HOST = os.environ.get("PMS_EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("PMS_EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("PMS_EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("PMS_EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("PMS_EMAIL_USE_TLS", "False").lower() == "true"
EMAIL_USE_SSL = os.environ.get("PMS_EMAIL_USE_SSL", "False").lower() == "true"
DEFAULT_FROM_EMAIL = os.environ.get(
    "PMS_DEFAULT_FROM_EMAIL", "noreply@property-operations-manager.local"
)
