from .base import *  # noqa: F403

DEBUG = False
SECRET_KEY = "test-secret-key-not-for-production"
ALLOWED_HOSTS = ["testserver", "localhost", "127.0.0.1"]
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.InMemoryStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
TTS_PROVIDER = "mock"
TTS_BROWSER_FALLBACK = False
TTS_REQUIRE_APPROVAL = False
TTS_GENERATE_ON_REQUEST = True  # mock only
TTS_ENGINE_VERSION = "2"
OPENAI_API_KEY = ""
LOGGING["root"]["level"] = "WARNING"  # noqa: F405
