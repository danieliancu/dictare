"""P0 hardening: verified-only analytics, strict approval, storage = availability."""

import importlib
import sys

import pytest
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.ai.services import tts
from apps.listening.models import AudioVariant, AudioVariantPattern, Level
from apps.listening.services import qa
from apps.listening.services.audio import get_audio_variant, phrase_ids_with_audio
from apps.practice.models import AttemptMistake, ListeningAttempt, PracticeSession
from apps.practice.services.personalization import WeaknessRecommender
from apps.practice.services.sessions import save_mistakes
from apps.progress.models import PatternMastery
from apps.progress.services import mastery
from apps.scoring.services import score_answer

QA = AudioVariant.QAStatus
V = AudioVariantPattern.Verification
_counter = iter(range(10_000))


def variant_with_file(
    phrase, accent, *, level=Level.CLEAR, provider="openai", status=QA.APPROVED, with_file=True
):
    variant = AudioVariant(
        phrase=phrase,
        level=level,
        accent=accent,
        voice="marin",
        provider=provider,
        qa_status=status,
        engine_version="2",
    )
    name = f"v{next(_counter)}.mp3"
    if with_file:
        variant.audio_file.save(name, ContentFile(b"ID3" + b"0" * 300), save=False)
    else:
        variant.audio_file.name = f"audio/missing/{name}"  # row exists, file does not
    variant.save()
    return variant


def check_all(variant, verification):
    for pp in variant.phrase.phrase_patterns.all():
        if pp.expected_at(variant.level):
            AudioVariantPattern.objects.update_or_create(
                audio_variant=variant, phrase_pattern=pp, defaults={"verification": verification}
            )


def completed_attempt(user, variant, typed):
    phrase = variant.phrase if variant else None
    attempt = ListeningAttempt.objects.create(
        user=user,
        phrase=phrase,
        audio_variant=variant,
        level=Level.CLEAR,
        typed_answer=typed,
        completed=True,
        score=50,
        word_accuracy=50,
    )
    from django.utils import timezone

    ListeningAttempt.objects.filter(pk=attempt.pk).update(completed_at=timezone.now())
    attempt.refresh_from_db()
    save_mistakes(attempt, score_answer(attempt.phrase.text, typed))
    return attempt


# --- storage = availability -------------------------------------------------------------------


@pytest.mark.django_db
class TestStorage:
    def test_approved_row_without_file_is_not_selected(self, phrases, accent):
        variant_with_file(phrases[0], accent, with_file=False)
        assert get_audio_variant(phrases[0], Level.CLEAR, accent) is None

    def test_skips_any_number_of_orphans(self, phrases, accent):
        valid = variant_with_file(phrases[0], accent, provider="openai")
        for _ in range(3):  # newer, human (higher priority) but orphaned
            variant_with_file(phrases[0], accent, provider="human", with_file=False)
        assert get_audio_variant(phrases[0], Level.CLEAR, accent) == valid

    def test_phrase_ids_with_audio_ignores_orphans(self, phrases, accent):
        variant_with_file(phrases[0], accent, with_file=False)
        variant_with_file(phrases[1], accent)
        assert phrase_ids_with_audio(Level.CLEAR, accent) == {phrases[1].pk}

    @override_settings(TTS_REQUIRE_APPROVAL=True, TTS_GENERATE_ON_REQUEST=False)
    def test_session_selection_never_picks_orphaned_audio(self, client, plans, accent, phrases):
        variant_with_file(phrases[0], accent, with_file=False)
        variant_with_file(phrases[1], accent)
        response = client.get(reverse("practice:daily"))
        session = PracticeSession.objects.get(pk=response.url.rstrip("/").split("/")[-1])
        assert [i.phrase_id for i in session.items.all()] == [phrases[1].pk]

    def test_orphans_are_kept_not_deleted(self, phrases, accent):
        orphan = variant_with_file(phrases[0], accent, with_file=False)
        get_audio_variant(phrases[0], Level.CLEAR, accent)
        assert AudioVariant.objects.filter(pk=orphan.pk).exists()


# --- only verified phenomena judge the learner ------------------------------------------------


