# Brand System - Design

## Purpose

One visual identity across the owner's public properties: the Landing Page at
`homelabor.net`, the interactive topology map it serves at `/topology/`, the
Documentation Site at `docs.homelabor.net`, the GitHub profile, and a CV.

There is one brand and **it is the person, not the infrastructure**. The
Landing Page title is "Norbert Csicsay - Homelab Infrastructure", its hero
kicker is the name alone, the Documentation Site is named "Norbert Csicsay -
Homelab", and `compose/vps/landing/PRODUCT.md` states the visitor "arrive[s]
with a question about a specific person, not with a problem they want a product
to solve".

See `CONTEXT.md` for **Mark**, **Portrait**, **Brand Tokens**, **Display Face**
and **Self-Hosted End to End**, which this spec uses in their defined senses.

## What is actually wrong today

### 1. The Landing Page disagrees with its own share card

| Token | `src/style.css` | `og.html` | `src/favicon.svg` |
|---|---|---|---|
| background | `#0b1120` | `#0b0e13` | `#0b0e13` |
| accent | `#e8a04c` | `#e8933f` | `#e8933f` |

Two backgrounds differing by a few points of blue, two oranges differing by a
shade nobody chose. The Mark and the share card sit on one side of the split
and the page itself on the other.

The node colours from the topology legend (`#e8a04c` hypervisor, `#5cc8ff`
LXC, `#b18aff` VM, `#6ee7a0` K3s) are coherent and stay; they become a
documented part of the system rather than inline literals.

### 2. The Documentation Site is an unrelated visual identity

Stock Material for MkDocs - `primary: indigo`, `accent: indigo` - with no
`theme.logo` and no `theme.favicon`. `docs/stylesheets/extra.css` is five lines
of code-block overflow fix and contains no colour. The two sites link to each
other and read as different products.

### 3. The pages contradict the Self-Hosted End to End claim

`compose/vps/landing/README.md` already names one instance: the topology map
carries two Google Fonts requests, and "this site's whole argument is that it
is self-hosted end to end, and a visitor reading the topology map is handed to
Google anyway."

There is a second the README does not know about: `mkdocs.yml` sets no
`theme.font`, so Material loads Roboto from Google Fonts. The Documentation
Site - the first thing the Landing Page links to - has the same defect.

This is the finding that drives most of the work, and the one worth doing on
its own merits.

## Typography

### The faces

`compose/proxmox-lxc-100/topology/build.js` already uses **Big Shoulders
Display** and **IBM Plex Mono** - deliberate choices, not defaults - while the
Landing Page runs a generic system stack. The brand does not need a typeface
invented, only the one it has released from quarantine and taken off Google's
servers.

**Big Shoulders Display stays on the topology map alone**, as its Display
Face. It is a condensed face, and the Landing Page's headings are set with
negative tracking (`-0.025em`, and `-0.038em` on `h1` at up to 4.1rem) - a
treatment written for a normal-width grotesque. Pushing a condensed face
through that CSS would collapse it, so adopting Big Shoulders site-wide is not
a font swap but a re-tuning of heading settings that were visibly dialled in on
purpose. On a long-form documentation site a condensed heading also costs
scannability.

So:

| Role | Face | Where |
|---|---|---|
| Body | IBM Plex Sans | all properties |
| Code, figures | IBM Plex Mono | all properties |
| Display | Big Shoulders Display | topology map only |

IBM Plex Sans is a normal-width grotesque, so the Landing Page's existing
heading CSS keeps working unchanged.

All three are SIL OFL licensed (Big Shoulders via Google Fonts, IBM Plex via
IBM), so self-hosting is clean.

### Variable, not static instances

One variable `.woff2` per family - three files, against nine static instances
(Big Shoulders 500/700/800, Plex Mono 400/500/600, Plex Sans regular/semibold/
italic).

This is not only a file-count argument. `src/style.css` sets `font-weight:
620`, `550` and `570`. Against the current static system stack those round to
the nearest available weight and are silently doing nothing. A variable font
makes them mean what they say.

**That is a visible change to the Landing Page, not just a font swap** -
headings that render bold today will render lighter. It is very likely what was
intended when those values were written, but it must be confirmed by comparing
screenshots before and after rather than assumed.

Subset to **Latin plus Latin Extended-A**, not to a hand-picked glyph list. The
Documentation Site's body text grows over time and Hungarian `ő`/`ű` must
survive; a fixed glyph set would fail silently on the first page that needs a
character outside it.

### One committed copy

The font files live in `brand/` and nowhere else. See ADR 0002 - the
copy-don't-import rule stops at text, because a stale `.woff2` is invisible in
a diff.

- **Landing:** `build.sh` copies `brand/*.woff2` into `dist/`. It already
  resolves `REPO_ROOT` to count Compose Stacks, so this is one `cp` and no new
  dependency.
- **Topology:** `build.js` reads the files from `brand/` and embeds them.
- **Documentation Site:** the only unavoidable committed copy, under
  `docs/assets/fonts/`, because MkDocs cannot pull from outside `docs_dir`
  without a plugin. Guarded by a checksum check against `brand/`.

