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
to solve". Nothing here introduces a separate mark for the homelab.

See `CONTEXT.md` for the terms **Mark**, **Brand Tokens** and **Self-Hosted End
to End**, which this spec uses in their defined senses.

## What is actually wrong today

Three findings, in ascending order of importance.

### 1. The Landing Page disagrees with its own share card

| Token | `src/style.css` | `og.html` |
|---|---|---|
| background | `#0b1120` | `#0b0e13` |
| accent | `#e8a04c` | `#e8933f` |

Two backgrounds differing by a few points of blue, two oranges differing by a
shade nobody chose. The card and the page it advertises do not match.

The node colours from the topology legend (`#e8a04c` hypervisor, `#5cc8ff`
LXC, `#b18aff` VM, `#6ee7a0` K3s) are coherent and stay as they are; they
become a documented part of the system rather than inline literals.

### 2. The Documentation Site is an unrelated visual identity

It runs stock Material for MkDocs - `primary: indigo`, `accent: indigo` - with
no `theme.logo` and no `theme.favicon`. `docs/stylesheets/extra.css` is five
lines of code-block overflow fix and contains no colour. The two sites link to
each other and read as different products.

### 3. The pages contradict the Self-Hosted End to End claim

`compose/vps/landing/README.md` already names one instance: the topology map
carries two Google Fonts requests, and "this site's whole argument is that it
is self-hosted end to end, and a visitor reading the topology map is handed to
Google anyway."

There is a second instance the README does not know about: `mkdocs.yml` sets no
`theme.font`, so Material loads Roboto from Google Fonts. The Documentation
Site - the first thing the Landing Page links to - has the same defect.

This is the finding that drives the largest part of the work, and it is the one
worth doing on its own merits.

## The typography already exists

`compose/proxmox-lxc-100/topology/build.js` uses **Big Shoulders Display** and
**IBM Plex Mono**. Those are deliberate typographic choices, not defaults - and
they sit on a subpage while the Landing Page itself runs a generic system stack
(`Liberation Sans` / `DejaVu Sans Mono`).

So the brand does not need a typeface invented. It needs the one it already has
released from quarantine and taken off Google's servers.

**Big Shoulders Display is a condensed display face** - excellent for headings,
unusable for the Documentation Site's long-form body text. A third face is
required, and the coherent choice is **IBM Plex Sans**, so the Plex family
carries body and code while Big Shoulders carries emphasis.

All three are SIL OFL licensed (Big Shoulders via Google Fonts, IBM Plex via
IBM), so self-hosting is clean.

| Role | Face |
|---|---|
| Display, headings | Big Shoulders Display |
| Body | IBM Plex Sans |
| Code, figures | IBM Plex Mono |

## Structure

### The `brand/` directory

A new top-level `brand/` holding `tokens.css`, `BRAND.md` and the subsetted
`.woff2` files. Top-level because it serves four consumers across three hosts;
nesting it under any one of them would be wrong.

Adding a top-level directory means `CLAUDE.md` and `AGENTS.md` both need a line
for it - they are kept in sync deliberately, and a new key directory is exactly
the kind of fact that goes stale in one of them.

### Consumers copy; they do not import

`brand/tokens.css` is the source of truth **as a document**. Every consumer
carries its own copy of the values and its own copy of the font files, each
with a comment naming `brand/BRAND.md` as the origin.

This is deliberate and load-bearing in three places:

- `compose/vps/landing/build.sh` is dependency-free POSIX shell by design, per
  its own spec. A CSS build step to resolve an import would undo that.
- `compose/vps/landing/og.html` states in its own comment that it is
  self-contained on purpose, so the share card keeps rendering identically
  years from now even if `style.css` moves on.
- The topology generator is a separate stack on a separate host with its own
  npm build. It shares nothing with the VPS checkout.

Drift becomes a review problem rather than a build problem. That is the correct
trade at this number of consumers, and it is recorded as an ADR because a
reader who finds the same hex values in four files will otherwise try to fix
it.

### Landing Page

- Reconcile `src/style.css` and `og.html` onto one background and one accent
- Add `@font-face` for the three faces, files served from `src/` - `build.sh`
  copies `src/` wholesale, so **no build change is needed**, only files
