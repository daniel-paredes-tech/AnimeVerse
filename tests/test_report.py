"""Tests for the plain-text import report."""

from animeverse.application.import_catalog import ExcludedAnime, FranchiseReport, UnsavedAnime
from animeverse.application.ports import Rejection, UnlinkedAnime
from animeverse.entrypoints.report import format_report


def test_report_lists_counts_exclusions_rejections_failures_and_result():
    naruto = FranchiseReport(
        "Naruto",
        fetched=4,
        rejected=[Rejection(position=3, source_id=None, reason="'id' is missing")],
        excluded=[ExcludedAnime(900003, "Onigiri")],
        unsaved=[UnsavedAnime(900004, "Broken", "episodes must be >= 0")],
        new=2,
        new_links=2,
    )
    titan = FranchiseReport("Attack on Titan", failed=True, error="source: AniList: boom")

    text = format_report([naruto, titan])

    assert "Naruto" in text and "FAILED" in text
    assert "Naruto: Onigiri (900003)" in text  # excluded anime are named
    assert "position 3" in text  # the rejected item is identified
    assert "Not saved" in text and "Broken (900004)" in text
    assert "Attack on Titan: source: AniList: boom" in text
    assert "Result: 1 of 2 franchises imported." in text


def test_report_shows_unlinked_anime_and_skipped_reconciliations():
    one_piece = FranchiseReport(
        "One Piece",
        unlinked=[
            UnlinkedAnime(139862, "Mizuiro no One-Piece", deleted=True),
            UnlinkedAnime(900005, "Watched one", deleted=False),
        ],
    )
    naruto = FranchiseReport("Naruto", reconciliation_skipped="1 rejected result(s) without an id")

    text = format_report([one_piece, naruto])

    header = text.splitlines()[0]
    assert "Unlinked" in header and "Deleted" in header
    assert "One Piece: Mizuiro no One-Piece (139862), deleted" in text
    assert "One Piece: Watched one (900005), kept (in the watchlist or another franchise)" in text
    assert "Reconciliation skipped" in text and "Naruto: 1 rejected result(s) without an id" in text
