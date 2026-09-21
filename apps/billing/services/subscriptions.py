"""Subscription state changes, independent of the payment provider."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.db import transaction

from ..models import Plan, Subscription


@dataclass(frozen=True)
class SubscriptionEvent:
    """Provider-agnostic event (e.g. built from a Stripe `customer.subscription.*` webhook)."""

    user_id: int
    plan_code: str
    status: str
    provider: str
    customer_id: str = ""
    subscription_id: str = ""
    current_period_end: datetime | None = None


@transaction.atomic
def apply_subscription_event(event: SubscriptionEvent) -> Subscription:
    plan = Plan.objects.get(code=event.plan_code)
    sub, _ = Subscription.objects.select_for_update().update_or_create(
        user_id=event.user_id,
        defaults={
            "plan": plan,
            "status": event.status,
            "provider": event.provider,
            "provider_customer_id": event.customer_id,
            "provider_subscription_id": event.subscription_id,
            "current_period_end": event.current_period_end,
        },
    )
    return sub
