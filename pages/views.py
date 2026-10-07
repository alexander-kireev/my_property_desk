"""Public pages and thin authenticated Dashboard endpoints."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST

from event.forms import EventContactForm, EventForm

from .dashboard.actions import dashboard_action
from .dashboard.data import dashboard_data


def home_view(request):
    return render(request, "pages/home.html")


def about_us_view(request):
    return render(request, "pages/about_us.html")


def contact_us_view(request):
    return render(request, "pages/contact_us.html")


@login_required
@ensure_csrf_cookie
def dashboard_view(request):
    hour = timezone.localtime().hour
    greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
    return render(
        request,
        "pages/dashboard.html",
        {
            "add_event_form": EventForm(user=request.user),
            "initial_contacts_form": EventContactForm(user=request.user),
            "edit_contacts_form": EventContactForm(
                user=request.user, auto_id="dashboard_edit_contacts_%s"
            ),
            "dashboard_date": timezone.localdate(),
            "dashboard_greeting": greeting,
        },
    )


@login_required
@require_GET
def dashboard_data_view(request):
    return dashboard_data(request)


@login_required
@require_POST
def dashboard_action_view(request):
    return dashboard_action(request)
