"""Automatic audio QA: technical, transcript, confidence, phonetics, decisions, cache, retry.

No real OpenAI calls: transcription and the audio evaluator are faked.
"""

from io import StringIO

import httpx
import openai
import pytest
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management import CommandError, call_command
from django.test import override_settings

from apps.ai.services import audio_qa, retry, tts
from apps.listening.models import (
    AudioQAResult,
    AudioVariant,
    AudioVariantPattern,
    Level,
)
from apps.listening.services.audio import get_audio_variant

QA = AudioVariant.QAStatus
V = AudioVariantPattern.Verification
D = AudioQAResult.Decision
_REQ = httpx.Request("POST", "https://api.openai.com/v1/audio/transcriptions")


def fake_mp3(seconds: float) -> bytes:
    frame = bytes([0xFF, 0xFB, 0x90, 0x64]) + b"\x00" * 413
    return frame * max(1, round(seconds * 44100 / 1152))


def expected_seconds(phrase, level):
    words = len(phrase.text.split())
    return audio_qa.expected_duration_ms(words, level, tts.LEVEL_STYLES[level].speed) / 1000


def real_variant(phrase, accent, *, level=Level.CLEAR, voice="marin", audio=None):
    v = AudioVariant(
        phrase=phrase,
        level=level,
        accent=accent,
        voice=voice,
        provider="openai",
        model="gpt-4o-mini-tts",
        engine_version="2",
        instructions="Speak British English.",
        speed=tts.LEVEL_STYLES[level].speed,
        generation_settings={"voice": voice},
        duration_measured=True,
        qa_status=QA.PENDING,
    )
    data = audio if audio is not None else fake_mp3(expected_seconds(phrase, level))
    v.duration_ms = (audio_qa.audio_duration_ms(data, "mp3") or 0) if audio is None else 0
    v.audio_file.save(f"{voice}-{level}-{phrase.pk}.mp3", ContentFile(data), save=False)
    v.save()
    return v


class FakeTranscriber:
    model = "fake-transcribe"

    def __init__(self, text=None, probs=(0.99, 0.98, 0.99, 0.97, 0.99), errors=()):
        self.text, self.probs, self.errors, self.calls = text, list(probs), list(errors), 0

    def transcribe(self, audio, filename):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        text = self.text
        if text is None:  # say exactly the phrase of this recording
            text = AudioVariant.objects.get(pk=filename.split(".")[0]).phrase.text
        return audio_qa.Transcription(text, self.probs)


class FakeEvaluator:
    model = "fake-evaluator"

    def __init__(
        self, accent=("british_compatible", 0.95), verdict=("present", 0.95), per_fragment=None
    ):
        self.accent, self.verdict, self.per_fragment, self.calls = (
            accent,
            verdict,
            per_fragment or {},
            0,
        )

    def evaluate(self, audio, transcript, level, patterns):
        self.calls += 1
        verdicts = {}
        for p in patterns:
            verification, confidence = self.per_fragment.get(p["words"], self.verdict)
            verdicts[p["id"]] = audio_qa.PatternVerdict(verification, confidence, "/x/", "ok")
        return audio_qa.Evaluation(self.accent[0], self.accent[1], verdicts)


@pytest.fixture
def phrase(phrases):
    return phrases[0]  # "Would you like to go?" — "Would you" + "to" expected at clear


def run(variant, transcriber=None, evaluator=None, **kw):
    return audio_qa.run_qa(
        variant, transcriber or FakeTranscriber(), evaluator or FakeEvaluator(), **kw
    )


# --- technical --------------------------------------------------------------------------------


@pytest.mark.django_db
class TestTechnical:
    def test_missing_file_is_rejected_without_api_calls(self, phrase, accent):
        v = real_variant(phrase, accent)
        v.audio_file.storage.delete(v.audio_file.name)
        t, e = FakeTranscriber(), FakeEvaluator()
        outcome = run(v, t, e)
        v.refresh_from_db()
        assert outcome.result.decision == D.REJECTED and v.qa_status == QA.REJECTED
        assert t.calls == 0 and e.calls == 0

    def test_corrupt_mp3_is_rejected(self, phrase, accent):
        v = real_variant(phrase, accent, audio=b"<html>error page</html>" * 200)
        t = FakeTranscriber()
        assert run(v, t).result.decision == D.REJECTED
        assert t.calls == 0

    def test_valid_mp3_continues_to_transcription(self, phrase, accent):
        v = real_variant(phrase, accent)
        t = FakeTranscriber()
        run(v, t)
        assert t.calls == 1


# --- transcript & confidence ---------------------------------------------------------------------


