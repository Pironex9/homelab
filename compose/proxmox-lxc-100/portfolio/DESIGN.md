---
name: Enci - rajzok
description: A museum accession register for one growing collection of drawings - japanned steel, oxblood buckram, conservation board, and a violet date stamp.
colors:
  steel: "#171a20"
  steel-3: "#262b35"
  ox: "#6e2029"
  ox-lit: "#8a2833"
  board: "#9aa7b4"
  board-ink: "#20242c"
  brass: "#b08d4f"
  brass-dim: "#7d6438"
  ink: "#dfe3e9"
  ink-soft: "#98a1af"
  rail-ink: "#e7d9c4"
  paper: "#f4f2ec"
  stamp: "#4a2d7a"
  stamp-lit: "#9b8ae0"
typography:
  display:
    fontFamily: "Archivo Narrow, system-ui, sans-serif"
    fontSize: "1.9rem"
    fontWeight: 700
    letterSpacing: "0.1em"
  title:
    fontFamily: "Archivo Narrow, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "normal"
  body:
    fontFamily: "Archivo Narrow, system-ui, sans-serif"
    fontSize: "1rem"
    fontWeight: 600
    lineHeight: 1.45
    letterSpacing: "normal"
  label:
    fontFamily: "Archivo Narrow, system-ui, sans-serif"
    fontSize: "0.75rem"
    fontWeight: 600
    lineHeight: 1.4
    letterSpacing: "0.14em"
  data:
    fontFamily: "Courier Prime, ui-monospace, monospace"
    fontSize: "0.75rem"
    fontWeight: 400
    lineHeight: 1.4
  stamp:
    fontFamily: "Courier Prime, ui-monospace, monospace"
    fontSize: "1rem"
    fontWeight: 700
    lineHeight: 1
    letterSpacing: "0.02em"
rounded:
  image: "1px"
  surface: "2px"
spacing:
  xs: "0.4rem"
  sm: "0.55rem"
  md: "0.9rem"
  lg: "1.4rem"
  gutter: "clamp(0.9rem, 3vw, 2rem)"
  section: "clamp(2.4rem, 5vw, 4rem)"
components:
  view-toggle:
    backgroundColor: "transparent"
    textColor: "{colors.rail-ink}"
    typography: "{typography.label}"
    padding: "0.45rem 0.85rem"
  view-toggle-active:
    backgroundColor: "{colors.board}"
    textColor: "{colors.board-ink}"
  tab-brass:
    backgroundColor: "{colors.brass}"
    textColor: "#2a2213"
    typography: "{typography.label}"
    rounded: "{rounded.surface}"
    padding: "0.5rem 0.8rem"
  tab-brass-active:
    backgroundColor: "#dcbd7c"
    textColor: "#231b0c"
  folder-card:
    backgroundColor: "{colors.board}"
    textColor: "{colors.board-ink}"
    typography: "{typography.data}"
    padding: "1.5rem 0.5rem 0.6rem"
  mount:
    backgroundColor: "{colors.paper}"
    rounded: "{rounded.surface}"
    padding: "0.75rem 0.75rem 2.5rem"
    height: "clamp(13rem, 25vw, 20rem)"
  year:
    backgroundColor: "transparent"
    textColor: "{colors.rail-ink}"
    typography: "{typography.data}"
    rounded: "{rounded.surface}"
    padding: "0.4rem 0.55rem"
  year-active:
    textColor: "#2a2213"
    padding: "0.75rem 0.8rem"
  search-label:
    backgroundColor: "{colors.brass}"
    textColor: "#2a2213"
    typography: "{typography.label}"
    padding: "0.4rem 0.7rem 0.35rem"
  search-input:
    backgroundColor: "{colors.board}"
    textColor: "{colors.board-ink}"
    typography: "{typography.data}"
    padding: "0.4rem 0.55rem"
    width: "11rem"
  slip:
    backgroundColor: "{colors.board}"
    textColor: "{colors.board-ink}"
    rounded: "{rounded.surface}"
    padding: "1.1rem 1.2rem 1.3rem"
  bar-button:
    backgroundColor: "transparent"
    textColor: "{colors.rail-ink}"
    typography: "{typography.label}"
    padding: "0.4rem 0.7rem"
