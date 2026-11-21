"""Renders the read-only AnimeVerse page as HTML.

Pure functions: no database and no network. Every value is escaped with
html.escape because it comes from an external API. The page has no
JavaScript and no external resources (no images, fonts or links), so the
browser never connects anywhere except this local server.
"""

import html
import re

from animeverse.models import Anime

IMPORT_COMMAND = ".venv/bin/python -m animeverse.import_anime"

STYLE = """
:root { --bg: #ffffff; --fg: #1d1d1f; --muted: #6e6e73; --line: #e5e5ea; --head: #f5f5f7; }
@media (prefers-color-scheme: dark) {
  :root { --bg: #161618; --fg: #f2f2f7; --muted: #a1a1a6; --line: #2c2c2e; --head: #1f1f22; }
}
* { box-sizing: border-box; }
body { margin: 0; padding: 24px 16px 48px; background: var(--bg); color: var(--fg);
       font: 15px/1.45 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
main { max-width: 1100px; margin: 0 auto; }
h1 { margin: 0 0 4px; font-size: 28px; }
h2 { margin: 36px 0 8px; font-size: 20px; }
.summary, .empty, .count { color: var(--muted); }
nav { margin: 16px 0 0; display: flex; flex-wrap: wrap; gap: 6px 14px; }
nav a { color: inherit; }
.table-wrap { overflow-x: auto; }
table { width: 100%; border-collapse: collapse; }
th, td { padding: 6px 10px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
th { background: var(--head); font-weight: 600; white-space: nowrap; }
td.num, th.num { text-align: right; font-variant-numeric: tabular-nums; }
.english { color: var(--muted); font-size: 13px; }
code { font-size: 13px; }
"""


def render_page(franchises: dict[str, list[Anime]]) -> str:
    """The full HTML page: a summary, links to each franchise, and one table per franchise."""
    if franchises:
        total = sum(len(anime) for anime in franchises.values())
        summary = f"{_plural(len(franchises), 'franchise')} · {_plural(total, 'anime', 'anime')}"
        nav = " ".join(
            f'<a href="#{_anchor(name)}">{_e(name)}</a> <span class="count">({len(anime)})</span>'
            for name, anime in franchises.items()
        )
        content = f"<nav>{nav}</nav>\n" + "\n".join(
            _franchise_section(name, anime) for name, anime in franchises.items()
        )
    else:
        summary = "No data yet."
        content = f'<p class="empty">Run <code>{_e(IMPORT_COMMAND)}</code> to import the anime.</p>'

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>AnimeVerse</title>
<style>{STYLE}</style>
</head>
<body>
<main>
<h1>AnimeVerse</h1>
<p class="summary">{_e(summary)}</p>
{content}
</main>
</body>
</html>
"""


def _franchise_section(name: str, anime_list: list[Anime]) -> str:
    heading = f'<h2 id="{_anchor(name)}">{_e(name)} <span class="count">({len(anime_list)})</span></h2>'
    if not anime_list:
        return f'{heading}\n<p class="empty">No anime imported for this franchise.</p>'
    rows = "\n".join(_row(anime) for anime in anime_list)
    return f"""{heading}
<div class="table-wrap"><table>
<thead><tr><th>Title</th><th>Type</th><th class="num">Episodes</th><th>Status</th>
<th class="num">Score</th><th class="num">Year</th></tr></thead>
<tbody>
{rows}
</tbody>
</table></div>"""


def _row(anime: Anime) -> str:
    english = ""
    if anime.title_english and anime.title_english != anime.title:
        english = f'<br><span class="english">{_e(anime.title_english)}</span>'
    return (
        "<tr>"
        f"<td>{_e(anime.title)}{english}</td>"
        f"<td>{_e(_label(anime.type))}</td>"
        f'<td class="num">{_e(_value(anime.episodes))}</td>'
        f"<td>{_e(_label(anime.status))}</td>"
        f'<td class="num">{_e(_value(anime.score))}</td>'
        f'<td class="num">{_e(_value(anime.start_year))}</td>'
        "</tr>"
    )


def _e(text: str) -> str:
    """Escape text for HTML, including quotes (safe inside attributes too)."""
    return html.escape(text, quote=True)


def _value(value: object) -> str:
    return "—" if value is None else str(value)


def _label(code: str | None) -> str:
    """AniList codes to readable text: 'NOT_YET_RELEASED' -> 'Not yet released', 'TV' stays 'TV'."""
    if code is None:
        return "—"
    if code in ("TV", "OVA", "ONA"):
        return code
    if code == "TV_SHORT":
        return "TV short"
    return code.replace("_", " ").capitalize()


def _anchor(name: str) -> str:
    """A safe id for in-page links: 'Yu-Gi-Oh!' -> 'franchise-yu-gi-oh'."""
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return f"franchise-{slug or 'unnamed'}"


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    word = singular if count == 1 else (plural or singular + "s")
    return f"{count} {word}"