- `og.html` gets the same `@font-face` inline, since it renders from `file://`
  and is self-contained by design
- Favicon replaced with the Mark
- `Caddyfile` gets a cache rule for `.woff2` if it does not already fall
  through to one

The strict CSP is unaffected: every font is same-origin.

### Topology map - fonts embedded as `data:` URIs

The generator's Google Fonts `<link>` tags are replaced with `@font-face`
blocks whose sources are **base64 `data:` URIs of the subsetted woff2**,
embedded by `build.js` into its output.

Separate font files would break two documented invariants:

1. `README.md` defines the transfer as a single file copy, and states that
   `src/topology/index.html` is "the only committed build artifact in `src/`",
   existing because `topology/dist/` is gitignored and absent from the VPS
   checkout. Font files alongside it would make that a directory copy and
   commit binaries into `src/`.
2. `topology/dist/` is also served standalone on port 3009, and that is what
   `topology.png` is screenshotted from. A font that resolves on the live page
   but not in the standalone view would render the screenshot in a different
   typeface than the page - the same class of silent mismatch the README
   already warns about for `topology.webp`.

Cost: that HTML grows from roughly 19 KB to roughly 150 KB, and its fonts are
not shared with the Landing Page's own copies. Accepted, because it keeps the
single-file property that both invariants depend on.

### Documentation Site

The brand reaches the header, the accent and the Mark. **It does not take over
the reading surfaces.**

The Landing Page is dark-only by design; the Documentation Site ships a
light/dark toggle that serves long-form reading and stays. Pushing brand
backgrounds into both schemes would require inventing a light palette from
nothing - there is no light reference anywhere in the repo to consolidate from,
which would make the hardest part of this job the part with the least evidence
behind it.

So:

- `mkdocs.yml`: `primary: custom`, `accent: custom`, plus `theme.logo` and
  `theme.favicon` pointing at the Mark
- `mkdocs.yml`: `theme.font: false`, which stops the Google Fonts request
- `docs/stylesheets/extra.css`: `@font-face` for the three faces,
  `--md-text-font` and `--md-code-font` set through the variables rather than
  `font-family` (setting `font-family` directly would disable Material's system
  fallback), plus `--md-primary-fg-color`, `--md-primary-fg-color--light`,
  `--md-primary-fg-color--dark` and `--md-accent-fg-color` for both
  `[data-md-color-scheme="default"]` and `[data-md-color-scheme="slate"]`
- Font files under `docs/assets/fonts/`
- The existing five-line code-block fix stays

`primary` is the dark brand background, so the header bar is dark in both
schemes; `accent` is the orange.

**Zensical:** Material for MkDocs reaches end of life on 2026-11-05 and this
repo is pinned below 10 pending a November migration. Zensical uses the same
CSS variable names, the same `default`/`slate` scheme names and the same
`custom` palette mechanism; only the config moves from YAML to TOML, and
automatic refactorings are promised. The CSS written here carries over intact.
This is not a reason to wait.

### The Mark

A monogram, produced in two stages:

1. **Exploration, generated.** 6 directions with `recraft_v4_1` in vector mode,
   1.25 credits each. These are for finding a direction, not for shipping.
2. **Execution, by hand.** The chosen direction is redrawn as clean SVG, on
   grid, in the brand's own display face.

Generated vector output is typically traced from raster, sits off-grid, and
needs a fresh generation for every adjustment. A monogram is two letters of
geometry and is well within reach of hand-drawing. Generation buys breadth of
idea; it does not buy the deliverable.

Everything downstream is derived from that SVG locally at no cost: the Landing
Page favicon, `theme.logo` and `theme.favicon` on the Documentation Site, the
mark on the OG card, and the CV header.

Budget: 7.5 credits.

### The portrait

Three surfaces want the owner's face: a CV header, an authorship mark on the
Documentation Site, and a GitHub avatar. What varies between them is background
and crop, not the face.

So no face is generated. A real photograph is selected, its background removed
with `image_background_remover`, and the brand background composited behind it
locally in three crops.

This is cheaper, needs one good photo rather than the 5-20 a Soul ID training
run would take, and is the defensible option on a CV - a generated face on an
identity document always needs explaining, and there is nothing here worth
explaining it for.

