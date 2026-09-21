"""Text-to-speech: generation of audio variants (the *write* path).

Generation only happens in management commands and the admin, never inside a learner's
request (see `apps.listening.services.audio.get_audio_variant` for the read path).

Providers are pluggable and selected with TTS_PROVIDER:

* ``mock``   – offline, deterministic WAV placeholder (no API key; dev and tests)
* ``openai`` – OpenAI Speech API; model and voice from TTS_MODEL / TTS_VOICE

Every generated file is cached under a hash of everything that shapes the audio — text,
provider, model, voice, accent, the full instructions sent, level, speed and
TTS_ENGINE_VERSION — so a prompt change never silently reuses an old recording.
New variants start with ``qa_status=pending``: a successful API call is not proof that the
audio is pedagogically correct.
"""

from __future__ import annotations

import hashlib
import io
import logging
import math
import struct
import wave
from dataclasses import dataclass, field
from typing import Protocol

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction

from .audio_meta import audio_duration_ms, looks_like_mp3

logger = logging.getLogger(__name__)


# --- errors ---------------------------------------------------------------------------------


class TTSError(Exception):
    """Base class: audio could not be generated."""

    kind = "error"
    transient = False  # worth retrying with backoff?

    def __init__(self, message: str = "", *, transient: bool | None = None):
        super().__init__(message)
        if transient is not None:
            self.transient = transient


class TTSUnavailable(TTSError):
    """Provider misconfigured, unknown, or the service is unreachable."""

    kind = "unavailable"


class TTSAuthError(TTSError):
    kind = "authentication"


class TTSRateLimited(TTSError):
    kind = "rate_limit"
    transient = True


class TTSTimeout(TTSError):
    kind = "timeout"
    transient = True


class TTSBadResponse(TTSError):
    """Empty or malformed audio returned by the provider."""

    kind = "bad_response"


# --- delivery per level -----------------------------------------------------------------------


@dataclass(frozen=True)
class LevelStyle:
    speed: float
    instructions: str


# Levels differ first by *delivery*; speed only nudges. Keep speeds moderate: a sped-up
# recording sounds artificial, which is the opposite of what the product trains.
LEVEL_STYLES: dict[str, LevelStyle] = {
    "clear": LevelStyle(
        speed=0.95,
        instructions=(
            "Deliver this line slightly slower than ordinary conversation, with clear "
            "articulation, so a learner can follow every word. Keep a natural British rhythm "
            "and intonation: do not pronounce the words in isolation, do not exaggerate or "
            "over-enunciate, and do not sound like a language textbook. Keep contractions "
            "natural. Use only light connected speech and avoid heavy reductions."
        ),
    ),
    "natural": LevelStyle(
        speed=1.0,
        instructions=(
            "Deliver this line at a normal conversational speed, as a native speaker would say "
            "it to a friend or colleague. Use natural rhythm and intonation, connected speech, "
            "linking between words, contractions, and the weak forms of function words where a "
            "native speaker would normally use them. Stress only the words that carry meaning. "
            "No artificial over-enunciation; it should sound like real conversation, not "
            "educational audio."
        ),
    ),
    "fast": LevelStyle(
        speed=1.08,
        instructions=(
            "Deliver this line fluently and somewhat faster than ordinary speech, like a "
            "relaxed native speaker in casual conversation. Use natural connected speech and "
            "realistic reductions: weak function words, elision and assimilation where they "
            "would naturally occur, and glottal stops only where they are natural for this "
            "accent and register. Keep a natural rhythm. Do not force or exaggerate any "
            "feature and do not caricature the accent."
        ),
    ),
}

DEFAULT_ACCENT_INSTRUCTIONS = (
    "Speak contemporary Standard Southern British English with natural, modern British "
    "pronunciation."
)


@dataclass(frozen=True)
class SpeechRequest:
    text: str
    accent: str
    voice: str
    style: str  # listening level: clear / natural / fast
    speed: float
    accent_instructions: str = DEFAULT_ACCENT_INSTRUCTIONS

    @property
    def instructions(self) -> str:
        """The exact instruction text sent to the provider (part of the cache key)."""
        style = LEVEL_STYLES.get(self.style)
        parts = [self.accent_instructions, style.instructions if style else ""]
        return " ".join(p.strip() for p in parts if p and p.strip())


