"""Audio selection for learners (the *read* path). Pure database lookups, no network calls.

Priority for a phrase × level × accent:

1. approved human recording;
2. approved TTS recording (current voice and engine version first, then newest);
3. only if TTS_REQUIRE_APPROVAL is False: pending recordings (human > real TTS > mock);
4. otherwise nothing — the page shows the "audio unavailable" state.

Rejected recordings are never served.
"""

from __future__ import annotations

from django.conf import settings
from django.db.models import Case, IntegerField, Value, When

from ..models import AudioVariant

QA = AudioVariant.QAStatus


def servable_statuses() -> list[str]:
    if settings.TTS_REQUIRE_APPROVAL:
        return [QA.APPROVED]
    return [QA.APPROVED, QA.PENDING]


def _ranked(qs):
    return qs.annotate(
        _status_rank=Case(
            When(qa_status=QA.APPROVED, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        ),
        _source_rank=Case(
            When(provider=AudioVariant.HUMAN, then=Value(0)),
            When(provider="mock", then=Value(2)),
            default=Value(1),
            output_field=IntegerField(),
        ),
        _voice_rank=Case(
            When(voice=settings.TTS_VOICE, then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        ),
        _engine_rank=Case(
            When(engine_version=str(settings.TTS_ENGINE_VERSION), then=Value(0)),
            default=Value(1),
            output_field=IntegerField(),
        ),
    ).order_by("_status_rank", "_source_rank", "_voice_rank", "_engine_rank", "-generated_at")


def servable_variants(phrase, level: str, accent):
    qs = AudioVariant.objects.filter(
        phrase=phrase, level=level, accent=accent, qa_status__in=servable_statuses()
    ).exclude(audio_file="")
    if settings.TTS_REQUIRE_APPROVAL:
        qs = qs.exclude(provider="mock")
    return _ranked(qs)


def file_exists(variant) -> bool:
    """A recording is available only if its file physically exists in storage."""
    name = variant.audio_file.name if variant.audio_file else ""
    return bool(name) and variant.audio_file.storage.exists(name)


def get_audio_variant(phrase, level: str, accent) -> AudioVariant | None:
    """Best servable recording whose file exists, or None. Never generates audio.

    Every ranked candidate is checked (there are only a handful per phrase): orphaned rows
    whose file is missing are skipped, never served.
    """
    for variant in servable_variants(phrase, level, accent):
        if file_exists(variant):
            return variant
    return None


def phrase_ids_with_audio(level: str, accent) -> set[int]:
    """Phrases with at least one servable recording whose file really exists."""
    qs = AudioVariant.objects.filter(
        level=level, accent=accent, qa_status__in=servable_statuses()
    ).exclude(audio_file="")
    if settings.TTS_REQUIRE_APPROVAL:
        qs = qs.exclude(provider="mock")
    available: set[int] = set()
    for variant in qs.only("id", "phrase_id", "audio_file"):
        if variant.phrase_id not in available and file_exists(variant):
            available.add(variant.phrase_id)
    return available


def can_generate_on_request() -> bool:
    """On-request generation is a development convenience for the offline mock only."""
    return bool(settings.TTS_GENERATE_ON_REQUEST) and settings.TTS_PROVIDER == "mock"
