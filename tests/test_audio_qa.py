"""Audio QA, selection, variant-specific explanations and the generation commands."""

import json
from io import StringIO

import pytest
from django.contrib.auth.models import Permission
from django.core.files.base import ContentFile
from django.core.management import CommandError, call_command
from django.test import override_settings
from django.urls import reverse

from apps.accounts.models import User
from apps.ai.services import tts
from apps.listening.models import Accent, AudioVariant, AudioVariantPattern, Level
from apps.listening.services.audio import get_audio_variant
from apps.listening.services.patterns import patterns_for_variant
from apps.practice.models import AttemptMistake, ListeningAttempt, PracticeSession

QA = AudioVariant.QAStatus
V = AudioVariantPattern.Verification
HTMX = {"HTTP_HX_REQUEST": "true"}


def make_variant(
    phrase,
    accent,
    *,
    level=Level.CLEAR,
    provider="openai",
    status=QA.APPROVED,
    voice="fable",
    key=None,
):
    variant = AudioVariant(
        phrase=phrase,
        level=level,
        accent=accent,
        voice=voice,
        provider=provider,
        qa_status=status,
        engine_version="2",
        cache_key=key or "",
    )
    variant.audio_file.save(
        f"{provider}-{level}-{status}-{voice}.mp3", ContentFile(b"ID3" + b"0" * 200), save=False
    )
    variant.save()
    return variant


def review_all(variant, verification=AudioVariantPattern.Verification.PRESENT):
    """Editorial QA done: every expected phenomenon marked present (or absent)."""
    for pp in variant.phrase.phrase_patterns.all():
        if pp.expected_at(variant.level):
            AudioVariantPattern.objects.update_or_create(
                audio_variant=variant,
                phrase_pattern=pp,
                defaults={"verification": verification},
            )


@pytest.mark.django_db
class TestSelection:
    def test_human_approved_beats_tts_approved(self, phrases, accent):
        make_variant(phrases[0], accent, provider="openai")
        human = make_variant(phrases[0], accent, provider="human")
        assert get_audio_variant(phrases[0], Level.CLEAR, accent) == human

    def test_rejected_never_selected(self, phrases, accent):
        make_variant(phrases[0], accent, status=QA.REJECTED)
        assert get_audio_variant(phrases[0], Level.CLEAR, accent) is None

    def test_approved_preferred_over_pending(self, phrases, accent):
        make_variant(phrases[0], accent, provider="human", status=QA.PENDING)
        approved = make_variant(phrases[0], accent, provider="openai", status=QA.APPROVED)
        assert get_audio_variant(phrases[0], Level.CLEAR, accent) == approved

    @override_settings(TTS_REQUIRE_APPROVAL=True)
    def test_pending_not_selected_when_approval_required(self, phrases, accent):
        make_variant(phrases[0], accent, status=QA.PENDING)
        assert get_audio_variant(phrases[0], Level.CLEAR, accent) is None

    @override_settings(TTS_REQUIRE_APPROVAL=False)
    def test_pending_allowed_in_development(self, phrases, accent):
        pending = make_variant(phrases[0], accent, status=QA.PENDING)
        assert get_audio_variant(phrases[0], Level.CLEAR, accent) == pending

    def test_respects_level_and_accent(self, phrases, accent):
        rp = Accent.objects.create(code="modern-rp", name_ro="RP", name_en="RP")
        make_variant(phrases[0], accent, level=Level.FAST)
        make_variant(phrases[0], rp, level=Level.CLEAR)
        assert get_audio_variant(phrases[0], Level.CLEAR, accent) is None
        assert get_audio_variant(phrases[0], Level.FAST, accent).level == Level.FAST
        assert get_audio_variant(phrases[0], Level.CLEAR, rp).accent == rp

    @override_settings(TTS_REQUIRE_APPROVAL=True)
    def test_mock_is_never_served_in_production(self, phrases, accent):
        make_variant(phrases[0], accent, provider="mock", status=QA.APPROVED)
        assert get_audio_variant(phrases[0], Level.CLEAR, accent) is None


