# 0006. Franchise membership decided by title

- Status: Superseded by 0012
- Date: 2026-11-16 (recorded 2026-11-21)

## Context

AniList has no "franchise" concept, and its search is loose: searching "Demon Slayer"
returns "Onigiri", an unrelated anime. Something must decide which results belong.

## Decision

A franchise keeps a search result only if its romaji or English title contains one of the
franchise's terms, compared ignoring case, accents, spaces and punctuation
(`TitleMatchRule`). Excluded anime are always listed in the import report.

The rule is a strategy behind the `MembershipRule` protocol, so it can be replaced per
franchise without changing the use case.

## Consequences

- Simple, explainable and checkable by hand: 163 of 166 results kept on 2026-11-16.
- False negatives: spin-offs with other names need extra terms ("kimetsu", "juju sanpo").
- False positives: "Mizuiro no One-Piece", a 1982 music video about a dress, is kept as
  One Piece. A better rule would use AniList's `relations`; it would be a new
  `MembershipRule` class.
