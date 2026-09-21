"""Exercise selection: which phrases go into a session, in what order."""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import timedelta

from django.utils import timezone

from apps.listening.models import ListeningPhrase

from .personalization import NeutralRecommender, Recommender


@dataclass(frozen=True)
class Candidate:
    phrase: ListeningPhrase
    weight: float


def target_difficulty(user) -> int:
    """Pick a comfortable difficulty from the user's recent scores."""
    if user is None or not user.is_authenticated:
        return 2
    from apps.practice.models import ListeningAttempt

    scores = list(
        ListeningAttempt.objects.filter(user=user, completed=True)
        .order_by("-completed_at")
        .values_list("score", flat=True)[:20]
    )
    if len(scores) < 5:
        return 2
    avg = sum(scores) / len(scores)
    if avg < 60:
        return 2
    if avg < 80:
        return 3
    if avg < 92:
        return 4
    return 5


def recently_completed(user, days: int = 3) -> set[int]:
    if user is None or not user.is_authenticated:
        return set()
    from apps.practice.models import ListeningAttempt

    since = timezone.now() - timedelta(days=days)
    return set(
        ListeningAttempt.objects.filter(
            user=user, completed=True, completed_at__gte=since
        ).values_list("phrase_id", flat=True)
    )


def ever_completed(user) -> set[int]:
    if user is None or not user.is_authenticated:
        return set()
    from apps.practice.models import ListeningAttempt

    return set(
        ListeningAttempt.objects.filter(user=user, completed=True).values_list(
            "phrase_id", flat=True
        )
    )


def choose_phrases(
    user,
    count: int,
    *,
    topic=None,
    pattern=None,
    max_difficulty: int | None = None,
    recommender: Recommender | None = None,
    seed: str | int | None = None,
) -> list[ListeningPhrase]:
    """Weighted sampling without replacement.

    weight = personalisation boost × freshness × closeness to the target difficulty
    """
    qs = (
        ListeningPhrase.objects.active().select_related("topic").prefetch_related("phrase_patterns")
    )
    if topic is not None:
        qs = qs.filter(topic=topic)
    if pattern is not None:
        qs = qs.filter(phrase_patterns__pattern=pattern).distinct()
    if max_difficulty is not None:
        qs = qs.filter(difficulty__lte=max_difficulty)
    phrases = list(qs)
    if not phrases:
        return []

    recommender = recommender or NeutralRecommender()
    target = target_difficulty(user)
    recent = recently_completed(user)
    seen = ever_completed(user)

    candidates = []
    for phrase in phrases:
        pattern_ids = [pp.pattern_id for pp in phrase.phrase_patterns.all()]
        weight = recommender.phrase_boost(pattern_ids)
        if phrase.pk in recent:
            weight *= 0.15
        elif phrase.pk not in seen:
            weight *= 1.5
        weight *= 1 / (1 + abs(phrase.difficulty - target))
        candidates.append(Candidate(phrase, weight))

    rng = random.Random(seed)
    chosen: list[ListeningPhrase] = []
    pool = candidates[:]
    while pool and len(chosen) < count:
        total = sum(c.weight for c in pool)
        pick = rng.uniform(0, total)
        acc = 0.0
        for i, c in enumerate(pool):
            acc += c.weight
            if acc >= pick:
                chosen.append(pool.pop(i).phrase)
                break
        else:  # floating point edge
            chosen.append(pool.pop().phrase)
    # Gentle ramp: easier phrases first within the session.
    chosen.sort(key=lambda p: p.difficulty)
    return chosen
