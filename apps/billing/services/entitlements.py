"""Centralised feature gating: views, templates and services ask here, not the plan."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings

from apps.listening.models import Level

from ..models import Plan, Subscription


@dataclass(frozen=True)
class Entitlements:
    plan_code: str
    plan_name: str
    daily_limit: int | None  # None = unlimited
    levels: frozenset[str]
    full_mistake_history: bool
    personalized_training: bool
    advanced_progress: bool
    is_anonymous: bool = False

    @property
    def is_pro(self) -> bool:
        return self.plan_code == Plan.Code.PRO

    def can_use_level(self, level: str) -> bool:
        return level in self.levels

    def remaining_today(self, done_today: int) -> int | None:
        if self.daily_limit is None:
            return None
        return max(0, self.daily_limit - done_today)


FREE_FALLBACK = Entitlements(
    plan_code=Plan.Code.FREE,
    plan_name="Gratuit",
    daily_limit=10,
    levels=frozenset({Level.CLEAR}),
    full_mistake_history=False,
    personalized_training=False,
    advanced_progress=False,
)


def _from_plan(plan: Plan) -> Entitlements:
    levels = {Level.CLEAR}
    if plan.natural_level:
        levels.add(Level.NATURAL)
    if plan.fast_level:
        levels.add(Level.FAST)
    return Entitlements(
        plan_code=plan.code,
        plan_name=plan.name,
        daily_limit=plan.daily_exercise_limit,
        levels=frozenset(levels),
        full_mistake_history=plan.full_mistake_history,
        personalized_training=plan.personalized_training,
        advanced_progress=plan.advanced_progress,
    )


def get_plan_for(user) -> Plan | None:
    if user is not None and user.is_authenticated:
        sub = Subscription.objects.select_related("plan").filter(user=user).first()
        if sub and sub.is_active:
            return sub.plan
    return Plan.objects.filter(code=Plan.Code.FREE).first()


def get_entitlements(user) -> Entitlements:
    """Entitlements for a user (cached on the user object for the request)."""
    if user is None or not user.is_authenticated:
        return Entitlements(
            plan_code="anonymous",
            plan_name="Încercare",
            daily_limit=settings.ANONYMOUS_TRIAL_EXERCISES,
            levels=frozenset({Level.CLEAR}),
            full_mistake_history=False,
            personalized_training=False,
            advanced_progress=False,
            is_anonymous=True,
        )
    cached = getattr(user, "_entitlements", None)
    if cached is not None:
        return cached
    plan = get_plan_for(user)
    ent = _from_plan(plan) if plan else FREE_FALLBACK
    user._entitlements = ent
    return ent
