"""Per-pattern mastery (0–100) from recent exposures.

An exposure is a completed attempt on a phrase that contains the pattern. The outcome of an
exposure is 1 minus the worst mistake severity inside the pattern's word span, reduced when
the transcript was shown before checking or when the phrase needed many replays. Recent
exposures and harder phrases weigh more; mastery is scaled down until there are enough
exposures to be confident.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from django.db.models import Prefetch
from django.utils import timezone

from apps.listening.models import PatternGroup, PhrasePattern, SpeechPattern
from apps.listening.services.patterns import verified_patterns_for_variant

from ..models import PatternMastery

WINDOW = 20
RECENCY_DECAY = 0.88
CONFIDENT_AFTER = 5
MISS_THRESHOLD = 0.7


def exposure_outcome(attempt, phrase_pattern, mistakes) -> tuple[float, bool]:
    worst = max(
        (
            m.severity
            for m in mistakes
            if m.position is not None
            and phrase_pattern.start_token <= m.position <= phrase_pattern.end_token
        ),
        default=0.0,
    )
    raw = max(0.0, 1.0 - worst)
    outcome = raw
    if attempt.revealed_before_check:
        outcome *= 0.5
    outcome *= max(0.7, 1 - 0.05 * max(0, attempt.replay_count - 2))
    return outcome, raw < MISS_THRESHOLD


def recompute(user, pattern_ids: Iterable[int] | None = None) -> None:
    from apps.practice.models import AttemptMistake, ListeningAttempt

    patterns = SpeechPattern.objects.all()
    if pattern_ids is not None:
        patterns = patterns.filter(pk__in=list(pattern_ids))
    pattern_ids = [p.pk for p in patterns]
    if not pattern_ids:
        return

    attempts = (
        ListeningAttempt.objects.filter(
            user=user, completed=True, phrase__phrase_patterns__pattern_id__in=pattern_ids
        )
        .distinct()
        .select_related("phrase", "audio_variant")
        .prefetch_related(
            Prefetch("phrase__phrase_patterns", queryset=PhrasePattern.objects.all()),
            Prefetch("mistakes", queryset=AttemptMistake.objects.all()),
            "audio_variant__pattern_checks",
        )
        .order_by("-completed_at")
    )

    samples: dict[int, list[tuple[float, float, bool]]] = defaultdict(list)
    totals: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    last_seen: dict[int, object] = {}
    for attempt in attempts:
        mistakes = list(attempt.mistakes.all())
        # Only phenomena verified as audible in the recording heard count as an exposure.
        applied = verified_patterns_for_variant(attempt.audio_variant, attempt.phrase)
        for pp in (a.phrase_pattern for a in applied):
            if pp.pattern_id not in pattern_ids:
                continue
            outcome, missed = exposure_outcome(attempt, pp, mistakes)
            totals[pp.pattern_id][0] += 1
            totals[pp.pattern_id][1] += int(missed)
            last_seen.setdefault(pp.pattern_id, attempt.completed_at)
            if len(samples[pp.pattern_id]) < WINDOW:
                difficulty_weight = 1 + 0.1 * (attempt.phrase.difficulty - 3)
                samples[pp.pattern_id].append((outcome, difficulty_weight, missed))

    for pid in pattern_ids:
        rows = samples.get(pid, [])
        if not rows:
            PatternMastery.objects.filter(user=user, pattern_id=pid).delete()
            continue
        num = den = 0.0
        for i, (outcome, diff_w, _) in enumerate(rows):
            w = (RECENCY_DECAY**i) * diff_w
            num += w * outcome
            den += w
        confidence = min(1.0, len(rows) / CONFIDENT_AFTER)
        mastery = round(100 * (num / den) * confidence)
        PatternMastery.objects.update_or_create(
            user=user,
            pattern_id=pid,
            defaults={
                "mastery": max(0, min(100, mastery)),
                "exposures": totals[pid][0],
                "misses": totals[pid][1],
                "last_practiced": last_seen.get(pid) or timezone.now(),
            },
        )


def mastery_map(user) -> dict[int, PatternMastery]:
    return {m.pattern_id: m for m in PatternMastery.objects.filter(user=user)}


GROUP_META = [
    (PatternGroup.WEAK_FORMS, "Forme slabe", "weak", "violet"),
    (PatternGroup.LINKING, "Sunete legate între cuvinte", "link", "blue"),
    (PatternGroup.FREQUENT, "Expresii folosite frecvent", "chat", "green"),
    (PatternGroup.ACCENTS, "Accente britanice", "people", "teal"),
]
DEMO_GROUPS = [78, 62, 45, 38, 71]


def group_progress(user) -> list[dict]:
    """Rows for the "Exercițiile tale" card. Anonymous visitors see demo values."""
    rows = []
    if user is None or not user.is_authenticated:
        for (group, label, icon, color), value in zip(GROUP_META, DEMO_GROUPS, strict=False):
            rows.append(
                {
                    "key": group,
                    "label": label,
                    "icon": icon,
                    "color": color,
                    "value": value,
                    "url_pattern": None,
                }
            )
        rows.append(
            {
                "key": "personal",
                "label": "Tiparele tale dificile",
                "icon": "target",
                "color": "red",
                "value": DEMO_GROUPS[-1],
                "url_pattern": None,
            }
        )
        return rows

    masteries = list(PatternMastery.objects.filter(user=user).select_related("pattern"))
    by_group: dict[str, list[PatternMastery]] = defaultdict(list)
    for m in masteries:
        by_group[m.pattern.group].append(m)
    for group, label, icon, color in GROUP_META:
        items = by_group.get(group, [])
        exposures = sum(m.exposures for m in items)
        value = round(sum(m.mastery * m.exposures for m in items) / exposures) if exposures else 0
        weakest = min(items, key=lambda m: m.mastery).pattern.slug if items else None
        rows.append(
            {
                "key": group,
                "label": label,
                "icon": icon,
                "color": color,
                "value": value,
                "url_pattern": weakest,
            }
        )
    hardest = sorted(masteries, key=lambda m: m.mastery)[:3]
    value = round(sum(m.mastery for m in hardest) / len(hardest)) if hardest else 0
    rows.append(
        {
            "key": "personal",
            "label": "Tiparele tale dificile",
            "icon": "target",
            "color": "red",
            "value": value,
            "url_pattern": hardest[0].pattern.slug if hardest else None,
        }
    )
    return rows
