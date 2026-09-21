import io
import wave

import httpx
import openai
import pytest
from django.test import override_settings

from apps.ai.services import tts
from apps.ai.services.audio_meta import mp3_duration_ms
from apps.listening.models import AudioVariant, Level


def request(**overrides):
    base = dict(text="Shall we head off?", accent="ssb", voice="marin", style="clear", speed=0.95)
    base.update(overrides)
    return tts.SpeechRequest(**base)


def fake_mp3(seconds: float = 1.0) -> bytes:
    """Valid MPEG-1 Layer III CBR frames (128 kbps, 44.1 kHz), silent payload."""
    header = bytes([0xFF, 0xFB, 0x90, 0x64])
    frame = header + b"\x00" * (417 - 4)
    frames = round(seconds * 44100 / 1152)
    return frame * frames


class TestCacheKey:
    def test_stable(self):
        assert tts.cache_key(request(), "openai", "m1") == tts.cache_key(request(), "openai", "m1")

    @pytest.mark.parametrize(
        "change",
        [
            {"text": "Shall we go?"},
            {"voice": "ballad"},
            {"style": "fast"},
            {"accent": "modern-rp"},
            {"speed": 1.1},
            {"accent_instructions": "Speak Modern RP."},
        ],
    )
    def test_changes_with_inputs(self, change):
        base = tts.cache_key(request(), "openai", "m1")
        assert base != tts.cache_key(request(**change), "openai", "m1")

    def test_changes_when_level_instructions_change(self, monkeypatch):
        base = tts.cache_key(request(), "openai", "m1")
        changed = tts.LevelStyle(speed=0.95, instructions="A different delivery prompt.")
        monkeypatch.setitem(tts.LEVEL_STYLES, "clear", changed)
        assert tts.cache_key(request(), "openai", "m1") != base

    def test_changes_with_provider_model_and_engine_version(self):
        base = tts.cache_key(request(), "openai", "m1")
        assert base != tts.cache_key(request(), "mock", "m1")
        assert base != tts.cache_key(request(), "openai", "m2")
        with override_settings(TTS_ENGINE_VERSION="99"):
            assert base != tts.cache_key(request(), "openai", "m1")

    def test_instructions_include_accent_and_level(self):
        r = request(style="natural")
        assert r.accent_instructions in r.instructions
        assert tts.LEVEL_STYLES["natural"].instructions in r.instructions


class TestLevels:
    def test_levels_differ_by_delivery_not_only_speed(self):
        texts = {level: style.instructions for level, style in tts.LEVEL_STYLES.items()}
        assert len(set(texts.values())) == 3
        assert "slightly slower" in texts["clear"]
        assert "connected speech" in texts["natural"]
        assert "glottal stops only where" in texts["fast"]

    def test_speeds_stay_moderate(self):
        speeds = [s.speed for s in tts.LEVEL_STYLES.values()]
        assert all(0.9 <= s <= 1.12 for s in speeds)


def test_mock_provider_returns_valid_wav():
    result = tts.MockProvider().synthesize(request())
    with wave.open(io.BytesIO(result.audio)) as wav:
        assert wav.getnframes() > 0
    assert result.duration_measured and result.duration_ms > 500


def test_mp3_duration_is_measured_from_frames():
    assert abs(mp3_duration_ms(fake_mp3(2.0)) - 2000) < 60
    assert mp3_duration_ms(b"not audio at all") is None


class FakeSpeech:
    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self.behaviour, Exception):
            raise self.behaviour
        data = self.behaviour
        return type("Resp", (), {"read": lambda self: data})()


def fake_openai(monkeypatch, behaviour):
    speech = FakeSpeech(behaviour)
    client = type("Client", (), {"audio": type("Audio", (), {"speech": speech})()})()
    monkeypatch.setattr(tts.OpenAIProvider, "_client", lambda self: client)
    return speech


_REQ = httpx.Request("POST", "https://api.openai.com/v1/audio/speech")


def _status_error(cls, code):
    return cls(
        "boom KEY-MATERIAL-should-never-leak",
        response=httpx.Response(code, request=_REQ),
        body=None,
    )


