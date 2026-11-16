"""Tests for animeverse.importer, using a fake AniList client and the real test database.

All anime below are made-up test data.
"""

import psycopg
import pytest

from animeverse import repository
from animeverse.anilist_client import AniListError
from animeverse.franchises import FRANCHISES, FranchiseConfig
from animeverse.importer import belongs_to_franchise, format_report, import_all, import_franchise, normalize
from animeverse.models import Anime

NARUTO = FranchiseConfig("Naruto", search="Naruto", match=("naruto",))
TITAN = FranchiseConfig("Attack on Titan", search="Attack on Titan", match=("attack on titan", "shingeki no kyojin"))


class FakeClient:
    """Stands in for AniListClient: returns (or raises) what each search was given."""

    def __init__(self, results: dict):
        self.results = results
        self.searches: list[str] = []

    def search_anime(self, search: str) -> list:
        self.searches.append(search)
        result = self.results[search]
        if isinstance(result, Exception):
            raise result
        return result


def raw(anilist_id, romaji, english=None):
    """A minimal raw AniList item."""
    return {"id": anilist_id, "title": {"romaji": romaji, "english": english}}


def count(conn, table):
    return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]  # fixed table names only


# --- Membership rule -----------------------------------------------------------


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
def test_belongs_to_franchise_checks_romaji_and_english_titles(title, english, expected):
    anime = Anime(anilist_id=1, title=title, title_english=english)
    assert belongs_to_franchise(anime, NARUTO.match) is expected


def test_second_match_term_is_used():
    anime = Anime(anilist_id=1, title="Shingeki no Kyojin Season 2", title_english=None)
    assert belongs_to_franchise(anime, TITAN.match) is True


def test_a_term_with_only_punctuation_matches_nothing():
    anime = Anime(anilist_id=1, title="Anything")
    assert belongs_to_franchise(anime, ("!!!",)) is False


def test_configured_franchises_have_unique_names_and_usable_terms():
    names = [f.name for f in FRANCHISES]
    assert len(names) == len(set(names))
    for franchise in FRANCHISES:
        assert franchise.match, f"{franchise.name} has no match terms"
        assert all(normalize(term) for term in franchise.match)


# --- Importing one franchise ---------------------------------------------------


def naruto_results():
    return [
        raw(900001, "NARUTO", "Naruto"),
        raw(900002, "NARUTO: Shippuuden", "Naruto Shippuden"),
        raw(900003, "Onigiri", "Onigiri"),  # will be excluded
        {"id": None, "title": {"romaji": "Broken"}},  # will be rejected by the parser
    ]


def test_import_stores_members_and_reports_what_happened(committing_conn):
    client = FakeClient({"Naruto": naruto_results()})

    report = import_franchise(client, committing_conn, NARUTO)

    assert not report.failed
    assert report.fetched == 4
    assert len(report.rejected) == 1
    assert [e.title for e in report.excluded] == ["Onigiri"]
    assert (report.new, report.refreshed, report.new_links) == (2, 0, 2)
    assert count(committing_conn, "franchises") == 1
    assert count(committing_conn, "anime") == 2  # Onigiri and the broken item were not stored
    assert count(committing_conn, "anime_franchises") == 2


def test_importing_twice_creates_nothing_new(committing_conn):
    client = FakeClient({"Naruto": naruto_results()})

    import_franchise(client, committing_conn, NARUTO)
    second = import_franchise(client, committing_conn, NARUTO)

    assert (second.new, second.refreshed, second.new_links) == (0, 2, 0)
    assert count(committing_conn, "franchises") == 1
    assert count(committing_conn, "anime") == 2
    assert count(committing_conn, "anime_franchises") == 2


def test_import_commits_so_other_connections_see_the_data(committing_conn, test_db_settings):
    import_franchise(FakeClient({"Naruto": naruto_results()}), committing_conn, NARUTO)

    with repository.connect(test_db_settings) as other:
        assert count(other, "anime") == 2


# --- Failures --------------------------------------------------------------------


def test_anilist_failure_for_one_franchise_does_not_stop_the_others(committing_conn):
    client = FakeClient({
        "Naruto": AniListError("AniList request failed after 4 attempts: server error (HTTP 503)", status=503),
        "Attack on Titan": [raw(900010, "Shingeki no Kyojin", "Attack on Titan")],
    })

    reports = import_all(client, committing_conn, franchises=[NARUTO, TITAN])

    assert client.searches == ["Naruto", "Attack on Titan"]
    assert reports[0].failed and "HTTP 503" in reports[0].error
    assert not reports[1].failed and reports[1].new == 1
    assert count(committing_conn, "franchises") == 1  # nothing was written for Naruto


def test_database_failure_rolls_back_only_that_franchise(committing_conn, monkeypatch):
    client = FakeClient({
        "Naruto": naruto_results(),
        "Attack on Titan": [raw(900010, "Shingeki no Kyojin", "Attack on Titan")],
    })
    import_franchise(client, committing_conn, NARUTO)  # succeeds and commits

    def broken_link(conn, anime_id, franchise_id):
        raise psycopg.OperationalError("simulated database failure")

    monkeypatch.setattr(repository, "link_anime_to_franchise", broken_link)
    report = import_franchise(client, committing_conn, TITAN)

    assert report.failed and "simulated database failure" in report.error
    assert (report.new, report.refreshed, report.new_links) == (0, 0, 0)
    # Attack on Titan's franchise row and anime were rolled back; Naruto is untouched.
    names = [row[0] for row in committing_conn.execute("SELECT name FROM franchises")]
    assert names == ["Naruto"]
    assert count(committing_conn, "anime") == 2
    assert count(committing_conn, "anime_franchises") == 2


def test_anime_refused_by_the_database_does_not_stop_the_franchise(committing_conn, monkeypatch):
    real_upsert = repository.upsert_anime

    def upsert_with_one_bad_value(conn, anime):
        if anime.anilist_id == 900001:
            # Slips past the parser on purpose: the CHECK constraint refuses a negative count.
            anime = Anime(anilist_id=anime.anilist_id, title=anime.title, episodes=-1)
        return real_upsert(conn, anime)

    monkeypatch.setattr(repository, "upsert_anime", upsert_with_one_bad_value)
    report = import_franchise(FakeClient({"Naruto": naruto_results()}), committing_conn, NARUTO)

    assert not report.failed
    assert [u.anilist_id for u in report.unsaved] == [900001]
    assert (report.new, report.refreshed, report.new_links) == (1, 0, 1)
    stored = [row[0] for row in committing_conn.execute("SELECT anilist_id FROM anime")]
    assert stored == [900002]  # the other anime was still imported
    assert "Not saved" in format_report([report]) and "(900001)" in format_report([report])


# --- Report ------------------------------------------------------------------------


def test_report_lists_counts_exclusions_failures_and_result(committing_conn):
    client = FakeClient({"Naruto": naruto_results(), "Attack on Titan": AniListError("boom")})

    text = format_report(import_all(client, committing_conn, franchises=[NARUTO, TITAN]))

    assert "Naruto" in text and "Attack on Titan" in text and "FAILED" in text
    assert "Naruto: Onigiri (900003)" in text  # excluded anime are named
    assert "position 3" in text  # the rejected item is identified
    assert "Attack on Titan: AniList: boom" in text
    assert "Result: 1 of 2 franchises imported." in text
