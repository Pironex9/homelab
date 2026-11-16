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
  amount-input:
    fontFamily: "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif"
    fontSize: "2rem"
    fontWeight: 800
    lineHeight: 1.45
    letterSpacing: "-0.02em"
    fontFeature: "tnum"
rounded:
  tile: "10px"
  control: "12px"
  menu-item: "8px"
  chip: "999px"
  switch: "13px"
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
  button-quiet:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    rounded: "{rounded.control}"
    height: "52px"
  input-amount:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.amount-input}"
    rounded: "{rounded.control}"
    height: "64px"
  seg-option:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    height: "48px"
  seg-option-selected:
    backgroundColor: "{colors.ink}"
    textColor: "{colors.ground}"
    typography: "{typography.label}"
    rounded: "{rounded.control}"
    height: "48px"
  secret-block:
    backgroundColor: "{colors.ground-2}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "12px"
  duplicate-prompt:
    backgroundColor: "{colors.ground-2}"
    textColor: "{colors.ink}"
    rounded: "{rounded.control}"
    padding: "16px"
  refused-box:
    backgroundColor: "{colors.error-wash}"
    textColor: "{colors.error}"
    rounded: "{rounded.control}"
    padding: "12px 16px"
  expandable-row:
    textColor: "{colors.ink}"
    typography: "{typography.body}"
    height: "56px"
---

# Design System: Háztartás

## Overview

**Creative North Star: "The Month as a Map"**

The month is a map of where the money went: category tiles sized by spending, each with a thin limit rail. Everything else, the forms, lists and menus, stays plain so the map is the one loud thing on any screen. The tool is used two ways: one-handed at a till, in shop daylight, and in the evening under a kitchen lamp. It is a family's working ledger, not a fintech dashboard, and it refuses the white-card dashboard with a hero metric and a donut.

The palette is one light, warm set: a stone ground, near-black ink, and eight deep earthy hues that exist only to colour category tiles. Weight is spent on amounts (800) and almost nowhere else; type is the system sans with tabular numerals everywhere, so columns of money line up. Depth is flat: the screen is separated by tone and hairlines, not shadow. The sub-pages (entries, entry form, pocket, settings) are plain forms and hairline rows on the same stone ground; none of them borrows the map's colour.

**Key Characteristics:**
- One light theme, tuned for daylight and lamplight; no dark theme.
- Colour carries category identity (tiles); ink-black carries the single action.
- Money is tabular, heavy and tight; labels are plain and quiet.
- Thumb-first: 48px targets, capture dock fixed at the bottom of the home screen, wide full-width submit buttons on forms.
- Offline-aware: one queue counter floats on every page; refused queue items are shown, not dropped.
- Hungarian only; strings live in `app/strings/hu.py`, never in templates.

## Colors

A warm stone neutral field, ink for text and action, and eight tile hues that are the only saturated colour in the product.

### Primary
- **Ink** (`#1c1b19`): text, and the one primary action (Kézi capture button, form submit, count badges, the queue counter, the selected segmented option, the switch when on). The action colour is black on purpose; colour belongs to the map.

### Secondary
- **Category tile hues** (eight, `--tile-0` to `--tile-7`): moss `#2e6b4f`, brick `#b2532d`, slate `#3c5a9a`, ochre `#7d6326`, plum `#6b5a7a`, teal `#1f6f78`, rose `#8c4a5b`, olive `#55622b`. Each carries white text; the source records them as deep enough for 4.5:1 or better. A category takes hue `c{id % 8}`, so the same category is the same colour every month; the list dots in entries, pocket and settings reuse the same hue. The Egyéb tile is a neutral charcoal (`#4a4740`) outside the cycle. Income amounts in lists reuse moss.

### Neutral
- **Warm Stone** (`#f3f1ec`): page ground and theme-color. Deliberately not cream.
- **Second Stone** (`#e7e3da`): bars, inactive controls, hover wash, the capture buttons, and the two quiet panels (the hidden-entry block and the duplicate prompt).
- **Ink Secondary** (`#5f5b53`): secondary text, hints, meta lines (6.1:1 on the ground per the source).
- **Ink Tertiary** (`#8a857a`): disabled text, and the off-state track of the switch; never body text.
- **Hairline** (`#d6d1c6`): list and row dividers, input and segmented-option borders, the quiet button border.
- **Surface White** (`#ffffff`): inputs, segmented options and the popover menu, the only places a surface lifts off the ground.
- **Focus Blue** (`#2b5bd7`): the 3px focus outline and input focus halo; the only blue outside the slate tile.
- **Error Brick-Red** (`#a3271c`) on **Error Wash** (`#f6e3df`): form errors, and the refused-queue box, which is also an error state.

