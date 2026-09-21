"""Text-to-speech service layer.

Business code calls `get_or_create_variant(phrase, level, accent)` (or the lower-level
`generate_speech`). Providers are pluggable and selected with the TTS_PROVIDER setting:

* ``mock``   – offline, deterministic WAV placeholder (no API key, used in dev and tests)
* ``openai`` – OpenAI speech API with per-level style instructions

Generated audio is cached: a variant is identified by a hash of everything that affects the
output (text, accent, voice, level/style, speed, model, provider, engine version), so the same
file is never generated twice.
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

logger = logging.getLogger(__name__)


class TTSUnavailable(Exception):
    """Raised when audio cannot be generated (provider misconfigured or failing)."""


@dataclass(frozen=True)
class LevelStyle:
    speed: float
    instructions: str


# Levels differ in delivery, not only in speed.
LEVEL_STYLES: dict[str, LevelStyle] = {
    "clear": LevelStyle(
        speed=0.92,
        instructions=(
            "Speak clearly and carefully, slightly slower than normal conversation, "
            "articulating each word while still sounding natural and friendly."
        ),
    ),
    "natural": LevelStyle(
        speed=1.0,
        instructions=(
            "Speak at a normal conversational pace, like a native speaker chatting with a "
            "friend. Use natural connected speech: weak forms of function words, linking "
            "between words and relaxed rhythm. Stress only the important words."
        ),
    ),
    "fast": LevelStyle(
        speed=1.12,
        instructions=(
            "Speak quickly and casually, like a native speaker in a hurry. Use strong "
            "connected speech: reduced function words, elision, glottal stops where natural "
            "and everyday reductions. Keep it realistic, not exaggerated."
        ),
    ),
}

DEFAULT_ACCENT_INSTRUCTIONS = "Use a Standard Southern British English accent."


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
        style = LEVEL_STYLES.get(self.style)
        return " ".join(
            filter(None, [self.accent_instructions, style.instructions if style else ""])
        )


@dataclass
class SpeechResult:
    audio: bytes
    extension: str
    duration_ms: int
    provider: str
    settings: dict = field(default_factory=dict)


class TTSProvider(Protocol):
    name: str
    model: str

    def synthesize(self, request: SpeechRequest) -> SpeechResult: ...


class MockProvider:
    """Deterministic WAV placeholder: one soft 'syllable' pulse per word, no real speech.

    Lets the whole flow (player, waveform, timing, caching) run without any API key.
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
            provider=self.name,
            settings={"model": self.model, "speed": request.speed, "placeholder": True},
        )


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise TTSUnavailable("OPENAI_API_KEY is not configured.")
        self.api_key = api_key
        self.model = model

    def synthesize(self, request: SpeechRequest) -> SpeechResult:
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key, timeout=30)
            response = client.audio.speech.create(
                model=self.model,
                voice=request.voice,
                input=request.text,
                instructions=request.instructions,
                speed=request.speed,
                response_format="mp3",
            )
            audio = response.read()
        except Exception as exc:  # network/auth/quota errors all mean "unavailable"
            logger.warning("OpenAI TTS failed: %s", exc)
            raise TTSUnavailable(str(exc)) from exc
        return SpeechResult(
            audio=audio,
            extension="mp3",
            duration_ms=_mp3_duration_ms(audio),
            provider=self.name,
            settings={
                "model": self.model,
                "voice": request.voice,
                "speed": request.speed,
                "instructions": request.instructions,
            },
        )


def _mp3_duration_ms(audio: bytes, bitrate_kbps: int = 128) -> int:
    """Rough estimate for constant-bitrate MP3; the player reads the exact duration."""
    return round(len(audio) * 8 / bitrate_kbps)


def get_provider(name: str | None = None) -> TTSProvider:
    name = name or settings.TTS_PROVIDER
    if name == "mock":
        return MockProvider()
    if name == "openai":
        return OpenAIProvider(settings.OPENAI_API_KEY, settings.TTS_MODEL)
    raise TTSUnavailable(f"Unknown TTS provider: {name}")


def cache_key(request: SpeechRequest, provider: str, model: str) -> str:
    parts = [
        request.text.strip(),
        request.accent,
        request.voice,
        request.style,
        f"{request.speed:.2f}",
        provider,
        model,
        settings.TTS_ENGINE_VERSION,
    ]
    return hashlib.sha256("\x1f".join(parts).encode()).hexdigest()


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


def build_request(phrase, level: str, accent, voice: str | None = None) -> SpeechRequest:
    style = LEVEL_STYLES[level]
    return SpeechRequest(
        text=phrase.text,
        accent=accent.code,
        voice=voice or settings.TTS_VOICE,
        style=level,
        speed=style.speed,
        accent_instructions=accent.tts_instructions or DEFAULT_ACCENT_INSTRUCTIONS,
    )


def get_or_create_variant(phrase, level: str, accent, provider: str | None = None):
    """Return the cached AudioVariant, generating and storing audio only when missing.

    Human recordings uploaded in the admin (provider="human") always win.
    """
    from apps.listening.models import AudioVariant

    existing = (
        AudioVariant.objects.filter(phrase=phrase, level=level, accent=accent)
        .exclude(audio_file="")
        .order_by("-generated_at")
    )
    human = existing.filter(provider="human").first()
    if human:
        return human

    tts = get_provider(provider)
    request = build_request(phrase, level, accent)
    key = cache_key(request, tts.name, tts.model)
    cached = AudioVariant.objects.filter(cache_key=key).first()
    if cached and cached.audio_file and cached.audio_file.storage.exists(cached.audio_file.name):
        return cached

    result = tts.synthesize(request)
    variant = cached or AudioVariant(
        phrase=phrase, level=level, accent=accent, voice=request.voice, cache_key=key
    )
    variant.provider = result.provider
    variant.duration_ms = result.duration_ms
    variant.generation_settings = result.settings
    variant.audio_file.save(f"{key}.{result.extension}", ContentFile(result.audio), save=False)
    try:
        with transaction.atomic():
            # A different engine version/model leaves an older row for the same voice.
            AudioVariant.objects.filter(
                phrase=phrase, level=level, accent=accent, voice=request.voice
            ).exclude(cache_key=key).delete()
            variant.save()
    except IntegrityError:  # generated concurrently by another request
        return AudioVariant.objects.get(cache_key=key)
    logger.info("Generated %s audio for phrase %s (%s)", result.provider, phrase.pk, level)
    return variant
