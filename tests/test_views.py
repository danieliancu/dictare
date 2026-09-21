import re

import pytest
from django.core import mail
from django.urls import reverse

from apps.accounts.models import User
from apps.practice.models import AttemptMistake, ListeningAttempt, PracticeSession, SessionKind
from apps.progress.models import DailyPractice, PatternMastery

HTMX = {"HTTP_HX_REQUEST": "true"}


def start_session(client):
    response = client.get(reverse("practice:daily"))
    assert response.status_code == 302
    session_id = response.url.rstrip("/").split("/")[-1]
    return PracticeSession.objects.get(pk=session_id), response.url


def verify_all_present(attempt):
    """Mark every expected phenomenon of the recording as verified audible (QA done)."""
    from apps.listening.models import AudioVariantPattern

    attempt.audio_variant.pattern_checks.update(
        verification=AudioVariantPattern.Verification.PRESENT
    )


def current_attempt(session):
    return (
        ListeningAttempt.objects.filter(session_item__session=session)
        .order_by("session_item__position")
        .last()
    )


@pytest.mark.django_db
class TestPublicPages:
    @pytest.mark.parametrize(
        "name",
        [
            "core:home",
            "practice:hub",
            "billing:pricing",
            "core:about",
            "core:contact",
            "core:privacy",
            "core:terms",
            "accounts:login",
            "accounts:signup",
            "accounts:password_reset",
        ],
    )
    def test_renders(self, client, plans, name):
        assert client.get(reverse(name)).status_code == 200

    def test_home_has_seo_and_design_copy(self, client, plans):
        html = client.get("/").content.decode()
        assert "Antrenează-te" in html and "pentru engleza britanică" in html
        assert '<link rel="canonical"' in html
        assert 'property="og:title"' in html
        assert 'name="description"' in html
        for text in [
            "Ascultă mai întâi",
            "Exerciții personalizate",
            "Nu mai depinde de subtitrări.",
            "Serie de 12 zile",
            "1 din 10",
            "Scrie aici ce ai auzit...",
        ]:
            assert text in html
        assert html.count("<h1") == 1

    def test_health_robots_sitemap(self, client):
        assert client.get("/health/").json()["database"] is True
        robots = client.get("/robots.txt").content.decode()
        assert "Disallow: /practice/session/" in robots and "Sitemap:" in robots
        assert b"<urlset" in client.get("/sitemap.xml").content

    def test_404_page(self, client):
        response = client.get("/nu-exista/")
        assert response.status_code == 404
        assert "Pagina nu există" in response.content.decode()

    def test_security_headers(self, client):
        response = client.get("/")
        assert "Content-Security-Policy-Report-Only" in response.headers
        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["X-Content-Type-Options"] == "nosniff"


@pytest.mark.django_db
class TestAuthProtection:
    @pytest.mark.parametrize("name", ["progress:progress", "progress:mistakes", "accounts:account"])
    def test_private_pages_redirect_to_login(self, client, name):
        response = client.get(reverse(name))
        assert response.status_code == 302
        assert response.url.startswith(reverse("accounts:login"))

    def test_pattern_and_personalized_require_login(self, client, patterns):
        assert client.post(reverse("practice:pattern", args=["weak-form"])).status_code == 302
        assert client.post(reverse("practice:personalized")).status_code == 302

    def test_private_pages_are_noindex(self, client, user):
        client.force_login(user)
        assert b"noindex" in client.get(reverse("progress:progress")).content


