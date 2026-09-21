"""Rule-based personalisation: phrases that contain the user's weakest patterns come first.

`Recommender` is a small strategy interface so a smarter (e.g. model-based) recommender can
replace `WeaknessRecommender` later without touching views or session code.
"""

from __future__ import annotations

from typing import Protocol

from apps.progress.models import PatternMastery

UNSEEN_WEAKNESS = 0.5


class Recommender(Protocol):
    def phrase_boost(self, pattern_ids: list[int]) -> float: ...


class NeutralRecommender:
    def phrase_boost(self, pattern_ids: list[int]) -> float:
        return 1.0


class WeaknessRecommender:
    """Boost = 1 + 2 × the largest weakness (1 − mastery) among the phrase's patterns."""

    def __init__(self, weakness: dict[int, float]):
        self.weakness = weakness

    @classmethod
    def for_user(cls, user) -> WeaknessRecommender:
        rows = PatternMastery.objects.filter(user=user).values_list("pattern_id", "mastery")
        return cls({pid: (100 - mastery) / 100 for pid, mastery in rows})

    def phrase_boost(self, pattern_ids: list[int]) -> float:
        if not pattern_ids:
            return 1.0
        worst = max(self.weakness.get(pid, UNSEEN_WEAKNESS) for pid in pattern_ids)
        return 1.0 + 2.0 * worst

    def weakest_patterns(self, limit: int = 3) -> list[int]:
        ranked = sorted(self.weakness.items(), key=lambda kv: kv[1], reverse=True)
        return [pid for pid, _ in ranked[:limit]]


def recommender_for(user, entitlements) -> Recommender:
    if user is not None and user.is_authenticated:
        return WeaknessRecommender.for_user(user)
    return NeutralRecommender()
