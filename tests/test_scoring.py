import pytest

from apps.scoring.normalize import expand, normalize_text, tokenize
from apps.scoring.services import Status, score_answer


class TestNormalization:
    def test_case_punctuation_and_whitespace(self):
        assert normalize_text("  Would   you, like TO go?! ") == "would you like to go"

    def test_curly_apostrophes(self):
        assert tokenize("I didn’t realise") == ["i", "didn't", "realise"]

    def test_apostrophe_less_contractions(self):
        assert tokenize("I didnt know") == ["i", "didn't", "know"]

    def test_small_numbers_become_words(self):
        assert tokenize("That's 10 pounds") == ["that's", "ten", "pounds"]

    def test_hyphens_split_words(self):
        assert tokenize("What time's pick-up?") == ["what", "time's", "pick", "up"]

    def test_possessive_is_not_expanded(self):
        assert [t.canon for t in expand(["john's"])] == ["john's"]

    def test_contraction_expansion(self):
        assert [t.canon for t in expand(["i'll", "won't"])] == ["i", "will", "will", "not"]


class TestScoring:
    def test_exact_answer_is_100(self):
        result = score_answer("Would you like to go?", "would you like to go")
        assert result.score == 100
        assert result.word_accuracy == 100
        assert result.mistakes == []

    def test_empty_answer_is_zero(self):
        result = score_answer("Shall we head off?", "")
        assert result.score == 0
        assert result.count(Status.MISSING) == 4

    def test_missing_weak_word_costs_less_than_changed_content_word(self):
        missing_weak = score_answer("Would you like to go?", "would you like go")
        changed_content = score_answer("Would you like to go?", "would you love to go")
        assert missing_weak.words[3].status == Status.MISSING
        assert changed_content.words[2].status == Status.INCORRECT
        assert 80 <= missing_weak.score < 100
        assert changed_content.score < missing_weak.score

    def test_extra_word(self):
        result = score_answer("Shall we head off?", "shall we head off now")
        assert result.count(Status.EXTRA) == 1
        assert result.score < 100
        assert result.word_accuracy == 100

    def test_word_order_mistake(self):
        result = score_answer("Have you got a minute?", "you have got a minute")
        assert result.count(Status.ORDER) == 1
        assert result.count(Status.EXTRA) == 0
        assert result.score >= 90

    def test_contraction_is_labelled_and_cheap(self):
        result = score_answer("I'll sort it out later.", "I will sort it out later")
        assert result.words[0].status == Status.CONTRACTION
        assert result.score >= 95
        assert result.word_accuracy == 100

    def test_partial_contraction_is_a_real_mistake(self):
        result = score_answer("I'll sort it out later.", "I sort it out later")
        assert result.words[0].status == Status.INCORRECT
        assert result.score < 95

    def test_uk_us_spelling_is_nearly_free(self):
        result = score_answer(
            "I didn't realise you were coming.", "I didn't realize you were coming"
        )
        assert result.words[2].status == Status.SPELLING
        assert result.score >= 98

    def test_negation_matters(self):
        result = score_answer("I didn't realise you were coming.", "I did realise you were coming")
        assert result.words[1].status == Status.INCORRECT
        assert result.score < 90

    def test_typo_is_near_miss(self):
        typo = score_answer("Do you fancy grabbing a coffee?", "do you fancy grabbing a coffe")
        wrong = score_answer("Do you fancy grabbing a coffee?", "do you fancy grabbing a tea")
        assert typo.score > wrong.score

    @pytest.mark.parametrize(
        "typed", ["WOULD YOU LIKE TO GO", "would   you like to go...", "Would you like to go ?"]
    )
    def test_formatting_differences_ignored(self, typed):
        assert score_answer("Would you like to go?", typed).score == 100

    def test_score_bounds(self):
        result = score_answer("Hi.", "completely unrelated words typed here instead")
        assert 0 <= result.score <= 100