@pytest.mark.django_db
class TestNoNetworkInRequests:
    @override_settings(
        TTS_PROVIDER="openai", OPENAI_API_KEY="test-key", TTS_GENERATE_ON_REQUEST=True
    )
    def test_practice_request_never_calls_openai(self, client, plans, accent, phrases, monkeypatch):
        def explode(*args, **kwargs):
            raise AssertionError("network call from a practice request")

        monkeypatch.setattr(tts.OpenAIProvider, "synthesize", explode)
        monkeypatch.setattr(tts.OpenAIProvider, "_client", explode)
        response = client.get(reverse("practice:daily"))
        page = client.get(response.url)
        assert page.status_code == 200
        assert "Audio indisponibil" in page.content.decode()

    @override_settings(TTS_REQUIRE_APPROVAL=True, TTS_GENERATE_ON_REQUEST=False)
    def test_production_sessions_only_use_phrases_with_approved_audio(
        self, client, plans, accent, phrases
    ):
        make_variant(phrases[1], accent, status=QA.APPROVED)
        make_variant(phrases[2], accent, status=QA.PENDING)
        response = client.get(reverse("practice:daily"))
        session = PracticeSession.objects.get(pk=response.url.rstrip("/").split("/")[-1])
        assert [i.phrase_id for i in session.items.all()] == [phrases[1].pk]
        html = client.get(response.url).content.decode()
        assert "data-player" in html and "Audio indisponibil" not in html

    def test_missing_audio_is_graceful(self, client, plans, accent, phrases, settings):
        settings.TTS_GENERATE_ON_REQUEST = False
        response = client.get(reverse("practice:daily"))
        html = client.get(response.url).content.decode()
        assert "Audio indisponibil momentan" in html


@pytest.mark.django_db
class TestVariantPatterns:
    def _phrase(self, phrases):
        phrase = phrases[0]  # Would you like to go? -> "Would you" (assimilation), "to" (weak)
        phrase.phrase_patterns.filter(fragment="Would you").update(expected_from_level="natural")
        return phrase

    def test_clear_and_natural_have_different_patterns(self, phrases, accent):
        phrase = self._phrase(phrases)
        clear = tts.generate_variant(phrase, Level.CLEAR, accent, provider="mock")
        natural = tts.generate_variant(phrase, Level.NATURAL, accent, provider="mock")
        assert [a.phrase_pattern.fragment for a in patterns_for_variant(clear)] == ["to"]
        assert [a.phrase_pattern.fragment for a in patterns_for_variant(natural)] == [
            "Would you",
            "to",
        ]

    def test_absent_is_hidden_present_is_heard(self, phrases, accent):
        phrase = self._phrase(phrases)
        natural = tts.generate_variant(phrase, Level.NATURAL, accent, provider="mock")
        natural.pattern_checks.filter(phrase_pattern__fragment="to").update(verification=V.ABSENT)
        natural.pattern_checks.filter(phrase_pattern__fragment="Would you").update(
            verification=V.PRESENT,
            realisation="/wʊdʒu/",
            explanation_override_ro="În această înregistrare, „would you” sună ca un cuvânt.",
        )
        applied = patterns_for_variant(natural)
        assert len(applied) == 1
        assert applied[0].heard and applied[0].realisation == "/wʊdʒu/"
        assert applied[0].text.startswith("În această înregistrare")

    def test_verified_present_even_if_not_expected_at_level(self, phrases, accent):
        phrase = self._phrase(phrases)
        clear = tts.generate_variant(phrase, Level.CLEAR, accent, provider="mock")
        pp = phrase.phrase_patterns.get(fragment="Would you")
        AudioVariantPattern.objects.create(
            audio_variant=clear, phrase_pattern=pp, verification=V.PRESENT
        )
        assert "Would you" in [a.phrase_pattern.fragment for a in patterns_for_variant(clear)]

    def _check(self, client, phrase_index=0, answer="like to go"):
        response = client.get(reverse("practice:daily"))
        session = PracticeSession.objects.get(pk=response.url.rstrip("/").split("/")[-1])
        client.get(response.url)
        attempt = ListeningAttempt.objects.filter(session_item__session=session).first()
        body = client.post(
            reverse("practice:check", args=[attempt.pk]), {"answer": answer}, **HTMX
        ).content.decode()
        attempt.refresh_from_db()
        return attempt, body

    def test_ui_labels_heard_vs_tendency_and_hides_absent(self, client, plans, accent, phrases):
        attempt, _ = self._check(client)
        variant = attempt.audio_variant
        checks = list(variant.pattern_checks.select_related("phrase_pattern"))
        assert checks, "expected pattern rows for the variant"
        present, *rest = checks
        present.verification = V.PRESENT
        present.save()
        for c in rest:
            c.verification = V.ABSENT
            c.save()
        page = client.get(
            reverse("practice:session", args=[attempt.session_item.session_id]) + "?pas=1"
        ).content.decode()
        assert "În această înregistrare" in page

        def shown(pp):
            return f'explain-item__frag" lang="en-GB">{pp.fragment}<' in page

        assert shown(present.phrase_pattern)
        for c in rest:
            assert not shown(c.phrase_pattern)

    def test_unverified_is_shown_only_as_tendency(self, client, plans, accent, phrases):
        _, body = self._check(client)
        assert "Tendință frecventă în vorbirea naturală" in body
        assert "În această înregistrare" not in body

    def test_mistakes_only_attributed_to_patterns_in_this_recording(
        self, client, plans, accent, phrases
    ):
        attempt, _ = self._check(client, answer="nothing matches here")
        attempt.audio_variant.pattern_checks.update(verification=V.ABSENT)
        AttemptMistake.objects.filter(attempt=attempt).delete()
        from apps.practice.services.sessions import save_mistakes
        from apps.scoring.services import score_answer

        save_mistakes(attempt, score_answer(attempt.phrase.text, "nothing matches here"))
        assert not AttemptMistake.objects.filter(
            attempt=attempt, speech_pattern__isnull=False
        ).exists()


