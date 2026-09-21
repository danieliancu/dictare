"""Payment provider abstraction.

The app never fakes payments. `ManualProvider` covers plans granted by staff in the admin.
A Stripe provider only needs to implement `PaymentProvider` and feed webhook events into
`apps.billing.services.subscriptions.apply_subscription_event`.
"""

from __future__ import annotations

from typing import Protocol

from django.conf import settings


class CheckoutUnavailable(Exception):
    pass


class PaymentProvider(Protocol):
    name: str

    def is_configured(self) -> bool: ...

    def create_checkout_url(self, user, plan, success_url: str, cancel_url: str) -> str: ...


class ManualProvider:
    """No online checkout: Pro is granted by staff (admin → Abonamente)."""

    name = "manual"

    def is_configured(self) -> bool:
        return False

    def create_checkout_url(self, user, plan, success_url: str, cancel_url: str) -> str:
        raise CheckoutUnavailable("Plata online nu este încă disponibilă.")


def get_payment_provider() -> PaymentProvider:
    name = getattr(settings, "PAYMENT_PROVIDER", "manual")
    if name == "manual":
        return ManualProvider()
    raise CheckoutUnavailable(f"Unknown payment provider: {name}")
