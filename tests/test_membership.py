"""Tests for animeverse.domain.membership and the configured franchises. Made-up anime only."""

import pytest

from animeverse.config.franchises import FRANCHISES
from animeverse.domain.membership import MembershipUndecidable, RelationRule
from animeverse.domain.models import Anime

RULE = RelationRule(main_anilist_id=900001)


def a(anilist_id: int) -> Anime:
    return Anime(anilist_id=anilist_id, title=f"Anime {anilist_id}")


def member_ids(anime: list[Anime], relations: dict[int, frozenset[int]]) -> list[int]:
    return [m.anilist_id for m in RULE.select_members(anime, relations)]


def test_anime_connected_to_the_main_one_are_members():
    relations = {
        900001: frozenset({900002}),
        900002: frozenset({900003}),  # reached through 900002, not directly
        900003: frozenset(),
        900004: frozenset(),  # unrelated search noise
    }

    assert member_ids([a(900001), a(900002), a(900003), a(900004)], relations) == [900001, 900002, 900003]


def test_members_keep_the_order_of_the_search_results():
    relations = {900001: frozenset({900002, 900003}), 900002: frozenset(), 900003: frozenset()}

    assert member_ids([a(900003), a(900001), a(900002)], relations) == [900003, 900001, 900002]


def test_relations_count_in_both_directions():
    # Only 900002 names the main anime: it is still a member.
    relations = {900001: frozenset({800001}), 900002: frozenset({900001})}

    assert member_ids([a(900001), a(900002)], relations) == [900001, 900002]


def test_relations_to_media_outside_the_results_do_not_connect():
    # Both point to 800000 (say, the manga), which is not a search result.
    relations = {900001: frozenset({800000}), 900002: frozenset({800000})}

    assert member_ids([a(900001), a(900002)], relations) == [900001]


def test_cycles_terminate():
    relations = {900001: frozenset({900002}), 900002: frozenset({900001})}

    assert member_ids([a(900001), a(900002)], relations) == [900001, 900002]


def test_main_anime_missing_is_undecidable():
    with pytest.raises(MembershipUndecidable, match="900001"):
        RULE.select_members([a(900002)], {900002: frozenset({900001})})


def test_main_anime_without_relations_is_undecidable():
    # A main series always has relations (at least its manga): none means incomplete data.
    with pytest.raises(MembershipUndecidable, match="900001"):
        RULE.select_members([a(900001), a(900002)], {900001: frozenset(), 900002: frozenset({900001})})


def test_configured_franchises_have_unique_names():
    names = [definition.name for definition in FRANCHISES]
    assert len(names) == len(set(names))


def test_every_configured_franchise_names_its_main_anime():
    # Checked on 2026-11-28: each id is in its franchise's AniList search results.
    assert {d.name: d.rule.main_anilist_id for d in FRANCHISES} == {
        "Naruto": 20,
        "Jujutsu Kaisen": 113415,
        "Yu-Gi-Oh!": 481,
        "One Piece": 21,
        "Dragon Ball": 223,
        "Attack on Titan": 16498,
        "Demon Slayer": 101922,
    }
