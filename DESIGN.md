---
name: AnimeVerse
description: A local anime universe map and watchlist, printed as this week's issue of a shōnen manga magazine.
colors:
  ink: "#121212"
  paper: "#ffffff"
  masthead-red: "#e4002b"
  stock-1: "#f6c9c2"
  stock-2: "#f3e6a0"
  stock-3: "#c9e6d2"
  stock-4: "#c8dcee"
  stock-5: "#d9d0ee"
  stock-6: "#f8d6b3"
  stock-7: "#dce3c3"
  tone-1: "#9e2a1c"
  tone-2: "#946e00"
  tone-3: "#1e7a3e"
  tone-4: "#1d4f86"
  tone-5: "#4b2a8c"
  tone-6: "#a4520e"
  tone-7: "#56740f"
typography:
  display:
    fontFamily: "Dela Gothic One, BIZ UDPGothic, sans-serif"
    fontSize: "clamp(1.9rem, 3.2vw, 2.75rem)"
    fontWeight: 400
    lineHeight: 1
    letterSpacing: "-0.02em"
  headline:
    fontFamily: "Dela Gothic One, BIZ UDPGothic, sans-serif"
    fontSize: "clamp(1.8rem, 3.2vw, 2.75rem)"
    fontWeight: 400
    lineHeight: 1.1
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Dela Gothic One, BIZ UDPGothic, sans-serif"
    fontSize: "clamp(1.6rem, 2.6vw, 2.25rem)"
    fontWeight: 400
    lineHeight: 1.1
    letterSpacing: "-0.01em"
  box-title:
    fontFamily: "Dela Gothic One, BIZ UDPGothic, sans-serif"
    fontSize: "1.2rem"
    fontWeight: 400
    lineHeight: 1.25
  card-title:
    fontFamily: "Dela Gothic One, BIZ UDPGothic, sans-serif"
    fontSize: "1.02rem"
    fontWeight: 400
    lineHeight: 1.25
  body:
    fontFamily: "BIZ UDPGothic, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.55
  body-sm:
    fontFamily: "BIZ UDPGothic, sans-serif"
    fontSize: "0.85rem"
    fontWeight: 400
    lineHeight: 1.35
  label:
    fontFamily: "BIZ UDPGothic, sans-serif"
    fontSize: "0.8rem"
    fontWeight: 700
    lineHeight: 1.3
  control:
    fontFamily: "BIZ UDPGothic, sans-serif"
    fontSize: "0.95rem"
    fontWeight: 700
    lineHeight: 1.2
  code:
    fontFamily: "ui-monospace, SF Mono, Menlo, Consolas, monospace"
    fontSize: "0.9em"
    fontWeight: 400
rounded:
  none: "0px"
  balloon-sm: "0.75rem"
  balloon-md: "1rem"
  balloon-lg: "1.75rem"
  pill: "999px"
  answer-box: "0.6rem"
spacing:
  gutter: "12px"
  pen: "3px"
  pen-thin: "2px"
  hairline: "1.5px"
components:
  button:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    typography: "{typography.control}"
    rounded: "{rounded.none}"
    padding: "0.45rem 0.95rem"
    height: "44px"
  button-ink:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    typography: "{typography.control}"
    rounded: "{rounded.none}"
    padding: "0.45rem 0.95rem"
    height: "44px"
  button-ink-hover:
    backgroundColor: "{colors.masthead-red}"
    textColor: "{colors.paper}"
  button-red:
    backgroundColor: "{colors.masthead-red}"
    textColor: "{colors.paper}"
    typography: "{typography.control}"
    rounded: "{rounded.none}"
    padding: "0.45rem 0.95rem"
    height: "44px"
  button-red-hover:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
  chip:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "0.2rem 0.55rem"
    height: "32px"
  chip-pressed:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
  control:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.none}"
    padding: "0.35rem 0.6rem"
    height: "40px"
  masthead:
    backgroundColor: "{colors.masthead-red}"
    textColor: "{colors.paper}"
    typography: "{typography.display}"
    height: "64px"
  box-head:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.paper}"
    typography: "{typography.box-title}"
    padding: "0.35rem 0.7rem"
  box-head-next-issue:
    backgroundColor: "{colors.masthead-red}"
    textColor: "{colors.paper}"
  balloon:
    backgroundColor: "{colors.paper}"
    textColor: "{colors.ink}"
    rounded: "{rounded.balloon-sm}"
    padding: "0.45rem 0.65rem"
  stamp:
    textColor: "{colors.masthead-red}"
    size: "76px"
---

# Design System: AnimeVerse

## Overview

**Creative North Star: "Weekly Shōnen Issue"**

