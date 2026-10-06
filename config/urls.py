"""Root URL routes; each app owns its named endpoints."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("pages.urls")),
    path("accounts/", include("accounts.urls")),
    path("properties/", include("property.urls")),
    path("issues/", include("issue.urls")),
    path("tasks/", include("task.urls")),
    path("contacts/", include("contact.urls")),
    path("events/", include("event.urls")),
]