@dataclass
class SpeechResult:
    audio: bytes
    extension: str
    duration_ms: int
    duration_measured: bool
    provider: str
    model: str
    settings: dict = field(default_factory=dict)


# --- providers ------------------------------------------------------------------------------


class TTSProvider(Protocol):
    name: str
    model: str

    def synthesize(self, request: SpeechRequest) -> SpeechResult: ...


class MockProvider:
    """Deterministic WAV placeholder: one soft pulse per word, no real speech.

    Lets the whole flow (player, waveform, caching, QA) run without an API key.
    Mock audio can never be approved for learners.
    """

    name = "mock"
    model = "mock-v1"
    sample_rate = 8000

    def synthesize(self, request: SpeechRequest) -> SpeechResult:
        words = request.text.split() or ["…"]
        word_s = 0.34 / max(request.speed, 0.5)
        total = int(self.sample_rate * (0.25 + len(words) * word_s + 0.25))
        seed = int(hashlib.sha1(request.text.encode()).hexdigest()[:8], 16)
        frames = bytearray()
        for n in range(total):
            t = n / self.sample_rate - 0.25
            idx = int(t / word_s) if t >= 0 else -1
            amp = 0.0
            if 0 <= idx < len(words):
                phase = (t - idx * word_s) / word_s
                loud = 0.45 + 0.4 * (((seed >> (idx % 24)) & 7) / 7)
                amp = loud * math.sin(math.pi * min(phase / 0.85, 1.0)) ** 2
            pitch = 140 + 25 * math.sin(n / 2600)
            sample = amp * 0.5 * math.sin(2 * math.pi * pitch * n / self.sample_rate)
            frames += struct.pack("<h", int(sample * 32767))
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(self.sample_rate)
            wav.writeframes(bytes(frames))
        return SpeechResult(
            audio=buf.getvalue(),
            extension="wav",
            duration_ms=round(1000 * total / self.sample_rate),
            duration_measured=True,
            provider=self.name,
            model=self.model,
            settings={"speed": request.speed, "placeholder": True},
        )


class OpenAIProvider:
    """OpenAI Speech API. The API key comes only from settings/env and is never logged."""

    name = "openai"

    def __init__(self, api_key: str, model: str, timeout: float = 60.0):
        if not api_key:
            raise TTSUnavailable("OPENAI_API_KEY is not set in the environment.")
        self._api_key = api_key
        self.model = model
        self.timeout = timeout

    def _client(self):
        from openai import OpenAI

        return OpenAI(api_key=self._api_key, timeout=self.timeout, max_retries=2)

    def synthesize(self, request: SpeechRequest) -> SpeechResult:
        import openai

        try:
            response = self._client().audio.speech.create(
                model=self.model,
                voice=request.voice,
                input=request.text,
                instructions=request.instructions,
                speed=request.speed,
                response_format="mp3",
            )
            audio = response.read()
        except openai.AuthenticationError as exc:
            # The SDK message contains a masked key: never propagate or log it.
            raise TTSAuthError("OpenAI rejected the API key (check OPENAI_API_KEY).") from exc
        except openai.PermissionDeniedError as exc:
            raise TTSAuthError("OpenAI denied access to this model or voice.") from exc
        except openai.RateLimitError as exc:
            raise TTSRateLimited("OpenAI rate limit or quota exceeded.") from exc
        except openai.APITimeoutError as exc:
            raise TTSTimeout(f"OpenAI did not answer within {self.timeout:.0f}s.") from exc
        except openai.APIConnectionError as exc:
            raise TTSUnavailable("Could not reach the OpenAI API.", transient=True) from exc
        except openai.BadRequestError as exc:
            raise TTSBadResponse(f"OpenAI refused the request: {exc.message}") from exc
        except openai.APIStatusError as exc:
            raise TTSUnavailable(
                f"OpenAI service error (HTTP {exc.status_code}).",
                transient=exc.status_code >= 500,
            ) from exc

        if not audio:
            raise TTSBadResponse("OpenAI returned empty audio.")
        if not looks_like_mp3(audio):
            raise TTSBadResponse("OpenAI returned data that is not an MP3 file.")
        duration = audio_duration_ms(audio, "mp3")
        return SpeechResult(
            audio=audio,
            extension="mp3",
            duration_ms=duration or 0,
            duration_measured=duration is not None,
            provider=self.name,
            model=self.model,
            settings={"voice": request.voice, "speed": request.speed, "format": "mp3"},
        )