---

# Design System: Enci - rajzok

Recorded from the built page, not from intention. Every value below was read out
of `lib/render.js` (the CSS, markup and client script all live in that one file)
and `lib/register.js`. `dist/` is generated - never edit it. The direction
contract sits in the HTML comment at the top of `<body>`; the approved comps and
the list of what must not be literalised are in `.impeccable/mocks/`.

## Overview

**Creative North Star: "The Accession Register"**

This is a museum accession register, not a gallery wall. The collection is a
numbered, dated list that grows; the drawings are the objects in the drawer. Every
material on the page is a register's own material - japanned steel for the cabinet,
oxblood buckram for the rails, blue-grey conservation board for the cards, brass for
the hardware, aniline violet for the stamp. The world was chosen over the incumbent
(warm paper, serif display, terracotta accent, masonry of matted thumbnails), which
had never been decided so much as defaulted into.

The dark ground is not a style preference and is not negotiable. The works are
graphite and watercolour on white paper; a dark cabinet ground is what makes them
read as objects sitting on the page rather than as page background. Every surface
that touches a drawing is paper-coloured (`#f4f2ec`), and every surface that holds
paper is board, steel or buckram.

Density is high and deliberately clerical. Chrome is small, condensed and uppercase;
data is monospaced; the drawings are the only large things. The one moment of
personality is the date stamp landing on the lead works - a single authored gesture
in a page that otherwise does not perform.

**Key Characteristics:**

- Dark japanned-steel ground throughout; no light theme exists and none is intended.
- Violet appears on dates and on nothing else, on the whole page.
- Condensed uppercase capitals for chrome, typewriter monospace for every figure.
- Two-corner language: 2px on surfaces, 1px on images. Nothing is pill-shaped or circular.
- Images are contained in fixed boxes, never cropped - in all four places images appear.
- Flat colour fields; no texture assets, no CSS gradients pretending to be cloth.
- Server-rendered in both views: the page works with JavaScript off.

## Colors

A cabinet palette: four materials (steel, buckram, board, brass) plus one ink that
is spent on exactly one thing.

### Primary

- **Aniline Stamp Violet on board** (`{colors.stamp}`): the date stamp wherever it
  sits on a light surface - the lead work's mount and the detail catalogue card.
- **Aniline Stamp Violet on steel** (`{colors.stamp-lit}`): the same stamp rendered
  for the dark ground. This is the default `.stamp` colour; the dark token is an
  override applied only by `.lead .sheet .stamp` and `.slip .stamp`.

### Secondary

- **Oxblood Buckram** (`{colors.ox}`): the top rail, the year rail, the detail bar,
  the filmstrip, and the ledger's hovered/active row. The colour of every band that
  frames the collection rather than being part of it.
- **Lit Oxblood** (`{colors.ox-lit}`): a single 1px ring on the pressed category tab,
  so a brass tab that has been selected is seated against the cabinet's own red.
- **Brass** (`{colors.brass}`) and **Dimmed Brass** (`{colors.brass-dim}`): the
  hardware. Brass carries every section label, table rule, hairline between an
  oxblood band and its neighbour, the category tabs, the search label, and the focus
  ring. It is the only material allowed to look dimensional.

### Tertiary

- **Conservation Board** (`{colors.board}`) with **Board Ink** (`{colors.board-ink}`):
  the card stock. Folder cards in the drawer, the detail catalogue slip, the search
  field, and the pressed view toggle.
- **Rail Ink** (`{colors.rail-ink}`, `#e7d9c4`): warm off-white text and hairline
  strokes used exclusively on oxblood - the count, the view toggles, the year labels,
  the detail-bar buttons. Never used on steel.
- **Mount Paper** (`{colors.paper}`, `#f4f2ec`): the backing behind every image, at
  every scale from the 2.4rem ledger thumbnail to the full detail stage. One paper
  colour, six occurrences, no variants.

