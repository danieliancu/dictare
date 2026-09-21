from collections import Counter

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import prefetch_related_objects
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.ai.services.tts import LEVEL_STYLES
from apps.billing.services.entitlements import get_entitlements
from apps.core.ratelimit import rate_limit
from apps.listening.models import LEVEL_DESCRIPTIONS, Level, SpeechPattern, Topic
from apps.listening.services.patterns import patterns_for_variant
from apps.progress.services.mastery import group_progress
from apps.scoring.normalize import surface_tokens
from apps.scoring.services import Status, score_answer

from .models import ListeningAttempt, PracticeSession, SessionKind
from .services import sessions as svc
from .services.topics import topic_sections

STATUS_LABELS = {
    Status.CORRECT: "corect",
    Status.MISSING: "lipsă",
    Status.INCORRECT: "greșit",
    Status.EXTRA: "în plus",
    Status.ORDER: "altă ordine",
    Status.CONTRACTION: "formă contrasă",
    Status.SPELLING: "ortografie UK/US",
}


def verdict_for(score: int) -> str:
    if score >= 95:
        return "Excelent! Ai prins tot."
    if score >= 80:
        return "Foarte bine!"
    if score >= 60:
        return "Aproape! Mai ascultă o dată."
    if score >= 30:
        return "Bun început. Uită-te la tiparele de mai jos."
    return "Fraza asta a fost grea. Ascult-o din nou cu transcrierea."


def tier_for(score: int) -> str:
    """Visual tier of the result card (colour, icon, celebration)."""
    if score >= 95:
        return "top"
    if score >= 80:
        return "great"
    if score >= 60:
        return "close"
    if score >= 30:
        return "start"
    return "hard"


RESULT_ICONS = {"top": "trophy", "great": "star", "close": "target", "start": "zap", "hard": "ear"}


# --- helpers ------------------------------------------------------------------------------


def _owned_session(request, session_id) -> PracticeSession:
    owner = svc.owner_from_request(request, create=False)
    qs = PracticeSession.objects.owned_by(owner.user, owner.anon_key).select_related(
        "accent", "topic", "pattern"
    )
    return get_object_or_404(qs, pk=session_id)


def _owned_attempt(request, attempt_id) -> ListeningAttempt:
    owner = svc.owner_from_request(request, create=False)
    qs = ListeningAttempt.objects.owned_by(owner.user, owner.anon_key).select_related(
        "phrase", "audio_variant", "session_item__session__accent"
    )
    attempt = get_object_or_404(qs, pk=attempt_id)
    if attempt.session_item is None:
        raise Http404
    return attempt


def _levels(ent, current: str) -> list[dict]:
    return [
        {
            "value": value,
            "label": label,
            "description": LEVEL_DESCRIPTIONS[value],
            "locked": not ent.can_use_level(value),
            "active": value == current,
        }
        for value, label in Level.choices
    ]


def _result_words(result) -> list[dict]:
    return [
        {"text": w.text, "status": w.status, "typed": w.typed, "label": STATUS_LABELS[w.status]}
        for w in result.words
    ]


def _typed_line(typed_answer: str, words: list[dict]) -> list[dict]:
    """The learner's own sentence, with the tokens the scorer rejected flagged as wrong."""
    wrong = Counter()
    for w in words:
        if w["status"] == Status.EXTRA:
            wrong[w["text"]] += 1
        elif w["status"] in (Status.INCORRECT, Status.ORDER) and w["typed"]:
            wrong[w["typed"]] += 1
    line = []
    for display, norm in surface_tokens(typed_answer or ""):
        bad = wrong[norm] > 0
        if bad:
            wrong[norm] -= 1
        line.append({"text": display, "wrong": bad})
    return line


