"""Topics grouped into sections for the practice hub, with per-user progress."""

from __future__ import annotations

from dataclasses import dataclass, field

from django.db.models import Count, Q

from apps.listening.models import Topic

# Presentation grouping only (topics themselves are managed in the admin).
TOPIC_SECTIONS = [
    (
        "Viața de zi cu zi",
        ["everyday", "shopping", "friends", "small-talk", "home", "eating-out", "family"],
    ),
    (
        "Muncă și servicii",
        [
            "work",
            "phone-calls",
            "healthcare",
            "school",
            "job-interview",
            "banking",
            "renting",
            "deliveries",
        ],
    ),
    (
        "Pe drum și în ritm rapid",
        ["transport", "airport", "driving", "directions", "fast-british"],
    ),
]
OTHER_SECTION = "Alte teme"


@dataclass
class TopicCard:
    topic: Topic
    total: int
    done: int


@dataclass
class TopicSection:
    title: str
    cards: list[TopicCard] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(c.total for c in self.cards)


def topic_sections(user) -> list[TopicSection]:
    topics = list(
        Topic.objects.filter(active=True).annotate(
            total=Count("phrases", filter=Q(phrases__active=True), distinct=True)
        )
    )
    done: dict[int, int] = {}
    if user is not None and user.is_authenticated:
        from apps.practice.models import ListeningAttempt

        rows = (
            ListeningAttempt.objects.filter(user=user, completed=True, phrase__active=True)
            .values("phrase__topic_id")
            .annotate(n=Count("phrase", distinct=True))
        )
        done = {r["phrase__topic_id"]: r["n"] for r in rows}

    by_slug = {t.slug: t for t in topics}
    placed: set[int] = set()
    sections = []
    for title, slugs in TOPIC_SECTIONS:
        cards = [
            TopicCard(by_slug[s], by_slug[s].total, done.get(by_slug[s].pk, 0))
            for s in slugs
            if s in by_slug and by_slug[s].total
        ]
        placed.update(c.topic.pk for c in cards)
        if cards:
            sections.append(TopicSection(title, cards))
    rest = [
        TopicCard(t, t.total, done.get(t.pk, 0)) for t in topics if t.pk not in placed and t.total
    ]
    if rest:
        sections.append(TopicSection(OTHER_SECTION, rest))
    return sections
