---
name: Háztartás
description: A family ledger whose month view is a treemap of where the money went, on a warm stone ground with one ink-black action.
colors:
  ground: "#f3f1ec"
  ground-2: "#e7e3da"
  ink: "#1c1b19"
  ink-2: "#5f5b53"
  ink-3: "#8a857a"
  line: "#d6d1c6"
  surface: "#ffffff"
  tile-moss: "#2e6b4f"
  tile-brick: "#b2532d"
  tile-slate: "#3c5a9a"
  tile-ochre: "#7d6326"
  tile-plum: "#6b5a7a"
  tile-teal: "#1f6f78"
  tile-rose: "#8c4a5b"
  tile-olive: "#55622b"
  tile-other: "#4a4740"
  on-tile: "#ffffff"
  focus: "#2b5bd7"
  error: "#a3271c"
  error-wash: "#f6e3df"
typography:
  display:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif"
    fontSize: "2.5rem"
    fontWeight: 800
    lineHeight: 1.05
    letterSpacing: "-0.03em"
    fontFeature: "tnum"
  headline:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif"
    fontSize: "1.75rem"
    fontWeight: 800
    lineHeight: 1.45
    letterSpacing: "-0.02em"
  title:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif"
    fontSize: "1.25rem"
    fontWeight: 500
    lineHeight: 1.25
  body:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.45
    fontFeature: "tnum"
  label:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif"
    fontSize: "0.875rem"
    fontWeight: 600
    lineHeight: 1.3
  caption:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif"
    fontSize: "0.75rem"
    fontWeight: 500
    lineHeight: 1.45
rounded:
  tile: "10px"
  control: "12px"
  menu-item: "8px"
  chip: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  xxl: "32px"
  tap: "48px"
components:
  button-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    height: "52px"
  button-capture:
    backgroundColor: "{colors.ground-2}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    height: "60px"
  button-capture-primary:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    height: "60px"
  input-field:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    height: "48px"
    padding: "0 12px"
  tile:
    backgroundColor: "{colors.tile-moss}"
    textColor: "{colors.on-tile}"
    rounded: "{rounded.tile}"
    padding: "8px 12px 12px"
  menu:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "8px"
  error-note:
    backgroundColor: "{colors.error-wash}"
    textColor: "{colors.error}"
    rounded: "{rounded.control}"
    padding: "12px"
  pending-chip:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    typography: "{typography.caption}"
    rounded: "{rounded.chip}"
---

# Design System: Háztartás

## Overview

**Creative North Star: "The Month as a Map"**

The month is a map of where the money went: category tiles sized by spending, each with a thin limit rail. Everything else, the forms, lists and menus, stays plain so the map is the one loud thing on any screen. The tool is used two ways: one-handed at a till, in shop daylight, and in the evening under a kitchen lamp. It is a family's working ledger, not a fintech dashboard, and it refuses the white-card dashboard with a hero metric and a donut.

The palette is one light, warm set: a stone ground, near-black ink, and eight deep earthy hues that exist only to colour category tiles. Weight is spent on amounts (800) and nowhere else; type is the system sans with tabular numerals everywhere, so columns of money line up. Depth is flat: the screen is separated by tone and hairlines, not shadow.

**Key Characteristics:**
- One light theme, tuned for daylight and lamplight; no dark theme.
- Colour carries category identity (tiles); ink-black carries the single action.
- Money is tabular, heavy and tight; labels are plain and quiet.
- Thumb-first: 48px targets, capture dock fixed at the bottom of the screen.
- Hungarian only; strings live in `app/strings/hu.py`, never in templates.

## Colors

A warm stone neutral field, ink for text and action, and eight tile hues that are the only saturated colour in the product.

### Primary
- **Ink** (`#1c1b19`): text, and the one primary action (Kézi capture button, form submit, count badges, the pending-queue chip). The action colour is black on purpose; colour belongs to the map.