def _glance(request, owner, items, scored, position, remaining) -> dict:
    """At-a-glance state for the practice aside: session dots, average, today's goal."""
    scores = [s for s in scored.values() if s is not None]
    glance = {
        "dots": [
            {
                "n": i + 1,
                "score": scored.get(i),
                "tier": tier_for(scored[i]) if scored.get(i) is not None else "",
                "current": i == position,
            }
            for i in range(len(items))
        ],
        "done": len(scored),
        "average": round(sum(scores) / len(scores)) if scores else None,
        "average_tier": tier_for(round(sum(scores) / len(scores))) if scores else "",
        "remaining": remaining,
    }
    if owner.user is not None:
        from apps.progress.services.stats import completed_today

        today, goal = completed_today(owner.user), request.user.profile.daily_goal
        goal_pct = min(100, round(100 * today / goal)) if goal else 0
        glance.update(today=today, goal=goal, goal_pct=goal_pct)
    return glance


def _exercise_context(request, session: PracticeSession, position: int | None) -> dict:
    owner = svc.owner_from_request(request)
    ent = get_entitlements(owner.user)
    items = svc.session_items(session)
    scored = dict(
        ListeningAttempt.objects.filter(session_item__session=session, completed=True).values_list(
            "session_item__position", "score"
        )
    )
    done = set(scored)
    completed_count = len(done)
    context = {
        "session": session,
        "total": len(items),
        "completed_count": completed_count,
        "progress_pct": round(100 * completed_count / len(items)) if items else 0,
        "entitlements": ent,
        "is_anonymous": owner.user is None,
        "browser_fallback": settings.TTS_BROWSER_FALLBACK and settings.DEBUG,
        "session_url": reverse("practice:session", args=[session.pk]),
    }
    remaining = svc.remaining_exercises(owner, ent)
    context["glance"] = _glance(request, owner, items, scored, position, remaining)

    if position is None:  # every item done → summary
        attempts = list(
            ListeningAttempt.objects.filter(session_item__session=session, completed=True)
            .select_related("phrase")
            .order_by("session_item__position")
        )
        scores = [a.score for a in attempts if a.score is not None]
        context.update(
            state="summary",
            attempts=attempts,
            average=round(sum(scores) / len(scores)) if scores else 0,
            levels=_levels(ent, session.level),
        )
        return context

    item = items[position]
    level = svc.allowed_level(session.level, ent)
    is_done = position in done
    if not is_done and remaining == 0:
        context.update(state="limit", position=position, levels=_levels(ent, level))
        return context

    attempt = svc.get_or_start_attempt(owner, item, level)
    context.update(
        state="result" if attempt.completed else "listen",
        item=item,
        attempt=attempt,
        position=position,
        human_position=position + 1,
        variant=attempt.audio_variant,
        levels=_levels(ent, attempt.level),
        playback_rate=LEVEL_STYLES[attempt.level].speed,
        next_position=position + 2 if position + 1 < len(items) else None,
        remaining=remaining,
    )
    if attempt.completed:
        result = score_answer(attempt.phrase.text, attempt.typed_answer)
        missed_positions = {w.position for w in result.mistakes if w.position is not None}
        # Only patterns that apply to *this* recording: verified ones are described as heard,
        # unverified ones only as a general tendency; verified-absent ones are not shown.
        prefetch_related_objects([attempt.phrase], "phrase_patterns__pattern")
        if attempt.audio_variant:
            prefetch_related_objects([attempt.audio_variant], "pattern_checks")
        explanations = [
            {
                "pp": applied.phrase_pattern,
                "heard": applied.heard,
                "realisation": applied.realisation,
                "text": applied.text,
                "missed": any(applied.covers(p) for p in missed_positions),
            }
            for applied in patterns_for_variant(
                attempt.audio_variant, attempt.phrase, attempt.level
            )
        ]
        anon_done = svc.completed_today(owner) if owner.user is None else 0
        words = _result_words(result)
        tier = tier_for(attempt.score or 0)
        context.update(
            result=result,
            verdict=verdict_for(attempt.score or 0),
            tier=tier,
            tier_icon=RESULT_ICONS[tier],
            words=words,
            typed_line=_typed_line(attempt.typed_answer, words),
            words_got=sum(
                w["status"] in (Status.CORRECT, Status.CONTRACTION, Status.SPELLING) for w in words
            ),
            words_missed=sum(w["status"] in (Status.MISSING, Status.INCORRECT) for w in words),
            words_total=sum(w["status"] != Status.EXTRA for w in words),
            heard_explanations=[e for e in explanations if e["heard"]],
            tendency_explanations=[e for e in explanations if not e["heard"]],
            show_signup_nudge=owner.user is None
            and anon_done >= settings.ANONYMOUS_SIGNUP_NUDGE_AFTER,
        )
    return context


