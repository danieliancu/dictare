"""Voice choice (Marin / Ballad / Cedar): preference, sessions, selection, generation."""

import json
from io import StringIO

import pytest
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.management import CommandError, call_command
from django.test import override_settings
from django.urls import reverse

from apps.accounts.forms import ProfileForm
from apps.accounts.models import Profile
from apps.ai.services import tts
from apps.listening.models import AudioVariant, Level
from apps.listening.services.audio import get_audio_variant, phrase_ids_with_audio
from apps.listening.voices import DEFAULT_VOICE, VOICE_CHOICES, VOICE_VALUES
from apps.practice.models import ListeningAttempt, PracticeSession

QA = AudioVariant.QAStatus
HTMX = {"HTTP_HX_REQUEST": "true"}


def variant(
    phrase,
    accent,
    voice,
    *,
    level=Level.CLEAR,
    provider="openai",
    status=QA.APPROVED,
    with_file=True,
):
    v = AudioVariant(
        phrase=phrase,
        level=level,
        accent=accent,
        voice=voice,
        provider=provider,
        qa_status=status,
        engine_version=str(settings.TTS_ENGINE_VERSION),
    )
    if with_file:
        v.audio_file.save(
            f"{voice}-{provider}-{level}.mp3", ContentFile(b"ID3" + b"0" * 300), save=False
        )
    else:
        v.audio_file.name = f"audio/missing/{voice}.mp3"
    v.save()
    return v


def start_session(client):
    response = client.get(reverse("practice:daily"))
    return PracticeSession.objects.get(pk=response.url.rstrip("/").split("/")[-1]), response.url


# --- definition & settings --------------------------------------------------------------------


def test_product_voices_are_exactly_marin_ballad_cedar():
    assert VOICE_VALUES == ["marin", "ballad", "cedar"]
    assert dict(VOICE_CHOICES) == {"marin": "Marin", "ballad": "Ballad", "cedar": "Cedar"}
    assert DEFAULT_VOICE == "marin"


def test_settings_agree_with_the_product_voices():
    assert settings.TTS_VOICE == DEFAULT_VOICE
    assert list(settings.TTS_AUDITION_VOICES) == VOICE_VALUES


@pytest.mark.django_db
class TestPreference:
    def test_profile_default_is_marin(self, user):
        assert user.profile.preferred_voice == "marin"
        field = Profile._meta.get_field("preferred_voice")
        assert [value for value, _ in field.choices] == VOICE_VALUES

    def test_form_saves_ballad(self, user):
        form = ProfileForm(
            {
                "first_name": "Ana",
                "preferred_voice": "ballad",
                "timezone": "Europe/London",
                "daily_goal": 10,
                "preferred_accent": "",
            },
            instance=user.profile,
            user=user,
        )
        assert form.is_valid(), form.errors
        form.save()
        user.profile.refresh_from_db()
        assert user.profile.preferred_voice == "ballad"

    @pytest.mark.parametrize("value", ["fable", "alloy", ""])
    def test_form_rejects_other_voices(self, user, value):
        form = ProfileForm(
            {"preferred_voice": value, "timezone": "Europe/London", "daily_goal": 10},
            instance=user.profile,
            user=user,
        )
        assert not form.is_valid()
        assert "preferred_voice" in form.errors

    def test_account_page_offers_the_three_voices(self, client, user):
        client.force_login(user)
        html = client.get(reverse("accounts:account")).content.decode()
        assert "Vocea exercițiilor" in html
        for label in ["Marin", "Ballad", "Cedar"]:
            assert f">{label}</option>" in html
        assert "fable" not in html.lower()


# --- sessions ---------------------------------------------------------------------------------