### Secondary
- **Category tile hues** (eight, `--tile-0` to `--tile-7`): moss `#2e6b4f`, brick `#b2532d`, slate `#3c5a9a`, ochre `#7d6326`, plum `#6b5a7a`, teal `#1f6f78`, rose `#8c4a5b`, olive `#55622b`. Each carries white text; the source records them as deep enough for 4.5:1 or better. A category takes hue `c{id % 8}`, so the same category is the same colour every month. The Egyéb tile is a neutral charcoal (`#4a4740`) outside the cycle. Income amounts in the entries list reuse moss.

### Neutral
- **Warm Stone** (`#f3f1ec`): page ground and theme-color. Deliberately not cream.
- **Second Stone** (`#e7e3da`): bars, inactive controls, hover wash, the capture buttons.
- **Ink Secondary** (`#5f5b53`): secondary text (6.1:1 on the ground per the source).
- **Ink Tertiary** (`#8a857a`): disabled only, never body text.
- **Hairline** (`#d6d1c6`): list dividers and input borders.
- **Surface White** (`#ffffff`): inputs and the popover menu, the only places a surface lifts off the ground.
- **Focus Blue** (`#2b5bd7`): the 3px focus outline and input focus halo; the only blue outside the slate tile.
- **Error Brick-Red** (`#a3271c`) on **Error Wash** (`#f6e3df`): form errors.

### Named Rules
**The Map Owns Colour Rule.** Saturated colour appears only as a category tile hue. Chrome, buttons, rows and menus are stone and ink.

**The Stable Hue Rule.** A category's hue is a function of its id (`c{id % 8}`), never of its rank or size, so it does not change between months or screens.

**The Not-Red-For-Over Rule.** Brick is a category hue, so red cannot mean "over limit". Over-limit is a hatched limit rail plus bold "+N € felett" text on the tile. `--error` is for form errors only.

## Typography

**Display, Body and Label Font:** the system sans stack (`system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif`). One family, no webfont.

**Character:** a product UI in Operate mode. The family's Android phones render Roboto with tabular figures, so a self-hosted face would add a request and no recognisable character. Tabular numerals are set on `body`, so every number aligns; `.num` adds no-wrap.

### Hierarchy
- **Display** (800, 2.5rem, 1.05, -0.03em): the balance in the month statement sentence only.
- **Headline** (800, 1.75rem, -0.02em): the login title and the large tile amount.
- **Title** (500, 1.25rem, 1.25): the statement sentence; tile amounts in regular tiles are 1.25rem at 800.
- **Body** (400, 1rem, 1.45): everything default; section headings are 1rem at 700.
- **Label** (600, 0.875rem): tile names, form labels, month stepper, capture button labels.
- **Caption** (500 to 600, 0.75rem): tile notes and limit lines, legend, meta lines, count badges.

### Named Rules
**The Heavy Amounts Rule.** Weight 800 is reserved for money (statement balance, tile amounts, login title). Names and labels stay at 500 to 700.

**The Step-Down Rule.** Type shrinks by scale step, never below `--fs-xs`; a narrow tile (container under 124px) drops name to xs and amount to m before a word breaks.

## Layout

A single column, phone first, designed for 360px width. The shell is a full-height flex column: top bar (name, month stepper, menu), `main` with 16px side padding and 190px bottom padding to clear the dock, and a fixed capture dock. From 640px the content is capped at 560px and centred. The spacing scale is 4, 8, 12, 16, 24, 32px.

The map is an absolutely positioned container (340px tall, 420px from 640px, 240px for the child view) where each tile is placed by percentage custom properties `--x --y --w --h` computed server-side by the treemap service. Tiles have 2px of padding between them. The login screen centres a 380px column.

Touch targets are 48px minimum (`--tap`): stepper arrows, menu button, menu rows, inputs; capture buttons are 60px and the submit button 52px.

### Named Rules
**The Whole Euros On Tiles Rule.** Tiles show whole euros (`eur_short`) because they are glanceable; lists and totals show exact cents (`eur`).

**The Limit Yields First Rule.** A short tile (`tile--small`) hides its limit line before the hidden-entry note, because the note is part of the truth of the number and the limit is still visible on the rail.

## Elevation & Depth

