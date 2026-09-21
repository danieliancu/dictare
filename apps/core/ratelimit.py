"""Tiny fixed-window rate limiter on top of Django's cache (use a shared cache in production)."""

from __future__ import annotations

import time
from functools import wraps

from django.core.cache import cache
from django.http import HttpResponse


def client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    return forwarded.split(",")[0].strip() or request.META.get("REMOTE_ADDR", "unknown")


def hit(key: str, limit: int, window: int) -> bool:
    """Register one hit. Returns False when the limit for the current window is exceeded."""
    bucket = f"rl:{key}:{int(time.time() // window)}"
    added = cache.add(bucket, 1, timeout=window + 1)
    if added:
        return True
    try:
        count = cache.incr(bucket)
    except ValueError:
        cache.set(bucket, 1, timeout=window + 1)
        return True
    return count <= limit


def rate_limit(scope: str, limit: int, window: int = 60, methods=("POST",)):
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method in methods:
                who = f"u{request.user.pk}" if request.user.is_authenticated else client_ip(request)
                if not hit(f"{scope}:{who}", limit, window):
                    response = HttpResponse(
                        "Prea multe cereri. Încearcă din nou peste un minut.", status=429
                    )
                    response["Retry-After"] = str(window)
                    return response
            return view(request, *args, **kwargs)

        return wrapped

    return decorator
