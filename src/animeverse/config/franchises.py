"""The franchises AnimeVerse imports.

This is configuration data, not logic: adding a franchise means adding one
line to FRANCHISES.

- name:   display name, stored in the franchises table.
- search: the text sent to the data source's search, stored as franchises.search_query.
- match:  an anime from the search results is kept only if its romaji or
          English title contains one of these terms (see TitleMatchRule).

The match terms were checked against real AniList results on 2026-11-16:
163 of 166 results kept; excluded were "Onigiri" and two One Piece tie-ins
whose titles don't mention One Piece.
"""

from animeverse.domain.membership import FranchiseDefinition, TitleMatchRule
from animeverse.domain.models import Franchise


def by_title(name: str, search: str, match: tuple[str, ...]) -> FranchiseDefinition:
    """A franchise whose anime are recognised by their titles."""
    return FranchiseDefinition(Franchise(name, search), TitleMatchRule(match))


FRANCHISES: tuple[FranchiseDefinition, ...] = (
    by_title("Naruto", search="Naruto", match=("naruto",)),
    # "juju sanpo": the Jujutsu Kaisen chibi shorts, whose titles don't say "Jujutsu Kaisen".
    by_title("Jujutsu Kaisen", search="Jujutsu Kaisen", match=("jujutsu kaisen", "juju sanpo")),
    by_title("Yu-Gi-Oh!", search="Yu-Gi-Oh!", match=("yu-gi-oh",)),
    by_title("One Piece", search="One Piece", match=("one piece",)),
    by_title("Dragon Ball", search="Dragon Ball", match=("dragon ball",)),
    # The main romaji title is the Japanese name, Shingeki no Kyojin.
    by_title("Attack on Titan", search="Attack on Titan", match=("attack on titan", "shingeki no kyojin")),
    # "kimetsu" also covers the "Kimetsu Gakuen" spin-off, not only "Kimetsu no Yaiba".
    by_title("Demon Slayer", search="Demon Slayer", match=("demon slayer", "kimetsu")),
)