Flat by default. Depth is conveyed by tone (ground, second stone, white surface) and 1px hairlines. The only shadow is the popover menu (`0 8px 24px rgb(28 27 25 / 0.14)`), a soft ambient lift because it floats over content. The dock sits on a ground-coloured fade (`linear-gradient` from ground at 70% to transparent) instead of a bar or shadow. Pressed tiles scale to 0.98 over 160ms (`cubic-bezier(0.16, 1, 0.3, 1)`), disabled under reduced motion.

### Named Rules
**The Flat-By-Default Rule.** Surfaces carry no shadow at rest; the menu popover is the single exception.

## Shapes

Softly rounded rectangles in three sizes: tiles 10px, controls and menu 12px, menu items 8px; the pending chip is a full pill. Small colour marks are 3px or 4px rounded squares (list dots, the login mark's three tiles, the legend miniature). Stepper and icon buttons are circles. Icons are one stroke family on a 24px grid with a 2px round stroke, drawn inline at 22px.

## Components

### Buttons
- **Shape:** 12px radius.
- **Primary:** ink background, stone text, weight 700, 52px high (form submit) or 60px (the Kézi capture button, with icon).
- **Hover:** background `#33312d`.
- **Capture (secondary):** second stone background, 60px high, label over a small "hamarosan" caption; disabled ones (Fotó, Hang) use tertiary ink and show no pointer.
- **Icon button:** 48px circle, transparent, second-stone wash on hover.

### Cards / Containers
- No card component. Lists are rows separated by 1px hairlines; the people list and entries list have no boxed container.

### Inputs / Fields
- **Style:** white fill, 1.5px hairline border, 12px radius, 48px high, 12px side padding.
- **Focus:** border turns ink with a 3px translucent focus-blue halo.
- **Error:** an error note on error wash with error-red text, 12px radius, announced with `role="alert"`.

### Navigation
- A month stepper (round 48px arrows around the month label) in the top bar, and a popover menu opened by the menu icon (white, 200px minimum, 48px rows, count badge in ink for waiting drafts). Mobile is the only layout.

### Category Tile (signature)
A rectangle in the category hue with white text: name at the top (with an optional note line for hidden entries), amount at the bottom, then a limit line ("N € / M €" or bold "+N € felett"). A 6px rail runs along the tile's bottom edge: a darkened track with the used part in white; over limit, the used part becomes white diagonal hatching. Tiles are links to the category's entries. Size variants `tile--big` (amount 1.75rem) and `tile--small` (name xs, amount 1rem, limit hidden).

### Capture Dock
Fixed to the bottom with safe-area padding: an optional ink pill showing queued offline items, then a three-column row (Fotó, Hang, Kézi) at 1 : 1 : 1.6. Kézi is the only live, primary action while photo and voice are shown disabled in phase 1.

## Do's and Don'ts

### Do:
- **Do** use ink `#1c1b19` for the single primary action on a screen, and the tile hues only for categories.
- **Do** assign category hue by `c{id % 8}` and keep "Egyéb" neutral.
- **Do** put tabular numerals on every amount and weight 800 only on amounts.
- **Do** show whole euros on tiles and exact cents in lists.
- **Do** signal over-limit with the hatched rail and "+N € felett" text.
- **Do** keep touch targets at 48px or more and every string in `app/strings/hu.py`.
- **Do** pick palette decisions from the scene: shop daylight and kitchen lamp, one light theme.

### Don't:
- **Don't** add a dark theme; one tuned palette beats two half-tuned ones.
- **Don't** use red, or `--error`, for over-limit, deletions or counts; it is for form errors only.
- **Don't** drop a tile's hidden-entry note to keep its limit line; the limit goes first.
- **Don't** add a hero-metric card, a donut chart, or white dashboard cards around the map.
- **Don't** use `--ink-3` for text people must read; it is disabled-only.
- **Don't** introduce a webfont or a second family; the system sans is a recorded decision.
- **Don't** reuse the repo owner's `brand/` identity; this is the family's tool.

## Known Drift (not canonized)

- None open. The negative-balance colour drift found while documenting was fixed the same day: a negative balance is ink, and the sentence itself ("... ennyivel több ment el, mint amennyi bejött") carries the meaning.