AnimeVerse is printed, not rendered. Every page is a page of this week's issue of a shōnen manga magazine: a red masthead strip with the logotype and issue number, ink panels with white gutters, and newsprint stocks that tell the franchises apart. The centre spread on the Universe page is a night sky built entirely from dot screentone, with each franchise as a constellation of four-point sparkle stars under a name plate. Browse is the series index and an anime page is a single series sheet with a reader-survey postcard for the watchlist.

The system is flat and high contrast. Depth comes from pen weight, gutters and screentone density, never from shadows or grey fills. Copy sits in narration boxes; the API's answers (validation errors, refused requests, missing data) speak in balloons; a confirmed save is a red hanko stamp. Density is a magazine's: compact type, tight gutters, many bordered panels, and every number in tabular figures. The world refuses the dark poster-grid streaming catalogue.

Anime data and cover images come from AniList, credited in the colophon on every page.

**Key Characteristics:**
- Ink `#121212` on paper white, one masthead red, seven franchise newsprint stocks.
- No grey anywhere: every tone is a dot or line screen.
- Pen-and-ink borders (3px panels, 2px controls, 1.5px rules), square corners, white gutters.
- Dela Gothic One for display and big numbers, BIZ UDPGothic for text.
- Speech balloons for the API's voice; a hanko stamp only after the API confirms.
- One authored move (the burst zoom into a constellation); every animation stops under reduced motion.

## Colors

A print palette: black ink, white paper, one red, and a set of pale newsprint stocks, each with a deep shade for its dots.

### Primary
- **Masthead Red** (masthead-red): the masthead strip, the current-issue "Continue watching" box, the save button, the hanko stamp, the watching-progress arc on stars, the postcard's inner frame, validation balloons and invalid-field borders, link underlines, the focus ring and text selection. It marks the issue's identity and anything the user acts on or must fix.

### Neutral
- **Press Ink** (ink): all text, every border and rule, box heads, pressed chips, the sky's dot screen, plate count boxes.
- **Paper White** (paper): the page, every panel's fill, text on ink and red, and the keyline that lifts marks off the dark sky.

### Franchise Stocks
Seven pale newsprint tints, one per franchise, assigned by ascending franchise id and cycled after seven (`stockByFranchiseId` in `web/src/universe/palette.ts`). Anime with no franchise print on plain paper. Stocks fill stars, name plates, plate chips, the coloured edge on Browse entries and the franchise tag on a series sheet.
- **Salmon** (stock-1), **Straw** (stock-2), **Mint** (stock-3), **Powder Blue** (stock-4), **Lilac** (stock-5), **Apricot** (stock-6), **Sage** (stock-7).

### Tone Inks
Each stock has a deep shade of the same hue (tone-1 to tone-7, same order) used only for the score dots printed over that stock, so a star's tone keeps its franchise's colour. Dots on plain paper are printed in ink. These are dot colours, never fills or text colours.

### Named Rules
**The No-Grey Rule.** There is no grey fill, grey text or grey border anywhere. Any tone is ink or a tone ink laid as dots (score, sky, loading roller, problem panel) or as a 45° line screen (unknown episode total).

**The One Stock Per Franchise Rule.** A franchise always prints on the same stock across the map, the index and the series sheet; a stock never stands for anything but its franchise.

**The Red Means Act Rule.** Red is reserved for the masthead, the user's own progress and actions (watching arc, save, stamp, next-issue box) and for errors and focus. It is never a decorative fill.

## Typography

**Display Font:** Dela Gothic One (with BIZ UDPGothic, sans-serif), weight 400 only.
**Body Font:** BIZ UDPGothic (sans-serif), weights 400 and 700.
**Code Font:** ui-monospace, SF Mono, Menlo, Consolas.

Both families are bundled from npm (`@fontsource`); nothing loads from a font service.

**Character:** a heavy, round Japanese gothic for logotype, headings and numbers, like magazine cover lettering, over a clear Japanese UD text face that reads well small.

### Hierarchy
- **Display** (400, clamp(1.9rem, 3.2vw, 2.75rem), line-height 1, -0.02em): the masthead logotype; the 404 numeral uses the same face in red at clamp(4.5rem, 16vw, 6rem).
- **Headline** (400, clamp(1.8rem, 3.2–4vw, 2.75rem), 1.1): page titles and the series title on a sheet.
- **Title** (400, clamp(1.6rem, 2.6vw, 2.25rem), 1.1): the spread and Browse titles; zoom-head title at clamp(1.5rem, 2.6vw, 2.1rem).
- **Box title** (400, 1.2–1.45rem, 1.2–1.25): ink box heads, the filter rail head, results title, section heads, the postcard title.
- **Card title** (400, 1.02–1.05rem, 1.2–1.25): entry and cover-card titles, name plates, plate chips.
- **Body** (400, 1rem, 1.55): running text; synopsis capped at 68ch, narration at 65ch.
- **Small body** (400, 0.85–0.9rem, 1.35): secondary lines, English titles, meta, the colophon.
- **Label** (700, 0.8–0.85rem): fact terms, field labels, chip-row labels, watch lines. Sentence case.
- **Control** (700, 0.82–0.95rem, 1.2): buttons, chips, tags.