@pytest.mark.django_db
class TestSessionVoice:
    def test_session_uses_the_profile_voice(self, client, user, accent, phrases):
        user.profile.preferred_voice = "cedar"
        user.profile.save()
        client.force_login(user)
        session, _ = start_session(client)
        assert session.voice == "cedar"

    def test_visitor_gets_marin(self, client, plans, accent, phrases):
        session, _ = start_session(client)
        assert session.voice == "marin"

    def test_changing_the_preference_does_not_change_the_running_session(
        self, client, user, accent, phrases
    ):
        client.force_login(user)
        session, _ = start_session(client)
        user.profile.preferred_voice = "ballad"
        user.profile.save()
        session.refresh_from_db()
        assert session.voice == "marin"

    def test_session_serves_its_own_voice(self, client, user, accent, phrases):
        for p in phrases:
            for v in VOICE_VALUES:
                variant(p, accent, v)
        user.profile.preferred_voice = "ballad"
        user.profile.save()
        client.force_login(user)
        session, url = start_session(client)
        client.get(url)
        attempt = ListeningAttempt.objects.get(
            session_item__session=session, session_item__position=0
        )
        assert attempt.audio_variant.voice == "ballad"

    def test_completed_attempt_keeps_the_recording_heard(self, client, user, accent, phrases):
        for p in phrases:
            for v in VOICE_VALUES:
                variant(p, accent, v)
        client.force_login(user)
        session, url = start_session(client)
        client.get(url)
        attempt = ListeningAttempt.objects.get(
            session_item__session=session, session_item__position=0
        )
        heard = attempt.audio_variant_id
        client.post(reverse("practice:check", args=[attempt.pk]), {"answer": "x"}, **HTMX)
        user.profile.preferred_voice = "cedar"
        user.profile.save()
        client.get(f"{url}?pas=1")
        attempt.refresh_from_db()
        assert attempt.completed and attempt.audio_variant_id == heard


# --- selection --------------------------------------------------------------------------------


@pytest.mark.django_db
class TestSelectionByVoice:
    def test_requested_voice_is_selected(self, phrases, accent):
        for v in VOICE_VALUES:
            variant(phrases[0], accent, v)
        chosen = get_audio_variant(phrases[0], Level.CLEAR, accent, "ballad")
        assert chosen.voice == "ballad"

    def test_missing_voice_falls_back_to_marin_only(self, phrases, accent):
        marin = variant(phrases[0], accent, "marin")
        variant(phrases[0], accent, "cedar")
        assert get_audio_variant(phrases[0], Level.CLEAR, accent, "ballad") == marin

    def test_never_falls_back_to_another_non_default_voice(self, phrases, accent):
        variant(phrases[0], accent, "cedar")
        with override_settings(TTS_REQUIRE_APPROVAL=True):
            assert get_audio_variant(phrases[0], Level.CLEAR, accent, "ballad") is None

    def test_orphaned_requested_voice_falls_back_to_marin(self, phrases, accent):
        variant(phrases[0], accent, "ballad", with_file=False)
        marin = variant(phrases[0], accent, "marin")
        assert get_audio_variant(phrases[0], Level.CLEAR, accent, "ballad") == marin

    @override_settings(TTS_REQUIRE_APPROVAL=True)
    def test_pending_requested_voice_is_not_served_in_production(self, phrases, accent):
        variant(phrases[0], accent, "ballad", status=QA.PENDING)
        marin = variant(phrases[0], accent, "marin")
        assert get_audio_variant(phrases[0], Level.CLEAR, accent, "ballad") == marin

    @override_settings(TTS_REQUIRE_APPROVAL=True)
    def test_phrase_ids_follow_the_same_tiers(self, phrases, accent):
        variant(phrases[0], accent, "ballad")
        variant(phrases[1], accent, "marin")
        variant(phrases[2], accent, "cedar")
        assert phrase_ids_with_audio(Level.CLEAR, accent, "ballad") == {
            phrases[0].pk,
            phrases[1].pk,
        }

    @override_settings(TTS_REQUIRE_APPROVAL=True, TTS_GENERATE_ON_REQUEST=False)
    def test_production_session_has_no_phrase_without_voice_or_marin(
        self, client, plans, accent, phrases
    ):
        variant(phrases[0], accent, "cedar")  # visitor = Marin: cedar alone is not enough
        variant(phrases[1], accent, "marin", with_file=False)
        response = client.get(reverse("practice:daily"))
        assert response.status_code == 200
        assert "Nu există exerciții" in response.content.decode()

    @override_settings(TTS_REQUIRE_APPROVAL=False, TTS_GENERATE_ON_REQUEST=False)
    def test_missing_voice_and_marin_shows_audio_unavailable(self, client, user, accent, phrases):
        for p in phrases:
            variant(p, accent, "cedar")
        user.profile.preferred_voice = "ballad"
        user.profile.save()
        client.force_login(user)
        _, url = start_session(client)
        assert "Audio indisponibil" in client.get(url).content.decode()