### Neutral

- **Japanned Steel** (`{colors.steel}`): the page ground, and the `theme-color` meta.
- **Steel Divider** (`{colors.steel-3}`): the only neutral hairline - the band, tab
  column and footer rules that separate regions of the dark ground itself.
- **Ink** (`{colors.ink}`) / **Soft Ink** (`{colors.ink-soft}`): body text and
  secondary/register text on steel.

### Named Rules

**The Violet-For-Dates Rule.** Violet appears on dates and on nothing else. It is
the only saturated violet on the page, so the eye lands on the thing the product is
arguing: that this is a body of work spanning years. Spending it on a button, a
link, a hover state or an active filter destroys the argument. Audit test: search
the stylesheet for `--stamp`; every hit must be a date.

**The Two Grounds Rule.** There are two violet tokens because one cannot serve both
grounds. `{colors.stamp}` on the dark ground fails contrast outright; `{colors.stamp-lit}`
on board is washed out. They are the same ink rendered for two papers. Do not
collapse them into one, and do not add a third.

**The Warm-On-Red Rule.** Text and hairlines on oxblood are `{colors.rail-ink}` or
brass, never `{colors.ink}`. Text on steel is `{colors.ink}`, never rail-ink. The two
warm/cool text families do not cross grounds.

## Typography

**Display / UI Font:** Archivo Narrow (600, 700) with `system-ui, sans-serif`
**Data Font:** Courier Prime (400, 700) with `ui-monospace, monospace`

Both faces are self-hosted from `assets/fonts/`, declared in `assets/fonts.css`,
in **both `latin` and `latin-ext` subsets**. The page makes no third-party request.

**Character:** condensed capitals with wide tracking for anything that behaves like
a drawer label, and a real typewriter for anything that behaves like a figure. The
monospace is used for data and measurement, not as a costume: it never sets a
sentence.

### Hierarchy

Three screen sizes exist. That is the whole ramp.

- **Display** (700, 1.9rem / 30.4px, `0.1em` tracking, uppercase): the name in the
  top rail. The page's only display step and its only use.
- **Title / Body** (600, 1rem / 16px, line-height 1.25 for work titles and 1.45 for
  the one intro sentence, max-width `60ch`): drawing titles in the ledger and the
  catalogue slip, and Enci's own sentence in the band. The intro is deliberately set
  in Archivo Narrow, not Courier: setting the only human voice on the page in the
  data face made it indistinguishable from machine metadata.
- **Label** (600, 0.75rem / 12px, `0.12em`-`0.2em` tracking, uppercase): tabs, view
  toggles, section rules, table headers, definition-list terms, buttons.
- **Data** (400, 0.75rem / 12px): every accession number, every ledger cell, the
  count, the year labels, the footer.
- **Stamp** (700, 1rem / 16px, `0.02em`, rotated `-2.5deg`): dates only.

An earlier build had six sizes inside a 1.6:1 range and read flat. Adding a fourth
step is a system change, not a tweak.

### Named Rules

**The Hungarian Line-Box Rule.** `--label` carries `line-height: 1.4`, not 1.1. At
1.1 the line box clips the marks off uppercase **Á**, **Ó**, **É**, **Ő** and **Ű** -
a bug that is invisible in English and disfiguring in Hungarian, on a page whose UI
is entirely Hungarian. Never tighten a line-height on an uppercase label below 1.3,
and never test a type change on ASCII text alone.

**The Latin-Ext Rule.** Both self-hosted faces ship `latin` **and** `latin-ext`
`@font-face` blocks. Hungarian needs U+0151 (ő) and U+0171 (ű), which the latin
subset does not carry and a system stack cannot promise. Dropping latin-ext is not a
saving of four files, it is a silent glyph-substitution bug in half the UI copy.

**The Typewriter-Is-Data Rule.** Courier Prime sets numbers, dates, codes and table
cells. It never sets prose, a heading, or a button label. If a new element carries a
figure, it is Courier; if it carries a word, it is Archivo Narrow.

