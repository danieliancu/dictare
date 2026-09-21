from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403
from .base import SECRET_KEY, env

DEBUG = False
if SECRET_KEY.startswith("insecure-") or len(SECRET_KEY) < 40:
    raise ImproperlyConfigured("Set a strong SECRET_KEY (≥ 40 chars) in the environment.")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=True)
SECURE_REDIRECT_EXEMPT = [r"^health/$"]
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=60 * 60 * 24 * 365)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
# Production serves real, pre-generated, QA-approved audio only.
TTS_BROWSER_FALLBACK = False
TTS_GENERATE_ON_REQUEST = False
TTS_REQUIRE_APPROVAL = env.bool("TTS_REQUIRE_APPROVAL", default=True)
