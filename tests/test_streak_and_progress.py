from datetime import date, timedelta

import pytest

from apps.progress.models import DailyPractice
from apps.progress.services import daily
from apps.progress.services.streak import compute_streak, user_streak

TODAY = date(2026, 9, 21)


def days_ago(*offsets):
    return [TODAY - timedelta(days=o) for o in offsets]


class TestComputeStreak:
    def test_no_days(self):
        info = compute_streak([], TODAY)
        assert (info.current, info.longest, info.practice_days) == (0, 0, 0)

    def test_streak_including_today(self):
        info = compute_streak(days_ago(0, 1, 2), TODAY)
        assert info.current == 3
        assert info.practiced_today

    def test_streak_still_alive_if_only_yesterday(self):
        info = compute_streak(days_ago(1, 2, 3, 4), TODAY)
        assert info.current == 4
        assert not info.practiced_today

    def test_streak_broken(self):
        info = compute_streak(days_ago(2, 3, 4), TODAY)
        assert info.current == 0
        assert info.longest == 3

    def test_longest_and_duplicates(self):
        info = compute_streak(days_ago(0, 0, 1, 5, 6, 7, 8, 12), TODAY)
        assert info.current == 2
        assert info.longest == 4
        assert info.practice_days == 7


@pytest.mark.django_db
class TestDailyPractice:
    def test_record_completion_counts_and_goal(self, user):
        user.profile.daily_goal = 3
        user.profile.save()
        for _ in range(3):
            row = daily.record_completion(user, TODAY)
        assert row.completed_count == 3
        assert row.goal_reached_at is not None
        assert DailyPractice.objects.filter(user=user).count() == 1

    def test_user_streak_uses_profile_timezone(self, user):
        for d in days_ago(0, 1, 2):
            DailyPractice.objects.create(user=user, date=d, completed_count=1)
        assert user_streak(user, TODAY).current == 3

    def test_local_today_respects_timezone(self, user):
        user.profile.timezone = "Europe/Bucharest"
        user.profile.save()
        assert user.profile.tzinfo.key == "Europe/Bucharest"
