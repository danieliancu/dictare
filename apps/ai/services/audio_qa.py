"""Automatic QA of generated recordings.

    generate → technical checks → transcription → duration → accent + phonetics → decision

Only strong evidence auto-approves. The pipeline is conservative by design:

* technical failure, wrong transcript, absurd duration or a clearly non-British accent
  → REJECTED (and no further paid calls once a hard failure is known);
* anything uncertain (low transcription confidence, accent unsure, a phonetic phenomenon
  the evaluator cannot confirm or rule out, levels that sound alike) → NEEDS_REVIEW;
* APPROVED only when every check passes and every expected phenomenon was verified
  PRESENT or ABSENT (the same rule human approval follows).

A correct transcript proves the words, not the pronunciation: transcript QA and phonetic QA
are separate checks. Results are cached per audio hash + AUDIO_QA_VERSION + models, so the
same MP3 is never transcribed or evaluated twice.
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import math
import re
import uuid
from dataclasses import dataclass, field
from typing import Protocol

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.listening.models import (
    AudioQAResult,
    AudioVariant,
    AudioVariantPattern,
    Level,
)
from apps.listening.voices import VOICE_VALUES
from apps.scoring.normalize import tokenize
from apps.scoring.services import Status, score_answer

from .audio_meta import audio_duration_ms, looks_like_mp3
from .retry import with_retries
from .tts import TTSUnavailable

logger = logging.getLogger(__name__)

QA = AudioVariant.QAStatus
Decision = AudioQAResult.Decision
Verification = AudioVariantPattern.Verification
AUTOMATIC = AudioVariant.ApprovalSource.AUTOMATIC
HUMAN = AudioVariant.ApprovalSource.HUMAN

MIN_BYTES = 2_000
# Typical words per second before the level's speed factor (tolerant windows below).
WORDS_PER_SECOND = {Level.CLEAR: 2.3, Level.NATURAL: 2.7, Level.FAST: 3.1}
DURATION_PASS = (0.5, 2.0)
DURATION_REVIEW = (0.35, 2.8)
TRANSCRIPT_PASS = 98.0
TRANSCRIPT_REVIEW = 94.0
CONFIDENCE_HIGH_MEAN, CONFIDENCE_HIGH_MIN = 0.90, 0.40
CONFIDENCE_MEDIUM_MEAN = 0.75
DELIVERY_MIN_SPREAD = 0.04  # three levels within 4% of each other sound "the same"
DELIVERY_INVERSION = 1.10  # Clear more than 10% faster than Fast is suspicious


# --- clients ------------------------------------------------------------------------------------


@dataclass
class Transcription:
    text: str
    token_probs: list[float] | None  # exp(logprob) per token, None if unavailable


@dataclass
class PatternVerdict:
    verification: str  # present / absent / uncertain
    confidence: float
    realisation: str = ""
    reason: str = ""


@dataclass
class Evaluation:
    accent_label: str  # british_compatible / uncertain / clearly_non_british
    accent_confidence: float
    patterns: dict[int, PatternVerdict] = field(default_factory=dict)


class Transcriber(Protocol):
    model: str

    def transcribe(self, audio: bytes, filename: str) -> Transcription: ...


class Evaluator(Protocol):
    model: str

    def evaluate(
        self, audio: bytes, transcript: str, level: str, patterns: list[dict]
    ) -> Evaluation: ...


def openai_client():
    """The only place QA creates an OpenAI client (tests replace it)."""
    from openai import OpenAI

    if not settings.OPENAI_API_KEY:
        raise TTSUnavailable("OPENAI_API_KEY is not set in the environment.")
    return OpenAI(api_key=settings.OPENAI_API_KEY, timeout=90, max_retries=0)


class OpenAITranscriber:
    def __init__(self, model: str):
        self.model = model

    def transcribe(self, audio: bytes, filename: str) -> Transcription:
        # No prompt and no expected text: we want what is actually audible.
        response = openai_client().audio.transcriptions.create(
            model=self.model,
            file=(filename, audio),
            language="en",
            response_format="json",
            include=["logprobs"],
        )
        logprobs = getattr(response, "logprobs", None)
        probs = [math.exp(lp.logprob) for lp in logprobs] if logprobs else None
        return Transcription(text=response.text or "", token_probs=probs)


EVALUATOR_SYSTEM = (
    "You are a strict, conservative phonetics QA reviewer for British English listening "
    "exercises. Judge only what you can hear in the audio. Never guess: when you are not sure, "
    "answer 'uncertain'. Reply with a single JSON object and nothing else."
)


class OpenAIEvaluator:
    def __init__(self, model: str):
        self.model = model

    def evaluate(
        self, audio: bytes, transcript: str, level: str, patterns: list[dict]
    ) -> Evaluation:
        instructions = {
            "task": (
                "1) Is the speaker's accent compatible with contemporary British English "
                "(any southern British standard), or clearly American/other? Do not name a "
                "region. 2) For each listed phenomenon, is it audibly present in THIS recording "
                "at the given words?"
            ),
            "speaking_level": level,
            "heard_transcript": transcript,
            "phenomena": patterns,
            "answer_format": {
                "accent": {
                    "label": "british_compatible | uncertain | clearly_non_british",
                    "confidence": "0..1",
                },
                "patterns": [
                    {
                        "id": "<id from phenomena>",
                        "verification": "present | absent | uncertain",
                        "confidence": "0..1",
                        "realisation": "what is actually heard, short (IPA welcome)",
                        "reason": "short",
                    }
                ],
            },
        }
        response = openai_client().chat.completions.create(
            model=self.model,
            modalities=["text"],
            temperature=0,
            messages=[
                {"role": "system", "content": EVALUATOR_SYSTEM},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": json.dumps(instructions, ensure_ascii=False)},
                        {
                            "type": "input_audio",
                            "input_audio": {
                                "data": base64.b64encode(audio).decode(),
                                "format": "mp3",
                            },
                        },
                    ],
                },
            ],
        )
        return parse_evaluation(response.choices[0].message.content or "", patterns)


class EvaluationFormatError(ValueError):
    pass


def parse_evaluation(text: str, patterns: list[dict]) -> Evaluation:
    """Strictly validate the evaluator's JSON. Anything malformed is an error, never a pass."""
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise EvaluationFormatError("no JSON object")
    try:
        data = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise EvaluationFormatError("invalid JSON") from exc
    accent = data.get("accent") or {}
    label = str(accent.get("label", "uncertain")).strip()
    if label not in {"british_compatible", "uncertain", "clearly_non_british"}:
        label = "uncertain"
    verdicts: dict[int, PatternVerdict] = {}
    known = {int(p["id"]) for p in patterns}
    for item in data.get("patterns") or []:
        try:
            pid = int(item.get("id"))
        except (TypeError, ValueError):
            continue
        if pid not in known:
            continue
        verification = str(item.get("verification", "uncertain")).strip()
        if verification not in {"present", "absent", "uncertain"}:
            verification = "uncertain"
        verdicts[pid] = PatternVerdict(
            verification=verification,
            confidence=_unit(item.get("confidence")),
            realisation=str(item.get("realisation", ""))[:120],
            reason=str(item.get("reason", ""))[:200],
        )
    return Evaluation(label, _unit(accent.get("confidence")), verdicts)


