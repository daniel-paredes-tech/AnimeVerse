"""The import report as plain text, for the terminal."""

from animeverse.application.import_catalog import FranchiseReport


def format_report(reports: list[FranchiseReport]) -> str:
    """A plain-text summary of an import run."""
    header = (
        f"{'Franchise':<18}{'Status':<8}{'Fetched':>8}{'Rejected':>10}{'Excluded':>10}"
        f"{'New':>6}{'Refreshed':>11}{'New links':>11}"
    )
    lines = [header, "-" * len(header)]
    for r in reports:
        status = "FAILED" if r.failed else "ok"
        lines.append(
            f"{r.name:<18}{status:<8}{r.fetched:>8}{len(r.rejected):>10}{len(r.excluded):>10}"
            f"{r.new:>6}{r.refreshed:>11}{r.new_links:>11}"
        )

    excluded = [f"{r.name}: {e.title} ({e.anilist_id})" for r in reports for e in r.excluded]
    rejected = [f"{r.name}: position {x.position} (id={x.source_id}): {x.reason}" for r in reports for x in r.rejected]
    unsaved = [f"{r.name}: {u.title} ({u.anilist_id}): {u.reason}" for r in reports for u in r.unsaved]
    failures = [f"{r.name}: {r.error}" for r in reports if r.failed]
    for title, items in (
        ("Excluded (not part of the franchise)", excluded),
        ("Rejected (malformed data)", rejected),
        ("Not saved (refused by the database)", unsaved),
        ("Failures", failures),
    ):
        if items:
            lines += ["", f"{title}:"] + [f"  - {item}" for item in items]

    succeeded = sum(not r.failed for r in reports)
    lines += ["", f"Result: {succeeded} of {len(reports)} franchises imported."]
    return "\n".join(lines)