## Layout

The page is one HTML document with two server-rendered views (`#view-fiok`,
`#view-naplo`) plus a detail overlay. Both views are in the DOM at all times; the
toggle only sets `hidden`. This is what makes the page work with JavaScript off and
what makes printing view-independent.

**The shell.** Above `60rem` the body is a three-column grid: category tabs (auto) |
work column (`minmax(0,1fr)`) | year rail (auto). The tabs stand up as a vertical
column of drawer dividers against a `steel-3` right border; the year rail is a
vertical oxblood strip. Below `60rem` the shell collapses to one column and both
rails become horizontal scrollers - the tabs above the work, the years below it,
each keeping its oxblood/steel band.

**Horizontal gutter.** One value everywhere: `clamp(0.9rem, 3vw, 2rem)`. Rail, band,
tabs, work column, year rail, detail bar, filmstrip and footer all share it, which is
what keeps the vertical edges of every band aligned.

**The drawer grid.** `repeat(auto-fill, minmax(9.5rem, 1fr))` with a `0.55rem 0.4rem`
gap. Even-indexed cards are pushed down `0.55rem` so the bank reads as leaning files
rather than as a table.

**The lead row.** `repeat(auto-fit, minmax(15rem, 1fr))` - three across on desktop,
reflowing to one on a phone, separated from the drawer by `clamp(2.4rem, 5vw, 4rem)`.

**The detail overlay.** `position: fixed` full-bleed at `z-index: 50`, grid rows
`auto 1fr`. Above `56rem` the body splits into stage | `20rem` catalogue slip; below
that they stack. Opening it sets `body { overflow: hidden }` and moves focus to the
close button; closing restores focus to the element that opened it.

**Scrollbar gutter.** `html { scrollbar-gutter: stable }` on screen, so switching
views does not shift the layout sideways.

### Named Rules

**The Register-Always-Prints Rule.** What comes out of Ctrl+P must not depend on
which view happened to be open. `@media print` forces `#view-fiok` and `#view-naplo`
to `display: block !important` (needed to beat the `hidden` attribute the toggle
leaves behind), hides the fiók drawer and every interactive band, and emits A3
portrait: one sheet of three selected works, then the full ledger. There is no second
renderer and there must never be one.

**The Print Gutter Rule.** `@media print { html { scrollbar-gutter: auto } }` is
load-bearing. The reserved gutter has no meaning without a scrollbar, but the print
layout keeps it and pushes every sheet left until the first character of each line
falls off the left edge of the paper. Anything added to `html` for screen scrolling
must be unwound for print.

## Elevation & Depth

Depth comes from cast shadow onto the dark ground, not from tonal layering: the
palette has no surface ramp, so a raised element is raised because it throws a
shadow. There are exactly two shadow roles.

### Shadow Vocabulary

- **Cast** (`box-shadow: 0 2px 4px rgba(0,0,0,.45), 0 18px 44px rgba(0,0,0,.5)`, the
  `--shadow` token): a real offset plus a wide soft blur. Applied to the things that
  hold a drawing - the lead mount, the folder cards, the detail stage, the catalogue
  slip.
- **Cast, lifted** (`--shadow-lift`, the same recipe scaled up): the hover state of a
  folder card, paired with `translateY(-4px)` and `brightness(1.06)`.
- **Seated** (`0 1px 2px rgba(0,0,0,.5)`; pressed: `0 0 0 1px var(--ox-lit), 0 2px 6px
  rgba(0,0,0,.6)`): brass hardware only. Hardware is bolted to the cabinet, so it
  gets a tight seating shadow, never the wide cast one.

### Named Rules

**The Drawings Cast Rule.** The wide cast shadow belongs to surfaces that carry a
drawing or its catalogue record. Chrome does not cast it: rails, bands, tabs, year
buttons and toggles are flush with the cabinet. If a new element wants `--shadow`,
first ask whether it holds a work.

## Shapes