@pytest.mark.django_db
class TestAccounts:
    def test_signup_logs_in_and_sends_verification(self, client, plans, accent, phrases):
        response = client.post(
            reverse("accounts:signup"),
            {
                "first_name": "Ana",
                "email": "Nou@Example.com",
                "password": "o-parola-lunga-9",
            },
        )
        assert response.status_code == 302
        user = User.objects.get(email="nou@example.com")
        assert not user.email_verified
        assert len(mail.outbox) == 1
        link = re.search(r"http\S+/verify-email/\S+/", mail.outbox[0].body).group(0)
        path = link.split("://", 1)[1].split("/", 1)[1]
        assert client.get("/" + path).status_code == 200
        user.refresh_from_db()
        assert user.email_verified

    def test_signup_validation(self, client, plans, user):
        response = client.post(reverse("accounts:signup"), {"email": user.email, "password": "123"})
        assert response.status_code == 200
        assert "Există deja un cont" in response.content.decode()

    def test_login_logout(self, client, user):
        response = client.post(
            reverse("accounts:login"),
            {"username": "ana@example.com", "password": "parola-sigura-123"},
        )
        assert response.status_code == 302
        assert client.get(reverse("accounts:account")).status_code == 200
        client.post(reverse("accounts:logout"))
        assert client.get(reverse("accounts:account")).status_code == 302

    def test_password_reset_email(self, client, user):
        client.post(reverse("accounts:password_reset"), {"email": user.email})
        assert len(mail.outbox) == 1
        assert "/password-reset/" in mail.outbox[0].body

    def test_signup_claims_trial_attempts(self, client, plans, accent, phrases):
        session, url = start_session(client)
        client.get(url)
        attempt = current_attempt(session)
        client.post(reverse("practice:check", args=[attempt.pk]), {"answer": "hello"}, **HTMX)
        client.post(
            reverse("accounts:signup"),
            {"email": "claim@example.com", "password": "o-parola-lunga-9"},
        )
        user = User.objects.get(email="claim@example.com")
        attempt.refresh_from_db()
        assert attempt.user == user
        assert DailyPractice.objects.filter(user=user, completed_count=1).exists()


