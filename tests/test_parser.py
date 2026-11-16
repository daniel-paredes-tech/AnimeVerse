"""Tests for animeverse.parser.

tests/fixtures/anilist_samples.json holds 5 real AniList items (fetched on
2026-11-16), chosen because each shows a real-world quirk. All other inputs
below are made-up test data.
"""

import copy
import json
import logging
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from animeverse.parser import InvalidAnimeError, parse_anime, parse_anime_list

SAMPLES_FILE = Path(__file__).parent / "fixtures" / "anilist_samples.json"


@pytest.fixture
def samples():
    """Real items, keyed by AniList id."""
    return {item["id"]: item for item in json.loads(SAMPLES_FILE.read_text())}


def minimal(**overrides):
    """The smallest valid item: only the required fields."""
    item = {"id": 900001, "title": {"romaji": "Test Anime"}}
    item.update(overrides)
    return item


# --- Real samples -------------------------------------------------------------


def test_all_real_samples_parse_without_rejections(samples):
    result = parse_anime_list(list(samples.values()))

    assert len(result.valid) == 5
    assert result.rejected == []


def test_complete_real_item_maps_every_field(samples):
    anime = parse_anime(samples[20])  # NARUTO

    assert anime.anilist_id == 20
    assert anime.mal_id == 20
    assert anime.title == "NARUTO"
    assert anime.title_english == "Naruto"
    assert anime.title_japanese == "NARUTO -ナルト-"
    assert (anime.type, anime.episodes, anime.status) == ("TV", 220, "FINISHED")
    assert (anime.aired_from, anime.aired_to) == (date(2002, 10, 3), date(2007, 2, 8))
    assert anime.score == Decimal("8.00")  # weightedScore 80
    assert anime.popularity == 741939
    assert anime.anilist_url == "https://anilist.co/anime/20"
    assert anime.image_url.startswith("https://s4.anilist.co/")


def test_real_description_becomes_plain_text_with_credit(samples):
    synopsis = parse_anime(samples[20]).synopsis

    assert "<" not in synopsis
    assert "newborn Naruto.\n\nShunned" in synopsis  # "<br><br>\n" -> one blank line
    assert synopsis.endswith("\n\n(Source: MAL Rewrite)")  # credit kept


def test_real_description_with_nested_tags_and_line_breaks(samples):
    synopsis = parse_anime(samples[162561]).synopsis  # NARUTO×NINKU

    assert "<" not in synopsis
    assert "\n\n\n" not in synopsis
    assert "by Kakashi.\nSince Kakashi" in synopsis  # single line breaks kept
    assert "(Source: NARUTO x NINKŪ Official Site)" in synopsis


def test_real_html_entity_is_decoded(samples):
    assert parse_anime(samples[7367]).synopsis.endswith("don't miss it‼")  # &#8252;


def test_real_partial_dates_become_none_without_warning(samples, caplog):
    with caplog.at_level(logging.WARNING):
        anime = parse_anime(samples[171630])  # THE ONE PIECE: start 2027-02-??, end empty

    assert (anime.aired_from, anime.aired_to) == (None, None)
    assert anime.type is None  # format is null in the real data
    assert caplog.records == []  # missing parts are normal, not an error


def test_real_missing_optional_values_become_none(samples):
    anime = parse_anime(samples[192810])  # no idMal, no English title

    assert anime.mal_id is None
    assert anime.title_english is None


# --- Required fields: invalid -> item rejected --------------------------------


@pytest.mark.parametrize(
    "item",
    [
        None,
        "not an object",
        {"title": {"romaji": "No id"}},
        minimal(id="123"),  # text, not a number
        minimal(id=True),  # bool counts as int in Python: must be refused
        minimal(id=0),
        minimal(id=-5),
        minimal(id=2_147_483_648),  # does not fit in a PostgreSQL INTEGER
        {"id": 900001},  # no title at all
        minimal(title="Test Anime"),  # title is not an object
        minimal(title={"romaji": None}),
        minimal(title={"romaji": "   "}),  # whitespace only
        minimal(title={"english": "Only English"}),
    ],
)
def test_invalid_required_field_rejects_the_item(item):
    with pytest.raises(InvalidAnimeError):
        parse_anime(item)


def test_minimal_item_parses_with_all_optional_fields_none():
    anime = parse_anime(minimal())

    assert anime.anilist_id == 900001
    assert anime.title == "Test Anime"
    assert anime.score is None and anime.aired_from is None and anime.synopsis is None


def test_text_is_trimmed_and_empty_text_becomes_none():
    anime = parse_anime(minimal(title={"romaji": "  Test  ", "english": "   "}, status=" FINISHED "))

    assert anime.title == "Test"
    assert anime.title_english is None
    assert anime.status == "FINISHED"


