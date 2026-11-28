# 0012. Membership by AniList relations, and link reconciliation

- Status: Accepted
- Date: 2026-11-28
- Supersedes: 0006. Amends: 0007.

## Context

Two problems made the catalogue wrong, with no way to correct it:

- The title rule (0006) kept unrelated anime whose title contains a franchise's term:
  "Mizuiro no One-Piece" (a 1982 music video about a dress) and "Noroi no One Piece".
- Imports never deleted (0007), so a link, once created, stayed forever. Fixing the rule would
  not have removed "Mizuiro" from the database. And because the catalogue lists every stored
  anime, removing only the link would have left it visible without a franchise.

AniList's search returns each result's `relations` (sequels, side stories, spin-offs, shared
characters, its manga...) in the same request, so no extra requests are needed. Checked on
2026-11-28 for all seven franchises: no relation list is paginated.

## Decision

**Membership.** Each franchise names its main anime by AniList id. A search result belongs to the
franchise if relations connect it to the main anime, walking only through other search results
and in both directions (AniList does not always list a relation on both sides). Every relation
type counts: without `CHARACTER`, the Demon Slayer spin-off "Kimetsu Gakuen: Valentine-hen" is
lost. Relations are used to decide and are never stored.

**Undecidable cases fail the franchise and touch nothing:** the main anime is not in the search
results, or it comes without any relations (a main series always has some, so none means
incomplete data; trusting it would drop almost every member).

**Reconciliation.** After saving a franchise's members, in the same transaction, every other
anime is unlinked from it. An anime this leaves in no franchise is deleted, unless it is in the
watchlist: user data is never deleted.

- Results we cannot judge keep their links: anime the database refused, and malformed results
  that have an id.
- A malformed result without an id could be any anime, so that franchise is not reconciled at
  all, and the report says why.
- Only anime unlinked in that step can be deleted: there is no global sweep.

This changes 0007's "imports never delete" to: **imports never delete user data, nor an anime that
still belongs to a franchise**. Imports stay idempotent: a second run with the same data unlinks
and deletes nothing.

## Consequences

- The catalogue follows the rule: changing the rule, or AniList changing its data, is reflected
  on the next import. The 2026-11-28 import removed "Mizuiro no One-Piece", "Noroi no One Piece"
  and "Jujutsu Kaisen Modulo PV" (163 → 162 anime) and added two Cup Noodle ads with One Piece
  characters.
- "Jujutsu Kaisen Modulo PV" is lost: a promo video with no anime relations in AniList.
- An anime that is deleted and later comes back gets a new internal id. Nothing outside the
  database refers to internal ids except the watchlist, whose anime are never deleted.
- A wrong main anime id in the configuration would fail that franchise loudly instead of
  silently importing the wrong anime.
- If AniList stopped sending relations for every result, the franchises would fail and the
  stored data would stay as it is.
