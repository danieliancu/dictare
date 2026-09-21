from .base import *  # noqa: F403
from .base import env

DEBUG = env.bool("DEBUG", default=True)
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1", "[::1]"])
TTS_BROWSER_FALLBACK = env.bool("TTS_BROWSER_FALLBACK", default=True)
