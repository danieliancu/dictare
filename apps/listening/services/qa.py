"""Editorial QA of recordings: only reviewed, approved audio reaches learners in production."""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from ..models import AudioVariant, AudioVariantPattern

QA = AudioVariant.QAStatus


@transaction.atomic
def set_status(variants, status: str, user, notes: str | None = None) -> tuple[int, int]:
    """Set the QA status. Mock placeholders are never approved. Returns (changed, skipped)."""
    changed = skipped = 0
    for variant in variants:
        if status == QA.APPROVED and (variant.is_placeholder or not variant.audio_file):
            skipped += 1
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


def mark_pattern_checked(check: AudioVariantPattern, user) -> None:
    """Stamp who verified a pattern in a recording (called when the verification changes)."""
    if check.verification != AudioVariantPattern.Verification.UNVERIFIED:
        check.verified_by = user
        check.verified_at = timezone.now()
