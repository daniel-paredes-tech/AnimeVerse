# Franchise Membership by Relations — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decide franchise membership with AniList `relations`, and make every import reconcile a franchise's links with its current members, deleting anime left without a franchise unless they are in the watchlist.

**Architecture:** The AniList adapter also returns each result's related ids in `SearchResult.relations`. A domain `RelationRule` walks that graph from the franchise's main anime. The use case saves the members, then asks the store (a new `CatalogSession` method) to keep only those links and delete the orphans, all in the franchise's existing unit of work.

**Tech Stack:** Python 3.11+, HTTPX, psycopg 3, PostgreSQL 18, pytest, ruff, mypy (strict), import-linter.

**Spec:** `docs/superpowers/specs/2026-11-28-membership-by-relations-design.md`

## Global Constraints

- Work on branch `membership-by-relations`, created from `main`.
- Before **every** commit run all checks and look at pytest's own exit code:
  `.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy && .venv/bin/lint-imports && .venv/bin/python -m pytest` (the database must be running: `docker compose up -d`).
- Commits are authored by the developer only: **no `Co-Authored-By` trailer, no Claude mention** (CLAUDE.md section 10 and the developer's explicit rule).
- All repo text (code, comments, commits, docs) in clear, concise English.
- No new dependencies. No migration. No change to `openapi.yaml` or `web/`.
- Layer rules: `domain/` imports nothing of ours except `domain`; `application/` only `domain`. Never weaken an import-linter contract.
- AniList data is untrusted: a malformed relation is skipped with a warning, never fatal.
- Main anime ids (verified in the search results on 2026-11-28): Naruto 20, Jujutsu Kaisen 113415, Yu-Gi-Oh! 481, One Piece 21, Dragon Ball 223, Attack on Titan 16498, Demon Slayer 101922.
- Test data in unit tests is made up (ids ≥ 900000), as in the existing tests.

## Review Focus

1. **AniList returns relations as `null` or empty for every result** (degraded API): no anime may be unlinked or deleted; the franchise must fail. → Task 2 `test_main_anime_without_relations_is_undecidable` and Task 4 `test_undecidable_membership_touches_nothing`.
2. **An anime unlinked from one franchise but still in another**: it must not be deleted. → Task 3 `test_an_anime_still_in_another_franchise_is_not_deleted`.
3. **An anime in the watchlist loses its last franchise**: kept, entry intact. → Task 3 `test_an_anime_in_the_watchlist_is_kept`.
4. **A result rejected by the parser without an id**: reconciliation skipped, report says so. → Task 4 `test_a_rejection_without_id_skips_reconciliation`.
5. **The store dies in the middle of reconciliation**: the whole franchise is undone. → Task 4 `test_store_failure_during_reconciliation_undoes_the_franchise`.

---

### Task 1: AniList adapter returns relations

**Files:**
- Modify: `src/animeverse/application/ports.py` (`SearchResult`)
- Modify: `src/animeverse/infrastructure/anilist/client.py` (`SEARCH_ANIME_QUERY`)
- Modify: `src/animeverse/infrastructure/anilist/mapper.py` (`parse_anime_list`, new `_relations`)
- Test: `tests/test_parser.py`, `tests/test_anilist_client.py`

**Interfaces:**
- Produces: `SearchResult.relations: Mapping[int, frozenset[int]]` — AniList id of each **valid** result → AniList ids of the media it relates to (anime or manga, inside or outside the result). Default: empty mapping (`field(default_factory=dict)`), so existing `SearchResult(anime, rejected)` calls keep working.

- [ ] **Step 1: Create the branch**

Run: `git switch -c membership-by-relations`

- [ ] **Step 2: Write the failing parser tests** in `tests/test_parser.py`

Use a minimal valid item (the one `test_minimal_item_parses_with_all_optional_fields_none` builds) plus a `relations` key.

```python
def test_relations_are_parsed_into_related_ids():
    item = {**minimal_item(1), "relations": {"pageInfo": {"hasNextPage": False},
            "edges": [{"node": {"id": 2}}, {"node": {"id": 3}}]}}
    assert parse_anime_list([item]).relations == {1: frozenset({2, 3})}

def test_missing_or_null_relations_become_empty_without_warning(caplog): ...
    # items without "relations" and with "relations": None -> frozenset(), no WARNING logged

@pytest.mark.parametrize("edges", [[{"node": {"id": "x"}}], [{"node": None}], [None], [{"node": {"id": -4}}], "not a list"])
def test_malformed_relation_edges_are_skipped_with_a_warning(edges, caplog):
    # the anime is still valid; its relations hold only the good edges (here: none); one WARNING
    ...

def test_paginated_relations_log_a_warning(caplog):
    # pageInfo.hasNextPage True -> relations kept, one WARNING mentioning "more relations"

def test_rejected_items_have_no_relations_entry():
    # a rejected item's id never appears in .relations
```

If the test module has no `minimal_item` helper, add one that returns the minimal valid dict already used there.

- [ ] **Step 3: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_parser.py -k relation -v` → FAIL (`SearchResult` has no `relations`).

- [ ] **Step 4: Implement**

- `ports.py`: add `relations: Mapping[int, frozenset[int]] = field(default_factory=dict)` to `SearchResult`, with a one-line comment.
- `mapper.py`: `_relations(raw: dict[str, Any], anilist_id: int) -> frozenset[int]`, called in `parse_anime_list` only for items that parsed. Edge ids are validated with the existing `_is_whole_number` and range check used for `id` (1..`MAX_INTEGER`).
- `client.py`: add `relations {{ pageInfo {{ hasNextPage }} edges {{ node {{ id }} }} }}` to `SEARCH_ANIME_QUERY` (inside `media`, after `siteUrl`). Update the module docstring's field list if it has one.

- [ ] **Step 5: Update the client tests**

In `tests/test_anilist_client.py`, add `"relations"` to `EXPECTED_MEDIA_FIELDS`. Run: `.venv/bin/python -m pytest tests/test_parser.py tests/test_anilist_client.py -v` → PASS.

- [ ] **Step 6: Run the live test once** (verifies the real API shape)

Run: `.venv/bin/python -m pytest -m live -v` → PASS.

- [ ] **Step 7: All checks, then commit**

```bash
git add src/animeverse/application/ports.py src/animeverse/infrastructure/anilist tests/test_parser.py tests/test_anilist_client.py
git commit -m "Fetch AniList relations with each search result"
```

---

### Task 2: Membership decided by relations

**Files:**
- Modify: `src/animeverse/domain/membership.py` (replace `TitleMatchRule`/`normalize` with `RelationRule`)
- Modify: `src/animeverse/config/franchises.py` (`by_title` → `by_relations`)
- Modify: `src/animeverse/application/import_catalog.py` (call `select_members`, handle `MembershipUndecidable`)
- Test: `tests/test_membership.py` (rewrite), `tests/test_import_catalog.py`, `tests/test_import_with_postgres.py`

**Interfaces:**
- Consumes: `SearchResult.relations` (Task 1).
- Produces:
  - `class MembershipUndecidable(Exception)` in `domain/membership.py`.
  - `MembershipRule.select_members(self, anime: Sequence[Anime], relations: Mapping[int, frozenset[int]]) -> list[Anime]` — members in the input order. Raises `MembershipUndecidable`.
  - `@dataclass(frozen=True) class RelationRule: main_anilist_id: int`.
  - `by_relations(name: str, search: str, main_anilist_id: int) -> FranchiseDefinition` in `config/franchises.py`.

- [ ] **Step 1: Write the failing rule tests** (replace the title tests in `tests/test_membership.py`)

```python
RULE = RelationRule(main_anilist_id=900001)
def a(i): return Anime(anilist_id=i, title=f"Anime {i}")

def test_anime_connected_to_the_main_one_are_members():
    # 900001 -> 900002 -> 900003 (chain through results); 900004 unrelated
    members = RULE.select_members([a(900001), a(900002), a(900003), a(900004)],
                                  {900001: frozenset({900002}), 900002: frozenset({900003}), 900003: frozenset(), 900004: frozenset()})
    assert [m.anilist_id for m in members] == [900001, 900002, 900003]

def test_relations_count_in_both_directions():
    # only 900002 lists 900001 -> 900002 is still a member

def test_relations_to_media_outside_the_results_do_not_connect():
    # 900001 -> 800000 (manga, not a result) <- 900002 : 900002 is NOT a member

def test_cycles_terminate():
    # 900001 <-> 900002 <-> 900001 : both members, no infinite loop

def test_main_anime_missing_is_undecidable():
    with pytest.raises(MembershipUndecidable, match="900001"): RULE.select_members([a(900002)], {900002: frozenset({900001})})

def test_main_anime_without_relations_is_undecidable():
    with pytest.raises(MembershipUndecidable): RULE.select_members([a(900001), a(900002)], {900001: frozenset(), 900002: frozenset({900001})})

def test_every_configured_franchise_names_a_main_anime():
    assert {d.name: d.rule.main_anilist_id for d in FRANCHISES} == {
        "Naruto": 20, "Jujutsu Kaisen": 113415, "Yu-Gi-Oh!": 481, "One Piece": 21,
        "Dragon Ball": 223, "Attack on Titan": 16498, "Demon Slayer": 101922}
```

Keep any existing test about `FRANCHISES` (unique names, etc.) that still applies.

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_membership.py -v` → FAIL (import error).

- [ ] **Step 3: Implement the rule and the config**

- `RelationRule.select_members`: build an undirected adjacency over result ids only, breadth-first from `main_anilist_id`, return the reached anime in input order. Error messages name the main id.
- Delete `TitleMatchRule` and `normalize`; rewrite the module docstring (relations, why both directions, why the two undecidable cases).
- `franchises.py`: `by_relations` and the seven definitions with the ids from Global Constraints; each line keeps a short comment naming the main anime (e.g. `# 21 = ONE PIECE (TV)`). Rewrite the docstring: the 2026-11-28 check (same results as before except: One Piece loses Mizuiro no One-Piece and Noroi no One Piece and gains two Cup Noodle ads; Jujutsu Kaisen loses Modulo PV).

- [ ] **Step 4: Switch the use case and its tests**

- `import_catalog.py`: replace the `includes` loop with `select_members(result.anime, result.relations)`; excluded = results not returned. `except MembershipUndecidable as exc: return _fail(report, f"membership: {exc}")` **before** opening a session.
- `tests/test_import_catalog.py` and `tests/test_import_with_postgres.py`: `NARUTO = by_relations("Naruto", search="Naruto", main_anilist_id=900001)`, `TITAN` likewise with `900010`; give each `SearchResult` a `relations` mapping that keeps today's expectations (Onigiri 900003 unrelated, so still excluded).
- Add to `tests/test_import_catalog.py`:

```python
def test_undecidable_membership_fails_the_franchise_and_saves_nothing():
    # results without the main anime -> report.failed, "membership" in report.error, store empty
```

- [ ] **Step 5: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_membership.py tests/test_import_catalog.py tests/test_import_with_postgres.py -v` → PASS.

- [ ] **Step 6: All checks, then commit**

```bash
git add src/animeverse/domain/membership.py src/animeverse/config/franchises.py src/animeverse/application/import_catalog.py tests/test_membership.py tests/test_import_catalog.py tests/test_import_with_postgres.py
git commit -m "Decide franchise membership by AniList relations"
```

---

### Task 3: Store can keep only a franchise's members and drop orphans

**Files:**
- Modify: `src/animeverse/application/ports.py` (new `UnlinkedAnime`, new `CatalogSession` method)
- Modify: `src/animeverse/infrastructure/postgres/repository.py` (two SQL functions)
- Modify: `src/animeverse/infrastructure/postgres/store.py` (`PostgresCatalogSession`)
- Modify: `tests/fakes.py` (`_InMemorySession`)
- Test: `tests/test_store_contract.py`, `tests/test_repository.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class UnlinkedAnime: anilist_id: int; title: str; deleted: bool` in `ports.py`.
  - `CatalogSession.keep_only_links(self, franchise_id: int, anilist_ids: frozenset[int]) -> list[UnlinkedAnime]` — removes this franchise's links to every anime whose AniList id is not in `anilist_ids`; then deletes those just-unlinked anime that have no link left and no watchlist entry. Returns them ordered by `anilist_id`. Raises `StoreUnavailable`.
  - `repository.unlink_anime_except(conn, franchise_id: int, keep_anilist_ids: list[int]) -> list[tuple[int, int, str]]` → `(anime.id, anilist_id, title)` of removed links (one `DELETE ... USING anime ... RETURNING`; `a.anilist_id <> ALL(%(keep)s)`).
  - `repository.delete_orphan_anime(conn, anime_ids: list[int]) -> set[int]` → anime ids deleted (`id = ANY(...)` AND `NOT EXISTS` link AND `NOT EXISTS` watchlist entry).

- [ ] **Step 1: Write the failing contract tests** (run against the fake and PostgreSQL)

Add a fixture that also yields a `WatchlistStore` (the fake itself, or `PostgresWatchlistStore(lambda: connect(settings))`). Each test first saves members through a session, then calls `keep_only_links` in a new session.

```python
def test_keep_only_links_removes_other_links_and_deletes_orphans(...):
    # Naruto: 900001, 900002 saved; keep {900001} -> returns [UnlinkedAnime(900002, title, deleted=True)];
    # total_anime == 1; anime_of(query, "Naruto") == [900001]

def test_an_anime_still_in_another_franchise_is_not_deleted(...):
    # 900002 in Naruto and Titan; keep_only_links(naruto, {900001}) -> deleted=False; still listed under Titan

def test_an_anime_in_the_watchlist_is_kept(...):
    # 900002 has a watchlist entry; unlinked -> deleted=False; anime still exists with franchises == () and its entry

def test_keep_only_links_with_every_member_kept_changes_nothing(...):
    # returns []; counts unchanged

def test_keep_only_links_is_undone_with_the_session(...):
    # raise inside the session after keep_only_links -> links and anime still there
```

Add to `tests/test_repository.py`: `test_unlink_anime_except_leaves_other_franchises_alone` (rows of another franchise untouched).

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_store_contract.py tests/test_repository.py -v` → FAIL.

- [ ] **Step 3: Implement** the two repository functions (parameterized SQL, no commit, docstrings in the file's style), `PostgresCatalogSession.keep_only_links` (translates `psycopg.Error` → `StoreUnavailable`, like `save_franchise`), the port method with its docstring, and the fake (removing from `state.links`, `state.anime`, `state.ids`, `state.refreshed_at`; protected by `state.watchlist`).

- [ ] **Step 4: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_store_contract.py tests/test_repository.py -v` → PASS (both params).

- [ ] **Step 5: All checks, then commit**

```bash
git add src/animeverse/application/ports.py src/animeverse/infrastructure/postgres tests/fakes.py tests/test_store_contract.py tests/test_repository.py
git commit -m "Let a catalogue session keep only a franchise's members"
```

---

### Task 4: Imports reconcile links, and the report shows it

**Files:**
- Modify: `src/animeverse/application/import_catalog.py`
- Modify: `src/animeverse/entrypoints/report.py`
- Test: `tests/test_import_catalog.py`, `tests/test_import_with_postgres.py`, `tests/test_report.py`

**Interfaces:**
- Consumes: `CatalogSession.keep_only_links`, `UnlinkedAnime` (Task 3).
- Produces: `FranchiseReport.unlinked: list[UnlinkedAnime]` (default empty) and `FranchiseReport.reconciliation_skipped: str | None` (the reason, or `None`).

- [ ] **Step 1: Write the failing use-case tests** (fakes)

```python
def test_an_anime_no_longer_related_is_unlinked_and_deleted():
    # import 1: 900002 related; import 2: 900002 unrelated -> report.unlinked == [UnlinkedAnime(900002, ..., deleted=True)]; not stored

def test_an_unlinked_anime_in_the_watchlist_is_kept(): ...
def test_rejected_and_refused_anime_keep_their_links():
    # import 2: 900002 comes back as a Rejection(source_id=900002) -> still linked; a refused one too
def test_a_rejection_without_id_skips_reconciliation():
    # Rejection(source_id=None) -> report.reconciliation_skipped mentions "without an id"; nothing unlinked
def test_undecidable_membership_touches_nothing():
    # import 1 ok; import 2 with main anime lacking relations -> failed; store.committed unchanged
def test_store_failure_during_reconciliation_undoes_the_franchise():
    # make keep_only_links raise StoreUnavailable (fake flag or subclass) -> failed; state as after import 1
def test_source_failure_touches_nothing(): ...
```

Add `test_reimport_after_membership_change_deletes_the_orphan` to `tests/test_import_with_postgres.py` (real store: count of `anime` and `anime_franchises` drops by one).

- [ ] **Step 2: Run them to see them fail**

Run: `.venv/bin/python -m pytest tests/test_import_catalog.py tests/test_import_with_postgres.py -v` → FAIL.

- [ ] **Step 3: Implement** in `import_franchise`, inside the same `with self._store.session()` block, after saving: keep = member ids ∪ refused (`unsaved`) ids ∪ rejected `source_id`s; if any rejection has `source_id is None`, set `reconciliation_skipped` and do not call `keep_only_links`; otherwise store its result in `report.unlinked` and log each one at INFO. Update the module docstring (step 4 and the "never deleted" paragraph).

- [ ] **Step 4: Update the report** (`tests/test_report.py` first)

Header gains `Unlinked` and `Deleted` columns after `New links`. New section `Unlinked (no longer part of the franchise):` with `Name: title (id), deleted` or `Name: title (id), kept (in the watchlist or another franchise)`, and a section `Reconciliation skipped:` with `Name: reason`.

- [ ] **Step 5: Run the tests**

Run: `.venv/bin/python -m pytest tests/test_import_catalog.py tests/test_import_with_postgres.py tests/test_report.py tests/test_cli.py -v` → PASS.

- [ ] **Step 6: All checks, then commit**

```bash
git add src/animeverse/application/import_catalog.py src/animeverse/entrypoints/report.py tests/test_import_catalog.py tests/test_import_with_postgres.py tests/test_report.py
git commit -m "Reconcile franchise links on every import"
```

---

### Task 5: Record the decision and check it on real data

**Files:**
- Create: `docs/adr/0012-membership-by-relations-and-link-reconciliation.md`
- Modify: `docs/adr/0006-franchise-membership-by-title.md` (status line only: `Superseded by 0012`), `docs/adr/0007-idempotent-import-never-delete.md` (status line only: `Accepted, amended by 0012`), `docs/adr/README.md` (table), `README.md:222`, `CLAUDE.md` section 12 ("Imports insert and refresh, never delete") — `CLAUDE.md` is git-excluded: edit it, don't commit it.

- [ ] **Step 1: Write ADR 0012** from the spec's Why, Decision (relations from a main anime; links reconciled; orphans deleted unless in the watchlist; the two undecidable cases fail the franchise) and Consequences (Modulo PV lost; Cup Noodle ads kept; no global sweep; an anime that leaves and comes back gets a new internal id).

- [ ] **Step 2: Snapshot, import, snapshot on the developer's database**

Run the snapshot SQL (`/private/tmp/.../scratchpad/foto.sql`) before and after `.venv/bin/animeverse import`.
Expected: exit code 0; One Piece unlinks and deletes 139862 and 116054, adds 101099 and 113308; Jujutsu Kaisen unlinks and deletes 211607; `anime` goes 163 → 162; watchlist still 1 (Shingeki no Kyojin). A second import reports 0 unlinked.

- [ ] **Step 3: All checks, then commit**

```bash
git add docs/adr docs/superpowers README.md
git commit -m "Record ADR 0012: membership by relations, link reconciliation"
```
