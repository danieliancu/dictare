import pytest
from django.core.management import call_command

from apps.accounts.models import User
from apps.billing.models import Plan, Subscription
from apps.listening.models import (
    Accent,
    ListeningPhrase,
    PatternGroup,
    PhrasePattern,
    SpeechPattern,
    Topic,
)


@pytest.fixture
def plans(db):
    free = Plan.objects.create(
        code=Plan.Code.FREE, name="Gratuit", price_monthly=0, daily_exercise_limit=10, order=0
    )
    pro = Plan.objects.create(
        code=Plan.Code.PRO,
        name="Pro",
        price_monthly=7.99,
        daily_exercise_limit=None,
        natural_level=True,
        fast_level=True,
        full_mistake_history=True,
        personalized_training=True,
        advanced_progress=True,
        order=1,
    )
    return {"free": free, "pro": pro}


@pytest.fixture
def accent(db):
    return Accent.objects.create(
        code="ssb",
        name_ro="Standard Southern British",
        name_en="SSB",
        is_default=True,
        tts_supported=True,
    )


@pytest.fixture
def topic(db):
    return Topic.objects.create(slug="everyday", name_ro="Zi cu zi", name_en="Everyday")


@pytest.fixture
def patterns(db):
    return {
        "weak-form": SpeechPattern.objects.create(
            slug="weak-form",
            name_ro="Forme slabe",
            name_en="Weak forms",
            description_ro="...",
            group=PatternGroup.WEAK_FORMS,
        ),
        "linking": SpeechPattern.objects.create(
            slug="linking",
            name_ro="Legare",
            name_en="Linking",
            description_ro="...",
            group=PatternGroup.LINKING,
        ),
        "assimilation": SpeechPattern.objects.create(
            slug="assimilation",
            name_ro="Asimilare",
            name_en="Assimilation",
            description_ro="...",
            group=PatternGroup.LINKING,
        ),
    }


PHRASES = [
    ("Would you like to go?", 1, [("assimilation", "Would you"), ("weak-form", "to")]),
    ("Have you got a minute?", 1, [("weak-form", "Have you")]),
    ("Shall we head off?", 1, [("linking", "head off")]),
    ("Do you fancy grabbing a coffee?", 2, [("linking", "grabbing a")]),
    ("I'll sort it out later.", 2, [("linking", "sort it out")]),
    ("You could have told me earlier.", 2, [("weak-form", "could have")]),
    ("I might pop in on the way home.", 2, [("linking", "pop in on")]),
]


@pytest.fixture
def phrases(db, topic, patterns, accent):
    out = []
    for text, difficulty, pps in PHRASES:
        phrase = ListeningPhrase.objects.create(
            text=text, topic=topic, difficulty=difficulty, translation_ro="traducere"
        )
        for slug, fragment in pps:
            PhrasePattern(
                phrase=phrase,
                pattern=patterns[slug],
                fragment=fragment,
                explanation_ro="Explicație.",
            ).save()
        out.append(phrase)
    return out


@pytest.fixture
def user(db, plans):
    return User.objects.create_user(email="ana@example.com", password="parola-sigura-123")


@pytest.fixture
def other_user(db, plans):
    return User.objects.create_user(email="radu@example.com", password="parola-sigura-123")


@pytest.fixture
def pro_user(db, plans):
    u = User.objects.create_user(email="pro@example.com", password="parola-sigura-123")
    Subscription.objects.create(user=u, plan=plans["pro"], status="active")
    return u


@pytest.fixture
def seeded(db):
    call_command("seed_demo", "--no-audio", "--no-demo-user", verbosity=0)


@pytest.fixture(autouse=True)
def no_real_openai(settings, monkeypatch, request):
    """The suite never talks to OpenAI: no key, and any unmocked client call fails loudly."""
    settings.OPENAI_API_KEY = ""
    if request.node.get_closest_marker("allow_openai_client"):
        return

    def refuse(self):
        raise AssertionError("A test tried to create a real OpenAI client (network call).")

    from apps.ai.services import tts

    monkeypatch.setattr(tts.OpenAIProvider, "_client", refuse)
