"""Membership rules: decide whether an anime belongs to a franchise.

AniList's search is loose (a search for "Demon Slayer" also returns an
unrelated anime called "Onigiri"), so every franchise needs a rule that
filters the search results.

MembershipRule is the contract. TitleMatchRule is today's only rule. A
better rule later (for example one based on AniList's "relations") is a new
class with an `includes` method; nothing that uses rules has to change.
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol

from animeverse.domain.models import Anime, Franchise


class MembershipRule(Protocol):
    def includes(self, anime: Anime) -> bool:
        """True if the anime belongs to the franchise."""
        ...


def normalize(text: str) -> str:
    """Lowercase, strip accents, keep only letters and digits: 'Yu☆Gi☆Oh!' -> 'yugioh'."""
    decomposed = unicodedata.normalize("NFKD", text.lower())  # 'é' -> 'e' + accent mark
    return re.sub(r"[^a-z0-9]", "", decomposed)  # drops the accent marks too


@dataclass(frozen=True)
class TitleMatchRule:
    """Includes an anime whose romaji or English title contains one of the terms.

    Terms are compared ignoring case, accents, spaces and punctuation.
    Known limitation: an unrelated title that happens to contain a term is
    included too (e.g. "Mizuiro no One-Piece", a 1982 music video).
    """

    terms: tuple[str, ...]

    def __post_init__(self) -> None:
        # Checked here, once: a term that normalizes to "" would match every title.
        if not self.terms:
            raise ValueError("a TitleMatchRule needs at least one term")
        unusable = [term for term in self.terms if not normalize(term)]
        if unusable:
            raise ValueError(f"terms without letters or digits would match everything: {unusable}")

    def includes(self, anime: Anime) -> bool:
        titles = [normalize(title) for title in (anime.title, anime.title_english) if title]
        return any(normalize(term) in title for term in self.terms for title in titles)


@dataclass(frozen=True)
class FranchiseDefinition:
    """What to import for one franchise: what to search for, and which results to keep."""

    franchise: Franchise
    rule: MembershipRule

    @property
    def name(self) -> str:
        return self.franchise.name
