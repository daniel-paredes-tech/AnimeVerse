"""Tests for the plain-text import report."""

from animeverse.application.import_catalog import ExcludedAnime, FranchiseReport, UnsavedAnime
from animeverse.application.ports import Rejection
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
