"""Tests for animeverse.page. All anime below are made-up test data."""

from datetime import date
from decimal import Decimal

from animeverse.domain.models import Anime
from animeverse.entrypoints.web.page import IMPORT_COMMAND, render_page

FULL = Anime(
    anilist_id=1,
    title="Test Anime",
    title_english="Test Anime (English)",
    type="TV_SHORT",
    episodes=12,
    status="NOT_YET_RELEASED",
    aired_from=date(2020, 4, 1),
    start_year=2020,
    score=Decimal("8.50"),
)


def test_year_is_shown_even_when_the_full_date_is_unknown():
    page = render_page({"Alpha": [Anime(anilist_id=3, title="Announced", start_year=2027)]})

    assert '<td class="num">2027</td>' in page


def test_page_shows_summary_navigation_and_rows():
    page = render_page({"Alpha": [FULL, Anime(anilist_id=2, title="Second")], "Beta": [FULL]})

    assert "2 franchises · 3 anime" in page
    assert 'href="#franchise-alpha"' in page and 'id="franchise-alpha"' in page
    assert "Test Anime (English)" in page
    assert "TV short" in page and "Not yet released" in page
    assert "8.50" in page and "2020" in page and ">12<" in page


def test_missing_values_are_shown_as_a_dash():
    page = render_page({"Alpha": [Anime(anilist_id=2, title="Bare")]})

    assert page.count("<td>—</td>") == 2  # type and status
    assert page.count('<td class="num">—</td>') == 3  # episodes, score and year


def test_english_title_is_not_repeated_when_identical():
    page = render_page({"Alpha": [Anime(anilist_id=3, title="ONE PIECE", title_english="ONE PIECE")]})

    assert page.count("ONE PIECE") == 1


def test_text_from_the_api_is_escaped():
    evil = Anime(anilist_id=4, title="<script>alert(1)</script>", title_english='" onmouseover="x')
    page = render_page({"<b>Franchise</b>": [evil]})

    assert "<script>" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "<b>Franchise</b>" not in page
    assert '" onmouseover="x' not in page


def test_page_loads_nothing_from_outside():
    page = render_page({"Alpha": [FULL]})

    assert "http://" not in page and "https://" not in page
    assert "<script" not in page and "<img" not in page


def test_empty_database_explains_how_to_import():
    page = render_page({})

    assert "No data yet." in page
    assert IMPORT_COMMAND in page


def test_franchise_without_anime_says_so():
    page = render_page({"Empty": []})

    assert "No anime imported for this franchise." in page
    assert "1 franchise · 0 anime" in page
