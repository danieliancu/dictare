"""Editorial QA of recordings: only reviewed, approved audio reaches learners in production.

Every approval path (admin action, change form, review page) goes through
`approval_problems()`, so the rules live in one place.
"""

from __future__ import annotations

from collections import Counter

from django.db import transaction
from django.utils import timezone

from ..models import AudioVariant, AudioVariantPattern
from .audio import file_exists

QA = AudioVariant.QAStatus
Verification = AudioVariantPattern.Verification

NO_FILE = "fișier audio lipsă"
PLACEHOLDER = "audio mock (placeholder)"


def unreviewed_patterns(variant) -> list:
    """Phrase patterns expected at the variant's level that are not yet PRESENT/ABSENT."""
    checks = {c.phrase_pattern_id: c.verification for c in variant.pattern_checks.all()}
    return [
        pp
        for pp in variant.phrase.phrase_patterns.all()
        if pp.expected_at(variant.level)
        and checks.get(pp.pk, Verification.UNVERIFIED) == Verification.UNVERIFIED
    ]


def unverified_label(count: int) -> str:
    if count == 1:
        return "1 fenomen fonetic încă neverificat"
    return f"{count} fenomene fonetice încă neverificate"


def approval_problems(variant) -> list[str]:
    """Why this recording cannot be approved yet (empty list = it can be approved)."""
    problems = []
    if variant.is_placeholder:
        problems.append(PLACEHOLDER)
    if not file_exists(variant):
        problems.append(NO_FILE)
    missing = len(unreviewed_patterns(variant))
    if missing:
        problems.append(unverified_label(missing))
    return problems


def can_approve(variant) -> bool:
    return not approval_problems(variant)


def skip_reason(problems: list[str]) -> str:
    """Group reasons for bulk messages ("2 fenomene…" and "3 fenomene…" count together)."""
    first = problems[0]
    return "fenomene fonetice neverificate" if "neverificat" in first else first


@transaction.atomic
def set_status(variants, status: str, user, notes: str | None = None) -> tuple[int, Counter]:
    """Set the QA status. Approval requires `approval_problems()` to be empty.

    Returns (changed, skipped reasons counter).
    """
    changed, skipped = 0, Counter()
    for variant in variants:
        if status == QA.APPROVED:
            problems = approval_problems(variant)
            if problems:
                skipped[skip_reason(problems)] += 1
                continue
        variant.qa_status = status
        variant.reviewed_by = user
        variant.reviewed_at = timezone.now()
        fields = ["qa_status", "reviewed_by", "reviewed_at"]
        if notes is not None:
            variant.qa_notes = notes
            fields.append("qa_notes")
        variant.save(update_fields=fields)
        changed += 1
    return changed, skipped


def describe_result(changed: int, skipped: Counter, verb: str = "aprobate") -> str:
    """E.g. "8 aprobate, 3 omise: 2 × fenomene fonetice neverificate, 1 × fișier audio lipsă"."""
    message = f"{changed} {verb}"
    total = sum(skipped.values())
    if total:
        reasons = ", ".join(f"{n} × {reason}" for reason, n in skipped.most_common())
        message += f", {total} omise: {reasons}"
    return message + "."


def pattern_summary(variant) -> dict[str, int]:
    """Counts of the variant's pattern checks (for the review page and admin)."""
    counts = Counter(c.verification for c in variant.pattern_checks.all())
    unreviewed = len(unreviewed_patterns(variant))
    return {
        "total": sum(counts.values()),
        "present": counts[Verification.PRESENT],
        "absent": counts[Verification.ABSENT],
        "unverified": unreviewed,
    }


def mark_pattern_checked(check: AudioVariantPattern, user) -> None:
    """Stamp who verified a pattern in a recording (called when the verification changes)."""
    if check.verification != Verification.UNVERIFIED:
        check.verified_by = user
        check.verified_at = timezone.now()