class TestOpenAIProvider:
    def test_no_key_needed_for_tests_and_missing_key_is_unavailable(self):
        with override_settings(OPENAI_API_KEY=""), pytest.raises(tts.TTSUnavailable):
            tts.get_provider("openai")

    @override_settings(OPENAI_API_KEY="test-key", TTS_MODEL="gpt-4o-mini-tts")
    def test_sends_model_voice_instructions_and_measures_duration(self, monkeypatch):
        speech = fake_openai(monkeypatch, fake_mp3(1.5))
        result = tts.get_provider("openai").synthesize(request(style="natural", voice="marin"))
        call = speech.calls[0]
        assert call["model"] == "gpt-4o-mini-tts"
        assert call["voice"] == "marin"
        assert call["instructions"] == request(style="natural").instructions
        assert call["response_format"] == "mp3"
        assert result.duration_measured and abs(result.duration_ms - 1500) < 60

    @pytest.mark.parametrize(
        "error, expected",
        [
            (_status_error(openai.AuthenticationError, 401), tts.TTSAuthError),
            (_status_error(openai.RateLimitError, 429), tts.TTSRateLimited),
            (openai.APITimeoutError(request=_REQ), tts.TTSTimeout),
            (openai.APIConnectionError(request=_REQ), tts.TTSUnavailable),
            (_status_error(openai.InternalServerError, 503), tts.TTSUnavailable),
        ],
    )
    @override_settings(OPENAI_API_KEY="test-key")
    def test_error_mapping(self, monkeypatch, error, expected):
        fake_openai(monkeypatch, error)
        with pytest.raises(expected) as exc:
            tts.get_provider("openai").synthesize(request())
        assert "KEY-MATERIAL" not in str(exc.value)

    @pytest.mark.parametrize("payload", [b"", b"<html>error</html>" * 20])
    @override_settings(OPENAI_API_KEY="test-key")
    def test_empty_or_malformed_audio(self, monkeypatch, payload):
        fake_openai(monkeypatch, payload)
        with pytest.raises(tts.TTSBadResponse):
            tts.get_provider("openai").synthesize(request())


@pytest.mark.django_db
class TestGenerateVariant:
    def test_cached_not_regenerated(self, phrases, accent, monkeypatch):
        calls = []
        original = tts.MockProvider.synthesize

        def counting(self, req):
            calls.append(req)
            return original(self, req)

        monkeypatch.setattr(tts.MockProvider, "synthesize", counting)
        first = tts.generate_variant(phrases[0], Level.CLEAR, accent, provider="mock")
        second = tts.generate_variant(phrases[0], Level.CLEAR, accent, provider="mock")
        assert first.pk == second.pk and len(calls) == 1
        assert first.qa_status == AudioVariant.QAStatus.PENDING
        assert first.instructions and first.engine_version == "2" and first.model == "mock-v1"

    def test_new_engine_version_generates_new_file_and_keeps_old(self, phrases, accent):
        old = tts.generate_variant(phrases[0], Level.CLEAR, accent, provider="mock")
        with override_settings(TTS_ENGINE_VERSION="3"):
            new = tts.generate_variant(phrases[0], Level.CLEAR, accent, provider="mock")
        assert new.pk != old.pk
        assert AudioVariant.objects.filter(pk=old.pk).exists()

    def test_new_voice_generates_new_file(self, phrases, accent):
        a = tts.generate_variant(phrases[0], Level.CLEAR, accent, voice="marin", provider="mock")
        b = tts.generate_variant(phrases[0], Level.CLEAR, accent, voice="cedar", provider="mock")
        assert a.pk != b.pk and b.voice == "cedar"

    @override_settings(OPENAI_API_KEY="test-key")
    def test_openai_variant_via_mocked_api(self, phrases, accent, monkeypatch):
        fake_openai(monkeypatch, fake_mp3(1.0))
        variant = tts.generate_variant(phrases[0], Level.NATURAL, accent, provider="openai")
        assert variant.provider == "openai" and variant.duration_measured
        assert variant.audio_file.name.endswith(".mp3")
        assert variant.qa_status == AudioVariant.QAStatus.PENDING

    def test_expected_pattern_checks_created_per_level(self, phrases, accent):
        phrase = phrases[0]  # "Would you like to go?" with assimilation + weak to
        phrase.phrase_patterns.filter(fragment="Would you").update(expected_from_level="natural")
        clear = tts.generate_variant(phrase, Level.CLEAR, accent, provider="mock")
        natural = tts.generate_variant(phrase, Level.NATURAL, accent, provider="mock")
        assert {c.phrase_pattern.fragment for c in clear.pattern_checks.all()} == {"to"}
        assert {c.phrase_pattern.fragment for c in natural.pattern_checks.all()} == {
            "Would you",
            "to",
        }