def merge_evaluations(runs: list[Evaluation]) -> Evaluation:
    """Consensus of independent evaluator runs: a verdict counts only if every run agrees.

    One audio-model call is not reliable enough on its own (the same MP3 can get opposite
    accent labels), so disagreement always degrades to 'uncertain'.
    """
    labels = {r.accent_label for r in runs}
    if len(labels) == 1:
        accent = Evaluation(runs[0].accent_label, min(r.accent_confidence for r in runs))
    else:
        accent = Evaluation("uncertain", 0.0)
    ids = set().union(*(r.patterns for r in runs))
    for pid in ids:
        verdicts = [r.patterns.get(pid) for r in runs]
        if all(verdicts) and len({v.verification for v in verdicts}) == 1:
            first = verdicts[0]
            accent.patterns[pid] = PatternVerdict(
                first.verification,
                min(v.confidence for v in verdicts),
                first.realisation,
                first.reason,
            )
        else:
            accent.patterns[pid] = PatternVerdict("uncertain", 0.0, "", "evaluator runs disagree")
    return accent


def _unit(value) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def get_transcriber() -> Transcriber:
    return OpenAITranscriber(settings.AUDIO_QA_TRANSCRIBE_MODEL)


def get_evaluator() -> Evaluator | None:
    model = settings.AUDIO_QA_EVALUATOR_MODEL
    return OpenAIEvaluator(model) if model else None


