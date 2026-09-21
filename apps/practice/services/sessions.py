"""Practice sessions and attempts: the listen → type → check → understand loop."""

from __future__ import annotations

import logging
import secrets
import zoneinfo
from dataclasses import dataclass

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.ai.services.tts import TTSError, generate_variant
from apps.billing.services.entitlements import Entitlements, get_entitlements
from apps.listening.models import Accent, Level
from apps.listening.services.audio import (
    can_generate_on_request,
    get_audio_variant,
    phrase_ids_with_audio,
)
from apps.listening.services.patterns import pattern_for_position, verified_patterns_for_variant
from apps.listening.voices import DEFAULT_VOICE
from apps.progress.services import daily, mastery
from apps.scoring.services import ScoreResult, Status, score_answer

from ..models import (
    AttemptMistake,
    ListeningAttempt,
    PracticeSession,
    SessionItem,
    SessionKind,
)
from .personalization import recommender_for
from .selection import choose_phrases

logger = logging.getLogger(__name__)

ANON_SESSION_KEY = "anon_key"
MAX_TELEMETRY_PLAYS = 50
MAX_TELEMETRY_MS = 30 * 60 * 1000
DEFAULT_TZ = zoneinfo.ZoneInfo("Europe/London")


class PracticeLimitReached(Exception):
    """The user's plan does not allow more exercises today."""


class NoExercisesAvailable(Exception):
    pass


# --- ownership ----------------------------------------------------------------------------


@dataclass(frozen=True)
class Owner:
    user: object | None
    anon_key: str

    @property
    def is_authenticated(self) -> bool:
        return self.user is not None and self.user.is_authenticated

    def fields(self) -> dict:
        if self.is_authenticated:
            return {"user": self.user, "anon_key": ""}
        return {"user": None, "anon_key": self.anon_key}

    def local_today(self):
        if self.is_authenticated:
            return self.user.profile.local_today()
        return timezone.now().astimezone(DEFAULT_TZ).date()


def owner_from_request(request, create: bool = True) -> Owner:
    user = request.user if request.user.is_authenticated else None
    key = request.session.get(ANON_SESSION_KEY, "")
    if user is None and not key and create:
        key = secrets.token_urlsafe(24)
        request.session[ANON_SESSION_KEY] = key
    return Owner(user, key)


def claim_anonymous_work(user, anon_key: str) -> int:
    """Attach a visitor's trial attempts to the account they just created or logged into."""
    if not anon_key:
        return 0
    with transaction.atomic():
        PracticeSession.objects.filter(user__isnull=True, anon_key=anon_key).update(user=user)
        attempts = ListeningAttempt.objects.filter(user__isnull=True, anon_key=anon_key)
        completed = list(attempts.filter(completed=True).values_list("completed_at", flat=True))
        claimed = attempts.update(user=user)
    tz = user.profile.tzinfo
    for completed_at in completed:
        daily.record_completion(user, completed_at.astimezone(tz).date())
    mastery.recompute(user)
    return claimed


# --- limits ---------------------------------------------------------------------------------


def completed_today(owner: Owner) -> int:
    if owner.is_authenticated:
        from apps.progress.services.stats import completed_today as user_completed_today

        return user_completed_today(owner.user)
    return ListeningAttempt.objects.filter(
        user__isnull=True, anon_key=owner.anon_key, completed=True
    ).count()


def remaining_exercises(owner: Owner, ent: Entitlements | None = None) -> int | None:
    ent = ent or get_entitlements(owner.user)
    return ent.remaining_today(completed_today(owner))


def allowed_level(level: str | None, ent: Entitlements) -> str:
    if level in Level.values and ent.can_use_level(level):
        return level
    return Level.CLEAR


# --- sessions -------------------------------------------------------------------------------


def _default_accent(owner: Owner) -> Accent:
    if owner.is_authenticated and owner.user.profile.preferred_accent_id:
        accent = owner.user.profile.preferred_accent
        if accent.active:
            return accent
    accent = Accent.default()
    if accent is None:
        raise NoExercisesAvailable("No accent configured.")
    return accent


def session_voice(owner: Owner) -> str:
    """The learner's chosen voice; visitors without an account always hear Marin."""
    if owner.is_authenticated:
        return owner.user.profile.preferred_voice or DEFAULT_VOICE
    return DEFAULT_VOICE