@pytest.mark.django_db
class TestPresentOnly:
    # phrases[0] = "Would you like to go?": "Would you" (assimilation), "to" (weak form)

    @pytest.mark.parametrize(
        "verification, expected_pattern",
        [(V.PRESENT, "assimilation"), (V.UNVERIFIED, None), (V.ABSENT, None)],
    )
    def test_attempt_mistake_pattern(self, user, phrases, accent, verification, expected_pattern):
        variant = variant_with_file(phrases[0], accent)
        check_all(variant, verification)
        attempt = completed_attempt(user, variant, "like to go")  # "Would you" missed
        mistake = AttemptMistake.objects.filter(attempt=attempt, position=0).get()
        slug = mistake.speech_pattern.slug if mistake.speech_pattern else None
        assert slug == expected_pattern

    def test_legacy_attempt_without_recording_gets_no_pattern(self, user, phrases):
        attempt = ListeningAttempt.objects.create(
            user=user, phrase=phrases[0], completed=True, typed_answer="like to go"
        )
        save_mistakes(attempt, score_answer(phrases[0].text, "like to go"))
        assert not AttemptMistake.objects.filter(
            attempt=attempt, speech_pattern__isnull=False
        ).exists()

    @pytest.mark.parametrize(
        "verification, counts", [(V.PRESENT, True), (V.UNVERIFIED, False), (V.ABSENT, False)]
    )
    def test_mastery_exposure(self, user, phrases, accent, patterns, verification, counts):
        variant = variant_with_file(phrases[0], accent)
        check_all(variant, verification)
        completed_attempt(user, variant, "would you like to go")
        mastery.recompute(user)
        has_row = PatternMastery.objects.filter(
            user=user, pattern=patterns["assimilation"]
        ).exists()
        assert has_row is counts

    def test_stale_mastery_is_deleted(self, user, phrases, accent, patterns):
        PatternMastery.objects.create(
            user=user, pattern=patterns["assimilation"], mastery=20, exposures=5, misses=4
        )
        variant = variant_with_file(phrases[0], accent)
        check_all(variant, V.UNVERIFIED)
        completed_attempt(user, variant, "like to go")
        mastery.recompute(user)
        assert not PatternMastery.objects.filter(user=user).exists()

    def test_unverified_mistakes_do_not_become_a_weakness(self, user, phrases, accent, patterns):
        variant = variant_with_file(phrases[0], accent)
        check_all(variant, V.UNVERIFIED)
        for _ in range(5):
            completed_attempt(user, variant, "like to go")
        mastery.recompute(user)
        rec = WeaknessRecommender.for_user(user)
        assert patterns["assimilation"].pk not in rec.weakness
        assert rec.weakest_patterns() == []

    def test_recompute_command(self, user, phrases, accent):
        variant = variant_with_file(phrases[0], accent)
        check_all(variant, V.PRESENT)
        completed_attempt(user, variant, "like to go")
        call_command("recompute_mastery")
        assert PatternMastery.objects.filter(user=user).exists()


# --- approval --------------------------------------------------------------------------------


