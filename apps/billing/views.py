from django.shortcuts import render

from .models import Plan
from .providers import get_payment_provider
from .services.entitlements import get_entitlements


def pricing(request):
    provider = get_payment_provider()
    return render(
        request,
        "pages/billing/pricing.html",
        {
            "plans": Plan.objects.all(),
            "entitlements": get_entitlements(request.user),
            "checkout_available": provider.is_configured(),
        },
    )