## Structure

### The `brand/` directory

A new top-level `brand/` holding `tokens.css`, `BRAND.md`, the Mark in both
sizes and the subsetted `.woff2` files. Top-level because it serves four
consumers across three hosts.

A new top-level directory is exactly the kind of fact that goes stale in one
place and not the other, so `CLAUDE.md` and `AGENTS.md` both get a line.

### Landing Page

- Reconcile `src/style.css`, `og.html` and `src/favicon.svg` onto one
  background and one accent
- `@font-face` for Plex Sans and Plex Mono, files placed by `build.sh`
- Favicon: the existing Mark, recoloured
- `Caddyfile` gets a cache rule for `.woff2` if it does not already fall
  through to one
- Re-render `src/og.png`, because the card's typeface changes

The strict CSP is unaffected: every font is same-origin.

### The share card renders over HTTP, not `file://`

`og.html` currently loads **no external resource at all** - no `<img>`, no
`src=`, no `url()`. That is why the documented headless-Chrome command
screenshots it straight from `file://` with no flags: it has never had a
subresource.

An `@font-face` would be its first. Chrome restricts font loads under
`file://`, and a failure is silent - the card would render in a fallback face
and look perfectly fine while being wrong. That is the same class of mismatch
the README already warns about twice.

So the documented regeneration command changes to serve the directory over
HTTP and screenshot that, following the pattern the README already uses for the
topology map on port 8899. `og.html` stays a hand-editable 5 KB file.

### Topology map - fonts embedded as `data:` URIs

The generator's Google Fonts `<link>` tags are replaced with `@font-face`
blocks whose sources are base64 `data:` URIs of the subsetted variable woff2,
read from `brand/` and embedded by `build.js` into its output.

Separate font files would break two documented invariants:

1. `README.md` defines the transfer as a single file copy and states that
   `src/topology/index.html` is "the only committed build artifact in `src/`",
   existing because `topology/dist/` is gitignored and absent from the VPS
   checkout. Font files alongside it would make that a directory copy and
   commit binaries into `src/`.
2. `topology/dist/` is also served standalone on port 3009, and that is what
   `topology.png` is screenshotted from. A font that resolves on the live page
   but not in the standalone view would render the screenshot in a different
   typeface than the page.

Cost: that HTML grows from roughly 19 KB to roughly 150 KB, and its fonts are
not shared with the Landing Page's copies. Accepted, because it preserves the
single-file property both invariants depend on.

`topology.png` and `topology.webp` are re-exported, since the page's rendering
changes.

### Documentation Site

The brand reaches the header, the accent and the Mark. **It does not take over
the reading surfaces.**

The Landing Page is dark-only by design; the Documentation Site ships a
light/dark toggle that serves long-form reading and stays. Pushing brand
backgrounds into both schemes would mean inventing a light palette from
nothing - there is no light reference anywhere in the repo - making the hardest
part of this job the part with the least evidence behind it.

- `mkdocs.yml`: `primary: custom`, `accent: custom`, plus `theme.logo` and
  `theme.favicon` pointing at the Mark
