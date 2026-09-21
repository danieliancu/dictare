import pytest

from apps.practice.services.personalization import WeaknessRecommender
from apps.practice.services.selection import choose_phrases
from apps.progress.models import PatternMastery


def test_weak_patterns_get_a_bigger_boost():
    rec = WeaknessRecommender({1: 0.9, 2: 0.1})
    assert rec.phrase_boost([1]) > rec.phrase_boost([2])
    assert rec.phrase_boost([2, 1]) == rec.phrase_boost([1])
    assert rec.weakest_patterns(1) == [1]


@pytest.mark.django_db
def test_selection_prioritises_the_users_weak_pattern(user, phrases, patterns):
    PatternMastery.objects.create(user=user, pattern=patterns["weak-form"], mastery=5, exposures=10)
    PatternMastery.objects.create(user=user, pattern=patterns["linking"], mastery=95, exposures=10)
    PatternMastery.objects.create(
        user=user, pattern=patterns["assimilation"], mastery=95, exposures=10
    )
    rec = WeaknessRecommender.for_user(user)
    weak_ids = {
        p.pk for p in phrases if p.phrase_patterns.filter(pattern__slug="weak-form").exists()
    }
    hits = 0
    for seed in range(40):
        first_three = choose_phrases(user, 3, recommender=rec, seed=seed)
        hits += sum(1 for p in first_three if p.pk in weak_ids)
    # 3 of 7 phrases contain weak forms; without personalisation we'd expect ~51 hits.
    assert hits > 65


@pytest.mark.django_db
def test_selection_filters(user, phrases, topic, patterns):
    only_linking = choose_phrases(user, 10, pattern=patterns["linking"], seed=1)
    assert only_linking
    assert all(p.phrase_patterns.filter(pattern=patterns["linking"]).exists() for p in only_linking)
    assert len({p.pk for p in only_linking}) == len(only_linking)
    easy = choose_phrases(None, 10, max_difficulty=1, seed=1)
    assert all(p.difficulty == 1 for p in easy)