@transaction.atomic
def create_session(
    owner: Owner,
    kind: str,
    *,
    level: str = Level.CLEAR,
    topic=None,
    pattern=None,
    count: int | None = None,
) -> PracticeSession:
    ent = get_entitlements(owner.user)
    count = count or settings.DAILY_EXERCISES
    max_difficulty = None
    if kind == SessionKind.TRIAL:
        count = settings.ANONYMOUS_TRIAL_EXERCISES
        max_difficulty = 2
    recommender = recommender_for(owner.user, ent)
    session = PracticeSession(
        kind=kind,
        level=allowed_level(level, ent),
        accent=_default_accent(owner),
        topic=topic,
        pattern=pattern,
        local_date=owner.local_today(),
        target_count=count,
        voice=session_voice(owner),
        **owner.fields(),
    )
    only_ids = None
    if settings.TTS_REQUIRE_APPROVAL:
        # Production: only phrases that already have an approved recording for this level.
        only_ids = phrase_ids_with_audio(session.level, session.accent, session.voice)
    phrases = choose_phrases(
        owner.user,
        count,
        topic=topic,
        pattern=pattern,
        max_difficulty=max_difficulty,
        only_ids=only_ids,
        recommender=recommender,
        seed=str(session.id),
    )
    if not phrases:
        raise NoExercisesAvailable("No active phrases match this session.")
    session.target_count = len(phrases)
    session.save()
    SessionItem.objects.bulk_create(
        SessionItem(session=session, phrase=p, position=i) for i, p in enumerate(phrases)
    )
    return session


def get_or_create_daily(owner: Owner, level: str = Level.CLEAR) -> PracticeSession:
    kind = SessionKind.DAILY if owner.is_authenticated else SessionKind.TRIAL
    existing = (
        PracticeSession.objects.owned_by(owner.user, owner.anon_key)
        .filter(kind=kind)
        .order_by("-created_at")
    )
    if kind == SessionKind.DAILY:
        existing = existing.filter(local_date=owner.local_today())
    session = existing.first()
    if session is not None:
        return session
    return create_session(owner, kind, level=level)


def session_items(session: PracticeSession) -> list[SessionItem]:
    return list(session.items.select_related("phrase").order_by("position"))


def completed_positions(session: PracticeSession) -> set[int]:
    return set(
        ListeningAttempt.objects.filter(session_item__session=session, completed=True).values_list(
            "session_item__position", flat=True
        )
    )


def current_position(session: PracticeSession) -> int | None:
    done = completed_positions(session)
    for pos in range(session.target_count):
        if pos not in done:
            return pos
    return None


def maybe_complete_session(session: PracticeSession) -> bool:
    if session.completed_at is None and current_position(session) is None:
        session.completed_at = timezone.now()
        session.save(update_fields=["completed_at"])
        return True
    return session.completed_at is not None


# --- attempts -------------------------------------------------------------------------------


def ensure_audio(attempt: ListeningAttempt, accent: Accent, voice: str = DEFAULT_VOICE) -> None:
    """Attach the best servable recording for the attempt's level and the session's voice.

    Never calls a remote API: Play only ever serves a stored file.

    Completed attempts keep the recording the learner actually heard, so the explanation
    shown afterwards still matches that audio.
    """
    if attempt.completed and attempt.audio_variant_id:
        return
    variant = get_audio_variant(attempt.phrase, attempt.level, accent, voice)
    if variant is None and can_generate_on_request():
        try:
            variant = generate_variant(
                attempt.phrase, attempt.level, accent, voice=voice, provider="mock"
            )
        except TTSError:
            variant = None
    if variant is None:
        logger.info("No servable audio for phrase %s (%s)", attempt.phrase_id, attempt.level)
    if attempt.audio_variant_id != (variant.pk if variant else None):
        attempt.audio_variant = variant
        attempt.save(update_fields=["audio_variant"])


