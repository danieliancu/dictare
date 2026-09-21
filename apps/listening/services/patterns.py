"""Which speech patterns apply to a specific recording, and how to describe them.

A `PhrasePattern` is a general tendency ("in natural speech /t/ may be glottalised here").
An `AudioVariantPattern` records whether a reviewer verified it in one recording.

* `patterns_for_variant` — for teaching (UI): verified phenomena plus expected ones, the
  latter shown only as a general tendency.
* `verified_patterns_for_variant` — for judging the learner (mistakes, mastery,
  personalisation): PRESENT only. If we have not verified that a phenomenon is audible, we do
  not use it to judge the user.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from ..models import AudioVariantPattern, PhrasePattern

Verification = AudioVariantPattern.Verification


@dataclass(frozen=True)
class AppliedPattern:
    phrase_pattern: PhrasePattern
    verification: str  # present / unverified
    realisation: str
    text: str

    @property
    def heard(self) -> bool:
        """True only when a reviewer confirmed the phenomenon in this recording."""
        return self.verification == Verification.PRESENT

    def covers(self, position: int) -> bool:
        return self.phrase_pattern.covers(position)


@transaction.atomic
def create_expected_checks(variant) -> int:
    """Create `unverified` rows for the patterns expected at the variant's level."""
    created = 0
    for pp in variant.phrase.phrase_patterns.all():
        if not pp.expected_at(variant.level):
            continue
        _, was_created = AudioVariantPattern.objects.get_or_create(
            audio_variant=variant, phrase_pattern=pp
        )
        created += int(was_created)
    return created


def patterns_for_variant(variant, phrase=None, level: str | None = None) -> list[AppliedPattern]:
    """Patterns that may be explained for this recording.

    * verified present → described as heard in this recording;
    * unverified but expected at this level → described only as a general tendency;
    * verified absent, or not expected at this level → omitted.

    Without a variant (legacy attempts), falls back to patterns expected at `level`.
    """
    if variant is None:
        phrase_patterns = _sorted(phrase.phrase_patterns.all()) if phrase else []
        return [
            AppliedPattern(pp, Verification.UNVERIFIED, "", pp.explanation_ro)
            for pp in phrase_patterns
            if level is None or pp.expected_at(level)
        ]

    applied = []
    for pp, check in _patterns_with_checks(variant, phrase):
        if check is not None and check.verification == Verification.ABSENT:
            continue
        if check is not None and check.verification == Verification.PRESENT:
            applied.append(_heard(pp, check))
            continue
        if pp.expected_at(variant.level):
            applied.append(AppliedPattern(pp, Verification.UNVERIFIED, "", pp.explanation_ro))
    return applied


def verified_patterns_for_variant(variant, phrase=None) -> list[AppliedPattern]:
    """Patterns a reviewer confirmed as audible in this recording (PRESENT only).

    This is the only source for judging the learner (mistake attribution, mastery,
    personalisation). Unverified or absent phenomena, and attempts without a recording,
    never count.
    """
    if variant is None:
        return []
    return [
        _heard(pp, check)
        for pp, check in _patterns_with_checks(variant, phrase)
        if check is not None and check.verification == Verification.PRESENT
    ]


def _patterns_with_checks(variant, phrase=None):
    """(phrase pattern, its check for this variant or None), in sentence order."""
    checks = {c.phrase_pattern_id: c for c in variant.pattern_checks.all()}
    source = phrase if phrase is not None else variant.phrase
    return [(pp, checks.get(pp.pk)) for pp in _sorted(source.phrase_patterns.all())]


def _heard(pp: PhrasePattern, check: AudioVariantPattern) -> AppliedPattern:
    return AppliedPattern(
        pp,
        Verification.PRESENT,
        check.realisation,
        check.explanation_override_ro or pp.explanation_ro,
    )


def _sorted(phrase_patterns) -> list[PhrasePattern]:
    """Works with prefetched querysets (no extra queries)."""
    return sorted(phrase_patterns, key=lambda pp: (pp.start_token, pp.pk))


def pattern_for_position(applied: list[AppliedPattern], position: int | None):
    """The most specific applicable pattern covering a word position (for mistakes)."""
    if position is None:
        return None
    covering = [a.phrase_pattern for a in applied if a.covers(position)]
    if not covering:
        return None
    return min(covering, key=lambda pp: pp.end_token - pp.start_token)