def test_nul_characters_are_removed_from_text():
    # PostgreSQL refuses a NUL character inside TEXT.
    anime = parse_anime(minimal(title={"romaji": "Te\x00st", "english": "\x00"}, description="A\x00B"))

    assert anime.title == "Test"
    assert anime.title_english is None
    assert anime.synopsis == "AB"


# --- Optional fields: invalid -> None + warning --------------------------------


@pytest.mark.parametrize(
    ("overrides", "field"),
    [
        ({"episodes": -3}, "episodes"),
        ({"episodes": "12"}, "episodes"),
        ({"episodes": True}, "episodes"),
        ({"popularity": -1}, "popularity"),
        ({"popularity": 2_147_483_648}, "popularity"),  # does not fit in a PostgreSQL INTEGER
        ({"idMal": 0}, "mal_id"),
        ({"format": 5}, "type"),
        ({"weightedScore": 101}, "score"),
        ({"weightedScore": -1}, "score"),
        ({"weightedScore": "85"}, "score"),
        ({"weightedScore": float("nan")}, "score"),
        ({"siteUrl": "javascript:alert(1)"}, "anilist_url"),
        ({"siteUrl": "not a url"}, "anilist_url"),
        ({"coverImage": {"large": "ftp://example.com/x.jpg"}}, "image_url"),
        ({"coverImage": "https://example.com/x.jpg"}, "image_url"),  # not an object
        ({"startDate": {"year": 2020, "month": 2, "day": 30}}, "aired_from"),  # Feb 30
        ({"startDate": {"year": "2020", "month": 1, "day": 1}}, "aired_from"),
        ({"startDate": "2020-01-01"}, "aired_from"),
    ],
)
def test_invalid_optional_field_becomes_none_with_warning(overrides, field, caplog):
    with caplog.at_level(logging.WARNING):
        anime = parse_anime(minimal(**overrides))

    assert getattr(anime, field) is None
    assert anime.title == "Test Anime"  # the rest of the item survives
    assert len(caplog.records) == 1
    assert "900001" in caplog.text  # the warning names the anime


@pytest.mark.parametrize(
    ("weighted_score", "expected"),
    [(0, Decimal("0.00")), (85, Decimal("8.50")), (100, Decimal("10.00")), (85.3, Decimal("8.53"))],
)
def test_score_is_converted_from_0_100_to_0_10(weighted_score, expected):
    assert parse_anime(minimal(weightedScore=weighted_score)).score == expected


def test_end_date_before_start_date_is_dropped_with_warning(caplog):
    item = minimal(
        startDate={"year": 2020, "month": 5, "day": 1},
        endDate={"year": 2019, "month": 1, "day": 1},
    )
    with caplog.at_level(logging.WARNING):
        anime = parse_anime(item)

    assert anime.aired_from == date(2020, 5, 1)
    assert anime.aired_to is None
    assert "before startDate" in caplog.text


def test_description_list_items_and_tags_become_plain_text():
    description = "Intro<br><ul><li>First</li><li>Second &amp; last</li></ul><b>Bold</b> end"

    synopsis = parse_anime(minimal(description=description)).synopsis

    # <br> + <ul> give a blank line before the list; </ul> gives one line break after it.
    assert synopsis == "Intro\n\n• First\n• Second & last\nBold end"


def test_description_with_only_tags_becomes_none():
    assert parse_anime(minimal(description="<br><br> <i></i>")).synopsis is None


def test_long_invalid_values_are_truncated_in_warnings(caplog):
    with caplog.at_level(logging.WARNING):
        parse_anime(minimal(siteUrl="x" * 5000))

    assert len(caplog.text) < 300  # untrusted data can't flood the logs


# --- Parsing a list: one bad item never stops the others -----------------------


def test_list_with_bad_items_keeps_good_ones_and_reports_rejections(samples, caplog):
    naruto = samples[20]
    bad_title = copy.deepcopy(naruto) | {"id": 900002, "title": {"romaji": ""}}
    items = [naruto, None, bad_title, minimal()]

    with caplog.at_level(logging.WARNING):
        result = parse_anime_list(items)

    assert [a.anilist_id for a in result.valid] == [20, 900001]
    assert [(r.position, r.anilist_id) for r in result.rejected] == [(1, None), (2, 900002)]
    assert "title.romaji" in result.rejected[1].reason
    assert len(caplog.records) == 2  # each rejection is logged


def test_empty_list_gives_empty_result():
    result = parse_anime_list([])

    assert result.valid == [] and result.rejected == []
