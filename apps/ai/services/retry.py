"""Bounded retries with exponential backoff for OpenAI calls (TTS, transcription, evaluator)."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import TypeVar

logger = logging.getLogger(__name__)
T = TypeVar("T")

DELAYS = (1, 2, 4, 8, 16)  # seconds between attempts; 6 attempts in total


def is_transient(exc: Exception) -> bool:
    """Rate limits, timeouts, connection problems and 5xx are worth retrying."""
    import openai

    from .tts import TTSError

    if isinstance(exc, TTSError):
        return exc.transient
    if isinstance(exc, openai.RateLimitError | openai.APITimeoutError | openai.APIConnectionError):
        return True
    if isinstance(exc, openai.APIStatusError):
        return exc.status_code >= 500
    return False


def with_retries(call: Callable[[], T], *, label: str = "", sleep=time.sleep) -> T:
    """Run `call`, retrying transient failures; authentication/bad requests fail at once."""
    for attempt, delay in enumerate((*DELAYS, None), start=1):
        try:
            return call()
        except Exception as exc:
            if delay is None or not is_transient(exc):
                raise
            logger.info("Retry %s after %s (attempt %s)", label, type(exc).__name__, attempt)
            sleep(delay)
    raise RuntimeError("unreachable")  # pragma: no cover
