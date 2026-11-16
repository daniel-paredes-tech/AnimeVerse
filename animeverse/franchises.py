"""The franchises AnimeVerse imports.

This is configuration data, not logic: adding a franchise means adding one
line to FRANCHISES.

- name:   display name, stored in the franchises table.
- search: the text sent to AniList's search, stored as franchises.search_query.
- match:  an anime from the search results is kept only if its romaji or
          English title contains one of these terms (compared ignoring case,
          accents, spaces and punctuation). This removes unrelated search
          noise, e.g. "Onigiri" in the "Demon Slayer" results.

The match terms were checked against real AniList results on 2026-11-16:
163 of 166 results kept; excluded were "Onigiri" and two One Piece tie-ins
whose titles don't mention One Piece.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FranchiseConfig:
    name: str
    search: str
    match: tuple[str, ...]


FRANCHISES: tuple[FranchiseConfig, ...] = (
    FranchiseConfig("Naruto", search="Naruto", match=("naruto",)),
    # "juju sanpo": the Jujutsu Kaisen chibi shorts, whose titles don't say "Jujutsu Kaisen".
    FranchiseConfig("Jujutsu Kaisen", search="Jujutsu Kaisen", match=("jujutsu kaisen", "juju sanpo")),
    FranchiseConfig("Yu-Gi-Oh!", search="Yu-Gi-Oh!", match=("yu-gi-oh",)),
    FranchiseConfig("One Piece", search="One Piece", match=("one piece",)),
    FranchiseConfig("Dragon Ball", search="Dragon Ball", match=("dragon ball",)),
    # The main romaji title is the Japanese name, Shingeki no Kyojin.
    FranchiseConfig("Attack on Titan", search="Attack on Titan", match=("attack on titan", "shingeki no kyojin")),
    # "kimetsu" also covers the "Kimetsu Gakuen" spin-off, not only "Kimetsu no Yaiba".
    FranchiseConfig("Demon Slayer", search="Demon Slayer", match=("demon slayer", "kimetsu")),
)
