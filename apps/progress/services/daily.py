from __future__ import annotations

from datetime import date

from django.db import transaction
from django.db.models import F
from django.utils import timezone

from ..models import DailyPractice


@transaction.atomic
def record_completion(user, local_date: date | None = None) -> DailyPractice:
    """Count one completed exercise on the user's local calendar day."""
    local_date = local_date or user.profile.local_today()
    row, _ = DailyPractice.objects.select_for_update().get_or_create(
        user=user, date=local_date, defaults={"goal": user.profile.daily_goal}
    )
    DailyPractice.objects.filter(pk=row.pk).update(completed_count=F("completed_count") + 1)
    row.refresh_from_db()
    if row.goal_reached and row.goal_reached_at is None:
        row.goal_reached_at = timezone.now()
        row.save(update_fields=["goal_reached_at"])
    return row
