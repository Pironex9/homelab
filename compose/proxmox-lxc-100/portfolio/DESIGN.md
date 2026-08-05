# Design

Recorded from the built page (`lib/render.js`), not from intention. The direction
contract sits at the top of the emitted `<body>` in `dist/index.html`; the approved
comps and what must not be literalised are in `.impeccable/mocks/`.

## The world

**Gyarapodási napló** - a museum accession register, not a gallery wall. The collection
is a numbered, dated list that grows; the drawings are the objects in the drawer. This
world was chosen over the incumbent one (warm paper, serif display, terracotta accent,
masonry of matted thumbnails), which had never been decided so much as defaulted into.

Dark ground is not a style preference. The works are graphite and watercolour on white
paper, so a dark cabinet ground is what makes them read as objects rather than as page
background.

## Colour

| Token | Value | Role |
|---|---|---|
| `--steel` | `#171a20` | page ground, the japanned cabinet |
| `--steel-2` / `--steel-3` | `#1e222a` / `#262b35` | raised surfaces, hairline dividers |
| `--ox` / `--ox-lit` | `#6e2029` / `#8a2833` | buckram rails; the top rail and the detail bar |
| `--board` | `#9aa7b4` | conservation board: catalogue cards, the drawer cards |
| `--board-ink` | `#20242c` | text on board |
| `--brass` / `--brass-dim` | `#b08d4f` / `#7d6438` | tabs, hairline rules, section labels |
| `--ink` / `--ink-soft` | `#dfe3e9` / `#98a1af` | text on steel |
| `--stamp` / `--stamp-lit` | `#4a2d7a` / `#9b8ae0` | date stamp on board / on steel |

**Two violets, not one.** `--stamp` on the dark ground fails contrast outright; the two
tokens are the same ink rendered for two grounds. Do not collapse them.

**Violet is reserved for dates and nothing else.** It is the only saturated violet on
the page, so the eye lands on the thing the product is arguing. Spending it on a button
or a hover state destroys that.

## Type

Two self-hosted faces in `assets/`, latin + latin-ext. **latin-ext is not optional**:
Hungarian needs U+0151 (ő) and U+0171 (ű), and a system stack cannot promise them.

- **Archivo Narrow** 600/700 - labels, navigation, titles. Condensed capitals with wide
  tracking for anything that behaves like a drawer label.
- **Courier Prime** 400/700 - every accession number, date and register figure. This is
  the register's typewriter, used for data and measurement, not as a costume.

Three sizes, deliberately: **12px** (labels and all register data), **16px** (work
titles and the date stamp), **30.4px** (the name in the top rail, the page's only
display step). An earlier build had six sizes inside a 1.6:1 range and read flat.

## Structure and materials

- **Corner radius is 2px everywhere.** Nothing is pill shaped; nothing is circular.
- **Hairlines are 1px, in brass.** There is no 2px+ neutral border anywhere.
- **One shadow recipe** (`--shadow`, with `--shadow-lift` on hover): real offset and
  soft blur, cast onto the dark ground. Drawings cast it. Chrome does not.
- **Images are contained, never cropped.** Lead mounts, drawer cards and ledger
  thumbnails are all fixed boxes with `object-fit: contain`. A fixed box is what gives
  a drawer its rhythm; `cover` would crop a drawing to fit a table, which is the one
  thing this page must not do.
- **No texture assets.** Buckram and board are flat colour fields. A CSS gradient
  pretending to be woven cloth is worse than the flat colour; if texture is ever wanted,
  it arrives as a real tiling image.

## Motion

One authored moment: **the date stamps land**, staggered, on the three lead works -
a quick over-scale settling into a slight rotation, the way a stamp hits paper. Nothing
else on the page animates except hover lift.

The stamps are legible before the animation runs and legible if it never runs
(`backwards` fill from an already-correct resting state), and the whole thing is off
under `prefers-reduced-motion`.

## Views

Three states of one page, all server-rendered so the page works with JavaScript off:

- **Fiók** (`#fiok`, default) - three selected works lead, then every work as a card.
- **Napló** (`#naplo`) - the ledger table, oldest first. This is also the print form:
  `@media print` turns it into A/3 portrait sheets, so the school's PDF is this view
  and not a second renderer.
- **Detail** - an overlay carrying the work large beside its catalogue card. Keyboard:
  Escape, arrows. Click to zoom, but only when the file actually holds more pixels than
  are being shown.

The view lives in the URL hash, so a link can point straight at the register.

## Rules that are load-bearing, not taste

- The date stamp is live text with a CSS transform. Never an image: it must stay
  selectable, translatable and searchable.
- Filters are real `<button>`s with `aria-pressed`, and the year rail is buttons rather
  than a slider. The composition is a rail either way; a slider only costs keyboard use.
- Clicking an active filter clears it. That is what people try first.
- `dist/` is generated. Edit `lib/render.js`.
