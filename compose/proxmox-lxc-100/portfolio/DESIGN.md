---
name: Enci - Portfólió
description: A gallery-paper portfolio - warm paper ground, matted drawings in a masonry wall, Young Serif over Karla, one terracotta accent.
colors:
  paper: "#f5f0e6"
  mat: "#fffdf8"
  ink: "#262218"
  ink-soft: "#6d6353"
  accent: "#c1502e"
  lightbox-ground: "rgba(24,21,15,.94)"
  lightbox-ink: "#efe9dc"
  lightbox-ink-soft: "#a89d89"
typography:
  display:
    fontFamily: "Young Serif, Georgia, serif"
    fontSize: "clamp(2.6rem, 8vw, 4.5rem)"
    fontWeight: 400
    lineHeight: 1.05
    letterSpacing: "-0.01em"
  caption:
    fontFamily: "Young Serif, Georgia, serif"
    fontSize: "0.95rem"
  body:
    fontFamily: "Karla, system-ui, sans-serif"
    fontSize: "1.06rem"
    lineHeight: 1.65
  label:
    fontFamily: "Karla, system-ui, sans-serif"
    fontSize: "0.78rem"
    letterSpacing: "0.22em"
    textTransform: "uppercase"
  meta:
    fontFamily: "Karla, system-ui, sans-serif"
    fontSize: "0.72rem"
    letterSpacing: "0.08em"
    textTransform: "uppercase"
rounded:
  image: "1px"
  frame: "2px"
spacing:
  gutter: "clamp(1rem, 4vw, 3rem)"
  column-gap: "1.75rem"
  frame: "12px 12px 10px"
components:
  frame:
    backgroundColor: "{colors.mat}"
    padding: "12px 12px 10px"
    rounded: "{rounded.frame}"
  tab:
    backgroundColor: "transparent"
    textColor: "{colors.ink-soft}"
    typography: "{typography.meta}"
    padding: "0.4rem 0"
  tab-active:
    textColor: "{colors.ink}"
  lightbox:
    backgroundColor: "{colors.lightbox-ground}"
    textColor: "{colors.lightbox-ink}"
---

# Design System: Enci - Portfólió

Recorded from the built page. The CSS, markup and client script all live in
`lib/render.js`; `dist/` is generated and must never be edited by hand.

## Overview

**A gallery wall on paper.** The page is a warm paper ground with the drawings
hung on it in white mats, arranged as a masonry wall rather than a grid. The
interface is almost absent: a name, an age, one sentence, a row of category
words, and then the work. Nothing frames the collection; the drawings sit
directly on the paper.

**Key characteristics**

- Warm paper ground (`#f5f0e6`) with a fixed SVG turbulence grain at 5% opacity
  over the whole viewport - self-contained, no external asset.
- Every drawing sits in a white mat (`#fffdf8`) with 12px of margin, a soft
  two-layer shadow and a 2px corner, like a mounted work behind glass.
- One accent, terracotta `#c1502e`, and it is spent on three small things only:
  the full stop after the name, the em dashes around the age, and the underline
  under the active category.
- Centred header, everything else flows. Maximum content width 1200px.
- Light ground throughout. There is no dark theme and none is intended.

## Colours

- **Paper** (`{colors.paper}`) - the ground. **Mat** (`{colors.mat}`) - every
  surface that touches a drawing, and nothing else.
- **Ink** (`{colors.ink}`) for titles and active state; **soft ink**
  (`{colors.ink-soft}`) for the intro, the metadata, inactive tabs and the
  footer. The two are the whole text hierarchy.
- **Accent** (`{colors.accent}`) is decoration, never a control colour: no
  button, link or focus state uses it.
- The lightbox has its own three: a near-black wash, warm off-white text and a
  muted tan for metadata.

## Type

Two faces from Google Fonts, loaded over the CDN with `preconnect`:

- **Young Serif** - the name, the drawing titles, the lightbox title. Display
  only; it never sets running text.
- **Karla** 400/500 - everything else, including all uppercase tracked labels.

The scale runs 0.72rem (metadata) / 0.78rem (age label) / 0.85rem (tabs) /
0.95rem (titles) / 1.06rem (intro) / clamp to 4.5rem (the name). Only the name
is large; the rest sits in a narrow band on purpose, so nothing competes with
the drawings.

## Layout

CSS multi-column masonry: `columns: 3 300px` with a 1.75rem gap, so the column
count follows the viewport and each drawing keeps its own aspect ratio.
`break-inside: avoid` holds a frame together. Images carry `width`/`height`
from the build, so the wall does not shift while it loads.

## Motion

One gesture: frames rise 16px into place with a staggered delay capped at
450ms, once, on render. Hover lifts a frame 4px and deepens its shadow.
Everything is off under `prefers-reduced-motion`.

## Lightbox

Opens on a frame, fills the viewport with a near-black wash. Keyboard: Escape,
left, right. Click-to-zoom is offered **only** when the file actually holds more
pixels than are being displayed (`naturalWidth > clientWidth + 8`) - blowing up
a small scan just makes it blurry. Zoomed, the native scroll pans and lands on
the point that was clicked.

## Rules that are load-bearing

- The gallery is rendered client-side from a JSON blob embedded in the page. The
  blob escapes `<` so a title can never break out of the `</script>`, and the
  client escapes again before `innerHTML`.
- Category folder names are accent-free ASCII because they become file paths;
  the accented display names live in `bio.yml`.
- `dist/` is generated by `build.js`. Edit `lib/render.js`.