# --- pure rules -----------------------------------------------------------------------------------


def technical_check(variant, data: bytes | None) -> tuple[bool, list[str], int | None]:
    """Everything that can be verified without any API call."""
    reasons = []
    duration = None
    if data is None:
        return False, ["fișier audio lipsă"], None
    if len(data) < MIN_BYTES:
        reasons.append("fișier audio prea mic")
    if not looks_like_mp3(data):
        reasons.append("nu este un MP3 valid")
    else:
        duration = audio_duration_ms(data, "mp3")
        if not duration:
            reasons.append("durata nu poate fi citită")
    if variant.provider != "openai":
        reasons.append(f"provider neașteptat: {variant.provider}")
    if variant.voice not in VOICE_VALUES:
        reasons.append(f"voce neoferită: {variant.voice}")
    if variant.level not in Level.values:
        reasons.append("nivel invalid")
    if not variant.accent.tts_supported:
        reasons.append("accent fără suport TTS")
    if not variant.model or not variant.engine_version:
        reasons.append("metadate de generare lipsă")
    if not variant.generation_settings and not variant.instructions:
        reasons.append("setări de generare lipsă")
    return not reasons, reasons, duration


def expected_duration_ms(words: int, level: str, speed: float | None) -> float:
    rate = WORDS_PER_SECOND.get(level, 2.7) * (speed or 1.0)
    return 1000 * (words / rate + 0.6)


def duration_check(duration_ms: int | None, words: int, level: str, speed) -> str:
    """'pass', 'review' or 'fail' — tolerant windows, natural speech varies a lot."""
    if not duration_ms:
        return "fail"
    ratio = duration_ms / expected_duration_ms(words, level, speed)
    if DURATION_PASS[0] <= ratio <= DURATION_PASS[1]:
        return "pass"
    if DURATION_REVIEW[0] <= ratio <= DURATION_REVIEW[1]:
        return "review"
    return "fail"


def transcript_similarity(expected: str, heard: str) -> float:
    """0..100 with the product's normalisation; contractions and UK/US spelling count as equal.

    Missing, wrong, reordered and extra (hallucinated) words all lower the score.
    """
    if not tokenize(expected):
        return 0.0
    words = score_answer(expected, heard).words
    expected_n = sum(1 for w in words if w.position is not None)
    extras = sum(1 for w in words if w.status == Status.EXTRA)
    equivalent = sum(
        1
        for w in words
        if w.position is not None
        and w.status in {Status.CORRECT, Status.CONTRACTION, Status.SPELLING}
    )
    return round(100 * equivalent / (expected_n + extras), 2)


def transcription_confidence(probs: list[float] | None) -> tuple[float | None, str]:
    """Mean token probability (documented metric) and a label; None if the API gave none."""
    if not probs:
        return None, ""
    mean = sum(probs) / len(probs)
    if mean >= CONFIDENCE_HIGH_MEAN and min(probs) >= CONFIDENCE_HIGH_MIN:
        return round(mean, 4), "high"
    if mean >= CONFIDENCE_MEDIUM_MEAN:
        return round(mean, 4), "medium"
    return round(mean, 4), "low"


def delivery_check(durations: dict[str, int], words: int) -> bool | None:
    """Do Clear / Natural / Fast actually differ? None until all three levels exist."""
    if not all(durations.get(lv) for lv in Level.values):
        return None
    values = [durations[lv] for lv in Level.values]
    if (max(values) - min(values)) / max(values) < DELIVERY_MIN_SPREAD:
        return False
    rate = {lv: words / (durations[lv] / 1000) for lv in Level.values}
    if rate[Level.CLEAR] > rate[Level.FAST] * DELIVERY_INVERSION:
        return False
    return True


def accent_result(evaluation: Evaluation | None) -> bool | None:
    if evaluation is None:
        return None
    if (
        evaluation.accent_label == "british_compatible"
        and evaluation.accent_confidence >= settings.AUDIO_QA_ACCENT_CONFIDENCE
    ):
        return True
    if (
        evaluation.accent_label == "clearly_non_british"
        and evaluation.accent_confidence >= settings.AUDIO_QA_ACCENT_CONFIDENCE
    ):
        return False
    return None


