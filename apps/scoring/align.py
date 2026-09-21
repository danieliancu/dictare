"""Word-level alignment between the expected transcript and the typed answer."""

from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import StrEnum

from .normalize import CanonToken, spelling_key


class Op(StrEnum):
    MATCH = "match"
    SUB = "sub"
    MISSING = "missing"  # expected word not typed (deletion)
    EXTRA = "extra"  # typed word not in transcript (insertion)


@dataclass(frozen=True)
class Step:
    op: Op
    expected: CanonToken | None
    typed: CanonToken | None


def similarity(a: str, b: str) -> float:
    if a == b:
        return 1.0
    if spelling_key(a) == spelling_key(b):
        return 0.98
    return SequenceMatcher(None, a, b).ratio()


def _sub_cost(e: CanonToken, t: CanonToken) -> float:
    if e.matches(t):
        return 0.0
    # Near-misses are cheaper than unrelated words, so alignment prefers pairing them.
    return 1.4 - 0.6 * similarity(e.canon, t.canon)


def align(expected: list[CanonToken], typed: list[CanonToken]) -> list[Step]:
    """Weighted Levenshtein alignment with backtrace (O(n·m), phrases are short)."""
    n, m = len(expected), len(typed)
    gap = 1.0
    cost = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        cost[i][0] = i * gap
    for j in range(1, m + 1):
        cost[0][j] = j * gap
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            cost[i][j] = min(
                cost[i - 1][j - 1] + _sub_cost(expected[i - 1], typed[j - 1]),
                cost[i - 1][j] + gap,
                cost[i][j - 1] + gap,
            )

    steps: list[Step] = []
    i, j = n, m
    while i > 0 or j > 0:
        if i > 0 and j > 0:
            sub = _sub_cost(expected[i - 1], typed[j - 1])
            if abs(cost[i][j] - (cost[i - 1][j - 1] + sub)) < 1e-9:
                op = Op.MATCH if sub == 0.0 else Op.SUB
                steps.append(Step(op, expected[i - 1], typed[j - 1]))
                i, j = i - 1, j - 1
                continue
        if i > 0 and abs(cost[i][j] - (cost[i - 1][j] + gap)) < 1e-9:
            steps.append(Step(Op.MISSING, expected[i - 1], None))
            i -= 1
        else:
            steps.append(Step(Op.EXTRA, None, typed[j - 1]))
            j -= 1
    steps.reverse()
    return steps
