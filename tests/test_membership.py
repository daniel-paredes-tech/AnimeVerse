"""Tests for animeverse.domain.membership and the configured franchises. Made-up titles only."""

import pytest

from animeverse.config.franchises import FRANCHISES
from animeverse.domain.membership import TitleMatchRule, normalize
from animeverse.domain.models import Anime

NARUTO = TitleMatchRule(("naruto",))
TITAN = TitleMatchRule(("attack on titan", "shingeki no kyojin"))


@pytest.mark.parametrize(
    ("text", "expected"),
    [("Yu☆Gi☆Oh!", "yugioh"), ("Yu-Gi-Oh!", "yugioh"), ("ONE PIECE", "onepiece"), ("Pokémon", "pokemon")],
)
def test_normalize_ignores_case_accents_spaces_and_punctuation(text, expected):
    assert normalize(text) == expected


@pytest.mark.parametrize(
    ("title", "english", "expected"),
    [
        ("NARUTO: Shippuuden", None, True),  # romaji title matches
        ("Some Romaji Title", "Naruto the Movie", True),  # only the English title matches
        ("Onigiri", "Onigiri", False),  # unrelated search noise
    ],
)
def test_title_rule_checks_romaji_and_english_titles(title, english, expected):
    anime = Anime(anilist_id=1, title=title, title_english=english)
    assert NARUTO.includes(anime) is expected


def test_second_term_is_used():
    anime = Anime(anilist_id=1, title="Shingeki no Kyojin Season 2", title_english=None)
    assert TITAN.includes(anime) is True


@pytest.mark.parametrize("terms", [(), ("!!!",), ("naruto", "   ")])
def test_rule_refuses_terms_that_would_match_everything(terms):
    with pytest.raises(ValueError):
        TitleMatchRule(terms)


def test_configured_franchises_have_unique_names():
    names = [definition.name for definition in FRANCHISES]
    assert len(names) == len(set(names))