@pytest.mark.django_db
class TestApproval:
    def test_all_reviewed_is_approved(self, user, phrases, accent):
        variant = variant_with_file(phrases[0], accent, status=QA.PENDING)
        check_all(variant, V.PRESENT)
        variant.pattern_checks.filter(phrase_pattern__fragment="to").update(verification=V.ABSENT)
        changed, skipped = qa.set_status([variant], QA.APPROVED, user)
        variant.refresh_from_db()
        assert changed == 1 and not skipped and variant.qa_status == QA.APPROVED

    def test_one_unverified_is_refused(self, user, phrases, accent):
        variant = variant_with_file(phrases[0], accent, status=QA.PENDING)
        check_all(variant, V.PRESENT)
        variant.pattern_checks.filter(phrase_pattern__fragment="to").update(
            verification=V.UNVERIFIED
        )
        assert qa.approval_problems(variant) == ["1 fenomen fonetic încă neverificat"]
        changed, skipped = qa.set_status([variant], QA.APPROVED, user)
        variant.refresh_from_db()
        assert changed == 0 and variant.qa_status == QA.PENDING

    def test_missing_check_row_counts_as_unverified(self, user, phrases, accent):
        variant = variant_with_file(phrases[0], accent, status=QA.PENDING)  # no rows at all
        assert not qa.can_approve(variant)

    def test_missing_file_is_refused(self, user, phrases, accent):
        variant = variant_with_file(phrases[0], accent, status=QA.PENDING, with_file=False)
        check_all(variant, V.PRESENT)
        assert qa.approval_problems(variant) == [qa.NO_FILE]

    def test_mock_is_refused(self, user, phrases, accent):
        variant = variant_with_file(phrases[0], accent, provider="mock", status=QA.PENDING)
        check_all(variant, V.PRESENT)
        assert qa.PLACEHOLDER in qa.approval_problems(variant)

    def test_phrase_without_patterns_is_approvable(self, user, phrases, accent):
        phrase = phrases[2]
        phrase.phrase_patterns.all().delete()
        variant = variant_with_file(phrase, accent, status=QA.PENDING)
        assert qa.can_approve(variant)

    def test_bulk_action_uses_the_same_rules(self, client, phrases, accent):
        admin_user = User.objects.create_superuser(email="qa@example.com", password="x-1-abc")
        ok = variant_with_file(phrases[0], accent, status=QA.PENDING)
        check_all(ok, V.PRESENT)
        unverified = variant_with_file(phrases[1], accent, status=QA.PENDING)
        orphan = variant_with_file(phrases[2], accent, status=QA.PENDING, with_file=False)
        check_all(orphan, V.PRESENT)
        client.force_login(admin_user)
        response = client.post(
            reverse("admin:listening_audiovariant_changelist"),
            {"action": "approve_selected", "_selected_action": [ok.pk, unverified.pk, orphan.pk]},
            follow=True,
        )
        statuses = dict(AudioVariant.objects.values_list("pk", "qa_status"))
        assert statuses[ok.pk] == QA.APPROVED
        assert statuses[unverified.pk] == QA.PENDING and statuses[orphan.pk] == QA.PENDING
        text = response.content.decode()
        assert "1 aprobate, 2 omise" in text
        assert "fenomene fonetice neverificate" in text and "fișier audio lipsă" in text

    def test_review_page_refuses_unverified_with_message(self, client, phrases, accent):
        admin_user = User.objects.create_superuser(email="qa@example.com", password="x-1-abc")
        variant = variant_with_file(phrases[0], accent, status=QA.PENDING)
        client.force_login(admin_user)
        page = client.get(reverse("admin:listening_audiovariant_review") + "?pilot=0")
        assert "neverificate 2" in page.content.decode()
        response = client.post(
            reverse("admin:listening_audiovariant_review_status", args=[variant.pk]),
            {"status": "approved"},
            follow=True,
        )
        variant.refresh_from_db()
        assert variant.qa_status == QA.PENDING
        assert "Nu poate fi aprobată" in response.content.decode()

    def test_change_form_reverts_invalid_approval(self, client, phrases, accent):
        admin_user = User.objects.create_superuser(email="qa@example.com", password="x-1-abc")
        variant = variant_with_file(phrases[0], accent, status=QA.PENDING)
        client.force_login(admin_user)
        url = reverse("admin:listening_audiovariant_change", args=[variant.pk])
        page = client.get(url)
        assert "fenomene fonetice încă neverificate" in page.content.decode()
        data = {
            "phrase": variant.phrase_id,
            "level": variant.level,
            "accent": variant.accent_id,
            "voice": variant.voice,
            "provider": variant.provider,
            "qa_status": "approved",
            "qa_notes": "",
            "pattern_checks-TOTAL_FORMS": "0",
            "pattern_checks-INITIAL_FORMS": "0",
            "pattern_checks-MIN_NUM_FORMS": "0",
            "pattern_checks-MAX_NUM_FORMS": "1000",
            "qa_results-TOTAL_FORMS": "0",
            "qa_results-INITIAL_FORMS": "0",
            "qa_results-MIN_NUM_FORMS": "0",
            "qa_results-MAX_NUM_FORMS": "1000",
        }
        response = client.post(url, data, follow=True)
        variant.refresh_from_db()
        assert variant.qa_status == QA.PENDING
        assert "Nu poate fi aprobată" in response.content.decode()


# --- production guarantees -------------------------------------------------------------------


def test_production_settings_guarantees(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "x" * 60)
    monkeypatch.setenv("TTS_REQUIRE_APPROVAL", "True")
    monkeypatch.setenv("TTS_GENERATE_ON_REQUEST", "True")  # must be ignored in production
    monkeypatch.setenv("TTS_BROWSER_FALLBACK", "True")  # must be ignored in production
    saved = {
        m: sys.modules.pop(m)
        for m in ("config.settings.prod", "config.settings.base")
        if m in sys.modules
    }
    prod = importlib.import_module("config.settings.prod")
    try:
        assert prod.DEBUG is False
        assert prod.TTS_GENERATE_ON_REQUEST is False
        assert prod.TTS_BROWSER_FALLBACK is False
        assert prod.TTS_REQUIRE_APPROVAL is True
    finally:
        sys.modules.pop("config.settings.prod", None)
        sys.modules.update(saved)


def test_suite_cannot_reach_openai():
    with pytest.raises(AssertionError, match="real OpenAI client"):
        tts.OpenAIProvider("fake-key", "gpt-4o-mini-tts")._client()
