"""Data-only: stop judging learners on phenomena nobody verified in the audio.

Before P0 hardening, mistakes and mastery were attributed to speech patterns that were only
*expected* in a recording. Keep every attempt and mistake, but:

* clear AttemptMistake.speech_pattern unless the recording heard has that pattern verified
  PRESENT over the mistaken word;
* delete PatternMastery rows with no remaining verified exposure (they are rebuilt by
  `python manage.py recompute_mastery` / the next completed exercise).
"""

from django.db import migrations

PRESENT = "present"


def drop_unverified(apps, schema_editor):
    AttemptMistake = apps.get_model("practice", "AttemptMistake")
    AudioVariantPattern = apps.get_model("listening", "AudioVariantPattern")
    PatternMastery = apps.get_model("progress", "PatternMastery")

    # (variant id, pattern id) -> spans verified present in that recording
    verified: dict[tuple[int, int], list[tuple[int, int]]] = {}
    for check in AudioVariantPattern.objects.filter(verification=PRESENT).select_related(
        "phrase_pattern"
    ):
        pp = check.phrase_pattern
        verified.setdefault((check.audio_variant_id, pp.pattern_id), []).append(
            (pp.start_token, pp.end_token)
        )

    invalid = []
    valid_pairs = set()
    for mistake in AttemptMistake.objects.filter(speech_pattern__isnull=False).select_related(
        "attempt"
    ):
        spans = verified.get((mistake.attempt.audio_variant_id, mistake.speech_pattern_id), [])
        ok = mistake.position is not None and any(
            start <= mistake.position <= end for start, end in spans
        )
        if ok:
            valid_pairs.add((mistake.attempt.user_id, mistake.speech_pattern_id))
        else:
            invalid.append(mistake.pk)
    AttemptMistake.objects.filter(pk__in=invalid).update(speech_pattern=None)

    # A mastery row is only valid if the user heard at least one verified exposure.
    ListeningAttempt = apps.get_model("practice", "ListeningAttempt")
    exposed = set()
    variant_patterns = {}
    for (variant_id, pattern_id) in verified:
        variant_patterns.setdefault(variant_id, set()).add(pattern_id)
    for user_id, variant_id in ListeningAttempt.objects.filter(
        completed=True, user__isnull=False, audio_variant_id__in=list(variant_patterns)
    ).values_list("user_id", "audio_variant_id"):
        for pattern_id in variant_patterns[variant_id]:
            exposed.add((user_id, pattern_id))
    stale = [
        m.pk
        for m in PatternMastery.objects.all()
        if (m.user_id, m.pattern_id) not in exposed
    ]
    PatternMastery.objects.filter(pk__in=stale).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("progress", "0001_initial"),
        ("practice", "0001_initial"),
        ("listening", "0002_audio_qa_and_variant_patterns"),
    ]

    operations = [migrations.RunPython(drop_unverified, migrations.RunPython.noop)]