**Corners.** Two values, no others. Surfaces are `2px` (mounts, tabs, year buttons,
the catalogue slip, the detail stage); images are `1px`. Nothing is pill-shaped and
nothing is circular anywhere on the page.

**Lines.** `1px` hairlines, in two families that do not mix: brass (`brass-dim`)
separates a material from another material - under the oxblood rails, around every
ledger cell, under table headers - while `steel-3` separates regions of the dark
ground from each other (the band, the tab column edge, the footer). The only strokes
above 1px are the `2px` brass edge along a folder tab and the `2px` brass top edge of
the search field, both of which read as a metal lip rather than as a border.

**Silhouettes.** The signature form is the die-cut folder, drawn with `clip-path`
rather than a raster image: a tab across the left `4.6rem` of the top edge, a
shoulder down to the full-width body, with tiny 0.1-0.3rem steps standing in for the
2px corners. The filmstrip thumbnails use a smaller version of the same polygon, and
the search label uses a chamfered variant. A folder is a countable flat shape - the
one kind of thing a vector path specifies exactly - and a path scales to any card
width without a second asset.

**The one raster.** `assets/img/brass-fitting.png` (copied to `dist/img/`) is a
generated image of a machined brass fitting, used twice: as the year rail's cap
(`.years::before`, present before anything is filtered) and as the background of the
active year button. It is a raster on purpose - a bevelled, lit metal object is
exactly what CSS gradients render badly - and it is the same object in both places,
because a rail with no fitting is just a coloured strip.

### Named Rules

**The Contained-Never-Cropped Rule.** Every image on the page sits in a fixed box
with `object-fit: contain` on a `paper` background: the `clamp(13rem, 25vw, 20rem)`
lead mount, the `6.5rem` folder-card window, the `3.2 x 2.4rem` ledger thumbnail, and
the `2.6rem` filmstrip tab. The fixed box is what gives the drawer and the ledger
their rhythm; `cover` would crop a drawing to fit a layout, which is the one thing
this page must not do. Sizing the image itself instead of the box looks equivalent
and is not - `max-height` on a grid item does not hold, and a tall drawing bursts out
of its mount.

**The Countable-Flat-Shape Rule.** Flat, countable geometry (folder silhouettes,
chamfers, tab edges) is CSS - `clip-path`, gradients, borders. Lit, bevelled,
material objects (the brass fitting) are real image assets. Neither medium is used
for the other's job: no CSS bevel imitating machined metal, and no raster of a shape
that a polygon describes exactly.

**The No-Fake-Texture Rule.** Buckram and board are flat colour fields. A CSS
gradient pretending to be woven cloth is worse than the flat colour. If texture is
ever wanted, it arrives as a real tiling image, the way the brass fitting did.

## Components

### Category tabs (brass)

- **Character:** drawer dividers standing up in the cabinet, brass at rest.
- **Shape:** 2px corners, `clip-path`-free, `1px` light-brass border with a lighter
  top edge.
- **Default:** a three-stop vertical brass gradient (`#c7a35d` → `{colors.brass}` 45%
  → `#8a6c38`) with near-black text (`#2a2213`), seated shadow.
- **Hover:** the gradient brightens one step.
- **Pressed** (`aria-pressed="true"`): a pale polished gradient (`#f0dcae` → `#dcbd7c`),
  `#fff0cc` border, and a `1px` `{colors.ox-lit}` ring.
- **Why brass at rest:** an unfiltered first viewport with no brass object in it
  contradicts the world's own description. The tabs are the brass.
- **Mobile:** the row scrolls sideways under a right-edge mask fade
  (`linear-gradient(to right, #000 88%, transparent)`), which says "there is more"
  without spending a control on saying it.

### Folder cards (the drawer)

- **Character:** files leaning in a real drawer, not a grid of thumbnails.
- **Shape:** the die-cut folder `clip-path`; no border-radius (the polygon's steps
  carry the corners); a `2px` brass gradient lip along the tab via `::before`.
