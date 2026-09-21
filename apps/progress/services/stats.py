"""Progress dashboard numbers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

from django.db.models import Avg, Count, Q
from django.db.models.functions import TruncDate

from ..models import PatternMastery
from .streak import StreakInfo, user_streak

DEMO_OVERVIEW = {"overall": 64, "phrases_completed": 312}


@dataclass
class DayPoint:
    day: date
    count: int
    avg_score: int | None


@dataclass
class ProgressStats:
    overall_score: int
    phrases_completed: int
    exercises_completed: int
    streak: StreakInfo
    average_accuracy: int
    average_score: int
    transcript_dependency: int  # % of exercises where the transcript was shown before checking
    replay_frequency: float  # average replays per exercise
    slowed_down_share: int
    recent_improvement: int | None  # score change: last 7 days vs the 7 before
    today_count: int
    daily_goal: int
    days: list[DayPoint] = field(default_factory=list)
    patterns: list[PatternMastery] = field(default_factory=list)

    @property
    def has_data(self) -> bool:
        return self.exercises_completed > 0


def completed_today(user, today: date | None = None) -> int:
    from apps.progress.models import DailyPractice

    today = today or user.profile.local_today()
    row = DailyPractice.objects.filter(user=user, date=today).only("completed_count").first()
    return row.completed_count if row else 0


def overall_score(average_score: float, masteries: list[PatternMastery]) -> int:
    """Blend of recent dictation scores and pattern mastery."""
    if not masteries:
        return round(average_score)
    mastery_avg = sum(m.mastery for m in masteries) / len(masteries)
    return round(0.6 * average_score + 0.4 * mastery_avg)


def user_progress(user, today: date | None = None, chart_days: int = 14) -> ProgressStats:
    from apps.practice.models import ListeningAttempt

    profile = user.profile
    today = today or profile.local_today()
    done = ListeningAttempt.objects.filter(user=user, completed=True)

    totals = done.aggregate(
        exercises=Count("id"),
        phrases=Count("phrase", distinct=True),
        accuracy=Avg("word_accuracy"),
        revealed=Count("id", filter=Q(revealed_before_check=True)),
        slowed=Count("id", filter=Q(slowed_down=True)),
        replays=Avg("replay_count"),
    )
    recent_scores = list(done.order_by("-completed_at").values_list("score", flat=True)[:30])
    average_score = sum(recent_scores) / len(recent_scores) if recent_scores else 0
    exercises = totals["exercises"] or 0

    tz = profile.tzinfo
    start = today - timedelta(days=chart_days - 1)
    per_day = {
        row["day"]: row
        for row in done.filter(completed_at__date__gte=start - timedelta(days=1))
        .annotate(day=TruncDate("completed_at", tzinfo=tz))
        .values("day")
        .annotate(n=Count("id"), avg=Avg("score"))
    }
    days = []
    for i in range(chart_days):
        d = start + timedelta(days=i)
        row = per_day.get(d)
        days.append(DayPoint(d, row["n"] if row else 0, round(row["avg"]) if row else None))

    week = done.filter(completed_at__date__gte=today - timedelta(days=6)).aggregate(a=Avg("score"))
    prev = done.filter(
        completed_at__date__gte=today - timedelta(days=13),
        completed_at__date__lt=today - timedelta(days=6),
    ).aggregate(a=Avg("score"))
    improvement = None
    if week["a"] is not None and prev["a"] is not None:
        improvement = round(week["a"] - prev["a"])

    masteries = list(
        PatternMastery.objects.filter(user=user).select_related("pattern").order_by("-mastery")
    )
    return ProgressStats(
        overall_score=overall_score(average_score, masteries),
        phrases_completed=totals["phrases"] or 0,
        exercises_completed=exercises,
        streak=user_streak(user, today),
        average_accuracy=round(totals["accuracy"] or 0),
        average_score=round(average_score),
        transcript_dependency=round(100 * totals["revealed"] / exercises) if exercises else 0,
        replay_frequency=round(totals["replays"] or 0, 1),
        slowed_down_share=round(100 * totals["slowed"] / exercises) if exercises else 0,
        recent_improvement=improvement,
        today_count=completed_today(user, today),
        daily_goal=profile.daily_goal,
        days=days,
        patterns=masteries,
    )


def overview(user) -> dict:
    """Small summary for the homepage card ("Progres general", "Expresii finalizate")."""
    if user is None or not user.is_authenticated:
        return {**DEMO_OVERVIEW, "demo": True}
    from apps.practice.models import ListeningAttempt

    done = ListeningAttempt.objects.filter(user=user, completed=True)
    scores = list(done.order_by("-completed_at").values_list("score", flat=True)[:30])
    avg = sum(scores) / len(scores) if scores else 0
    masteries = list(PatternMastery.objects.filter(user=user))
    return {
        "overall": overall_score(avg, masteries),
        "phrases_completed": done.values("phrase").distinct().count(),
        "demo": False,
    }


CHART_RANGES = (7, 14, 30)


def score_label(score: int) -> str:
    if score >= 90:
        return "Excelent"
    if score >= 75:
        return "Foarte bine"
    if score >= 55:
        return "Bine"
    if score >= 30:
        return "În progres"
    return "La început"


def greeting(user) -> str:
    from django.utils import timezone as tz

    hour = tz.now().astimezone(user.profile.tzinfo).hour
    if 5 <= hour < 12:
        return "Bună dimineața"
    if 12 <= hour < 18:
        return "Bună ziua"
    return "Bună seara"


@dataclass
class ActivityDay:
    day: date
    count: int
    level: int  # 0-4, for the heatmap colour
    future: bool = False


def activity_weeks(user, today: date | None = None, weeks: int = 6) -> list[list[ActivityDay]]:
    """Calendar heatmap: `weeks` rows, Monday first, ending with the current week."""
    from apps.progress.models import DailyPractice

    today = today or user.profile.local_today()
    start = today - timedelta(days=today.weekday() + 7 * (weeks - 1))
    counts = dict(
        DailyPractice.objects.filter(user=user, date__gte=start, date__lte=today).values_list(
            "date", "completed_count"
        )
    )
    goal = max(user.profile.daily_goal, 1)
    rows = []
    for w in range(weeks):
        row = []
        for d in range(7):
            day = start + timedelta(days=7 * w + d)
            count = counts.get(day, 0)
            level = 0 if not count else min(4, 1 + (3 * count) // goal)
            row.append(ActivityDay(day, count, level, future=day > today))
        rows.append(row)
    return rows


def last_week_strip(user, today: date | None = None) -> list[ActivityDay]:
    """The last 7 days, oldest first (for the streak card)."""
    rows = activity_weeks(user, today, weeks=2)
    days = [d for row in rows for d in row if not d.future]
    return days[-7:]
