"""The franchises AnimeVerse imports.

This is configuration data, not logic: adding a franchise means adding one
line to FRANCHISES.

- name:            display name, stored in the franchises table.
- search:          the text sent to the data source's search, stored as franchises.search_query.
- main_anilist_id: the franchise's main anime on AniList. A search result is
                   kept only if AniList's relations connect it to this anime
                   (see RelationRule and ADR 0012).

Checked against real AniList results on 2026-11-28: every main anime is in
its search results, and the members are the same as with the old title rule,
except that One Piece loses "Mizuiro no One-Piece" and "Noroi no One Piece"
(unrelated titles) and gains two Cup Noodle ads with One Piece characters,
and Jujutsu Kaisen loses "Jujutsu Kaisen Modulo PV" (a promo video with no
anime relations).
"""

from animeverse.domain.membership import FranchiseDefinition, RelationRule
from animeverse.domain.models import Franchise


def by_relations(name: str, search: str, main_anilist_id: int) -> FranchiseDefinition:
    """A franchise whose anime are the search results related to its main anime."""
    return FranchiseDefinition(Franchise(name, search), RelationRule(main_anilist_id))


FRANCHISES: tuple[FranchiseDefinition, ...] = (
    by_relations("Naruto", search="Naruto", main_anilist_id=20),  # NARUTO (TV)
    by_relations("Jujutsu Kaisen", search="Jujutsu Kaisen", main_anilist_id=113415),  # Jujutsu Kaisen (TV)
    by_relations("Yu-Gi-Oh!", search="Yu-Gi-Oh!", main_anilist_id=481),  # Yu☆Gi☆Oh! Duel Monsters (TV)
    by_relations("One Piece", search="One Piece", main_anilist_id=21),  # ONE PIECE (TV)
    by_relations("Dragon Ball", search="Dragon Ball", main_anilist_id=223),  # Dragon Ball (TV)
    by_relations("Attack on Titan", search="Attack on Titan", main_anilist_id=16498),  # Shingeki no Kyojin (TV)
    by_relations("Demon Slayer", search="Demon Slayer", main_anilist_id=101922),  # Kimetsu no Yaiba (TV)
)