Budget: roughly 1 credit. The exact figure could not be measured in advance,
because `image_background_remover` takes no prompt and so cannot be costed
without a real upload.

### Rule: text never goes through generation

Any asset carrying words - the OG card, the CV header, banner copy - is
rendered locally from HTML with headless Chrome, exactly as
`compose/vps/landing/og.html` does today.

This is not primarily a cost decision. Generated text is unreliable at small
sizes and cannot be corrected without regenerating the whole image.
`gpt_image_2` is what the Higgsfield brandkit skill reaches for when overlaying
text, at 7 credits per call - the most expensive image model measured, bought
for the one job it should not be doing here.

## Measured costs

From `higgsfield generate cost`, which estimates without creating a job and
consumes nothing:

| Model | Role | Credits |
|---|---|---|
| `recraft_v4_1` | SVG vector, Mark exploration | 1.25 |
| `text2image_soul_v2` | Soul portrait - not used | 0.12 |
| `nano_banana_2_lite`, `flux_2` | texture, background | 1 |
| `nano_banana_flash` | general image | 1.5 |
| `seedream_v5_pro` | photoreal mockup | 3 |
| `gpt_image_2` | text overlay - avoided | 7 |
| `image_background_remover` | portrait cutout | unmeasurable without an upload |

Account: Basic plan, 112 credits, 70 per month. Total planned spend is roughly
**9 credits**. Credits are not a constraint on this work; they were never the
interesting part of it.

## Tooling

The official Higgsfield skill set (`higgsfield-ai/skills`) gets installed; its
setup handles the CLI and auth. Only `higgsfield-generate` is genuinely needed
here.

No wrapper script for credit accounting. `higgsfield generate cost` before a
call and `higgsfield account status` after are sufficient, and a logging
wrapper would be a second thing to maintain for a number the CLI already
reports.

## Rejected alternatives

**A separate mark for the infrastructure, distinct from the person.** Rejected:
both site titles, the hero kicker and `PRODUCT.md` all say the brand is the
person. A product mark would require changing `PRODUCT.md` to stop contradicting
it.

**Full brand adoption on the Documentation Site, with a designed light mode.**
Rejected: no light reference exists in the repo, so it would be invention
dressed as consolidation, and it risks the readability of the one surface
built for long-form reading.

**Soul ID for the portraits.** Rejected: it needs 5-20 photos, costs an
unmeasured training run, and puts a generated face on a CV to solve a problem
that background replacement solves outright.

**Generating the final Mark rather than hand-drawing it.** Rejected: traced
vector output is off-grid and awkward to edit, and every tweak costs another
generation.

**Separate woff2 files for the topology map.** Rejected: breaks the documented
one-line copy, commits binaries into `src/`, and desynchronises the standalone
render used for `topology.png`.

**A CSS build step so consumers import one token file.** Rejected: it adds a
dependency to a build script whose spec commits to having none, and defeats the
deliberate self-containment of `og.html`. See the ADR.

**Splitting this into two specs.** Considered - the typography rollout and the
Mark are independent, and the rollout could ship while the Mark is still being
decided. Rejected by the owner in favour of one document.

## Success criteria

- `brand/` exists at the repo root with `tokens.css`, `BRAND.md` and the
  subsetted font files, and both `CLAUDE.md` and `AGENTS.md` list it
- `src/style.css` and `og.html` agree on background and accent, each pointing
  at `brand/BRAND.md`
- No page on any property requests a font from a third-party origin. Verified
  by loading the Landing Page, `/topology/` and the Documentation Site with the
  network panel filtered to third-party requests
- `topology/dist/index.html` remains a single self-contained file, and
  `cp`-ing it to `src/topology/index.html` remains a one-line operation
- `topology.png` re-screenshotted from port 3009 renders in the same typefaces
  as the live page
- The Documentation Site's light/dark toggle still works, and body text remains
  comfortable to read in both
- One SVG Mark, hand-drawn, serving as favicon on both sites, `theme.logo` on
  the Documentation Site, and the mark on the OG card
- One portrait, from a real photograph, in three crops on the brand background
- `build.sh` runs with no new dependency; the MkDocs build is clean

This spec lives under `docs/superpowers/`, which `mkdocs.yml` lists in
`exclude_docs`. It is not published and needs no `nav` or `docs/README.md`
entry.