class TestSimilarity:
    def test_exact_and_formatting_are_100(self):
        assert (
            audio_qa.transcript_similarity("Would you like to go?", "Would you like to go?") == 100
        )
        assert (
            audio_qa.transcript_similarity("Would you like to go?", "would you like to go") == 100
        )
        assert audio_qa.transcript_similarity("I'll sort it out.", "I will sort it out") == 100

    def test_missing_extra_and_wrong_words_count(self):
        assert audio_qa.transcript_similarity("Would you like to go?", "Would you like go") == 80
        assert audio_qa.transcript_similarity("Shall we go?", "Shall we go now") == 75
        assert audio_qa.transcript_similarity("Shall we go?", "Tell me more") < 50

    def test_confidence_labels(self):
        assert audio_qa.transcription_confidence([0.99, 0.95, 0.97])[1] == "high"
        assert audio_qa.transcription_confidence([0.9, 0.7, 0.8])[1] == "medium"
        assert audio_qa.transcription_confidence([0.4, 0.5])[1] == "low"
        assert audio_qa.transcription_confidence(None) == (None, "")


@pytest.mark.django_db
class TestTranscriptDecisions:
    def test_punctuation_difference_still_approves(self, phrase, accent):
        v = real_variant(phrase, accent)
        outcome = run(v, FakeTranscriber(text="would you like to go"))
        assert outcome.result.decision == D.APPROVED

    def test_missing_word_is_rejected_with_score(self, phrase, accent):
        v = real_variant(phrase, accent)
        e = FakeEvaluator()
        r = run(v, FakeTranscriber(text="Would you like go?"), e).result
        assert r.transcript_similarity == 80 and r.decision == D.REJECTED
        assert e.calls == 0  # no paid evaluator call after a hard failure

    def test_wrong_sentence_is_rejected(self, phrase, accent):
        v = real_variant(phrase, accent)
        assert run(v, FakeTranscriber(text="Shall we head off?")).result.decision == D.REJECTED

    def test_low_confidence_needs_review(self, phrase, accent):
        v = real_variant(phrase, accent)
        r = run(v, FakeTranscriber(probs=(0.5, 0.6, 0.5))).result
        v.refresh_from_db()
        assert r.decision == D.NEEDS_REVIEW and v.qa_status == QA.NEEDS_REVIEW


# --- phonetics, accent, final decision --------------------------------------------------------