def _render_exercise(request, session, position, status=200, extra=None):
    if not request.htmx:  # no-JS fallback: post/redirect/get back to the exercise
        return redirect(session_url(session, position))
    context = _exercise_context(request, session, position)
    if extra:
        context.update(extra)
    return render(request, "partials/practice/exercise.html", context, status=status)


# --- pages ----------------------------------------------------------------------------------


def hub(request):
    owner = svc.owner_from_request(request, create=False)
    ent = get_entitlements(owner.user)
    context = {
        "topic_sections": topic_sections(request.user),
        "entitlements": ent,
        "groups": group_progress(request.user) if request.user.is_authenticated else None,
        "remaining": svc.remaining_exercises(owner, ent) if owner.anon_key or owner.user else None,
    }
    if request.user.is_authenticated:
        from apps.progress.services.stats import completed_today

        context["today_count"] = completed_today(request.user)
        context["daily_goal"] = request.user.profile.daily_goal
    return render(request, "pages/practice/hub.html", context)


def daily(request):
    """Entry point from every "Începe să asculți" CTA. Visitors get a short free trial."""
    owner = svc.owner_from_request(request)
    level = request.GET.get("nivel", Level.CLEAR)
    try:
        session = svc.get_or_create_daily(owner, level=level)
    except svc.NoExercisesAvailable:
        return render(request, "pages/practice/empty.html", status=200)
    return redirect("practice:session", session_id=session.pk)


@require_POST
def start_topic(request, slug: str):
    topic = get_object_or_404(Topic, slug=slug, active=True)
    owner = svc.owner_from_request(request)
    if owner.user is None:
        return redirect("practice:daily")
    try:
        session = svc.create_session(
            owner, SessionKind.TOPIC, topic=topic, level=request.POST.get("nivel", Level.CLEAR)
        )
    except svc.NoExercisesAvailable:
        messages.info(request, "Nu există încă exerciții pentru această temă.")
        return redirect("practice:hub")
    return redirect("practice:session", session_id=session.pk)


@login_required
@require_POST
def start_pattern(request, slug: str):
    pattern = get_object_or_404(SpeechPattern, slug=slug)
    owner = svc.owner_from_request(request)
    try:
        session = svc.create_session(owner, SessionKind.PATTERN, pattern=pattern)
    except svc.NoExercisesAvailable:
        messages.info(request, "Nu există încă exerciții pentru acest tipar.")
        return redirect("progress:mistakes")
    return redirect("practice:session", session_id=session.pk)


@login_required
@require_POST
def start_personalized(request):
    ent = get_entitlements(request.user)
    if not ent.personalized_training:
        messages.info(request, "Antrenamentul personalizat face parte din planul Pro.")
        return redirect("billing:pricing")
    owner = svc.owner_from_request(request)
    try:
        session = svc.create_session(owner, SessionKind.PERSONALIZED)
    except svc.NoExercisesAvailable:
        return render(request, "pages/practice/empty.html")
    return redirect("practice:session", session_id=session.pk)


@require_GET
def session_view(request, session_id):
    session = _owned_session(request, session_id)
    current = svc.current_position(session)
    position = current
    step = request.GET.get("pas")
    if step and step.isdigit():
        requested = int(step) - 1
        # Completed items can be reviewed; you cannot skip ahead of the current one.
        if 0 <= requested < session.target_count and (current is None or requested <= current):
            position = requested
    context = _exercise_context(request, session, position)
    is_partial = request.htmx and not request.htmx.history_restore_request
    template = "partials/practice/exercise.html" if is_partial else "pages/practice/session.html"
    response = render(request, template, context)
    response["X-Robots-Tag"] = "noindex"
    return response


