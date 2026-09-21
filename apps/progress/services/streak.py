"""Streaks are computed from the user's local calendar days (see Profile.timezone)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from ..models import DailyPractice


@dataclass(frozen=True)
class StreakInfo:
    current: int
    longest: int
    practice_days: int
    practiced_today: bool


def compute_streak(days: Iterable[date], today: date) -> StreakInfo:
    """Current streak = consecutive days ending today (or yesterday, if today is not done)."""
    unique = sorted(set(days))
    day_set = set(unique)

    anchor = today if today in day_set else today - timedelta(days=1)
    current = 0
    while anchor in day_set:
        current += 1
        anchor -= timedelta(days=1)

    longest = run = 0
    previous: date | None = None
    for d in unique:
        run = run + 1 if previous is not None and d - previous == timedelta(days=1) else 1
        longest = max(longest, run)
        previous = d

    return StreakInfo(current, longest, len(unique), today in day_set)


def user_streak(user, today: date | None = None) -> StreakInfo:
    today = today or user.profile.local_today()
    days = DailyPractice.objects.filter(user=user, completed_count__gt=0).values_list(
        "date", flat=True
    )
    return compute_streak(days, today)