@pytest.mark.django_db
class TestPatternsAndDecision:
    def test_all_pass_is_approved_automatically(self, phrase, accent):
        v = real_variant(phrase, accent)
        r = run(v).result
        v.refresh_from_db()
        assert r.decision == D.APPROVED and r.overall_score >= 90
        assert v.qa_status == QA.APPROVED
        assert v.approval_source == AudioVariant.ApprovalSource.AUTOMATIC
        assert v.reviewed_by is None
        checks = list(v.pattern_checks.all())
        assert checks and all(
            c.verification == V.PRESENT and c.source == "automatic" for c in checks
        )

    def test_confident_absent_is_recorded_and_still_approvable(self, phrase, accent):
        v = real_variant(phrase, accent)
        e = FakeEvaluator(per_fragment={"to": ("absent", 0.9)})
        assert run(v, evaluator=e).result.decision == D.APPROVED
        assert v.pattern_checks.get(phrase_pattern__fragment="to").verification == V.ABSENT

    def test_uncertain_pattern_stays_unverified_and_blocks_approval(self, phrase, accent):
        v = real_variant(phrase, accent)
        e = FakeEvaluator(per_fragment={"Would you": ("uncertain", 0.9)})
        r = run(v, evaluator=e).result
        assert r.decision == D.NEEDS_REVIEW
        check = v.pattern_checks.get(phrase_pattern__fragment="Would you")
        assert check.verification == V.UNVERIFIED

    def test_low_confidence_present_is_not_trusted(self, phrase, accent):
        v = real_variant(phrase, accent)
        r = run(v, evaluator=FakeEvaluator(verdict=("present", 0.6))).result
        assert r.decision == D.NEEDS_REVIEW
        assert not v.pattern_checks.exclude(verification=V.UNVERIFIED).exists()

    def test_human_verification_is_never_overwritten(self, phrase, accent):
        v = real_variant(phrase, accent)
        pp = phrase.phrase_patterns.get(fragment="to")
        AudioVariantPattern.objects.create(
            audio_variant=v, phrase_pattern=pp, verification=V.ABSENT, source="human"
        )
        run(v, evaluator=FakeEvaluator(verdict=("present", 0.99)))
        assert v.pattern_checks.get(phrase_pattern=pp).verification == V.ABSENT

    def test_clearly_non_british_is_rejected(self, phrase, accent):
        v = real_variant(phrase, accent)
        r = run(v, evaluator=FakeEvaluator(accent=("clearly_non_british", 0.9))).result
        assert r.decision == D.REJECTED

    def test_uncertain_accent_needs_review(self, phrase, accent):
        v = real_variant(phrase, accent)
        r = run(v, evaluator=FakeEvaluator(accent=("uncertain", 0.9))).result
        assert r.decision == D.NEEDS_REVIEW and r.accent_pass is None

    def test_no_evaluator_never_auto_approves(self, phrase, accent):
        v = real_variant(phrase, accent)
        r = audio_qa.run_qa(v, FakeTranscriber(), None).result
        assert r.decision == D.NEEDS_REVIEW and r.accent_pass is None

    def test_malformed_evaluator_output_is_not_a_pass(self):
        with pytest.raises(audio_qa.EvaluationFormatError):
            audio_qa.parse_evaluation("I think it sounds fine", [{"id": 1}])
        parsed = audio_qa.parse_evaluation(
            '{"accent": {"label": "posh", "confidence": 3}, "patterns": '
            '[{"id": 1, "verification": "maybe", "confidence": 0.9}, {"id": 99}]}',
            [{"id": 1}],
        )
        assert parsed.accent_label == "uncertain" and parsed.accent_confidence == 1.0
        assert parsed.patterns[1].verification == "uncertain" and 99 not in parsed.patterns

    def test_human_decision_is_never_overridden(self, phrase, accent):
        v = real_variant(phrase, accent)
        v.qa_status, v.approval_source = QA.REJECTED, "human"
        v.save()
        run(v)
        v.refresh_from_db()
        assert v.qa_status == QA.REJECTED

    def test_delivery_check(self):
        assert audio_qa.delivery_check({"clear": 3000, "natural": 2600, "fast": 2200}, 6) is True
        assert audio_qa.delivery_check({"clear": 3000, "natural": 2990, "fast": 2980}, 6) is False
        assert audio_qa.delivery_check({"clear": 2000, "natural": 2600, "fast": 3000}, 6) is False
        assert audio_qa.delivery_check({"clear": 3000}, 6) is None

    def test_duration_windows(self):
        assert audio_qa.duration_check(3000, 5, "clear", 0.95) == "pass"
        assert audio_qa.duration_check(1200, 5, "clear", 0.95) == "review"
        assert audio_qa.duration_check(100, 5, "clear", 0.95) == "fail"
        assert audio_qa.duration_check(30000, 5, "clear", 0.95) == "fail"

    @override_settings(TTS_REQUIRE_APPROVAL=True)
    def test_needs_review_is_never_served_in_production(self, phrase, accent):
        v = real_variant(phrase, accent)
        run(v, FakeTranscriber(probs=(0.5, 0.5)))
        v.refresh_from_db()
        assert v.qa_status == QA.NEEDS_REVIEW
        assert get_audio_variant(phrase, Level.CLEAR, accent, "marin") is None


# --- cache & retry -------------------------------------------------------------------------------


@pytest.mark.django_db
class TestCacheAndRetry:
    def test_same_audio_and_version_is_not_checked_twice(self, phrase, accent):
        v = real_variant(phrase, accent)
        t, e = FakeTranscriber(), FakeEvaluator()
        first = run(v, t, e)
        second = run(v, t, e)
        assert not first.reused and second.reused
        assert t.calls == 1 and e.calls == settings.AUDIO_QA_EVALUATOR_RUNS
        assert v.audio_sha256 and AudioQAResult.objects.filter(audio_variant=v).count() == 1

    def test_new_qa_version_reruns(self, phrase, accent):
        v = real_variant(phrase, accent)
        t = FakeTranscriber()
        run(v, t)
        with override_settings(AUDIO_QA_VERSION="next"):
            assert not run(v, t).reused
        assert t.calls == 2

    def test_transient_errors_are_retried(self, phrase, accent, monkeypatch):
        monkeypatch.setattr(retry.time, "sleep", lambda s: None)
        v = real_variant(phrase, accent)
        rate = openai.RateLimitError(
            "slow down", response=httpx.Response(429, request=_REQ), body=None
        )
        t = FakeTranscriber(errors=[rate, openai.APITimeoutError(request=_REQ)])
        assert run(v, t).result.decision == D.APPROVED
        assert t.calls == 3

    def test_auth_error_fails_immediately_and_stays_pending(self, phrase, accent, monkeypatch):
        monkeypatch.setattr(retry.time, "sleep", lambda s: pytest.fail("must not retry"))
        v = real_variant(phrase, accent)
        auth = openai.AuthenticationError(
            "bad key", response=httpx.Response(401, request=_REQ), body=None
        )
        t = FakeTranscriber(errors=[auth])
        r = run(v, t).result
        v.refresh_from_db()
        assert r.decision == D.ERROR and v.qa_status == QA.PENDING and t.calls == 1
        assert not run(v, FakeTranscriber()).reused  # errors are not cached: next run retries