### Named Rules
**The Display Numbers Rule.** Scores, counts, the issue number and page positions are set in Dela Gothic One or in tabular figures (`font-variant-numeric: tabular-nums`), so numbers line up like a printed table.

**The Unknown Is Italic Rule.** A missing value is written out ("No English title", "Unscored", "No cover image") in italic or bold text, never left blank or shown as zero.

**The Sentence Case Rule.** Labels and headings are sentence or title case. Uppercase appears only inside the hanko stamp and its "Stamp here" placeholder, where it is printed lettering.

## Layout

The content area is capped at 1680px with a 12px gutter (`--gutter`) as the universal spacing unit: page padding, grid gaps, and the white gutter between panels all use it.

- **Universe (centre spread):** a two-column grid, 7fr for the sky panel and minmax(17rem, 3fr) for the right page. Above 720px the stage (title, chip rows and the panel) fills the viewport under the 64px masthead; the panel takes the remaining height. The right page stacks "Airing now", "Coming" and "Continue watching" boxes. A Map/List toggle swaps the sky for a sortable table in the same frame.
- **Browse:** a 17.5rem sticky filter rail beside a results column; entries in an auto-fill grid of minmax(21rem, 1fr) cards; a pager under a 3px rule.
- **Detail (series sheet):** a main column beside a sticky postcard column of minmax(22rem, 27rem); the head is a 150px cover beside the titles; facts sit in a three-column ruled grid.
- **Text pages** (404 and similar) cap at 70rem, or 46rem when narrow.

Desktop is the supported layout. Narrower widths have breakpoints in the code but have not been designed or reviewed: at 960px and below the sheet stacks; at 860px and below the spread and Browse stack into one column (panel first, right page after); at 720px and below the sky panel switches to a taller 0.8 aspect ratio, chip rows scroll sideways, a strip of franchise plate chips appears under the map, and the zoom head collapses to one row; at 560px and below the masthead logotype takes its own row.

## Elevation & Depth

The system is flat. There are no drop shadows. Depth is conveyed by pen weight (3px for panels, 2px for controls, 1.5px for inner rules), by white gutters and keylines that separate marks from the dark sky, and by screentone density.

### Shadow Vocabulary
- **Paper gutter** (`box-shadow: 0 0 0 5px #ffffff`): the hovering cover card on the sky, so it sits on the page like a panel with its own white gutter. It is a spread ring, not a shadow.
- **Stamp double ring** (`box-shadow: inset 0 0 0 3px #ffffff, inset 0 0 0 4.5px #e4002b`): draws the hanko's inner ring.

### Named Rules
**The Gutter Not Shadow Rule.** Anything that sits over the sky or another panel gets a paper keyline or gutter and an ink border, never an offset or blurred shadow.

## Shapes

Corners are square (0px) on every panel, box, button, chip, control, card and cover image. Curves are reserved for things that are round on paper: speech balloons (0.75rem field balloons and postcard summary, 1rem compact problem balloon, 1.75rem full problem balloon, each with a pointed tail on field balloons), the ring around a chosen survey answer (a pill, 999px, on the Status choices; a rounded box, 0.6rem, on the Rating scale, so the ring clears its widest label, "None"), the round tick boxes, the hanko stamp (circle, rotated -12°) and the watchlist rings around stars.

Recurring forms: the four-point sparkle star (`sparklePath`), focus lines (ink wedges radiating from a constellation in the burst), dashed outlines for missing or inactive things (no cover image, disabled buttons, the empty stamp box, filtered-out ghost stars), and a dotted red ring for an unknown episode total.

## Components

### Buttons
Square, bordered, bold: a printed box.
- **Shape:** square corners (0px), 2px ink border, minimum height 44px.
- **Default:** paper with ink text; hover underlines the label in red.
- **Ink:** ink fill, paper text; hover turns red. Used for the main action in a context (back from a zoom).
- **Red:** red fill, paper text; hover turns ink. Used for saving the watchlist entry.
- **Disabled / pending:** the border becomes dashed (`not-allowed` or `progress` cursor).
- **Link button:** bold ink text with a 2px red underline, no box.

### Chips
- **Style:** 32px tall, 2px ink border, paper fill, bold 0.82rem text with a regular-weight tabular count.
- **State:** pressed chips invert to ink with paper text (`aria-pressed`). Used for release status, format and Map/List view on the Universe page.
- **Tags (active filters on Browse):** the same box with an "×" mark; hover inverts to ink.