# --- generation -------------------------------------------------------------------------------


@pytest.mark.django_db
class TestMultiVoiceGeneration:
    def _pilot(self, phrases, n=2):
        for p in phrases[:n]:
            p.in_pilot = True
            p.save()

    def test_dry_run_counts_without_api_calls(self, phrases, accent, monkeypatch):
        monkeypatch.setattr(
            tts.MockProvider, "synthesize", lambda *a, **k: pytest.fail("API call in dry run")
        )
        self._pilot(phrases)
        out = StringIO()
        call_command(
            "generate_audio",
            "--pilot",
            "--voices",
            "marin",
            "ballad",
            "cedar",
            "--real-api",
            "--dry-run",
            stdout=out,
        )
        text = out.getvalue()
        for line in [
            "2 phrases",
            "3 voices (marin, ballad, cedar)",
            "3 levels",
            "18 possible variants",
            "0 already cached",
            "18 to generate",
        ]:
            assert line in text

    def test_each_voice_has_its_own_cache_key(self, phrases, accent):
        keys = {tts.planned_key(phrases[0], Level.CLEAR, accent, v, "openai") for v in VOICE_VALUES}
        assert len(keys) == 3

    def test_generates_all_voices_and_skips_cached(self, phrases, accent):
        self._pilot(phrases, 1)
        tts.generate_variant(phrases[0], Level.CLEAR, accent, voice="ballad", provider="mock")
        out = StringIO()
        call_command(
            "generate_audio",
            "--pilot",
            "--provider",
            "mock",
            "--voices",
            "marin",
            "ballad",
            "cedar",
            stdout=out,
        )
        text = out.getvalue()
        assert "Voice: Marin" in text and "Voice: Ballad" in text and "Voice: Cedar" in text
        assert "Generated: 8\nCached: 1\nFailed: 0" in text
        voices = set(AudioVariant.objects.filter(phrase=phrases[0]).values_list("voice", flat=True))
        assert voices == {"marin", "ballad", "cedar"}
        assert not AudioVariant.objects.exclude(qa_status=QA.PENDING).exists()

    def test_failure_in_one_voice_does_not_stop_the_others_and_resume_works(
        self, phrases, accent, monkeypatch
    ):
        self._pilot(phrases, 1)
        original = tts.MockProvider.synthesize

        def flaky(self, req):
            if req.voice == "ballad":
                raise tts.TTSRateLimited("rate limited")
            return original(self, req)

        monkeypatch.setattr(tts.MockProvider, "synthesize", flaky)
        err = StringIO()
        with pytest.raises(CommandError):
            call_command(
                "generate_audio",
                "--pilot",
                "--provider",
                "mock",
                "--voices",
                "marin",
                "ballad",
                "cedar",
                stdout=StringIO(),
                stderr=err,
            )
        assert "[ballad/clear] rate_limit" in err.getvalue()
        made = set(AudioVariant.objects.values_list("voice", flat=True))
        assert made == {"marin", "cedar"}

        monkeypatch.setattr(tts.MockProvider, "synthesize", original)
        out = StringIO()
        call_command(
            "generate_audio",
            "--pilot",
            "--provider",
            "mock",
            "--voices",
            "marin",
            "ballad",
            "cedar",
            stdout=out,
        )
        assert "Generated: 3\nCached: 6\nFailed: 0" in out.getvalue()

    def test_single_voice_option_still_works(self, phrases, accent):
        self._pilot(phrases, 1)
        out = StringIO()
        call_command(
            "generate_audio",
            "--pilot",
            "--provider",
            "mock",
            "--voice",
            "cedar",
            "--level",
            "clear",
            stdout=out,
        )
        assert "1 voices (cedar)" in out.getvalue()
        assert AudioVariant.objects.get().voice == "cedar"

    def test_default_audition_uses_marin_ballad_cedar(self, accent, tmp_path, settings):
        settings.MEDIA_ROOT = tmp_path
        call_command(
            "audition_voices", "--provider", "mock", "--levels", "clear", stdout=StringIO()
        )
        manifest = json.loads(
            (tmp_path / "qa" / "tts-audition" / "manifest.json").read_text(encoding="utf-8")
        )
        assert {f["voice"] for f in manifest["files"]} == {"marin", "ballad", "cedar"}