@pytest.mark.django_db
class TestQAPermissions:
    def test_anonymous_and_normal_users_cannot_review(self, client, user, phrases, accent):
        variant = make_variant(phrases[0], accent, status=QA.PENDING)
        review = reverse("admin:listening_audiovariant_review")
        status = reverse("admin:listening_audiovariant_review_status", args=[variant.pk])
        assert client.get(review).status_code == 302  # to admin login
        client.force_login(user)
        assert client.get(review).status_code == 302
        client.post(status, {"status": "approved"})
        variant.refresh_from_db()
        assert variant.qa_status == QA.PENDING

    def test_staff_without_permission_is_forbidden(self, client, phrases, accent):
        staff = User.objects.create_user(
            email="staff@example.com", password="x-123-abc", is_staff=True
        )
        variant = make_variant(phrases[0], accent, status=QA.PENDING)
        client.force_login(staff)
        assert client.get(reverse("admin:listening_audiovariant_review")).status_code == 403
        response = client.post(
            reverse("admin:listening_audiovariant_review_status", args=[variant.pk]),
            {"status": "approved"},
        )
        assert response.status_code == 403

    def test_staff_with_permission_can_approve_and_reject(self, client, phrases, accent):
        staff = User.objects.create_user(
            email="qa@example.com", password="x-123-abc", is_staff=True
        )
        staff.user_permissions.add(
            *Permission.objects.filter(codename__in=["view_audiovariant", "change_audiovariant"])
        )
        variant = make_variant(phrases[0], accent, status=QA.PENDING)
        review_all(variant)
        client.force_login(staff)
        page = client.get(reverse("admin:listening_audiovariant_review") + "?pilot=0")
        assert page.status_code == 200 and phrases[0].text in page.content.decode()
        url = reverse("admin:listening_audiovariant_review_status", args=[variant.pk])
        client.post(url, {"status": "approved", "qa_notes": "natural, clear"})
        variant.refresh_from_db()
        assert variant.qa_status == QA.APPROVED and variant.reviewed_by == staff
        assert variant.qa_notes == "natural, clear" and variant.reviewed_at is not None
        client.post(url, {"status": "rejected"})
        variant.refresh_from_db()
        assert variant.qa_status == QA.REJECTED

    def test_admin_actions_never_approve_mock(self, client, phrases, accent):
        admin_user = User.objects.create_superuser(email="a@example.com", password="x-123-abc")
        mock = make_variant(phrases[0], accent, provider="mock", status=QA.PENDING)
        real = make_variant(phrases[1], accent, provider="openai", status=QA.PENDING)
        review_all(mock)
        review_all(real)
        client.force_login(admin_user)
        client.post(
            reverse("admin:listening_audiovariant_changelist"),
            {"action": "approve_selected", "_selected_action": [mock.pk, real.pk]},
        )
        mock.refresh_from_db()
        real.refresh_from_db()
        assert mock.qa_status == QA.PENDING and real.qa_status == QA.APPROVED


