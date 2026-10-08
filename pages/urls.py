from django.urls import path
from django.views.generic.base import RedirectView

from . import views

app_name = "pages"

urlpatterns = [
    path("", views.home_view, name="home"),
    path("about/", views.about_us_view, name="about_us"),
    path("contact/", views.contact_us_view, name="contact_us"),
    path("features/", views.features_view, name="features"),
    path("faq/", views.faq_view, name="faq"),
    path("coming-soon/", views.coming_soon_view, name="coming_soon"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path(
        "dashboard/layout-preview/",
        RedirectView.as_view(pattern_name="pages:dashboard", permanent=False),
    ),
    path("dashboard/data/", views.dashboard_data_view, name="dashboard_data"),
    path("dashboard/action/", views.dashboard_action_view, name="dashboard_action"),
]
