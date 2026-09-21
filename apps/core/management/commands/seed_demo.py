"""Populate a fresh database with content and demo data.

python manage.py seed_demo              # content + mock audio + demo user
python manage.py seed_demo --no-audio   # skip audio generation
python manage.py seed_demo --no-demo-user
"""

from __future__ import annotations

import random
from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.ai.services.tts import TTSUnavailable, get_or_create_variant
from apps.billing.models import Plan, Subscription
from apps.core.models import Testimonial
from apps.listening.models import (
    Accent,
    Level,
    ListeningPhrase,
    PatternGroup,
    PhrasePattern,
    SpeechPattern,
    Topic,
)
from apps.listening.seed_data import PHRASES
from apps.practice.models import ListeningAttempt, PracticeSession, SessionItem, SessionKind
from apps.practice.services.sessions import save_mistakes
from apps.progress.models import DailyPractice
from apps.progress.services import mastery
from apps.scoring.normalize import FUNCTION_WORDS, surface_tokens
from apps.scoring.services import score_answer

TOPICS = [
    ("everyday", "Conversații de zi cu zi", "Everyday conversations", "home"),
    ("work", "La muncă", "Work", "briefcase"),
    ("shopping", "Cumpărături", "Shopping", "bag"),
    ("phone-calls", "Convorbiri telefonice", "Phone calls", "phone"),
    ("transport", "Transport", "Transport", "bus"),
    ("healthcare", "La medic", "Healthcare", "health"),
    ("school", "Școală", "School", "school"),
    ("friends", "Cu prietenii", "Friends", "coffee"),
    ("small-talk", "Small talk", "Small talk", "sun"),
    ("fast-british", "Engleză britanică rapidă", "Fast British speech", "zap"),
]

ACCENTS = [
    # code, RO, EN, active, tts_supported, default, instructions, description
    (
        "ssb",
        "Standard Southern British",
        "Standard Southern British",
        True,
        True,
        True,
        "Use a Standard Southern British English accent (the modern standard accent of "
        "southern England).",
        "Accentul standard modern din sudul Angliei; cel mai des auzit la BBC și în Londra.",
    ),
    (
        "modern-rp",
        "Modern RP",
        "Modern Received Pronunciation",
        True,
        True,
        False,
        "Use a Modern Received Pronunciation British English accent.",
        "Pronunția „educată” modernă, clară, folosită des în media.",
    ),
    (
        "london",
        "Londra",
        "London",
        False,
        False,
        False,
        "",
        "Varietăți urbane londoneze. Necesită înregistrări umane: "
        "sinteza vocală nu le redă fiabil.",
    ),
    (
        "estuary",
        "Estuary English",
        "Estuary English",
        False,
        False,
        False,
        "",
        "Între RP și accentul londonez (glottal t, „l” vocalizat). Necesită înregistrări umane.",
    ),
    (
        "northern",
        "Nordul Angliei",
        "Northern English",
        False,
        False,
        False,
        "",
        "Manchester, Leeds, Newcastle etc. — vocale diferite (ex. „bath”, „strut”). "
        "Necesită înregistrări umane.",
    ),
    (
        "scottish",
        "Scoțian",
        "Scottish",
        False,
        False,
        False,
        "",
        "Accente scoțiene, de obicei rotice („r” pronunțat). Necesită înregistrări umane.",
    ),
    (
        "welsh",
        "Galez",
        "Welsh",
        False,
        False,
        False,
        "",
        "Accente din Țara Galilor, cu intonație specifică. Necesită înregistrări umane.",
    ),
]