@pytest.mark.django_db
class TestCommands:
    def test_generate_dry_run_makes_no_calls(self, phrases, accent, monkeypatch):
        monkeypatch.setattr(
            tts.MockProvider, "synthesize", lambda *a, **k: pytest.fail("API call in dry run")
        )
        for p in phrases[:3]:
            p.in_pilot = True
            p.save()
        out = StringIO()
        call_command(
            "generate_audio", "--pilot", "--voice", "marin", "--real-api", "--dry-run", stdout=out
        )
        text = out.getvalue()
        assert "3 phrases x 3 levels x 1 voice = 9 audio generations" in text
        assert "openai" in text and "No API calls" not in text and "no API calls" in text

    def test_generate_resumes_and_reports_failures(self, phrases, accent, monkeypatch):
        original = tts.MockProvider.synthesize
        failing_text = phrases[1].text

        def flaky(self, req):
            if req.text == failing_text:
                raise tts.TTSRateLimited("rate limited")
            return original(self, req)

        monkeypatch.setattr(tts.MockProvider, "synthesize", flaky)
        err = StringIO()
        with pytest.raises(CommandError):
            call_command(
                "generate_audio",
                "--provider",
                "mock",
                "--limit",
                "2",
                "--level",
                "clear",
                stdout=StringIO(),
                stderr=err,
            )
        assert "rate_limit" in err.getvalue() and failing_text in err.getvalue()
        assert AudioVariant.objects.filter(phrase=phrases[0]).count() == 1
        monkeypatch.setattr(tts.MockProvider, "synthesize", original)
        out = StringIO()
        call_command(
            "generate_audio", "--provider", "mock", "--limit", "2", "--level", "clear", stdout=out
        )
        assert "1 cached, 1 to generate" in out.getvalue()

    @override_settings(OPENAI_API_KEY="")
    def test_real_api_without_key_fails_clearly(self, phrases, accent):
        with pytest.raises(CommandError, match="OPENAI_API_KEY"):
            call_command("generate_audio", "--real-api", "--limit", "1", stdout=StringIO())

    def test_audition_writes_files_manifest_and_index(self, accent, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path
        call_command(
            "audition_voices",
            "--provider",
            "mock",
            "--voices",
            "marin",
            "cedar",
            "--levels",
            "clear",
            "natural",
            stdout=StringIO(),
        )
        base = tmp_path / "qa" / "tts-audition"
        manifest = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
        assert len(manifest["files"]) == 11 * 2 * 2
        entry = manifest["files"][0]
        for key in [
            "phrase",
            "voice",
            "model",
            "level",
            "accent",
            "instructions",
            "speed",
            "filename",
            "generated_at",
        ]:
            assert key in entry
        assert (base / entry["filename"]).exists()
        assert (base / "index.html").exists()
        assert not AudioVariant.objects.exists()  # audition files are not learner audio
