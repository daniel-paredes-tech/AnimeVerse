---
version: 1
slug: "web-src-pages-universepage-tsx"
primary_target: "web/src/pages/UniversePage.tsx"
related_targets: ["web/src/pages/BrowsePage.tsx","web/src/pages/AnimeDetailPage.tsx"]
---

# Surface brief: AnimeVerse web UI

## Scope and mode

- Universe `/` (the dashboard): **Experience**. The map is the work, and it leads from the first viewport.
- Browse `/anime`, Detail `/anime/:id` (with the watchlist form), and every empty, error and 404 state: **Operate**. Same world, precision first, known patterns.

## Audience, job, constraints

- The developer tracks their own anime daily, and shows the UI at a Migracode presentation (equal weight).
- Data only from `openapi.yaml`, through the generated client.
- English, WCAG 2.2 AA, local-only CSP (self + `https://s4.anilist.co` images; fonts bundled).
- Every null is shown as unknown, never hidden.

## Memorable moment

A franchise panel bursting to a full spread along focus lines.

## Unresolved

- Exact screentone densities and the star layout's constants: the builder decides, inside the contract.

## Direction contract

**THESIS:** AnimeVerse is this week's issue of a shōnen manga magazine, and its centre spread is the universe map: seven franchise constellations in one screentoned night sky. It refuses the dark poster-grid streaming catalogue.

**OWN-WORLD:**
- **Colour:** ink black `#121212` on paper white `#FFFFFF`, masthead red `#E4002B`.
- **Franchise stocks:** each franchise prints on its own newsprint tint, in order of id: `#F6C9C2` `#F3E6A0` `#C9E6D2` `#C8DCEE` `#D9D0EE` `#F8D6B3` `#DCE3C3`.
- **Tone:** no grey fills. Every tone is screentone (SVG dot or line patterns). A star's score sets its dot density, and an unscored anime stays untoned.
- **Line:** pen-and-ink panel borders with white gutters, four-point sparkle stars, focus lines.
- **Type:** Dela Gothic One for display and big numbers, BIZ UDPGothic for text.
- **Components:** narration boxes and balloons carry copy. Save confirmations are a hanko stamp. The watchlist form is the reader-survey postcard.

**STORY:** The visitor opens the issue and sees all seven universes at once. They hover a star to read its cover card, dive into a franchise, open an anime, and log progress on the postcard. The API's validation answers in balloons next to each field.

**FIRST VIEWPORT:**
- **Masthead strip:** logotype, issue date, and nav (Universe · Browse).
- **The spread below it:**
  - A left page of about 70%: one night-sky panel holding the seven constellations with franchise name plates.
  - A right column: "Airing now", "Coming", and a "Continue watching" next-issue box.
- **Primary action:** the stars and the franchise plates.
- **Phone:** the panel first, at full width.

**FORM:** Weekly Shōnen Issue, position 3 of 7 on the ordered list, seed:55f14cb198c66d31. Raises:
- **ASCII:** score as screentone density.
- **Op-art:** no grey.
- **Sleeping city:** one stock per franchise.
- **Miura:** a one-move zoom.
- **Darkroom:** a stamp only after the API confirms.

**FINISH:** unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