- `mkdocs.yml`: `theme.font: false`, which stops the Google Fonts request
- `docs/stylesheets/extra.css`: `@font-face` for Plex Sans and Plex Mono, set
  through `--md-text-font` and `--md-code-font` rather than `font-family`
  (setting `font-family` directly disables Material's system fallback), plus
  `--md-primary-fg-color`, `--md-primary-fg-color--light`,
  `--md-primary-fg-color--dark` and `--md-accent-fg-color` for both
  `[data-md-color-scheme="default"]` and `[data-md-color-scheme="slate"]`
- Font files under `docs/assets/fonts/`, checksum-checked against `brand/`
- The existing five-line code-block fix stays

`primary` is the dark brand background, so the header bar is dark in both
schemes; `accent` is the orange.

**Zensical:** Material for MkDocs reaches end of life on 2026-11-05 and this
repo is pinned below 10 pending a November migration. Zensical uses the same
CSS variable names, the same `default`/`slate` scheme names and the same
`custom` palette mechanism; only the config moves from YAML to TOML, and
automatic refactorings are promised. The CSS written here carries over intact.
Not a reason to wait.

### The Mark already exists

`compose/vps/landing/src/favicon.svg` is not a placeholder. It is a
hand-drawn, on-grid SVG with its rationale in its own comment: "One hypervisor
over two guests: the top left corner of topology.png, reduced to three shapes
so it still reads at 16px." It even warns a future editor that an XML comment
cannot contain two consecutive hyphens.

It is diagrammatic rather than a monogram, and that suits this brand better
than two letters would: it is derived from what the owner actually operates. A
person's mark need not be their initials, and this one says "this person runs
infrastructure", which is the brand.

So the Mark is kept. What it needs costs nothing:

- Recolour onto the reconciled tokens - it currently sits on the `og.html` side
  of the split
- A larger-format variant, since the existing drawing is tuned for 16px and the
  Documentation Site header and CV need more room
- Wiring into `theme.logo` and `theme.favicon`, where the Documentation Site
  currently has neither

### The Portrait

Three surfaces want the owner's face: a CV header, authorship on the
Documentation Site, and a GitHub avatar. What varies between them is background
and crop, not the face.

So no face is generated. A real photograph is selected, its background removed
with `image_background_remover`, and the brand background composited behind it
locally in three crops. This needs one good photo rather than the 5-20 a Soul
ID training run would take, and a generated face on a CV always needs
explaining.

### Rule: text never goes through generation

Any asset carrying words - the share card, the CV header - is rendered locally
from HTML with headless Chrome, as `og.html` does today. Generated text is
unreliable at small sizes and cannot be corrected without regenerating the
whole image.

## Cost

Total planned generation: **roughly 1 credit**, for the portrait cutout. Its
exact figure could not be measured in advance because
`image_background_remover` takes no prompt and cannot be costed without a real
upload.

Everything else - tokens, typography, the Mark, the card - is text, files and
hand-drawing.

This is worth stating plainly: the work began as "do something with
Higgsfield", and each round of scrutiny shrank the tool's role, ending at one
background removal. The measurements below and the installed skill set remain
useful; no work was invented to justify the tool.

Costs measured with `higgsfield generate cost`, which estimates without
creating a job and consumes nothing:

| Model | Credits |
|---|---|
| `nano_banana_2_lite`, `flux_2` | 1 |
| `recraft_v4_1` | 1.25 |
| `nano_banana_flash` | 1.5 |
| `seedream_v5_pro` | 3 |
| `gpt_image_2` | 7 |
| `text2image_soul_v2` | 0.12 |
| `image_background_remover` | not costable without an upload |

Account: Basic plan, 112 credits, 70 per month.

## Rejected alternatives

**A separate mark for the infrastructure.** Both site titles, the hero kicker
and `PRODUCT.md` say the brand is the person.

**Replacing the Mark with a monogram.** The existing mark is hand-drawn,
documented, reads at 16px and is derived from the topology map. Six generated
directions would have cost 7.5 credits to replace something that works.

**Full brand adoption on the Documentation Site with a designed light mode.**
No light reference exists in the repo, so it would be invention dressed as
consolidation, on the one surface built for long-form reading.

**Big Shoulders Display site-wide.** It is condensed; the Landing Page's
headings are tracked negatively for a normal-width face. Adopting it means
re-tuning heading CSS that was deliberately dialled in, and it costs
scannability in long documentation.

**Static font instances.** Nine files instead of three, and `font-weight: 620`
would go on silently rounding.

**Soul ID for the Portrait.** Needs 5-20 photos and an unmeasured training run,
to put a generated face on a CV, solving a problem background replacement
solves outright.

**Separate woff2 files for the topology map.** Breaks the documented one-line
copy, commits binaries into `src/`, and desynchronises the standalone render
used for `topology.png`.

**Committed font copies on every surface.** Two of the three consumers have
build scripts that can read `brand/` directly, so their drift can be made
structurally impossible rather than merely checked.

**A CSS build step so consumers import one token file.** Adds a dependency to a
build script whose spec commits to having none, and defeats the deliberate
self-containment of `og.html`. See ADR 0002.

**Splitting this into two specs.** Considered - the typography rollout and the
Mark work are independent. Rejected by the owner in favour of one document.

## Success criteria

- `brand/` exists at the repo root with `tokens.css`, `BRAND.md`, the Mark in
  both sizes and the three subsetted variable font files; `CLAUDE.md` and
  `AGENTS.md` both list it
- `style.css`, `og.html` and `favicon.svg` agree on background and accent, each
  pointing at `brand/BRAND.md`
- `brand/` holds the only committed copy of each font except the Documentation
  Site's, and that copy is checksum-checked against it
- No page on any property requests a font from a third-party origin. Verified
  by loading the Landing Page, `/topology/` and the Documentation Site with the
  network panel filtered to third-party requests
- `topology/dist/index.html` remains a single self-contained file, and `cp`-ing
  it to `src/topology/index.html` remains a one-line operation
- `og.png`, `topology.png` and `topology.webp` are all regenerated, and
  `topology.png` renders in the same typefaces as the live page
- Landing Page screenshots before and after are compared, and the weight change
  from `620`/`550`/`570` becoming live is confirmed as wanted rather than
  discovered later
- The Documentation Site's light/dark toggle still works, and body text remains
  comfortable to read in both
- The Mark serves as favicon on both sites, `theme.logo` on the Documentation
  Site, and the mark on the share card
- One Portrait, from a real photograph, in three crops on the brand background
- `build.sh` runs with no new dependency; `test-build.sh` and `node --test`
  both pass; the MkDocs build is clean

This spec lives under `docs/superpowers/`, which `mkdocs.yml` lists in
`exclude_docs`. It is not published and needs no `nav` or `docs/README.md`
entry.
