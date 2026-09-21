from django.db import connection
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.cache import cache_control
from django.views.decorators.http import require_GET

from apps.billing.models import Plan
from apps.billing.providers import get_payment_provider
from apps.billing.services.entitlements import get_entitlements
from apps.progress.services.mastery import group_progress
from apps.progress.services.stats import overview

from .models import Testimonial

HERO_DEMO = {
    "streak": 12,
    "position": 1,
    "total": 10,
    "duration": "0:04",
    "explanation_title": "O expresie frecventă în vorbirea de zi cu zi",
    "rows": [("Ai vrea", "ai vrea"), ("să mergi", "să mergi"), ("la", "la")],
}


def home(request):
    context = {
        "testimonials": list(Testimonial.objects.filter(active=True)[:6]),
        "plans": list(Plan.objects.all()),
        "groups": group_progress(request.user),
        "overview": overview(request.user),
        "demo": HERO_DEMO,
        "entitlements": get_entitlements(request.user),
        "checkout_available": get_payment_provider().is_configured(),
        "header_overlay": True,
    }
    return render(request, "pages/home.html", context)


STATIC_PAGES = {
    "about": ("pages/static/about.html", "Despre noi"),
    "contact": ("pages/static/contact.html", "Contact"),
    "privacy": ("pages/static/privacy.html", "Confidențialitate"),
    "terms": ("pages/static/terms.html", "Termeni și condiții"),
}


def static_page(request, page: str):
    template, title = STATIC_PAGES[page]
    return render(request, template, {"page_title": title})


@require_GET
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        db_ok = True
    except Exception:  # pragma: no cover - reported, not raised
        db_ok = False
    status = 200 if db_ok else 503
    return JsonResponse({"status": "ok" if db_ok else "degraded", "database": db_ok}, status=status)


@require_GET
@cache_control(max_age=86400, public=True)
def robots_txt(request):
    base = request.build_absolute_uri("/").rstrip("/")
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        "Disallow: /account/",
        "Disallow: /practice/session/",
        "Disallow: /practice/attempt/",
        "Disallow: /progress/",
        "Disallow: /mistakes/",
        "",
        f"Sitemap: {base}/sitemap.xml",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")


def error_404(request, exception=None):
    return render(request, "pages/errors/404.html", status=404)


def error_500(request):
    return render(request, "pages/errors/500.html", status=500)


def error_403_csrf(request, reason=""):
    return render(request, "pages/errors/403_csrf.html", status=403)


@require_GET
def serve_media(request, path: str):
    """Media (generated audio) with long cache headers: file names are content hashes."""
    from django.conf import settings
    from django.views.static import serve

    response = serve(request, path, document_root=settings.MEDIA_ROOT)
    if path.startswith("audio/"):
        response["Cache-Control"] = "public, max-age=31536000, immutable"
    return response