@pytest.mark.django_db
class TestPracticeFlow:
    def test_anonymous_trial_full_loop(self, client, plans, accent, phrases):
        session, url = start_session(client)
        assert session.kind == SessionKind.TRIAL and session.user is None
        page = client.get(url)
        assert page.status_code == 200
        html = page.content.decode()
        attempt = current_attempt(session)
        # Listen first: the transcript is not in the page before checking.
        assert attempt.phrase.text not in html
        assert "data-player" in html and "1 din" in html

        response = client.post(
            reverse("practice:check", args=[attempt.pk]), {"answer": attempt.phrase.text}, **HTMX
        )
        assert response.status_code == 200
        body = response.content.decode()
        assert "correction__line--right" in body and "Tendință frecventă în vorbirea naturală" in body
        attempt.refresh_from_db()
        assert attempt.completed and attempt.score == 100
        assert response.headers["HX-Trigger"] == "progress-updated"

    def test_check_saves_mistakes_with_patterns(self, client, user, accent, phrases):
        client.force_login(user)
        session, url = start_session(client)
        client.get(url)
        attempt = current_attempt(session)
        verify_all_present(attempt)
        words = attempt.phrase.text.split()
        client.post(
            reverse("practice:check", args=[attempt.pk]), {"answer": " ".join(words[1:])}, **HTMX
        )
        mistake = AttemptMistake.objects.get(attempt=attempt, mistake_type="missing")
        assert mistake.position == 0
        assert DailyPractice.objects.get(user=user).completed_count == 1
        assert PatternMastery.objects.filter(user=user).exists()

    def test_empty_answer_is_a_validation_error(self, client, plans, accent, phrases):
        session, url = start_session(client)
        client.get(url)
        attempt = current_attempt(session)
        response = client.post(
            reverse("practice:check", args=[attempt.pk]), {"answer": "  "}, **HTMX
        )
        assert response.status_code == 422
        assert "Scrie ce ai auzit" in response.content.decode()
        attempt.refresh_from_db()
        assert not attempt.completed

    def test_reveal_marks_transcript_dependency(self, client, plans, accent, phrases):
        session, url = start_session(client)
        client.get(url)
        attempt = current_attempt(session)
        response = client.post(
            reverse("practice:reveal", args=[attempt.pk]), {"answer": ""}, **HTMX
        )
        assert attempt.phrase.text.split()[0] in response.content.decode()
        attempt.refresh_from_db()
        assert attempt.completed and attempt.revealed_before_check and attempt.score == 0

    def test_check_is_idempotent(self, client, plans, accent, phrases):
        session, url = start_session(client)
        client.get(url)
        attempt = current_attempt(session)
        check = reverse("practice:check", args=[attempt.pk])
        client.post(check, {"answer": attempt.phrase.text}, **HTMX)
        client.post(check, {"answer": "something else"}, **HTMX)
        attempt.refresh_from_db()
        assert attempt.score == 100

    def test_next_and_completion(self, client, user, accent, phrases):
        client.force_login(user)
        session, url = start_session(client)
        for position in range(session.target_count):
            page = client.get(f"{url}?pas={position + 1}", **HTMX)
            assert f"{position + 1} din {session.target_count}" in page.content.decode()
            attempt = current_attempt(session)
            client.post(reverse("practice:check", args=[attempt.pk]), {"answer": "hello"}, **HTMX)
        session.refresh_from_db()
        assert session.completed_at is not None
        assert "Sesiune terminată" in client.get(url).content.decode()

    def test_cannot_skip_ahead(self, client, plans, accent, phrases):
        session, url = start_session(client)
        html = client.get(f"{url}?pas=4").content.decode()
        assert f"1 din {session.target_count}" in html

    def test_listen_telemetry_is_clamped(self, client, plans, accent, phrases):
        session, url = start_session(client)
        client.get(url)
        attempt = current_attempt(session)
        response = client.post(
            reverse("practice:listen", args=[attempt.pk]),
            {"plays": 9999, "replays": 2, "ms": 10**9, "slowed": "1"},
        )
        assert response.status_code == 204
        attempt.refresh_from_db()
        assert attempt.listened_count == 50
        assert attempt.replay_count == 2
        assert attempt.time_spent_ms == 30 * 60 * 1000
        assert attempt.slowed_down

    def test_anonymous_trial_limit(self, client, plans, accent, phrases, settings):
        settings.ANONYMOUS_TRIAL_EXERCISES = 2
        session, url = start_session(client)
        for _ in range(2):
            client.get(url)
            attempt = current_attempt(session)
            client.post(reverse("practice:check", args=[attempt.pk]), {"answer": "x"}, **HTMX)
        other = PracticeSession.objects.create(
            anon_key=session.anon_key,
            kind=SessionKind.TRIAL,
            accent=accent,
            local_date=session.local_date,
            target_count=1,
        )
        other.items.create(phrase=phrases[-1], position=0)
        html = client.get(reverse("practice:session", args=[other.pk])).content.decode()
        assert "Creează cont" in html

    def test_signup_nudge_after_a_few_exercises(self, client, plans, accent, phrases, settings):
        settings.ANONYMOUS_SIGNUP_NUDGE_AFTER = 1
        session, url = start_session(client)
        client.get(url)
        attempt = current_attempt(session)
        body = client.post(
            reverse("practice:check", args=[attempt.pk]), {"answer": "x"}, **HTMX
        ).content.decode()
        assert "Creează cont pentru a-ți salva progresul." in body

    def test_no_exercises_state(self, client, plans, accent):
        response = client.get(reverse("practice:daily"))
        assert response.status_code == 200
        assert "Nu există exerciții" in response.content.decode()