@dataclass
class Checks:
    technical: bool
    similarity: float | None = None
    confidence: float | None = None
    confidence_label: str = ""
    duration: str | None = None  # pass / review / fail
    delivery: bool | None = None
    accent: bool | None = None
    phonetic_reviewed: int = 0
    phonetic_expected: int = 0
    evaluator_ran: bool = False

    @property
    def transcript_pass(self) -> bool | None:
        if self.similarity is None:
            return None
        return self.similarity >= TRANSCRIPT_PASS and self.confidence_label == "high"

    @property
    def phonetic_complete(self) -> bool:
        return self.phonetic_reviewed >= self.phonetic_expected


def overall_score(c: Checks) -> int:
    """Transparent 0..100 score (weights documented in the README)."""
    if not c.technical:
        return 0
    score = 45 * (c.similarity or 0) / 100
    score += 15 * (c.confidence or 0)
    score += {"pass": 10, "review": 5}.get(c.duration or "", 0)
    score += 0 if c.delivery is False else 10
    score += {True: 10, None: 5, False: 0}[c.accent]
    score += 10 if not c.phonetic_expected else 10 * c.phonetic_reviewed / c.phonetic_expected
    return round(score)


def decide(c: Checks, score: int) -> tuple[str, list[str]]:
    """Deterministic decision. Mandatory failures are never compensated by the score."""
    reasons = []
    if not c.technical:
        return Decision.REJECTED, ["verificare tehnică eșuată"]
    if c.similarity is not None and c.similarity < TRANSCRIPT_REVIEW:
        return Decision.REJECTED, [f"transcriere diferită de text ({c.similarity:.0f}%)"]
    if c.duration == "fail":
        return Decision.REJECTED, ["durată absurdă față de text"]
    if c.accent is False:
        return Decision.REJECTED, ["accentul nu sună britanic"]
    if score < settings.AUDIO_QA_REVIEW_SCORE:
        return Decision.REJECTED, [f"scor prea mic ({score})"]

    if not c.transcript_pass:
        reasons.append(
            f"transcriere {c.similarity:.0f}%, încredere {c.confidence_label or 'necunoscută'}"
        )
    if c.duration != "pass":
        reasons.append("durată la limită")
    if c.delivery is False:
        reasons.append("nivelurile sună prea asemănător")
    if c.accent is not True:
        reasons.append("accent neconfirmat")
    if not c.phonetic_complete:
        reasons.append(
            f"{c.phonetic_expected - c.phonetic_reviewed} fenomene fonetice neconfirmate"
        )
    if score < settings.AUDIO_QA_AUTO_APPROVE_SCORE:
        reasons.append(f"scor {score} sub pragul de aprobare")
    if reasons:
        return Decision.NEEDS_REVIEW, reasons
    return Decision.APPROVED, []


# --- orchestration -----------------------------------------------------------------------------


def read_audio(variant) -> bytes | None:
    name = variant.audio_file.name if variant.audio_file else ""
    if not name or not variant.audio_file.storage.exists(name):
        return None
    with variant.audio_file.storage.open(name, "rb") as fh:
        return fh.read()


def cache_key(
    audio_sha: str, transcriber_model: str, evaluator_model: str, variant_id: int | None = None
) -> str:
    """Same recording + same audio + same QA version and models → reuse the result.

    The variant id is part of the key because phonetic verdicts are stored per recording.
    """
    parts = [
        audio_sha,
        str(variant_id or ""),
        str(settings.AUDIO_QA_VERSION),
        transcriber_model,
        evaluator_model,
    ]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def expected_patterns(variant) -> list:
    return [
        pp
        for pp in variant.phrase.phrase_patterns.select_related("pattern")
        if pp.expected_at(variant.level)
    ]


def sibling_durations(variant) -> dict[str, int]:
    rows = AudioVariant.objects.filter(
        phrase_id=variant.phrase_id,
        voice=variant.voice,
        accent_id=variant.accent_id,
        provider=variant.provider,
        model=variant.model,
        engine_version=variant.engine_version,
        duration_measured=True,
    ).order_by("-generated_at")
    durations: dict[str, int] = {}
    for row in rows:
        durations.setdefault(row.level, row.duration_ms)
    return durations


@dataclass
class QAOutcome:
    result: AudioQAResult
    reused: bool