def get_or_start_attempt(owner: Owner, item: SessionItem, level: str) -> ListeningAttempt:
    try:
        attempt, _ = ListeningAttempt.objects.select_related(
            "audio_variant", "phrase"
        ).get_or_create(
            session_item=item,
            defaults={"phrase": item.phrase, "level": level, **owner.fields()},
        )
    except IntegrityError:
        attempt = ListeningAttempt.objects.get(session_item=item)
    ensure_audio(attempt, item.session.accent, item.session.voice)
    return attempt


def change_level(attempt: ListeningAttempt, level: str, ent: Entitlements) -> bool:
    if attempt.completed or not ent.can_use_level(level):
        return False
    if attempt.level != level:
        attempt.level = level
        attempt.save(update_fields=["level"])
        session = attempt.session_item.session
        if session.level != level:
            session.level = level
            session.save(update_fields=["level"])
        ensure_audio(attempt, session.accent, session.voice)
    return True


def record_listening(
    attempt: ListeningAttempt, *, plays: int, replays: int, ms: int, slowed: bool
) -> None:
    """Store player telemetry. Values come from the browser, so they are clamped."""
    plays = max(0, min(int(plays), MAX_TELEMETRY_PLAYS))
    replays = max(0, min(int(replays), MAX_TELEMETRY_PLAYS))
    ms = max(0, min(int(ms), MAX_TELEMETRY_MS))
    attempt.listened_count = min(attempt.listened_count + plays, 1000)
    attempt.replay_count = min(attempt.replay_count + replays, 1000)
    attempt.time_spent_ms = min(attempt.time_spent_ms + ms, 10 * MAX_TELEMETRY_MS)
    attempt.slowed_down = attempt.slowed_down or bool(slowed)
    attempt.save(update_fields=["listened_count", "replay_count", "time_spent_ms", "slowed_down"])


def save_mistakes(attempt: ListeningAttempt, result: ScoreResult) -> None:
    """Store word mistakes. A mistake is linked to a speech pattern only if a reviewer verified
    that pattern as audible in the recording the learner heard; otherwise it stays word-level."""
    applied = verified_patterns_for_variant(attempt.audio_variant, attempt.phrase)
    mistakes = []
    for w in result.mistakes:
        pp = pattern_for_position(applied, w.position)
        mistakes.append(
            AttemptMistake(
                attempt=attempt,
                position=w.position,
                expected_word=w.text[:80] if w.status != Status.EXTRA else "",
                typed_word=w.typed[:80],
                mistake_type=w.status,
                speech_pattern_id=pp.pattern_id if pp else None,
                severity=round(w.severity, 3),
            )
        )
    AttemptMistake.objects.bulk_create(mistakes)


def check_attempt(owner: Owner, attempt: ListeningAttempt, typed: str) -> ScoreResult:
    """Score the answer, store mistakes and update progress. Idempotent once completed."""
    if attempt.completed:
        return score_answer(attempt.phrase.text, attempt.typed_answer)

    if remaining_exercises(owner) == 0:
        raise PracticeLimitReached

    typed = (typed or "").strip()[:500]
    result = score_answer(attempt.phrase.text, typed)
    with transaction.atomic():
        locked = ListeningAttempt.objects.select_for_update().get(pk=attempt.pk)
        if locked.completed:
            return score_answer(locked.phrase.text, locked.typed_answer)
        attempt.typed_answer = typed
        attempt.score = result.score
        attempt.word_accuracy = result.word_accuracy
        attempt.completed = True
        attempt.completed_at = timezone.now()
        attempt.transcript_revealed = True  # the result view shows the transcript
        attempt.save(
            update_fields=[
                "typed_answer",
                "score",
                "word_accuracy",
                "completed",
                "completed_at",
                "transcript_revealed",
            ]
        )
        save_mistakes(attempt, result)

    if owner.is_authenticated:
        daily.record_completion(owner.user)
        mastery.recompute(
            owner.user, attempt.phrase.phrase_patterns.values_list("pattern_id", flat=True)
        )
    if attempt.session_item_id:
        maybe_complete_session(attempt.session_item.session)
    return result


def reveal_before_check(attempt: ListeningAttempt) -> None:
    """User asked for the transcript without checking: counts as transcript dependency."""
    if attempt.completed:
        return
    attempt.transcript_revealed = True
    attempt.revealed_before_check = True
    attempt.save(update_fields=["transcript_revealed", "revealed_before_check"])
