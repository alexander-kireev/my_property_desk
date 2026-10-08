"""Root URL routes; each app owns its named endpoints."""

from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
from django.views.decorators.http import require_GET


@require_GET
def health_view(request):
    return HttpResponse("ok", content_type="text/plain")


urlpatterns = [
    path("health/", health_view, name="health"),
    path("admin/", admin.site.urls),
    path("", include("pages.urls")),
    path("accounts/", include("accounts.urls")),
    path("properties/", include("property.urls")),
    path("issues/", include("issue.urls")),
    path("tasks/", include("task.urls")),
    path("contacts/", include("contact.urls")),
    path("events/", include("event.urls")),
]