DEFAULT = object()  # use the configured client


def run_qa(
    variant,
    transcriber: Transcriber | None = None,
    evaluator=DEFAULT,
    *,
    force: bool = False,
) -> QAOutcome:
    """Run (or reuse) automatic QA for one recording and apply the decision.

    `evaluator=None` means "no audio evaluator": accent and phonetics stay unconfirmed,
    so the recording can at best reach NEEDS_REVIEW.
    """
    data = read_audio(variant)
    sha = hashlib.sha256(data).hexdigest() if data is not None else "missing"
    transcriber = transcriber or get_transcriber()
    evaluator = get_evaluator() if evaluator is DEFAULT else evaluator
    t_model = transcriber.model
    e_model = evaluator.model if evaluator else ""
    key = cache_key(sha, t_model, e_model, variant.pk)

    if data is not None and not force:
        cached = AudioQAResult.objects.filter(cache_key=key).first()
        if cached is not None:
            apply_decision(variant, cached)
            return QAOutcome(cached, reused=True)
    if data is not None and variant.audio_sha256 != sha:
        variant.audio_sha256 = sha
        variant.save(update_fields=["audio_sha256"])

    technical, tech_reasons, duration_ms = technical_check(variant, data)
    checks = Checks(technical=technical)
    meta: dict = {}
    transcript_text = ""
    if not technical:
        return _save(variant, key, sha, t_model, e_model, checks, "", tech_reasons, meta)

    words = len(tokenize(variant.phrase.text))
    checks.duration = duration_check(duration_ms, words, variant.level, variant.speed)
    meta["duration_ms"] = duration_ms
    meta["expected_duration_ms"] = round(expected_duration_ms(words, variant.level, variant.speed))

    try:
        heard = with_retries(
            lambda: transcriber.transcribe(data, f"{variant.pk}.mp3"), label="transcribe"
        )
    except Exception as exc:  # noqa: BLE001 - recorded as a retryable QA error
        return _error(variant, key, sha, t_model, e_model, f"transcriere: {type(exc).__name__}")
    transcript_text = heard.text
    checks.similarity = transcript_similarity(variant.phrase.text, heard.text)
    checks.confidence, checks.confidence_label = transcription_confidence(heard.token_probs)
    if heard.token_probs:
        meta["token_prob_min"] = round(min(heard.token_probs), 4)
        meta["token_count"] = len(heard.token_probs)

    expected = expected_patterns(variant)
    checks.phonetic_expected = len(expected)
    hard_fail = checks.similarity < TRANSCRIPT_REVIEW or checks.duration == "fail"
    evaluation = None
    if evaluator is not None and not hard_fail:
        payload = [
            {
                "id": pp.pk,
                "words": pp.fragment,
                "phenomenon": pp.pattern.name_en,
                "typical_realisation": pp.sounds_like,
                "definition": pp.pattern.description_ro,
            }
            for pp in expected
        ]
        try:
            runs = [
                with_retries(
                    lambda: evaluator.evaluate(data, heard.text, variant.level, payload),
                    label="evaluate",
                )
                for _ in range(max(1, settings.AUDIO_QA_EVALUATOR_RUNS))
            ]
            evaluation = merge_evaluations(runs)
            meta["evaluator_runs"] = [[r.accent_label, r.accent_confidence] for r in runs]
            checks.evaluator_ran = True
        except EvaluationFormatError as exc:
            meta["evaluator_error"] = str(exc)
        except Exception as exc:  # noqa: BLE001
            return _error(variant, key, sha, t_model, e_model, f"evaluator: {type(exc).__name__}")
    if evaluation is not None:
        meta["accent"] = [evaluation.accent_label, evaluation.accent_confidence]
        checks.accent = accent_result(evaluation)
        checks.phonetic_reviewed = apply_pattern_verdicts(variant, expected, evaluation)
    else:
        checks.phonetic_reviewed = _already_reviewed(variant, expected)

    checks.delivery = delivery_check(sibling_durations(variant), words)
    return _save(
        variant,
        key,
        sha,
        t_model,
        e_model,
        checks,
        transcript_text,
        [],
        meta,
        accent_label=evaluation.accent_label if evaluation else "",
    )