@pytest.mark.django_db
class TestGatingAndPermissions:
    def test_other_users_attempt_is_404(self, client, user, other_user, accent, phrases):
        client.force_login(user)
        session, url = start_session(client)
        client.get(url)
        attempt = current_attempt(session)
        client.force_login(other_user)
        for name in ["practice:check", "practice:reveal", "practice:level", "practice:listen"]:
            response = client.post(
                reverse(name, args=[attempt.pk]), {"answer": "x", "level": "clear"}
            )
            assert response.status_code == 404, name
        assert client.get(url).status_code == 404

    def test_anonymous_cannot_touch_user_attempt(self, client, user, accent, phrases):
        client.force_login(user)
        session, url = start_session(client)
        client.get(url)
        attempt = current_attempt(session)
        client.logout()
        assert (
            client.post(reverse("practice:check", args=[attempt.pk]), {"answer": "x"}).status_code
            == 404
        )

    def test_free_user_cannot_switch_to_fast(self, client, user, accent, phrases):
        client.force_login(user)
        session, url = start_session(client)
        client.get(url)
        attempt = current_attempt(session)
        body = client.post(
            reverse("practice:level", args=[attempt.pk]), {"level": "fast"}, **HTMX
        ).content.decode()
        assert "planul Pro" in body
        attempt.refresh_from_db()
        assert attempt.level == "clear"

    def test_pro_user_can_switch_level(self, client, pro_user, accent, phrases):
        client.force_login(pro_user)
        session, url = start_session(client)
        client.get(url)
        attempt = current_attempt(session)
        client.post(reverse("practice:level", args=[attempt.pk]), {"level": "fast"}, **HTMX)
        attempt.refresh_from_db()
        assert attempt.level == "fast"
        assert attempt.audio_variant.level == "fast"

    def test_personalized_is_pro_only(self, client, user, pro_user, accent, phrases):
        client.force_login(user)
        response = client.post(reverse("practice:personalized"))
        assert response.url == reverse("billing:pricing")
        client.force_login(pro_user)
        response = client.post(reverse("practice:personalized"))
        assert "/practice/session/" in response.url

    def test_free_daily_limit(self, client, user, accent, phrases, plans):
        plans["free"].daily_exercise_limit = 1
        plans["free"].save()
        client.force_login(user)
        session, url = start_session(client)
        client.get(url)
        attempt = current_attempt(session)
        client.post(reverse("practice:check", args=[attempt.pk]), {"answer": "x"}, **HTMX)
        html = client.get(f"{url}?pas=2").content.decode()
        assert "Gata pentru azi" in html

    def test_pattern_session_filters_phrases(self, client, user, accent, phrases, patterns):
        client.force_login(user)
        response = client.post(reverse("practice:pattern", args=["assimilation"]))
        session = PracticeSession.objects.get(pk=response.url.rstrip("/").split("/")[-1])
        assert session.kind == SessionKind.PATTERN
        assert all(
            item.phrase.phrase_patterns.filter(pattern__slug="assimilation").exists()
            for item in session.items.all()
        )


@pytest.mark.django_db
class TestProgressPages:
    def test_empty_states(self, client, user):
        client.force_login(user)
        assert "Încă nu ai progres" in client.get(reverse("progress:progress")).content.decode()
        assert "Nicio greșeală încă" in client.get(reverse("progress:mistakes")).content.decode()

    def test_dashboard_after_practice(self, client, user, accent, phrases):
        client.force_login(user)
        session, url = start_session(client)
        client.get(url)
        attempt = current_attempt(session)
        verify_all_present(attempt)
        client.post(reverse("practice:check", args=[attempt.pk]), {"answer": "would"}, **HTMX)
        html = client.get(reverse("progress:progress")).content.decode()
        assert "Serie zilnică" in html and "zi la rând" in html
        partial = client.get(reverse("progress:progress"), **HTMX).content.decode()
        assert "<html" not in partial and "Scor general" in partial
        mistakes = client.get(reverse("progress:mistakes")).content.decode()
        assert "Exersează acest tipar" in mistakes

    def test_streak_fragment(self, client, user):
        client.force_login(user)
        assert b"Serie de 0 zile" in client.get(reverse("progress:streak")).content

    def test_home_shows_real_values_for_logged_in_user(self, client, user, plans):
        client.force_login(user)
        html = client.get("/").content.decode()
        assert "Exemplu." not in html


@pytest.mark.django_db
def test_seed_demo_command(seeded):
    from apps.listening.models import ListeningPhrase, SpeechPattern, Topic

    assert ListeningPhrase.objects.count() >= 50
    assert Topic.objects.count() == 20
    assert SpeechPattern.objects.count() >= 9
    assert ListeningPhrase.objects.filter(text="Shall we head off?").exists()