### Named Rules
**The Map Owns Colour Rule.** Saturated colour appears only as a category tile hue. Chrome, buttons, rows and menus are stone and ink.

**The Stable Hue Rule.** A category's hue is a function of its id (`c{id % 8}`), never of its rank or size, so it does not change between months or screens.

**The Not-Red-For-Over Rule.** Brick is a category hue, so red cannot mean "over limit". Over-limit is a hatched limit rail plus bold "+N € felett" text on the tile. `--error` is for form errors and refused queue items only.

## Typography

**Display, Body and Label Font:** the system sans stack (`system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif`). One family, no webfont.

**Character:** a product UI in Operate mode. The family's Android phones render Roboto with tabular figures, so a self-hosted face would add a request and no recognisable character. Tabular numerals are set on `body`, so every number aligns; `.num` adds no-wrap.

### Hierarchy
- **Display** (800, 2.5rem, 1.05, -0.03em): the balance in the month statement sentence only.
- **Headline** (800, 1.75rem, -0.02em): the login title and the large tile amount.
- **Amount input** (800, 2rem, -0.02em): the amount field of the entry form and pocket forms; it is money, so it takes the amount weight.
- **Title** (500, 1.25rem, 1.25): the statement sentence; tile amounts in regular tiles are 1.25rem at 800. Sub-page titles in the top bar are 1.25rem at 800 (see Known Drift).
- **Body** (400, 1rem, 1.45): everything default; section headings (`h2`) are 1rem at 700.
- **Label** (600, 0.875rem): tile names, form labels, segmented options, month stepper, capture button labels, filter summary, facts values.
- **Caption** (500 to 600, 0.75rem): tile notes and limit lines, legend, meta lines, hints, count badges, the queue counter.

### Named Rules
**The Heavy Amounts Rule.** Weight 800 is reserved for money (statement balance, tile amounts, amount input, login title). Names and labels stay at 500 to 700.

**The Step-Down Rule.** Type shrinks by scale step, never below 0.6875rem; a narrow tile (container under 124px) drops name to xs and amount to m, and under 92px it also tightens its padding to 8px and drops the name to 0.6875rem, before a word breaks.

## Layout

A single column, phone first, designed for 360px width. The shell is a full-height flex column: top bar, `main` with 16px side padding and 190px bottom padding, and on the home screen a fixed capture dock. The home top bar carries the name, the month stepper and the menu; sub-pages swap this for a sub-page header (back icon, page title, and the month stepper only where the page is month-scoped). From 640px the content is capped at 560px and centred. The spacing scale is 4, 8, 12, 16, 24, 32px.

The map is an absolutely positioned container (340px tall, 420px from 640px, 240px for the child view) where each tile is placed by percentage custom properties `--x --y --w --h` computed server-side by the treemap service. Tiles have 2px of padding between them and are size containers, so their type steps down by container width (124px and 92px steps) rather than by viewport. The login screen centres a 380px column.

Forms are one column of label over control with 8px gaps. The entry form follows the till: amount (with a 104px currency select beside it), kind, category, merchant, date, payment, wallet, note, then the hidden-entry block. Settings and pocket use expandable hairline rows: a closed row is a 56px summary, an open row shows its form beneath. The entries list has a search field always visible and the other filters folded into a `details` that opens by itself when a filter is active.

Touch targets are 48px minimum (`--tap`): stepper arrows, menu and back buttons, menu rows, inputs, segmented options, the switch row; capture buttons are 60px, the submit button 52px, the amount input 64px. The one exception is the refused-queue action button at 40px.

### Named Rules
**The Whole Euros On Tiles Rule.** Tiles show whole euros (`eur_short`) because they are glanceable; lists and totals show exact cents (`eur`).

**The Limit Yields First Rule.** A short tile (`tile--small`) hides its limit line before the hidden-entry note, because the note is part of the truth of the number and the limit is still visible on the rail.

**The Counter Floats Rule.** The offline queue counter exists once per page, fixed and centred at the bottom; where a capture dock exists it sits 92px above the bottom edge, clear of the dock, otherwise 16px.

## Elevation & Depth

