"""Membership rules: decide which search results belong to a franchise.

AniList's search is loose (a search for "Demon Slayer" also returns an
unrelated anime called "Onigiri", and "One Piece" returns a music video about
a dress), so every franchise needs a rule that filters the search results.

MembershipRule is the contract. It sees the whole search result at once,
because a rule may need to compare results with each other.

RelationRule is today's only rule (ADR 0012). It starts at the franchise's
main anime and follows AniList's relations (sequels, side stories, spin-offs,
shared characters...) from result to result. Two details:
- Relations count in both directions: AniList does not always list a
  relation on both sides.
- Only search results connect. Two anime that both point to the same manga
  are not linked through it: the manga is not a result.
"""

from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from animeverse.domain.models import Anime, Franchise


class MembershipUndecidable(Exception):
    """The search result is not enough to decide which anime belong.

    The import must then leave the franchise exactly as it is.
    """


class MembershipRule(Protocol):
    def select_members(self, anime: Sequence[Anime], relations: Mapping[int, frozenset[int]]) -> list[Anime]:
        """The anime that belong to the franchise, in their original order.

        relations maps an anime's AniList id to the AniList ids it relates to.
        Raises MembershipUndecidable.
        """
        ...


@dataclass(frozen=True)
class RelationRule:
    """Members are the results connected to the main anime through relations."""

    main_anilist_id: int

    def select_members(self, anime: Sequence[Anime], relations: Mapping[int, frozenset[int]]) -> list[Anime]:
        result_ids = {item.anilist_id for item in anime}
        if self.main_anilist_id not in result_ids:
            raise MembershipUndecidable(f"the main anime ({self.main_anilist_id}) is not in the search results")

        # Undirected graph between search results only.
        neighbours: dict[int, set[int]] = {anilist_id: set() for anilist_id in result_ids}
        for anilist_id in result_ids:
            for related in relations.get(anilist_id, frozenset()) & result_ids:
                neighbours[anilist_id].add(related)
                neighbours[related].add(anilist_id)

        if not relations.get(self.main_anilist_id):
            # A main series always has relations (at least its manga). None means the
            # source sent incomplete data: trusting it would drop almost every member.
            raise MembershipUndecidable(f"the main anime ({self.main_anilist_id}) came without relations")

        # Breadth-first walk from the main anime.
        reached = {self.main_anilist_id}
        queue = deque([self.main_anilist_id])
        while queue:
            for neighbour in neighbours[queue.popleft()] - reached:
                reached.add(neighbour)
                queue.append(neighbour)
        return [item for item in anime if item.anilist_id in reached]


@dataclass(frozen=True)
class FranchiseDefinition:
    """What to import for one franchise: what to search for, and which results to keep."""

    franchise: Franchise
    rule: MembershipRule

    @property
    def name(self) -> str:
        return self.franchise.name
