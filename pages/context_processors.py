"""Analytics beacon eligibility for public marketing pages."""

from django.conf import settings

ANALYTICS_OPT_OUT_COOKIE = "mpd_analytics_off"
ANALYTICS_PAGE_NAMES = frozenset(
    {
        "pages:home",
        "pages:features",
        "pages:faq",
        "pages:coming_soon",
        "pages:privacy_policy",
    }
)


def public_analytics(request):
    opted_out = request.COOKIES.get(ANALYTICS_OPT_OUT_COOKIE) == "1"
    page_name = request.resolver_match.view_name if request.resolver_match else None
    token = getattr(settings, "PMS_CLOUDFLARE_WEB_ANALYTICS_TOKEN", "")
    return {
        "analytics_opted_out": opted_out,
        "cloudflare_analytics_token": (
            token if token and page_name in ANALYTICS_PAGE_NAMES and not opted_out else ""
        ),
    }