PATTERNS = [
    (
        "weak-form",
        "Forme slabe",
        "Weak forms",
        PatternGroup.WEAK_FORMS,
        "Cuvintele gramaticale neaccentuate (to, of, for, can, was) se pronunță scurt, "
        "adesea cu vocala /ə/.",
    ),
    (
        "reduced-function-word",
        "Cuvinte funcționale reduse",
        "Reduced function words",
        PatternGroup.WEAK_FORMS,
        "Pronume și auxiliare (are you, your, have you) se reduc atât de mult "
        "încât aproape dispar.",
    ),
    (
        "schwa",
        "Schwa /ə/",
        "Schwa",
        PatternGroup.WEAK_FORMS,
        "Cea mai frecventă vocală din engleză: un sunet scurt, neutru, în silabele neaccentuate.",
    ),
    (
        "linking",
        "Legarea cuvintelor",
        "Linking",
        PatternGroup.LINKING,
        "Consoana de la finalul unui cuvânt se lipește de vocala cuvântului următor.",
    ),
    (
        "linking-r",
        "„R” de legătură",
        "Linking R",
        PatternGroup.LINKING,
        "În engleza britanică „r”-ul final nu se pronunță, dar reapare înaintea unei vocale.",
    ),
    (
        "intrusive-r",
        "„R” intruziv",
        "Intrusive R",
        PatternGroup.LINKING,
        "Un „r” care nu e scris apare între două vocale (ex. „law and order”).",
    ),
    (
        "assimilation",
        "Asimilare",
        "Assimilation",
        PatternGroup.LINKING,
        "Un sunet se schimbă sub influența celui vecin (ex. „did you” → /dɪdʒu/).",
    ),
    (
        "elision",
        "Eliziune",
        "Elision",
        PatternGroup.LINKING,
        "Un sunet dispare, de obicei /t/ sau /d/ între consoane (ex. „next day”).",
    ),
    (
        "contraction",
        "Forme contrase",
        "Contractions",
        PatternGroup.FREQUENT,
        "I'll, didn't, you're: forme scurte care se aud foarte diferit de forma completă.",
    ),
    (
        "everyday-reduction",
        "Reduceri uzuale",
        "Everyday reductions",
        PatternGroup.FREQUENT,
        "„going to” → „gonna”, „let me” → „lemme”: reduceri informale foarte frecvente.",
    ),
    (
        "fast-phrase",
        "Expresii rapide",
        "Fast phrases",
        PatternGroup.FREQUENT,
        "Expresii fixe spuse dintr-o suflare, recunoscute mai mult după ritm decât după cuvinte.",
    ),
    (
        "glottal-t",
        "T glotal",
        "T-glottalisation",
        PatternGroup.ACCENTS,
        "În multe accente britanice, /t/ devine o scurtă oprire în gât (ex. „got a” → „go'a”).",
    ),
    (
        "dropped-consonant",
        "Consoane căzute",
        "Dropped consonants",
        PatternGroup.ACCENTS,
        "Sunete ca /h/ din „him”, „his”, „he” dispar când cuvântul nu e accentuat.",
    ),
]

PLANS = [
    {
        "code": Plan.Code.FREE,
        "name": "Gratuit",
        "order": 0,
        "price_monthly": 0,
        "tagline": "Tot ce îți trebuie ca să începi.",
        "daily_exercise_limit": 10,
        "natural_level": False,
        "fast_level": False,
        "full_mistake_history": False,
        "personalized_training": False,
        "advanced_progress": False,
        "features_ro": "10 exerciții pe zi\nEngleză britanică clară\nTranscrieri și explicații\n"
        "Progres de bază și serie zilnică",
    },
    {
        "code": Plan.Code.PRO,
        "name": "Pro",
        "order": 1,
        "price_monthly": 7.99,
        "tagline": "Pentru cei care vor să înțeleagă engleza de pe stradă.",
        "daily_exercise_limit": None,
        "natural_level": True,
        "fast_level": True,
        "full_mistake_history": True,
        "personalized_training": True,
        "advanced_progress": True,
        "features_ro": "Exerciții nelimitate\nEngleză naturală și Engleză rapidă\n"
        "Istoric complet al greșelilor\nAntrenament personalizat pe tiparele tale\n"
        "Progres avansat pe fiecare tipar",
    },
]

TESTIMONIALS = [
    (
        "Înainte nu înțelegeam engleza când oamenii vorbeau, dar acum chiar înțeleg ce spun.",
        "Sophie L.",
        "Franța",
        "FR",
    ),
    (
        "Lucrez în Londra de doi ani. Abia acum prind ce spun colegii la pauza de cafea.",
        "Andrei M.",
        "România",
        "RO",
    ),
    (
        "Explicațiile despre formele slabe m-au ajutat mai mult decât orice curs.",
        "Ioana P.",
        "România",
        "RO",
    ),
    (
        "Exerciții scurte, zilnice. Exact ce aveam nevoie ca să nu mă mai bazez pe subtitrări.",
        "Mihai D.",
        "Moldova",
        "MD",
    ),
]


