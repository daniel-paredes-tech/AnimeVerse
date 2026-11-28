# Franchise membership by AniList relations, with link reconciliation

- Date: 2026-11-28
- Status: proposed

## Why

The catalogue must be correct: a franchise should hold exactly the anime that belong to it.

Two problems block that today:

1. **The title rule has false positives.** `TitleMatchRule` keeps any anime whose title contains a
   term. "Mizuiro no One-Piece" (a 1982 music video about a dress) and "Noroi no One Piece" (an
   unrelated special) are stored as One Piece.
2. **A wrong link can never be fixed by the import.** Imports only insert and refresh (ADR 0007),
   so a link stays forever, even after the rule changes. Fixing the rule would not remove
   "Mizuiro" from the database.

The catalogue (`/v1/anime`) lists every stored anime, with or without a franchise. Removing a link
alone would leave "Mizuiro" visible in the web UI, so an anime left without any franchise must go.

## Goals

- Membership is decided by AniList's `relations`: a search result belongs to a franchise if it is
  connected to the franchise's main anime through relations between search results.
- After a successful import, a franchise's links are exactly its current members.
- An anime left with no franchise is deleted, **unless it has a watchlist entry**.

## Non-goals

- Fetching anime that the search did not return (no extra requests, no "hoarding").
- Storing relations in the database. They are only used to decide membership.
- Changing the API contract (`openapi.yaml`) or the web UI. Only the data changes.

## Anti-goals (a failure even if it works)

- A temporary AniList problem empties a franchise or deletes anime.
- User data (the watchlist) is lost.
- One malformed relation crashes the import.

## Constraints

- Hexagonal layers stay as they are: the rule lives in the domain, sees no AniList types.
- AniList data is untrusted input: relations are validated like any other field.
- Same rate-limit budget: relations must come in the existing search request.

## Verified against AniList (2026-11-28)

- `Media.relations` is a `MediaConnection` with `edges { relationType node { id } }` and
  `pageInfo`. It works inside the existing `Page(perPage: 50)` search: no extra requests.
- No relation list was paginated (`hasNextPage` false for every result of all 7 franchises).
- Every relation type is needed: without `CHARACTER`, "Kimetsu Gakuen: Valentine-hen" (a real
  Demon Slayer spin-off) is lost. Bridging through manga nodes added nothing.
- Expected effect on today's data, compared with the title rule:

  | Franchise | Change |
  |---|---|
  | Naruto, Yu-Gi-Oh!, Dragon Ball, Attack on Titan, Demon Slayer | none |
  | One Piece | out: Mizuiro no One-Piece (139862), Noroi no One Piece (116054); in: HUNGRY DAYS: Aoharu ka yo. (101099), Kinen Satsuei (113308), Cup Noodle ads with One Piece characters |
  | Jujutsu Kaisen | out: Jujutsu Kaisen Modulo PV (211607), a promo video with no anime relations |

## Approaches considered

1. **Relations inside each `Anime`** (a `related_ids` field). Fewest changes, but `Anime` is the
   model of what is stored, and it would carry data that is never stored.
2. **Relations returned beside the anime; the rule sees the whole result.** `SearchResult` gets a
   map `anilist_id -> related anilist ids`, and the rule becomes
   `select_members(anime, relations)`. The stored model stays clean and the contract says what the
   rule needs. **Chosen by the developer.**
3. **Keep `includes(anime)` and give the rule the graph when it is built.** Same signature, but
   the use case would build the rule on every import from search data: the rule stops being
   configuration and the logic is split in two places.

## Decisions taken with the developer

- Option b: a rule based on AniList relations (not a manual exclusion list).
- An anime left without franchises is deleted, unless it is in the watchlist.
- Approach 2 above.

## Design

### Domain (`domain/membership.py`)

- `MembershipRule.select_members(anime, relations) -> list[Anime]` replaces `includes(anime)`.
- `RelationRule(main_anilist_id)`: starts at the main anime and walks the relations, treated as
  undirected, visiting only anime in the search result. Raises `MembershipUndecidable` if the main
  anime is not in the result, **or if it has no relations at all**: a main series always has some
  (at least its manga), so an empty list means AniList sent incomplete data, and trusting it would
  unlink and delete almost the whole franchise.
- `TitleMatchRule` is removed (no franchise would use it).

### Config (`config/franchises.py`)

Each franchise names its main anime by AniList id. All seven were checked to be in their search
results: Naruto 20, Jujutsu Kaisen 113415, Yu-Gi-Oh! 481, One Piece 21, Dragon Ball 223, Attack on
Titan 16498, Demon Slayer 101922.

### AniList adapter

- The search query also asks for `relations { pageInfo { hasNextPage } edges { node { id } } }`.
- The mapper validates relations: a malformed edge is skipped with a warning, never fatal. If a
  relation list says it has more pages, a warning is logged (not seen today).
- `SearchResult.relations: Mapping[int, frozenset[int]]` holds them.

### Use case (`application/import_catalog.py`)

Per franchise, in its existing single unit of work:

1. Search (unchanged).
2. `select_members`. If membership is undecidable (main anime missing, or without relations), the
   franchise **fails and nothing is touched**.
3. Save members (unchanged).
4. **Reconcile:** remove this franchise's links to every anime not kept, then delete the anime that
   this step left with no links and no watchlist entry.
   - Anime the source rejected (malformed) or the store refused keep their existing links: we
     cannot tell whether they belong.
   - If a rejected item has no valid id, reconciliation is **skipped** for that franchise and the
     report says so (we cannot tell which anime it was).
   - An anime still linked to another franchise is never deleted.
   - Only anime unlinked in this step can be deleted: no global sweep.

### Store port and adapters

- `CatalogSession` gets one new method that keeps only the given anime linked to a franchise and
  deletes the anime this leaves orphaned (no links, no watchlist entry). It returns what was
  unlinked and what was deleted.
- PostgreSQL and the in-memory fake implement it; `tests/test_store_contract.py` checks both.
- No migration: the schema already has what is needed (`ON DELETE CASCADE` on links).

### Report

New columns "Removed links" and "Deleted", and the titles of unlinked anime, like "Excluded" today.

### Documentation

- ADR 0012: membership by relations and link reconciliation. It supersedes ADR 0006 and amends
  ADR 0007 ("imports never delete" becomes "imports never delete user data, nor anime that still
  belong to a franchise").
- Update `CLAUDE.md` ("Imports insert and refresh, never delete"), the README and docstrings that
  repeat the old rule.

### Tests (written first)

- Rule: connected results kept, unconnected excluded, cycles, edges to anime outside the result
  ignored, main anime missing, main anime without relations.
- Mapper: relations parsed; malformed edges skipped; missing `relations` field tolerated.
- Use case with fakes: excluded anime unlinked; orphan deleted; watchlist anime kept; anime in
  another franchise kept; rejected and refused anime keep their links; rejection without id skips
  reconciliation; source failure and missing main anime touch nothing.
- Store contract (fake and PostgreSQL): the new method.
- Live test: the real search returns relations in the expected shape.

## Left to the builder

- Exact names of the new session method, its result type and the domain error.
- Exact report layout.
