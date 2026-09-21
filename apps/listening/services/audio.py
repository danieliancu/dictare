"""Audio selection for learners (the *read* path). Pure database lookups, no network calls.

Play only ever serves a stored file. For a phrase × level × accent and the session's voice,
the first tier with a servable recording whose file exists wins:

1. TTS recording in exactly the requested voice (Marin, Ballad or Cedar);
2. controlled fallback: TTS recording in Marin (only if another voice was requested);
3. human recording (``provider=human``) — for accents or content without TTS;
4. development only (TTS_REQUIRE_APPROVAL=False): the offline mock placeholder.

Inside a tier: approved before others, current engine version first, then newest — never
database order. "Servable" means approved; in development (TTS_REQUIRE_APPROVAL=False) also
pending / needs_review.
Rejected recordings and rows whose file is missing are never served.
"""

from __future__ import annotations

from django.conf import settings
from django.db.models import Case, IntegerField, Q, Value, When

from ..models import AudioVariant
from ..voices import DEFAULT_VOICE, FALLBACK_VOICE

QA = AudioVariant.QAStatus
MOCK = "mock"


def servable_statuses() -> list[str]:
    """Production: approved only. Development may also play not-yet-approved audio."""
    if settings.TTS_REQUIRE_APPROVAL:
        return [QA.APPROVED]
    return [QA.APPROVED, QA.PENDING, QA.NEEDS_REVIEW]


def _tts(voice: str) -> Q:
    return Q(voice=voice) & ~Q(provider__in=[AudioVariant.HUMAN, MOCK])


def voice_tiers(voice: str) -> list[Q]:
    """The ordered selection tiers for a requested voice (see module docstring)."""
    tiers = [_tts(voice)]
    if voice != FALLBACK_VOICE:
        tiers.append(_tts(FALLBACK_VOICE))
    tiers.append(Q(provider=AudioVariant.HUMAN))
    if not settings.TTS_REQUIRE_APPROVAL:
        tiers.append(Q(provider=MOCK))
    return tiers


def _servable():
    return AudioVariant.objects.filter(qa_status__in=servable_statuses()).exclude(audio_file="")


def _ranked(qs):
    return qs.annotate(
        _status_rank=Case(
            When(qa_status=QA.APPROVED, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        ),
        _engine_rank=Case(
            When(engine_version=str(settings.TTS_ENGINE_VERSION), then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        ),
    ).order_by("_status_rank", "_engine_rank", "-generated_at", "-pk")


def file_exists(variant) -> bool:
    """A recording is available only if its file physically exists in storage."""
    name = variant.audio_file.name if variant.audio_file else ""
    return bool(name) and variant.audio_file.storage.exists(name)


def get_audio_variant(phrase, level: str, accent, voice: str = DEFAULT_VOICE):
    """Best servable recording whose file exists, following the voice tiers, or None.

    Never generates audio. Every candidate of a tier is checked, so orphaned rows (file
    missing) are skipped rather than ending the search.
    """
    base = _servable().filter(phrase=phrase, level=level, accent=accent)
    for tier in voice_tiers(voice):
        for variant in _ranked(base.filter(tier)):
            if file_exists(variant):
                return variant
    return None


def phrase_ids_with_audio(level: str, accent, voice: str = DEFAULT_VOICE) -> set[int]:
    """Phrases for which `get_audio_variant(..., voice)` would find a real file."""
    any_tier = Q()
    for tier in voice_tiers(voice):
        any_tier |= tier
    available: set[int] = set()
    rows = _servable().filter(any_tier, level=level, accent=accent)
    for variant in rows.only("id", "phrase_id", "audio_file"):
        if variant.phrase_id not in available and file_exists(variant):
            available.add(variant.phrase_id)
    return available


def can_generate_on_request() -> bool:
    """On-request generation is a development convenience for the offline mock only."""
    return bool(settings.TTS_GENERATE_ON_REQUEST) and settings.TTS_PROVIDER == MOCK