- **Colour:** a board gradient (`#a6b2be` → `{colors.board}` 18% → `#8f9dab`), board
  ink, accession number in Courier.
- **Interaction:** the whole card is a `<button>` with `title` and an `aria-label` of
  "accession – title". Hover lifts 4px with `--shadow-lift` and a 6% brightness rise;
  `:focus-visible` gets the same brightness plus the global brass outline.
- **Rhythm:** every card is the same size, with a fixed `6.5rem` image window. Cards
  in a drawer are the same size; that is what makes them a drawer rather than a pile.
- **Deliberate omission:** the approved comp dims its back rows to suggest depth.
  That is **not** carried over. The comp shows a drawer with a few files in it; this
  list is the entire collection, and fading real work that the admissions panel came
  to look at trades the product's job for an atmosphere effect. It is also on the
  comp's own `doNotLiteralize` list.

### Lead mounts (selected works)

- **Character:** three works hung on a common centre line.
- **Shape:** paper-coloured 2px rectangle, cast shadow, one shared height
  (`clamp(13rem, 25vw, 20rem)`), asymmetric padding `0.75rem 0.75rem 2.5rem`.
- **The deep bottom margin is the point.** The date stamp is absolutely positioned in
  it, bottom-right. Over the image the stamp lands on whatever tone the drawing
  happens to have and a violet date on a dark drawing is unreadable; on the mount it
  is always violet on paper. Moving the stamp into a caption row is also wrong - it
  stops being a stamp and becomes a label, and three of them stop sharing a line the
  moment one title wraps.
- **Caption:** the accession number in brass Courier. Titles are not printed beside
  the lead images; they live in the `alt` text and in the detail view.

### The date stamp (signature)

- **Live text, always.** A CSS `rotate(-2.5deg)` on a real date string, never an
  image, so it stays selectable, translatable and searchable.
- **The one authored moment:** staggered 180/310/440ms, `0.32s cubic-bezier(.16,1,.3,1)`,
  from `rotate(-9deg) scale(1.7)`, transparent and 1px-blurred - the way a stamp hits
  paper. `animation-fill-mode: backwards` from an already-correct resting state, so
  it is legible before it runs and legible if it never runs.
- Nothing else on the page animates except hover lift, and the whole thing is off
  under `prefers-reduced-motion: reduce`.

### Year rail

- **Character:** the drawer's index rail - an oxblood strip with the years set into
  it and a machined brass fitting marking the active one.
- **Buttons, not a slider.** The composition is a rail either way; a drag control
  only costs keyboard operability. Each year is a `<button>` with `aria-pressed`.
- **Desktop:** vertical (`writing-mode: vertical-rl`), fitting at the top as a
  `1.7 x 3.4rem` cap. **Mobile:** horizontal scroller along the bottom of the shell,
  fitting as a `1.9 x 1.2rem` cap at the left.
- **Active:** the brass fitting image behind the label, near-black text with a warm
  1px text-shadow, and extra padding so the label sits inside the fitting.

### Filters

- Category tabs, year buttons and the ledger view toggle are all real `<button>`s
  carrying `aria-pressed`, driven by one `bindGroup` helper.
- **Clicking the active filter clears it.** That is what people try first.
- Filtering hides cards with `.is-hidden`; the live count in the section rule and the
  empty state ("Ebben a szűrésben nincs tétel.") both update from the same pass.

### Search field

- **Character:** a brass file-tab label butted against a board-coloured card.
- **Label:** brass gradient, uppercase 12px, with a chamfered `clip-path` top corner.
- **Input:** board gradient, no border except a `2px` brass top lip, Courier text,
  `11rem` wide, placeholder `#4a5361`. There is no gap between label and input - they
  are one object.
- Matches on title, technique and accession number, case-insensitively. Accent
  folding is deliberately not done: the titles and the query come from the same
  keyboard.

### Ledger table

- **Character:** register furniture. Real `<table>` markup with a `<caption>`.
- **Rules:** a brass hairline around every cell, a heavier brass rule under the
  uppercase brass headers, `tabular-nums` throughout.
