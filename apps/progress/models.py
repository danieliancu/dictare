from django.conf import settings
from django.db import models


class DailyPractice(models.Model):
    """One row per user per local calendar day with at least one completed exercise."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="daily_practice"
    )
    date = models.DateField("dată (locală)")
    completed_count = models.PositiveSmallIntegerField("exerciții finalizate", default=0)
    goal = models.PositiveSmallIntegerField("obiectiv", default=10)
    goal_reached_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-date"]
        verbose_name = "zi de practică"
        verbose_name_plural = "zile de practică"
        constraints = [models.UniqueConstraint(fields=["user", "date"], name="unique_user_day")]

    def __str__(self) -> str:
        return f"{self.user} · {self.date} · {self.completed_count}/{self.goal}"

    @property
    def goal_reached(self) -> bool:
        return self.completed_count >= self.goal


class PatternMastery(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="pattern_mastery"
    )
    pattern = models.ForeignKey(
        "listening.SpeechPattern", on_delete=models.CASCADE, related_name="mastery"
    )
    mastery = models.PositiveSmallIntegerField(default=0)
    exposures = models.PositiveIntegerField("expuneri", default=0)
    misses = models.PositiveIntegerField("ratări", default=0)
    last_practiced = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["user", "mastery"]
        verbose_name = "stăpânire tipar"
        verbose_name_plural = "stăpânire tipare"
        constraints = [
            models.UniqueConstraint(fields=["user", "pattern"], name="unique_user_pattern"),
            models.CheckConstraint(condition=models.Q(mastery__lte=100), name="mastery_range"),
        ]

    def __str__(self) -> str:
        return f"{self.user} · {self.pattern} · {self.mastery}%"

    @property
    def miss_rate(self) -> int:
        return round(100 * self.misses / self.exposures) if self.exposures else 0