Flat by default. Depth is conveyed by tone (ground, second stone, white surface) and 1px hairlines. Two shadows exist, both for things that float over content: the popover menu (`0 8px 24px rgb(28 27 25 / 0.14)`), a soft ambient lift, and the queue counter (`0 4px 14px rgb(28 27 25 / 0.18)`), a small chip that must stay readable over any list or tile. The dock sits on a ground-coloured fade (`linear-gradient` from ground at 70% to transparent) instead of a bar or shadow. Pressed tiles scale to 0.98 over 160ms (`cubic-bezier(0.16, 1, 0.3, 1)`), disabled under reduced motion; the switch thumb and track animate over the same 160ms and easing.

### Named Rules
**The Flat-By-Default Rule.** Surfaces carry no shadow at rest; only elements that float over scrolling content (the menu popover, the queue counter) are lifted.

## Shapes

Softly rounded rectangles in three sizes: tiles 10px, controls and panels 12px, menu items 8px; the queue counter is a full pill and the switch a 13px pill. A segmented choice is one joined strip: only its outer ends take the 12px radius, the shared edges are square. Small colour marks are 3px or 4px rounded squares (list dots, the legend miniature). Stepper and icon buttons are circles. Icons are one stroke family on a 24px grid with a 2px round stroke, drawn inline at 22px.

**The Mark.** Three tiles in a 1.6 : 1 split: one tall moss tile on the left, brick above slate on the right, 3px gaps, 4px corners at the 56px login size. The PWA icon (180, 192 and 512px PNGs) is the same mark, rounded, centred on the stone ground inside the maskable safe zone, with no text and no border.

## Components

### Buttons
- **Shape:** 12px radius.
- **Primary:** ink background, stone text, weight 700, 52px high (form submit) or 60px (the Kézi capture button, with icon). `btn--wide` makes it full width, which is how every form submit is set; `btn--small` (48px, 14px type) sits beside the search field.
- **Hover:** background `#33312d`.
- **Quiet:** `btn--quiet`, transparent with a 1.5px hairline border and ink text, second-stone wash on hover. For secondary actions that must not compete with the one ink action (archive in settings, delete on the entry detail, cancel in the duplicate prompt). `aside-action` places a full-width quiet button under a form.
- **Capture (secondary):** second stone background, 60px high, label over a small "hamarosan" caption; disabled ones (Fotó, Hang) use tertiary ink and show no pointer.
- **Icon button:** 48px circle, transparent, second-stone wash on hover; the back icon on sub-pages is the same button, pulled 12px left so the glyph aligns with the page edge.

### Cards / Containers
- No card component. Lists are rows separated by 1px hairlines; the people list, entries list and settings rows have no boxed container. The only boxed blocks are quiet panels on second stone (hidden-entry block, duplicate prompt) and the error-wash refused box, all 12px radius.

### Inputs / Fields
- **Style:** white fill, 1.5px hairline border, 12px radius, 48px high, 12px side padding. Selects and date inputs share the style.
- **Focus:** border turns ink with a 3px translucent focus-blue halo.
- **Amount:** the amount input is 64px high at 2rem 800, beside a 104px currency select; the first field the thumb reaches, autofocused on the entry form.
- **Segmented choice (`seg`):** a legend over a joined strip of equal options (kind, payment, category kind); white with a hairline border, the selected option fills ink with stone text. The radio itself is invisible and the focus ring is drawn on the option.
- **Switch:** a 44 x 26px pill, tertiary-ink track when off, ink when on, white thumb. It lives in the hidden-entry block with a hint line; turning it on reveals the reveal-date field.
- **Hint:** 0.75rem secondary ink under a field, for one-line guidance.
- **Error:** an error note on error wash with error-red text, 12px radius, announced with `role="alert"`.

### Navigation
- Home top bar: a month stepper (round 48px arrows around the month label) and a popover menu opened by the menu icon (white, 200px minimum, 48px rows, count badge in ink for waiting drafts). Sub-pages: back icon, bold page title, and the month stepper only on the entries list when a month is shown.

### Entry List
Hairline rows in a three-column grid: hue dot, name, amount, with a quiet meta line under the name. Names link to the entry; income amounts are moss and prefixed "+". Above it, a search field with a small ink submit button and a folded "more filters" summary (48px, secondary ink). An empty result is a single secondary-ink line.

### Expandable Rows
A `details` row (`row`) with a 56px summary: dot, name, value; the open row reveals its form and a quiet action under it. `row--add` is the same without the divider and with a secondary-ink summary, for "add" entries. Used by settings (categories, recurring items) and by the pocket top-up forms.