PROVIDERS = {
    "mock": lambda: MockProvider(),
    "openai": lambda: OpenAIProvider(settings.OPENAI_API_KEY, settings.TTS_MODEL),
}


def get_provider(name: str | None = None) -> TTSProvider:
    name = name or settings.TTS_PROVIDER
    factory = PROVIDERS.get(name)
    if factory is None:
        raise TTSUnavailable(f"Unknown TTS provider: {name}")
    return factory()


def provider_identity(name: str | None = None) -> tuple[str, str]:
    """(provider name, model) without needing credentials — for dry runs and planning."""
    name = name or settings.TTS_PROVIDER
    if name == "openai":
        return "openai", settings.TTS_MODEL
    if name == "mock":
        return "mock", MockProvider.model
    raise TTSUnavailable(f"Unknown TTS provider: {name}")


# --- cache key & requests ---------------------------------------------------------------------


def cache_key(request: SpeechRequest, provider: str, model: str) -> str:
    """Hash of everything that influences the generated audio."""
    parts = [
        request.text.strip(),
        provider,
        model,
        request.voice,
        request.accent,
        request.instructions,
        request.style,
        f"{request.speed:.3f}",
        str(settings.TTS_ENGINE_VERSION),
    ]
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


def build_request(text: str, level: str, accent, voice: str | None = None) -> SpeechRequest:
    style = LEVEL_STYLES[level]
    return SpeechRequest(
        text=text,
        accent=accent.code,
        voice=voice or settings.TTS_VOICE,
        style=level,
        speed=style.speed,
        accent_instructions=accent.tts_instructions or DEFAULT_ACCENT_INSTRUCTIONS,
    )


def generate_speech(
    text: str,
    accent: str,
    speed: float,
    style: str,
    voice: str,
    provider: str | None = None,
    accent_instructions: str = DEFAULT_ACCENT_INSTRUCTIONS,
) -> SpeechResult:
    request = SpeechRequest(text, accent, voice, style, speed, accent_instructions)
    return get_provider(provider).synthesize(request)


# --- audio variants (write path) ----------------------------------------------------------------


def planned_key(phrase, level: str, accent, voice: str | None = None, provider=None) -> str:
    """Cache key a generation would use, without calling the provider."""
    name, model = provider_identity(provider)
    return cache_key(build_request(phrase.text, level, accent, voice), name, model)


def cached_variant(key: str):
    from apps.listening.models import AudioVariant

    variant = AudioVariant.objects.filter(cache_key=key).first()
    if (
        variant
        and variant.audio_file
        and variant.audio_file.storage.exists(variant.audio_file.name)
    ):
        return variant
    return None


def generate_variant(phrase, level: str, accent, voice: str | None = None, provider=None):
    """Return the cached variant for these exact settings, generating it only if missing.

    Never deletes other variants (older engine versions or voices keep their QA state).
    """
    from apps.listening.models import AudioVariant
    from apps.listening.services.patterns import create_expected_checks

    tts = get_provider(provider)
    request = build_request(phrase.text, level, accent, voice)
    key = cache_key(request, tts.name, tts.model)
    existing = cached_variant(key)
    if existing is not None:
        return existing

    result = tts.synthesize(request)
    variant = AudioVariant.objects.filter(cache_key=key).first() or AudioVariant(
        phrase=phrase, level=level, accent=accent, voice=request.voice, cache_key=key
    )
    variant.provider = result.provider
    variant.model = result.model
    variant.instructions = request.instructions
    variant.speed = request.speed
    variant.engine_version = str(settings.TTS_ENGINE_VERSION)
    variant.duration_ms = result.duration_ms
    variant.duration_measured = result.duration_measured
    variant.generation_settings = result.settings
    variant.qa_status = AudioVariant.QAStatus.PENDING
    variant.audio_file.save(f"{key}.{result.extension}", ContentFile(result.audio), save=False)
    try:
        with transaction.atomic():
            variant.save()
            create_expected_checks(variant)
    except IntegrityError:  # generated concurrently elsewhere
        return AudioVariant.objects.get(cache_key=key)
    logger.debug("Generated %s audio for phrase %s (%s)", result.provider, phrase.pk, level)
    return variant


# Backwards-compatible name used by older code paths.
get_or_create_variant = generate_variant