def _already_reviewed(variant, expected) -> int:
    reviewed = set(
        variant.pattern_checks.exclude(verification=Verification.UNVERIFIED).values_list(
            "phrase_pattern_id", flat=True
        )
    )
    return sum(1 for pp in expected if pp.pk in reviewed)


def apply_pattern_verdicts(variant, expected, evaluation: Evaluation) -> int:
    """Write confident verdicts; uncertain stays UNVERIFIED; human verifications are kept."""
    threshold = settings.AUDIO_QA_PATTERN_CONFIDENCE
    reviewed = 0
    for pp in expected:
        check, _ = AudioVariantPattern.objects.get_or_create(
            audio_variant=variant, phrase_pattern=pp
        )
        if check.source == HUMAN and check.verification != Verification.UNVERIFIED:
            reviewed += 1
            continue
        verdict = evaluation.patterns.get(pp.pk)
        if (
            verdict
            and verdict.confidence >= threshold
            and verdict.verification
            in {
                "present",
                "absent",
            }
        ):
            check.verification = (
                Verification.PRESENT if verdict.verification == "present" else Verification.ABSENT
            )
            check.realisation = verdict.realisation if verdict.verification == "present" else ""
            reviewed += 1
        else:
            check.verification = Verification.UNVERIFIED
            check.realisation = ""
        check.source = AUTOMATIC
        check.confidence = verdict.confidence if verdict else None
        check.verified_by = None
        check.verified_at = timezone.now()
        check.save()
    return reviewed


def _save(
    variant,
    key,
    sha,
    t_model,
    e_model,
    checks: Checks,
    transcript,
    reasons,
    meta,
    accent_label: str = "",
) -> QAOutcome:
    score = overall_score(checks)
    decision, why = decide(checks, score)
    with transaction.atomic():
        result = AudioQAResult.objects.create(
            audio_variant=variant,
            cache_key=key if checks.technical else f"{key[:40]}{uuid.uuid4().hex[:24]}",
            qa_version=str(settings.AUDIO_QA_VERSION),
            audio_sha256=sha,
            transcribe_model=t_model,
            evaluator_model=e_model,
            technical_pass=checks.technical,
            transcript_pass=checks.transcript_pass,
            transcript_text=transcript[:500],
            transcript_similarity=checks.similarity,
            transcript_confidence=checks.confidence,
            confidence_label=checks.confidence_label,
            duration_pass=None if checks.duration is None else checks.duration == "pass",
            accent_pass=checks.accent,
            accent_label=accent_label,
            delivery_pass=checks.delivery,
            phonetic_pass=(
                None
                if not checks.evaluator_ran and checks.phonetic_expected
                else checks.phonetic_complete
            ),
            overall_score=score,
            decision=decision,
            reasons=(reasons or []) + why,
            raw_metadata=meta,
        )
        apply_decision(variant, result)
    return QAOutcome(result, reused=False)


def _error(variant, key, sha, t_model, e_model, reason: str) -> QAOutcome:
    """API failure after retries: recorded, not cached, variant stays pending for a rerun."""
    result = AudioQAResult.objects.create(
        audio_variant=variant,
        cache_key=f"{key[:40]}{uuid.uuid4().hex[:24]}",
        qa_version=str(settings.AUDIO_QA_VERSION),
        audio_sha256=sha,
        transcribe_model=t_model,
        evaluator_model=e_model,
        technical_pass=True,
        decision=Decision.ERROR,
        reasons=[reason],
    )
    return QAOutcome(result, reused=False)


def apply_decision(variant, result: AudioQAResult) -> str:
    """Set the variant's status from a QA result. Human decisions are never overridden."""
    from apps.listening.services.qa import set_status

    variant.refresh_from_db()
    if variant.approval_source == HUMAN or result.decision == Decision.ERROR:
        return variant.qa_status
    target = {
        Decision.APPROVED: QA.APPROVED,
        Decision.NEEDS_REVIEW: QA.NEEDS_REVIEW,
        Decision.REJECTED: QA.REJECTED,
    }[result.decision]
    if target == QA.APPROVED:
        changed, _ = set_status([variant], QA.APPROVED, None, source=AUTOMATIC)
        if not changed:  # the strict approval rules still apply
            target = QA.NEEDS_REVIEW
        else:
            return QA.APPROVED
    set_status([variant], target, None, source=AUTOMATIC)
    return target