# --- htmx endpoints ---------------------------------------------------------------------------


@require_POST
@rate_limit("check", limit=40, window=60)
def check(request, attempt_id):
    attempt = _owned_attempt(request, attempt_id)
    session = attempt.session_item.session
    typed = request.POST.get("answer", "")
    if not typed.strip() and not attempt.completed:
        return _render_exercise(
            request,
            session,
            attempt.session_item.position,
            status=422,
            extra={
                "form_error": "Scrie ce ai auzit, chiar dacă nu ești sigur de toate cuvintele.",
                "typed": typed,
            },
        )
    owner = svc.owner_from_request(request)
    try:
        svc.check_attempt(owner, attempt, typed)
    except svc.PracticeLimitReached:
        pass  # the exercise partial renders the "limit reached" state
    return _render_result(request, attempt)


@require_POST
@rate_limit("reveal", limit=40, window=60)
def reveal(request, attempt_id):
    """Show the transcript: finish with whatever was typed, flagged as transcript dependency."""
    attempt = _owned_attempt(request, attempt_id)
    owner = svc.owner_from_request(request)
    svc.reveal_before_check(attempt)
    try:
        svc.check_attempt(owner, attempt, request.POST.get("answer", ""))
    except svc.PracticeLimitReached:
        pass
    return _render_result(request, attempt)


def _render_result(request, attempt):
    session = PracticeSession.objects.select_related("accent").get(
        pk=attempt.session_item.session_id
    )
    response = _render_exercise(
        request, session, attempt.session_item.position, extra={"just_checked": True}
    )
    response["HX-Trigger"] = "progress-updated"
    return response


@require_POST
@rate_limit("level", limit=30, window=60)
def change_level(request, attempt_id):
    attempt = _owned_attempt(request, attempt_id)
    ent = get_entitlements(request.user)
    level = request.POST.get("level", "")
    extra = {}
    if level not in Level.values:
        return HttpResponse(status=400)
    if not svc.change_level(attempt, level, ent):
        extra["level_locked_message"] = (
            "Nivelurile Engleză naturală și Engleză rapidă sunt disponibile în planul Pro."
        )
    session = attempt.session_item.session
    session.refresh_from_db()
    return _render_exercise(request, session, attempt.session_item.position, extra=extra)


@require_POST
@rate_limit("listen", limit=120, window=60)
def listen(request, attempt_id):
    attempt = _owned_attempt(request, attempt_id)
    try:
        svc.record_listening(
            attempt,
            plays=int(request.POST.get("plays", 0)),
            replays=int(request.POST.get("replays", 0)),
            ms=int(request.POST.get("ms", 0)),
            slowed=request.POST.get("slowed") == "1",
        )
    except (TypeError, ValueError):
        return HttpResponse(status=400)
    return HttpResponse(status=204)


@require_GET
@rate_limit("speech", limit=60, window=60, methods=("GET",))
def speech_text(request, attempt_id):
    """Development fallback: text for the browser's en-GB speech synthesis.

    Only served for placeholder (mock) audio and only when TTS_BROWSER_FALLBACK is on,
    so the transcript is never embedded in the page itself.
    """
    if not (settings.TTS_BROWSER_FALLBACK and settings.DEBUG):
        raise Http404
    attempt = _owned_attempt(request, attempt_id)
    if attempt.audio_variant and not attempt.audio_variant.is_placeholder:
        raise Http404
    style = LEVEL_STYLES[attempt.level]
    response = JsonResponse({"text": attempt.phrase.text, "rate": style.speed, "lang": "en-GB"})
    response["Cache-Control"] = "no-store"
    return response


def session_url(session: PracticeSession, position: int) -> str:
    return f"{reverse('practice:session', args=[session.pk])}?pas={position + 1}"
