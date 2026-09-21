import io
import wave

import pytest
from django.test import override_settings

from apps.ai.services import tts
from apps.listening.models import AudioVariant, Level


def request(**overrides):
    base = dict(text="Shall we head off?", accent="ssb", voice="fable", style="clear", speed=0.92)
    base.update(overrides)
    return tts.SpeechRequest(**base)


class TestCacheKey:
    def test_stable(self):
        assert tts.cache_key(request(), "mock", "m1") == tts.cache_key(request(), "mock", "m1")

    @pytest.mark.parametrize(
        "change",
        [
            {"text": "Shall we go?"},
            {"voice": "nova"},
            {"style": "fast"},
            {"accent": "modern-rp"},
            {"speed": 1.1},
        ],
    )
    def test_changes_with_inputs(self, change):
        assert tts.cache_key(request(), "mock", "m1") != tts.cache_key(
            request(**change), "mock", "m1"
        )

    def test_changes_with_provider_model_and_engine_version(self):
        base = tts.cache_key(request(), "mock", "m1")
        assert base != tts.cache_key(request(), "openai", "m1")
        assert base != tts.cache_key(request(), "mock", "m2")
        with override_settings(TTS_ENGINE_VERSION="2"):
            assert base != tts.cache_key(request(), "mock", "m1")


def test_mock_provider_returns_valid_wav():
    result = tts.MockProvider().synthesize(request())
    with wave.open(io.BytesIO(result.audio)) as wav:
        assert wav.getnchannels() == 1
        assert wav.getnframes() > 0
    assert result.duration_ms > 500


def test_levels_differ_by_more_than_speed():
    assert tts.LEVEL_STYLES["clear"].instructions != tts.LEVEL_STYLES["fast"].instructions
    assert tts.LEVEL_STYLES["clear"].speed < tts.LEVEL_STYLES["fast"].speed


def test_openai_without_key_is_unavailable():
    with override_settings(OPENAI_API_KEY=""), pytest.raises(tts.TTSUnavailable):
        tts.get_provider("openai")


@pytest.mark.django_db
def test_variant_is_cached_not_regenerated(phrases, accent, monkeypatch):
    calls = []
    original = tts.MockProvider.synthesize

    def counting(self, req):
        calls.append(req)
        return original(self, req)

    monkeypatch.setattr(tts.MockProvider, "synthesize", counting)
    first = tts.get_or_create_variant(phrases[0], Level.CLEAR, accent)
    second = tts.get_or_create_variant(phrases[0], Level.CLEAR, accent)
    assert first.pk == second.pk
    assert len(calls) == 1
    other_level = tts.get_or_create_variant(phrases[0], Level.FAST, accent)
    assert other_level.pk != first.pk
    assert AudioVariant.objects.filter(phrase=phrases[0]).count() == 2
