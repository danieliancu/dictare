"""Dictation scoring.

`score_answer(expected, typed)` compares a typed answer with the transcript and returns a
0–100 score plus per-word results. Rules (tunable via the constants below):

* exact answer (after normalisation) → 100
* a missed unstressed/function word costs less than a missed content word
* a changed content word costs the most
* contraction vs full form ("I'll" / "I will") and UK/US spelling are labelled but cheap
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field

from .align import Op, Step, align, similarity
from .normalize import expand, is_function_word, spelling_key, surface_tokens, tokenize


class Status:
    CORRECT = "correct"
    MISSING = "missing"
    INCORRECT = "incorrect"
    EXTRA = "extra"
    ORDER = "order"
    CONTRACTION = "contraction"
    SPELLING = "spelling"


ACCEPTED = {Status.CORRECT, Status.CONTRACTION, Status.SPELLING}

FUNCTION_WEIGHT = 0.6
CONTENT_WEIGHT = 1.0
SEVERITY = {
    Status.MISSING: 1.0,
    Status.INCORRECT: 1.0,
    "near_miss": 0.5,  # typo-like: "coffe" for "coffee"
    "partial": 0.6,  # part of a contraction heard ("I" for "I'll")
    Status.ORDER: 0.3,
    Status.CONTRACTION: 0.15,
    Status.SPELLING: 0.05,
    Status.EXTRA: 0.4,
}
NEAR_MISS_SIMILARITY = 0.75


@dataclass
class WordResult:
    text: str  # display form (expected word, or typed word for extras)
    status: str
    position: int | None = None  # index in the expected transcript (None for extras)
    typed: str = ""
    severity: float = 0.0
    weight: float = 1.0

    @property
    def accepted(self) -> bool:
        return self.status in ACCEPTED


@dataclass
class ScoreResult:
    score: int
    word_accuracy: int
    words: list[WordResult] = field(default_factory=list)

    @property
    def mistakes(self) -> list[WordResult]:
        return [w for w in self.words if w.status != Status.CORRECT]

    def count(self, status: str) -> int:
        return sum(1 for w in self.words if w.status == status)

    @property
    def is_perfect(self) -> bool:
        return self.score == 100


def word_weight(norm_word: str) -> float:
    pieces = [t.canon for t in expand([norm_word])]
    if all(is_function_word(p) for p in pieces):
        return FUNCTION_WEIGHT
    return CONTENT_WEIGHT


def _classify(steps: list[Step], typed_norm: list[str]) -> tuple[str, str, float]:
    """Status, typed text and severity for one expected surface word."""
    typed_origins = sorted({s.typed.origin for s in steps if s.typed is not None})
    typed_text = " ".join(typed_norm[o] for o in typed_origins)
    ops = {s.op for s in steps}

    if ops == {Op.MISSING}:
        return Status.MISSING, "", SEVERITY[Status.MISSING]
    if ops == {Op.MATCH}:
        expected_contracted = steps[0].expected.contracted
        if any(s.typed.contracted != expected_contracted for s in steps):
            return Status.CONTRACTION, typed_text, SEVERITY[Status.CONTRACTION]
        return Status.CORRECT, typed_text, 0.0
    if ops == {Op.SUB} and len(steps) == 1:
        e, t = steps[0].expected.canon, steps[0].typed.canon
        if spelling_key(e) == spelling_key(t):
            return Status.SPELLING, typed_text, SEVERITY[Status.SPELLING]
        if similarity(e, t) >= NEAR_MISS_SIMILARITY:
            return Status.INCORRECT, typed_text, SEVERITY["near_miss"]
        return Status.INCORRECT, typed_text, SEVERITY[Status.INCORRECT]
    if Op.MATCH in ops:
        return Status.INCORRECT, typed_text, SEVERITY["partial"]
    return Status.INCORRECT, typed_text, SEVERITY[Status.INCORRECT]


def score_answer(expected_text: str, typed_text: str) -> ScoreResult:
    surface = surface_tokens(expected_text)
    expected_norm = [norm for _, norm in surface]
    typed_norm = tokenize(typed_text)
    if not expected_norm:
        return ScoreResult(score=0, word_accuracy=0)

    steps = align(expand(expected_norm), expand(typed_norm))

    # Pair a missing word with the same word typed elsewhere → word-order mistake.
    order_pairs: dict[int, str] = {}
    consumed_extras: set[int] = set()
    missing = [s for s in steps if s.op == Op.MISSING]
    extras = [s for s in steps if s.op == Op.EXTRA]
    for miss in missing:
        for idx, extra in enumerate(extras):
            if idx in consumed_extras or not miss.expected.matches(extra.typed):
                continue
            order_pairs[miss.expected.origin] = typed_norm[extra.typed.origin]
            consumed_extras.add(idx)
            break
    consumed_typed = {extras[i].typed.origin for i in consumed_extras}

    by_origin: dict[int, list[Step]] = defaultdict(list)
    extras_before: dict[int, list[int]] = defaultdict(list)
    next_expected = 0
    for step in steps:
        if step.expected is not None:
            by_origin[step.expected.origin].append(step)
            next_expected = step.expected.origin + 1
        elif step.typed.origin not in consumed_typed:
            bucket = extras_before[next_expected]
            if step.typed.origin not in bucket:
                bucket.append(step.typed.origin)

    words: list[WordResult] = []
    penalty = 0.0
    total_weight = 0.0
    for pos, (display, norm) in enumerate(surface):
        for typed_origin in extras_before.get(pos, []):
            penalty += _append_extra(words, typed_norm[typed_origin])
        weight = word_weight(norm)
        total_weight += weight
        if pos in order_pairs:
            status, typed, severity = Status.ORDER, order_pairs[pos], SEVERITY[Status.ORDER]
        else:
            status, typed, severity = _classify(by_origin[pos], typed_norm)
        penalty += weight * severity
        words.append(WordResult(display, status, pos, typed, severity, weight))
    for typed_origin in extras_before.get(len(surface), []):
        penalty += _append_extra(words, typed_norm[typed_origin])

    if not typed_norm:
        score = 0
    else:
        score = round(100 * max(0.0, 1 - penalty / total_weight))
    accepted = sum(1 for w in words if w.position is not None and w.accepted)
    word_accuracy = round(100 * accepted / len(surface))
    return ScoreResult(score=score, word_accuracy=word_accuracy, words=words)


def _append_extra(words: list[WordResult], typed: str) -> float:
    weight = word_weight(typed)
    severity = SEVERITY[Status.EXTRA]
    words.append(WordResult(typed, Status.EXTRA, None, typed, severity, weight))
    return weight * severity
