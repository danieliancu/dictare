"""Shared settings. Environment-specific overrides live in dev.py / prod.py / test.py."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    CSRF_TRUSTED_ORIGINS=(list, []),
    TTS_BROWSER_FALLBACK=(bool, False),
    CSP_ENFORCE=(bool, False),
)
environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

SECRET_KEY = env("SECRET_KEY", default="insecure-dev-key-change-me")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")
SITE_URL = env("SITE_URL", default="http://localhost:8000").rstrip("/")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django.contrib.sitemaps",
    "django.contrib.humanize",
    "django_htmx",
    "apps.core",
    "apps.accounts",
    "apps.listening",
    "apps.ai",
    "apps.practice",
    "apps.progress",
    "apps.billing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.middleware.SecurityHeadersMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site",
            ],
            "builtins": ["apps.core.templatetags.ui"],
        },
    },
]

DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://dictare:dictare@127.0.0.1:5435/dictare")
}
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

CACHES = {"default": env.cache("CACHE_URL", default="locmemcache://")}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 8},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL = "accounts:login"
LOGIN_REDIRECT_URL = "practice:hub"
LOGOUT_REDIRECT_URL = "core:home"

LANGUAGE_CODE = "ro"
TIME_ZONE = "Europe/London"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(env("MEDIA_ROOT", default=str(BASE_DIR / "media")))
# Serve /media/ from Django (fine for a single host; prefer the web server or object storage).
SERVE_MEDIA = env.bool("SERVE_MEDIA", default=True)

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

EMAIL_CONFIG = env.email("EMAIL_URL", default="consolemail://")
vars().update(EMAIL_CONFIG)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="dictare.ro <salut@dictare.ro>")

SESSION_COOKIE_AGE = 60 * 60 * 24 * 30
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = False  # htmx reads the token from the page, not the cookie
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
CSRF_FAILURE_VIEW = "apps.core.views.error_403_csrf"

FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 6 * 1024 * 1024

# --- Content-Security-Policy (see apps.core.middleware) ----------------------
CSP_ENFORCE = env("CSP_ENFORCE")
CSP_POLICY = {
    "default-src": ["'self'"],
    "script-src": ["'self'"],
    "style-src": ["'self'", "https://fonts.googleapis.com"],
    "style-src-attr": ["'unsafe-inline'"],
    "font-src": ["'self'", "https://fonts.gstatic.com"],
    "img-src": ["'self'", "data:"],
    "media-src": ["'self'", "blob:"],
    "connect-src": ["'self'"],
    "frame-ancestors": ["'none'"],
    "base-uri": ["'self'"],
    "form-action": ["'self'"],
    "object-src": ["'none'"],
}

# --- Text-to-speech ----------------------------------------------------------
TTS_PROVIDER = env("TTS_PROVIDER", default="mock")
TTS_MODEL = env("TTS_MODEL", default="gpt-4o-mini-tts")
TTS_VOICE = env("TTS_VOICE", default="fable")
TTS_ENGINE_VERSION = "1"
TTS_BROWSER_FALLBACK = env("TTS_BROWSER_FALLBACK")
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")

# --- Product rules -----------------------------------------------------------
DAILY_EXERCISES = 10
ANONYMOUS_TRIAL_EXERCISES = 5
ANONYMOUS_SIGNUP_NUDGE_AFTER = 3

# Social profiles (leave empty until the accounts exist; the footer then shows "în curând")
SOCIAL_YOUTUBE_URL = env("SOCIAL_YOUTUBE_URL", default="")
SOCIAL_INSTAGRAM_URL = env("SOCIAL_INSTAGRAM_URL", default="")
SOCIAL_X_URL = env("SOCIAL_X_URL", default="")

LOG_LEVEL = env("LOG_LEVEL", default="INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "plain": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"},
    },
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {
        "django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "apps": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}