### Facts List
`facts`: a two-column definition list, secondary-ink terms in 0.875rem and 600-weight values, for the detail view of one entry.

### Duplicate Prompt
Shown in place of the submit button when a similar entry exists: a second-stone panel (16px padding, `role="alert"`) with a bold title, a short list of the matching entries, a full-width ink confirm button and a quiet cancel link. It informs and asks; it is not red.

### Queue Counter and Refused Box
The queue counter (`pending--global`) is the ink pill in caption type, hidden until the offline queue holds items; it is fixed, centred, above the dock where one exists, and the only floating chip. The refused box is an error-wash panel on the capture page listing queue items the server rejected, each with a 40px fix or discard action; the hint line above it is error-red at 600.

### Category Tile (signature)
A rectangle in the category hue with white text: name at the top (with an optional note line for hidden entries), amount at the bottom, then a limit line ("N € / M €" or bold "+N € felett"). A 6px rail runs along the tile's bottom edge: a darkened track with the used part in white; over limit, the used part becomes white diagonal hatching. Tiles are links to the category's entries. Size variants `tile--big` (amount 1.75rem) and `tile--small` (name xs, amount 1rem, limit hidden), plus the container-driven narrow steps described under Typography. The legend miniature under the map is a 28 x 14px tile with a 4px rail at the bottom edge.

### Capture Dock
Fixed to the bottom of the home screen with safe-area padding: a three-column row (Fotó, Hang, Kézi) at 1 : 1 : 1.6. Kézi is the only live, primary action while photo and voice are shown disabled in phase 1. The queue counter floats above it.

## Do's and Don'ts

### Do:
- **Do** use ink `#1c1b19` for the single primary action on a screen, and the tile hues only for categories.
- **Do** assign category hue by `c{id % 8}` and keep "Egyéb" neutral.
- **Do** put tabular numerals on every amount and weight 800 only on amounts.
- **Do** show whole euros on tiles and exact cents in lists.
- **Do** signal over-limit with the hatched rail and "+N € felett" text.
- **Do** keep touch targets at 48px or more and every string in `app/strings/hu.py`.
- **Do** make secondary actions quiet buttons (hairline outline), so the ink button stays the single action.
- **Do** use a segmented choice for two to three exclusive options and a `details` row for anything that needs a form but is rarely opened.
- **Do** pick palette decisions from the scene: shop daylight and kitchen lamp, one light theme.

### Don't:
- **Don't** add a dark theme; one tuned palette beats two half-tuned ones.
- **Don't** use red, or `--error`, for over-limit, deletions or counts; it is for form errors and refused queue items only.
- **Don't** drop a tile's hidden-entry note to keep its limit line; the limit goes first.
- **Don't** add a hero-metric card, a donut chart, or white dashboard cards around the map.
- **Don't** use `--ink-3` for text people must read; it is disabled-only.
- **Don't** introduce a webfont or a second family; the system sans is a recorded decision.
- **Don't** add a second floating element or a second queue counter; one chip per page.
- **Don't** reuse the repo owner's `brand/` identity; this is the family's tool.

## Known Drift (not canonized)

- **Sub-page titles at weight 800.** `.subbar h1` is 1.25rem at 800, but the Heavy Amounts Rule reserves 800 for money. The titles are not amounts; this is a defect the build carries, not a precedent. New surfaces should use 700.
- **Dock clearance on every page.** `main` keeps 190px of bottom padding on all pages, though only the home screen has a dock. On sub-pages it is dead scroll room (the floating counter does use some of it). Not a rule for new surfaces.
- **Literal colours in the stylesheet.** Error wash (`#f6e3df`), the primary hover (`#33312d`) and white (`#fff`) are written as literals in `app.css` rather than tokens; the tokens file has no `--error-wash`, hover or surface variable. The documented values are the same.
- **Small type under the scale.** `0.6875rem` appears in the capture caption and the narrowest tile name, below `--fs-xs`; it is outside the token scale.
- **Refused-box action at 40px.** Below the 48px touch minimum, kept because it sits inside a dense list row; not a size to reuse.
- **Impeccable side-tab flag, false positive.** The hook flags `.map-legend i::after` as a side-tab border. It is a 4px rail miniature along the bottom of a 28 x 14px legend swatch (the tile's limit rail at small scale), not a coloured side border; recorded here so it is not "fixed".
- The negative-balance colour drift found earlier stays fixed: a negative balance is ink, and the sentence itself ("... ennyivel több ment el, mint amennyi bejött") carries the meaning.
