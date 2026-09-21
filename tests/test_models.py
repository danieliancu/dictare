import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError

from apps.listening.models import ListeningPhrase, PhrasePattern
from apps.listening.validators import validate_audio_file
from apps.practice.models import ListeningAttempt


@pytest.mark.django_db
class TestPhrase:
    def test_slug_is_generated_and_unique(self, topic):
        a = ListeningPhrase.objects.create(text="Shall we head off?", topic=topic)
        b = ListeningPhrase.objects.create(text="Shall we head off!!", topic=topic)
        assert a.slug == "shall-we-head-off"
        assert b.slug == "shall-we-head-off-2"

    def test_pattern_span_is_located(self, phrases):
        pp = phrases[0].phrase_patterns.get(fragment="to")
        assert (pp.start_token, pp.end_token) == (3, 3)
        wy = phrases[0].phrase_patterns.get(fragment="Would you")
        assert (wy.start_token, wy.end_token) == (0, 1)
        assert wy.covers(1) and not wy.covers(2)

    def test_pattern_fragment_must_exist(self, phrases, patterns):
        pp = PhrasePattern(
            phrase=phrases[0], pattern=patterns["linking"], fragment="banana", explanation_ro="x"
        )
        with pytest.raises(ValidationError):
            pp.clean()


@pytest.mark.django_db
class TestAttempt:
    def test_score_constraint(self, phrases, user):
        with pytest.raises(IntegrityError):
            ListeningAttempt.objects.create(user=user, phrase=phrases[0], score=150)

    def test_owned_by(self, phrases, user, other_user):
        mine = ListeningAttempt.objects.create(user=user, phrase=phrases[0])
        ListeningAttempt.objects.create(user=other_user, phrase=phrases[0])
        anon = ListeningAttempt.objects.create(anon_key="abc", phrase=phrases[0])
        assert list(ListeningAttempt.objects.owned_by(user, None)) == [mine]
        from django.contrib.auth.models import AnonymousUser

        assert list(ListeningAttempt.objects.owned_by(AnonymousUser(), "abc")) == [anon]
        assert not ListeningAttempt.objects.owned_by(AnonymousUser(), "").exists()


class TestAudioValidation:
    def test_rejects_non_audio(self):
        fake = SimpleUploadedFile("x.mp3", b"<html>not audio</html>")
        with pytest.raises(ValidationError):
            validate_audio_file(fake)

    def test_rejects_wrong_extension(self):
        with pytest.raises(ValidationError):
            validate_audio_file(SimpleUploadedFile("x.exe", b"RIFF0000WAVEfmt "))

    def test_accepts_wav(self):
        validate_audio_file(SimpleUploadedFile("x.wav", b"RIFF\x00\x00\x00\x00WAVEfmt "))