class Command(BaseCommand):
    help = "Seed topics, accents, speech patterns, phrases, plans, testimonials and demo data."

    def add_arguments(self, parser):
        parser.add_argument("--no-audio", action="store_true", help="Skip audio generation.")
        parser.add_argument("--no-demo-user", action="store_true", help="Skip demo users.")

    def handle(self, *args, **options):
        with transaction.atomic():
            topics = self.seed_topics()
            self.seed_accents()
            patterns = self.seed_patterns()
            self.seed_phrases(topics, patterns)
            self.seed_plans()
            self.seed_testimonials()
        if not options["no_audio"]:
            self.seed_audio()
        if not options["no_demo_user"]:
            self.seed_demo_users()
        self.stdout.write(self.style.SUCCESS("Seed complet."))

    # --- content ----------------------------------------------------------------------

    def seed_topics(self) -> dict[str, Topic]:
        out = {}
        for order, (slug, ro, en, icon) in enumerate(TOPICS):
            out[slug], _ = Topic.objects.update_or_create(
                slug=slug, defaults={"name_ro": ro, "name_en": en, "icon": icon, "order": order}
            )
        self.stdout.write(f"  teme: {len(out)}")
        return out

    def seed_accents(self) -> None:
        for order, (code, ro, en, active, tts, default, instr, desc) in enumerate(ACCENTS):
            Accent.objects.update_or_create(
                code=code,
                defaults={
                    "name_ro": ro,
                    "name_en": en,
                    "active": active,
                    "tts_supported": tts,
                    "is_default": default,
                    "tts_instructions": instr,
                    "description_ro": desc,
                    "order": order,
                },
            )
        self.stdout.write(f"  accente: {len(ACCENTS)}")

    def seed_patterns(self) -> dict[str, SpeechPattern]:
        out = {}
        for order, (slug, ro, en, group, desc) in enumerate(PATTERNS):
            out[slug], _ = SpeechPattern.objects.update_or_create(
                slug=slug,
                defaults={
                    "name_ro": ro,
                    "name_en": en,
                    "group": group,
                    "description_ro": desc,
                    "order": order,
                },
            )
        self.stdout.write(f"  tipare: {len(out)}")
        return out

    def seed_phrases(self, topics, patterns) -> None:
        for row in PHRASES:
            phrase, _ = ListeningPhrase.objects.update_or_create(
                text=row["text"],
                defaults={
                    "translation_ro": row["translation_ro"],
                    "topic": topics[row["topic"]],
                    "difficulty": row["difficulty"],
                    "active": True,
                },
            )
            phrase.phrase_patterns.all().delete()
            for p in row["patterns"]:
                PhrasePattern(
                    phrase=phrase,
                    pattern=patterns[p["pattern"]],
                    fragment=p["fragment"],
                    sounds_like=p.get("sounds_like", ""),
                    explanation_ro=p["explanation_ro"],
                ).save()
        self.stdout.write(f"  fraze: {len(PHRASES)}")

    def seed_plans(self) -> None:
        for plan in PLANS:
            Plan.objects.update_or_create(code=plan["code"], defaults=plan)

    def seed_testimonials(self) -> None:
        for order, (quote, name, location, cc) in enumerate(TESTIMONIALS):
            Testimonial.objects.update_or_create(
                author_name=name,
                defaults={
                    "quote": quote,
                    "location": location,
                    "country_code": cc,
                    "order": order,
                    "active": True,
                },
            )

    def seed_audio(self) -> None:
        accent = Accent.default()
        made = 0
        try:
            for phrase in ListeningPhrase.objects.active():
                for level in Level.values:
                    get_or_create_variant(phrase, level, accent)
                    made += 1
        except TTSUnavailable as exc:
            self.stdout.write(self.style.WARNING(f"  audio indisponibil: {exc}"))
            return
        self.stdout.write(f"  variante audio ({settings.TTS_PROVIDER}): {made}")

    # --- demo users -------------------------------------------------------------------

    def seed_demo_users(self) -> None:
        password = "dictare-demo-2026"
        pro_plan = Plan.objects.get(code=Plan.Code.PRO)
        for email, name, is_pro in [
            ("demo@dictare.ro", "Ana", True),
            ("free@dictare.ro", "Radu", False),
        ]:
            user, created = User.objects.get_or_create(
                email=email, defaults={"first_name": name, "email_verified": True}
            )
            if created:
                user.set_password(password)
                user.save()
            if is_pro:
                Subscription.objects.update_or_create(
                    user=user, defaults={"plan": pro_plan, "status": "active", "provider": "manual"}
                )
            if not ListeningAttempt.objects.filter(user=user).exists():
                self.build_history(user, streak_days=12 if is_pro else 3)
        self.stdout.write(
            f"  utilizatori demo: demo@dictare.ro (Pro), free@dictare.ro (Gratuit) · "
            f"parola: {password}"
        )

    def build_history(self, user, streak_days: int) -> None:
        """~3 weeks of realistic practice: a current streak, a gap, and improving scores."""
        rng = random.Random(user.email)
        tz = user.profile.tzinfo
        today = user.profile.local_today()
        accent = Accent.default()
        phrases = list(ListeningPhrase.objects.active().prefetch_related("phrase_patterns"))
        days = list(range(streak_days)) + [d for d in range(streak_days + 2, 21) if d % 5 != 0]
        total_days = max(days)

        for offset in sorted(days, reverse=True):
            day = today - timedelta(days=offset)
            progress = 1 - offset / (total_days + 1)  # 0 → 1 over the period
            count = rng.randint(6, 10) if offset else rng.randint(3, 6)
            chosen = rng.sample(phrases, count)
            session = PracticeSession.objects.create(
                user=user,
                kind=SessionKind.DAILY,
                level=Level.CLEAR,
                accent=accent,
                local_date=day,
                target_count=count,
            )
            for pos, phrase in enumerate(chosen):
                item = SessionItem.objects.create(session=session, phrase=phrase, position=pos)
                when = timezone.make_aware(
                    datetime.combine(day, time(8 + pos % 12, rng.randint(0, 59))), tz
                )
                typed = self.simulated_answer(phrase, rng, skill=0.45 + 0.45 * progress)
                result = score_answer(phrase.text, typed)
                revealed = rng.random() < 0.25 * (1 - progress)
                attempt = ListeningAttempt.objects.create(
                    user=user,
                    session_item=item,
                    phrase=phrase,
                    level=Level.CLEAR,
                    typed_answer=typed,
                    score=result.score,
                    word_accuracy=result.word_accuracy,
                    listened_count=rng.randint(1, 4),
                    replay_count=rng.randint(0, 3),
                    time_spent_ms=rng.randint(8000, 60000),
                    slowed_down=rng.random() < 0.2,
                    transcript_revealed=True,
                    revealed_before_check=revealed,
                    completed=True,
                    completed_at=when,
                )
                ListeningAttempt.objects.filter(pk=attempt.pk).update(started_at=when)
                save_mistakes(attempt, result)
            PracticeSession.objects.filter(pk=session.pk).update(
                completed_at=timezone.make_aware(datetime.combine(day, time(21, 0)), tz)
            )
            DailyPractice.objects.update_or_create(
                user=user,
                date=day,
                defaults={"completed_count": count, "goal": user.profile.daily_goal},
            )
        mastery.recompute(user)

    @staticmethod
    def simulated_answer(phrase, rng: random.Random, skill: float) -> str:
        """Drop or blur words the way learners do: weak forms and pattern words go first."""
        hard = set()
        for pp in phrase.phrase_patterns.all():
            hard.update(range(pp.start_token, pp.end_token + 1))
        out = []
        for i, (display, norm) in enumerate(surface_tokens(phrase.text)):
            risk = 0.08
            if norm in FUNCTION_WORDS:
                risk += 0.25
            if i in hard:
                risk += 0.3
            risk *= 1.6 - skill
            roll = rng.random()
            if roll < risk * 0.6:
                continue  # missed completely
            if roll < risk:
                out.append(norm[:-1] if len(norm) > 3 else norm + "s")  # misheard
                continue
            out.append(display)
        return " ".join(out)
