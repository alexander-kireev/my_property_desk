"""Public pages, contact submissions and thin authenticated Dashboard endpoints."""

import logging

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from event.forms import EventContactForm, EventForm

from .contact_mail import send_problem_report, send_public_message
from .dashboard.actions import dashboard_action
from .dashboard.data import dashboard_data
from .forms import MessageForm, ProblemReportForm

logger = logging.getLogger(__name__)


def home_view(request):
    if request.user.is_authenticated:
        return redirect("pages:dashboard")
    return render(request, "pages/home.html")


def about_us_view(request):
    return redirect("pages:home")


@require_GET
def features_view(request):
    return render(request, "pages/features.html")


@require_GET
def faq_view(request):
    return render(request, "pages/faq.html")


@require_GET
def coming_soon_view(request):
    return render(request, "pages/coming_soon.html")


@require_http_methods(["GET", "POST"])
def contact_us_view(request):
    active_tab = "report"
    report_form = ProblemReportForm(prefix="report")
    message_form = MessageForm(prefix="message")

    if request.method == "POST":
        active_tab = request.POST.get("form_type", "report")
        if active_tab == "report":
            report_form = ProblemReportForm(request.POST, request.FILES, prefix="report")
            form = report_form
            deliver = send_problem_report
        elif active_tab == "message":
            message_form = MessageForm(request.POST, prefix="message")
            form = message_form
            deliver = send_public_message
        else:
            active_tab = "report"
            report_form.add_error(None, "Choose a form before sending your message.")
            return render(
                request,
                "pages/contact_us.html",
                {
                    "report_form": report_form,
                    "message_form": message_form,
                    "active_tab": active_tab,
                },
                status=400,
            )

        if form.is_valid():
            try:
                sent = deliver(form.cleaned_data)
            except Exception:
                logger.exception("Public contact delivery failed.")
                sent = 0
            if sent:
                return redirect(f"{reverse('pages:contact_us')}?sent={active_tab}")
            form.add_error(None, "Your message could not be sent. Please try again later.")

    sent = request.GET.get("sent")
    if sent not in {"report", "message"}:
        sent = None
    return render(
        request,
        "pages/contact_us.html",
        {
            "report_form": report_form,
            "message_form": message_form,
            "active_tab": active_tab,
            "sent": sent,
        },
    )


@login_required
@ensure_csrf_cookie
def dashboard_view(request):
    hour = timezone.localtime().hour
    greeting = (
        "Hello"
        if hour < 5
        else "Good morning"
        if hour < 12
        else "Good afternoon"
        if hour < 18
        else "Good evening"
    )
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