# --- commands ------------------------------------------------------------------------------------


class FakeTTS:
    """Stands in for the OpenAI TTS provider: returns MP3 frames with plausible durations."""

    name = "openai"
    model = "gpt-4o-mini-tts"

    def synthesize(self, request):
        words = len(request.text.split())
        seconds = audio_qa.expected_duration_ms(words, request.style, request.speed) / 1000
        data = fake_mp3(seconds)
        return tts.SpeechResult(
            data,
            "mp3",
            audio_qa.audio_duration_ms(data, "mp3"),
            True,
            "openai",
            self.model,
            {"voice": request.voice},
        )


@pytest.fixture
def fakes(monkeypatch, settings):
    settings.OPENAI_API_KEY = "test-key"
    t, e = FakeTranscriber(), FakeEvaluator()
    monkeypatch.setitem(tts.PROVIDERS, "openai", lambda: FakeTTS())
    monkeypatch.setattr(audio_qa, "get_transcriber", lambda: t)
    monkeypatch.setattr(audio_qa, "get_evaluator", lambda: e)
    return t, e


@pytest.mark.django_db
class TestCommands:
    def test_generate_with_auto_qa_approves_good_audio(self, phrases, accent, fakes):
        phrases[0].in_pilot = True
        phrases[0].save()
        out = StringIO()
        call_command(
            "generate_audio",
            "--pilot",
            "--voices",
            "marin",
            "ballad",
            "--real-api",
            "--auto-qa",
            stdout=out,
        )
        text = out.getvalue()
        assert "Possible variants: 6" in text and "Generated now: 6" in text
        assert "Auto-approved: 6" in text and "Needs review: 0" in text
        assert "Marin:\napproved 3" in text and "Ballad:\napproved 3" in text
        assert AudioVariant.objects.filter(qa_status=QA.APPROVED).count() == 6

        rerun = StringIO()
        call_command(
            "generate_audio",
            "--pilot",
            "--voices",
            "marin",
            "ballad",
            "--real-api",
            "--auto-qa",
            stdout=rerun,
        )
        assert "Already cached: 6" in rerun.getvalue()
        assert "QA reused: 6" in rerun.getvalue() and "QA performed now: 0" in rerun.getvalue()

    def test_generate_without_auto_qa_stays_pending(self, phrases, accent, fakes):
        call_command(
            "generate_audio",
            "--voice",
            "marin",
            "--level",
            "clear",
            "--limit",
            "1",
            "--real-api",
            stdout=StringIO(),
        )
        assert AudioVariant.objects.get().qa_status == QA.PENDING
        assert not AudioQAResult.objects.exists()

    def test_auto_qa_requires_real_audio(self, phrases, accent):
        with pytest.raises(CommandError, match="--real-api"):
            call_command("generate_audio", "--provider", "mock", "--auto-qa", stdout=StringIO())

    def test_qa_audio_dry_run_and_run(self, phrases, accent, fakes):
        v = real_variant(phrases[0], accent)
        out = StringIO()
        call_command("qa_audio", "--dry-run", stdout=out)
        assert "1 recordings selected" in out.getvalue() and fakes[0].calls == 0
        out = StringIO()
        call_command("qa_audio", stdout=out)
        v.refresh_from_db()
        assert v.qa_status == QA.APPROVED and "Auto-approved: 1" in out.getvalue()

    def test_qa_audio_skips_mock_and_human(self, phrases, accent, fakes):
        tts.generate_variant(phrases[0], Level.CLEAR, accent, provider="mock")
        human = real_variant(phrases[1], accent)
        human.approval_source = "human"
        human.save()
        out = StringIO()
        call_command("qa_audio", "--all", "--dry-run", stdout=out)
        assert "0 recordings selected" in out.getvalue()


def test_evaluator_runs_must_agree():
    agree = audio_qa.Evaluation(
        "british_compatible", 0.9, {1: audio_qa.PatternVerdict("present", 0.9)}
    )
    other = audio_qa.Evaluation(
        "british_compatible", 0.85, {1: audio_qa.PatternVerdict("present", 0.95)}
    )
    merged = audio_qa.merge_evaluations([agree, other])
    assert merged.accent_label == "british_compatible" and merged.accent_confidence == 0.85
    assert merged.patterns[1].verification == "present" and merged.patterns[1].confidence == 0.9

    split = audio_qa.Evaluation(
        "clearly_non_british", 0.95, {1: audio_qa.PatternVerdict("absent", 0.9)}
    )
    merged = audio_qa.merge_evaluations([agree, split])
    assert merged.accent_label == "uncertain"  # never rejected nor approved on a split vote
    assert merged.patterns[1].verification == "uncertain"
