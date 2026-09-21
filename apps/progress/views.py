from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count
from django.shortcuts import render
from django.utils import timezone

from apps.billing.services.entitlements import get_entitlements
from apps.practice.models import AttemptMistake

from .models import PatternMastery
from .services.mastery import group_progress
from .services.stats import user_progress

FREE_HISTORY_DAYS = 7


@login_required
def progress(request):
    stats = user_progress(request.user)
    context = {
        "stats": stats,
        "groups": group_progress(request.user),
        "entitlements": get_entitlements(request.user),
        "max_day": max((d.count for d in stats.days), default=0) or 1,
    }
    template = "pages/progress/progress.html"
    if request.htmx and not request.htmx.history_restore_request:
        template = "partials/progress/dashboard.html"
    return render(request, template, context)


@login_required
def mistakes(request):
    ent = get_entitlements(request.user)
    problem_patterns = PatternMastery.objects.filter(
        user=request.user, exposures__gt=0
    ).select_related("pattern")
    problem_patterns = sorted(problem_patterns, key=lambda m: (-m.miss_rate, m.mastery))

    history = (
        AttemptMistake.objects.filter(attempt__user=request.user)
        .exclude(mistake_type__in=["spelling"])
        .select_related("attempt__phrase", "speech_pattern")
        .order_by("-attempt__completed_at", "position")
    )
    history_limited = not ent.full_mistake_history
    if history_limited:
        since = timezone.now() - timedelta(days=FREE_HISTORY_DAYS)
        history = history.filter(attempt__completed_at__gte=since)
    page = Paginator(history, 20).get_page(request.GET.get("pagina"))

    frequent_words = (
        AttemptMistake.objects.filter(attempt__user=request.user)
        .exclude(expected_word="")
        .exclude(mistake_type__in=["spelling", "contraction"])
        .values("expected_word")
        .annotate(n=Count("id"))
        .order_by("-n")[:8]
    )
    return render(
        request,
        "pages/progress/mistakes.html",
        {
            "problem_patterns": problem_patterns,
            "page": page,
            "history_limited": history_limited,
            "history_days": FREE_HISTORY_DAYS,
            "frequent_words": frequent_words,
            "entitlements": ent,
        },
    )


@login_required
def streak_badge(request):
    """Small fragment refreshed by htmx after each completed exercise."""
    return render(request, "components/streak_badge.html", {"pill": request.GET.get("pill") == "1"})