### Cards / Containers
- **Side box:** 3px ink border, an ink head with display title and an inverted count badge; the "Continue watching" box is red-bordered with a red head.
- **Browse entry:** 2px ink border, a 10px franchise-stock edge across the top, an 84×120 cover, title, facts grid and a star glyph showing the score tone; a watch line at the foot turns red when the anime is on the watchlist. Hover turns the border red; the whole card is the link target.
- **Cover card (map hover):** 2px ink border with a 5px paper gutter, 76×108 cover, facts, watch line.
- **Narration box:** paper with a 2px ink border, max 65ch.

### Inputs / Fields
- **Style:** 40px minimum height, 2px ink border, square, paper fill; placeholders in italic ink (no grey); selects draw their own chevron.
- **Focus:** 3px red outline, 2px offset.
- **Error:** the border turns red at 3px, and a red-bordered speech balloon below the field carries the API's message with its tail pointing up at the control.
- **Stepper:** 40px square −/+ buttons that invert to ink on hover around a centred number input.

### Navigation
The masthead: a red strip with a 3px ink bottom rule, the logotype in paper, an issue badge (paper box with ink border, issue number in display face, date), and nav links in display face on the right. Links carry a 3px bottom bar: ink on hover, paper for the current page.

### The Universe Map (signature)
A hand-written SVG sky in one 3px ink panel. The sky is stacked sheets of ink dot screen, darkest at the top, cut into lighter clearings around each constellation. Each anime is a four-point sparkle: size from popularity, fill from its franchise stock, score as dot density in the stock's tone ink (half-point steps; an unscored anime stays untoned), ink outline on a paper keyline. A watchlist entry adds a ring; "watching" adds a red arc of episodes watched, dotted when the total is unknown. Filtered-out stars become dashed ghosts. Franchise name plates are stock boxes with an ink count box. Hover or focus draws a red ring. Choosing a plate runs the burst: the spread scales from 2.6 to 1 over 760ms (cubic-bezier(0.16, 1, 0.3, 1)) behind focus lines, and a zoom head names the franchise. A legend under the panel explains size, tone, untoned and ring using the map's own marks.

### The Postcard (signature)
The watchlist form as a reader-survey postcard: 3px ink border with a 1.5px red inner frame inset 6px, sticky beside the series sheet. Status and rating are real radio buttons drawn as round tick boxes; the chosen answer is circled in ink. A dashed stamp box in the corner holds "Stamp here" until the API confirms a save; then a 76px red hanko (word and date, rotated -12°) is printed, pressing in over 420ms only for a save that just happened.

### Balloons and Problem Panels
The API's voice. Field-level validation (400/422) answers in red-bordered balloons beside each field; whole-request problems (database down, not found) appear as a paper balloon with a 3px ink border on a dot-screen panel, with a hint line and the problem's metadata.

### Loading
A press roller: a hard-edged band of dot screen sweeps across the panel (1.8s; 1.2s as a thin strip over Browse results while the next page loads), easing cubic-bezier(0.65, 0, 0.35, 1). Under reduced motion the band stays still in the middle.

### Colophon
A 3px ink rule over a small-text footer that credits AniList as the data source and says the app runs on this computer only.

## Do's and Don'ts

### Do:
- **Do** build every tone from dots or lines: `--tone-dots` (ink dots, 8px pitch) for decoration, the score screen (4.6 unit pitch, rotated 45°) for scores, a 45° line screen for unknowns.
- **Do** give each franchise its stock in ascending id order and keep it on every surface.
- **Do** frame panels with a 3px ink pen and separate them with the 12px white gutter; use 2px for controls and 1.5px for inner rules.
- **Do** set headings, plates and numbers in Dela Gothic One at weight 400, and all other text in BIZ UDPGothic.
- **Do** show missing data as words ("Unscored", "No cover image", "Format unknown"), never blank or zero.
- **Do** put the API's validation messages in a balloon next to the field they belong to.
- **Do** print the hanko only after the API confirms a save, and animate it only for a fresh save.
- **Do** use the 3px red outline for keyboard focus, and paper for focus on red or ink grounds.
- **Do** turn off every animation under `prefers-reduced-motion: reduce`.
- **Do** credit AniList as the data source on every page.

### Don't:
- **Don't** use grey in any form: fill, text, border or placeholder.
- **Don't** use drop shadows or blurred shadows; use a paper gutter and an ink border.
- **Don't** round panels, buttons, cards, inputs or images; curves belong only to balloons, stamps, rings and tick boxes.
- **Don't** use red as decoration; it marks the masthead, the user's actions and progress, errors and focus.
- **Don't** use a franchise stock or tone ink for anything but its franchise.
- **Don't** lay dot screen under running text; text sits on paper.
- **Don't** add uppercase labels or small lines above headings; uppercase lives only in the stamp.
- **Don't** add a second hero motion; the burst zoom is the one authored move.
- **Don't** load fonts, scripts or images from anywhere but the app itself and AniList's image host.