- **Rows:** oxblood on hover **and** on `.is-active`, so the row stays marked after
  the pointer leaves and the reader can see where they were when the overlay closes.
  Active rows switch their cell borders to bright brass and their Courier cells to
  rail ink.
- Wrapped in an `overflow-x: auto` container with a `38rem` min-width, so it scrolls
  rather than crushing on a phone.

### Detail overlay

- **Ground:** `rgba(11,13,17,.96)` over the page, oxblood bar above, oxblood
  filmstrip below.
- **Bar:** position counter ("18 / 34") in Courier, then Előző / Következő / Bezárás
  as ghost buttons - transparent with a `rgba(231,217,196,.35)` hairline, filling to
  12% rail-ink on hover.
- **Stage:** a paper-coloured 2px panel with the cast shadow. **Zoom is offered only
  when the file actually holds more pixels than are being shown**
  (`naturalWidth > clientWidth + 8`); blowing up a small scan just makes it blurry.
  `cursor: zoom-in` / `zoom-out` is the only affordance.
- **Slip:** a board catalogue card, `20rem` on desktop, `<dl>` with uppercase label
  terms and Courier definitions; the title definition switches to Archivo Narrow.
  The date definition is the same violet stamp with its animation disabled. Empty
  technique/date rows are hidden rather than shown blank.
- **Filmstrip:** the works either side of this one as small folder tabs at 65%
  opacity, the current one at full opacity and lifted `0.3rem`, auto-scrolled to
  centre. Moving through the collection is a place you can see rather than two
  unlabelled buttons.
- **Keyboard:** Escape closes, arrows step, focus is trapped to the overlay by moving
  it to the close button on open and returned to the opener on close.

### Deep links

- `#fiok` / `#naplo` select a view; `#tetel=CS.001/24` opens one work directly, so a
  single drawing can be sent as its own link rather than as "the site, then scroll".
- The view toggle writes the hash with `history.replaceState`, so switching views does
  not fill the back button.

## Do's and Don'ts

### Do:

- **Do** spend violet only on dates, and keep both violet tokens - `{colors.stamp}`
  on light grounds, `{colors.stamp-lit}` on dark.
- **Do** put every new image in a fixed box with `object-fit: contain` on a
  `{colors.paper}` background.
- **Do** keep `line-height: 1.4` on uppercase labels and test type changes on
  "ÁRVÍZTŰRŐ TÜKÖRFÚRÓGÉP", not on ASCII.
- **Do** ship both `latin` and `latin-ext` subsets for any font added, self-hosted.
- **Do** render new content server-side into the HTML and let the client script only
  filter, toggle and overlay. The page must survive with JavaScript off.
- **Do** make anything filterable a real `<button>` with `aria-pressed`, and make
  clicking the active one clear it.
- **Do** unwind screen-only `html`/`body` scroll properties inside `@media print`.
- **Do** reach for `clip-path` for flat countable shapes and a real image asset for
  lit material.
- **Do** edit `lib/render.js`; `dist/` is build output.

### Don't:

- **Don't** collapse the two violet tokens, and don't add a third violet.
- **Don't** use violet, at any lightness, on anything that is not a date.
- **Don't** use `object-fit: cover` anywhere. Cropping a drawing to fit a layout is
  the one thing this page must not do.
- **Don't** dim, fade or blur real works to suggest depth - not the back rows of the
  drawer, not the filmstrip's ends, not a scroll mask over cards. The mask fade is
  for the tab strip only, where it covers chrome.
- **Don't** add a fourth type size, a pill radius, or a circle.
- **Don't** give chrome the wide cast shadow, and don't give a drawing-bearing
  surface the tight seated one.
- **Don't** fake buckram or board texture with a CSS gradient.
- **Don't** render the date stamp as an image, and don't move it off the mount's
  bottom margin onto the drawing.
- **Don't** replace the year rail with a drag slider or a range input; keyboard
  operability is the reason it is buttons.
- **Don't** make the print output depend on which view is open.
