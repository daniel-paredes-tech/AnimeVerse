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
- A malformed result without an id could be any anime, and a result whose relations came
  incomplete (missing, null, malformed or on more than one page) could connect members the walk
  cannot reach. In both cases that franchise is not reconciled at all, and the report says why.
  An empty relation list is complete: some anime have none.
- The anime to delete are locked (`SELECT ... FOR UPDATE`) before the delete, so a watchlist
  entry the API saves at that very moment is always seen: the anime is then kept.
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
- An anime that is deleted and later comes back gets a new internal id. The API's URLs
  (`/v1/anime/{id}`) and the web UI's pages use internal ids, so an old link or bookmark to it
  then answers 404. The watchlist is not affected: its anime are never deleted.
- An import can delete an anime while the API is saving a watchlist entry for it: the entry is
  then refused, and the API answers 404 (the anime no longer exists), never 500.
- ADR 0011's note on `ON DELETE CASCADE` ("only matters for manual cleanup") no longer holds:
  imports delete anime too. The cascade can't remove a watchlist entry, because an anime with
  one is never deleted, and the lock described above closes the race.
- A wrong main anime id in the configuration would fail that franchise loudly instead of
  silently importing the wrong anime.
- If AniList stopped sending relations for every result, the franchises would fail and the
  stored data would stay as it is.
