# Homelab Brand System - Design

## Purpose

One visual identity covering the two public surfaces that already exist - the
Landing Page at `homelabor.net` and the Documentation Site at
`docs.homelabor.net` - plus a personal layer for the places where the author
appears rather than the infrastructure.

This is mostly a consolidation. The Landing Page already has a considered
identity - dark background, orange accent, a sans/mono pairing - and it is
broadly right. Two problems sit on top of it.

## The two problems being fixed

### Internal drift on the Landing Page

Two near-identical palettes live inside `compose/vps/landing/`:

| Token | `style.css` | `og.html` |
|---|---|---|
| background | `#0b1120` | `#0b0e13` |
| accent | `#e8a04c` | `#e8933f` |

Two backgrounds differing by a few points of blue, and two oranges differing by
a shade nobody chose on purpose. The share card and the page it advertises do
not match.

The node-colour set from the topology legend (`#e8a04c` hypervisor, `#5cc8ff`
LXC, `#b18aff` VM, `#6ee7a0` K3s) is coherent and stays as-is; it becomes a
documented part of the system rather than a set of inline literals.

### The Documentation Site is a different brand entirely

`docs.homelabor.net` runs stock Material for MkDocs: `primary: indigo`,
`accent: indigo`, with a light/dark toggle. `docs/stylesheets/extra.css` is
five lines - a code-block overflow fix - and contains no colour at all.

So this is not drift, it is an unrelated visual identity sharing a domain. The
two sites are linked from each other and read as different products.

## Scope

In scope: a token layer, a logo mark for the infrastructure brand, a personal
mark and portrait set, and the derived assets each of those feeds (favicon,
site headers, OG card, CV header, avatars).

Out of scope: Enci's art portfolio on LXC 100. That site is her work and her
call; it does not inherit this system. Also out of scope: any redesign of the
Landing Page or Documentation Site layout. This changes what colours and marks
they use, not how they are built.

## Structure

### Level 0 - shared base

A `brand/` directory at the repository root holding `tokens.css` and
`BRAND.md`. One background, one accent, one font pairing, one spacing scale,
plus the topology node colours.

**The system must define a light mode as well as a dark one.** The Landing
Page is dark-only and stays that way, but the Documentation Site ships a
light/dark toggle that has no reason to be removed. A dark-only token set would
force that choice; defining both avoids it.

**Consuming surfaces copy the values; they do not import the file.** This is
deliberate and load-bearing in two places:

- `compose/vps/landing/build.sh` is dependency-free POSIX shell by design, per
  its own spec. Adding a CSS build step to resolve an import would undo that.
- `compose/vps/landing/og.html` carries a comment stating it is self-contained
  on purpose, so the share card keeps rendering identically years from now even
  if `style.css` moves on. Its values are copied from `style.css`, not
  imported.

So `brand/tokens.css` is the source of truth as a *document*, and each consumer
carries the same values with a comment naming `brand/BRAND.md` as the origin.
Drift becomes a review problem rather than a build problem - the correct trade
at three consumers.

Cost: zero credits. This layer is text.

#### Adopting it on the Documentation Site

Material does not accept arbitrary hex in `theme.palette`. The supported route
is `primary: custom` and `accent: custom` in `mkdocs.yml`, with the actual
values set as CSS custom properties in `docs/stylesheets/extra.css` - one block
per scheme, keyed on `[data-md-color-scheme="default"]` and
`[data-md-color-scheme="slate"]`, setting at minimum
`--md-primary-fg-color`, `--md-primary-fg-color--light`,
`--md-primary-fg-color--dark` and `--md-accent-fg-color`.

The existing five-line code-block fix in that file stays; the colour blocks are
added alongside it.

Note for later: Material for MkDocs reaches end of life on 2026-11-05 and this
repo is pinned below 10 pending a Zensical migration in November. Custom
properties are the portable part of this change - the `mkdocs.yml` palette keys
are the part that may need revisiting. That is a small, known cost and not a
reason to delay.

### Level 1a - infrastructure brand

A logo mark for `homelabor.net`, generated as SVG with `recraft_v4_1` in vector
mode.

- 6 directions explored, 1.25 credits each
- 2 refinements of the chosen direction

Everything downstream is derived locally from that SVG at no further cost: the
favicon (replacing the existing `src/favicon.svg`), the Documentation Site
header, and the mark on the OG card.

Budget: 10 credits.

### Level 1b - personal layer

Three surfaces, chosen by the author: a CV header, an authorship mark on
`docs.homelabor.net`, and a GitHub profile avatar. All three need the same
face, or the identity falls apart across them.

**Soul ID** solves this and is unlocked by the Basic plan. Training takes 5-20
face photographs at varied angles and lighting - supplied by the author, this
is the one external dependency in the plan. Generation afterwards costs 0.12
credits per image via `text2image_soul_v2`, so roughly 15 candidates get
generated and the good ones selected.

Constraint on the portraits: the Soul is trained on real photographs of the
author and the prompts stay within lighting, background and framing. A CV
header and a GitHub avatar are identity claims. Stylising them is fine;
generating a different face is not.

A monogram accompanies the portraits - a separate mark from the infrastructure
logo, drawn from the same token layer. 4 directions at 1.25 credits.

Budget: roughly 7 credits plus Soul training, whose cost is reported by the CLI
at creation time and is not yet measured.

### Optional - mockups

`seedream_v5_pro` at 3 credits each, only if a photoreal presentation of the
mark is actually wanted. Nothing depends on this.

## Rule: text never goes through generation

Any asset carrying words - the OG card, the CV header, banner copy - is
rendered locally from HTML with headless Chrome, exactly as
`compose/vps/landing/og.html` already does today.

This is not a cost decision, though it is also cheaper. Generated text is
unreliable at small sizes and cannot be corrected without regenerating the
whole image. `gpt_image_2` is the model the Higgsfield brandkit skill reaches
for when overlaying text, at 7 credits per call - the most expensive image
model measured, bought for the one job we should not be using it for.

## Measured costs

Taken from `higgsfield generate cost`, which estimates without creating a job
and consumes nothing:

| Model | Role | Credits |
|---|---|---|
| `recraft_v4_1` | SVG vector logo | 1.25 |
| `text2image_soul_v2` | Soul portrait | 0.12 |
| `nano_banana_2_lite`, `flux_2` | texture, background | 1 |
| `nano_banana_flash` | general image | 1.5 |
| `seedream_v5_pro` | photoreal mockup | 3 |
| `gpt_image_2` | text overlay - avoided | 7 |

Account state at time of writing: Basic plan, 112 credits, 70 per month.
Planned spend is roughly 20, so credits do not constrain this work. `generate
cost` should still be run before any unmeasured model, because it is free.

## Tooling

The official Higgsfield skill set (`higgsfield-ai/skills`, 9 skills) gets
installed; its setup handles the CLI and auth. The relevant ones here are
`higgsfield-brandkit`, `higgsfield-soul-id` and `higgsfield-generate`.

No wrapper script for credit accounting. `higgsfield generate cost` before a
call and `higgsfield account status` after are sufficient, and a logging
wrapper would be a second thing to maintain for a number the CLI already
reports.

## Rejected alternatives

**A CSS build step so the three consumers import one token file.** Rejected:
it would add a dependency to a build script whose spec commits to having none,
and would defeat the deliberate self-containment of `og.html`. Three consumers
do not justify it.

**Generating an identity from scratch.** Rejected: an identity already exists
and is broadly right. Replacing it would discard working design and cost more.

**`higgsfield website` for a new site.** Rejected: both sites already exist, are
deployed by Komodo, and are documented. A third one solves nothing.

**Video explainer of the homelab architecture.** Out of scope here. Now
affordable on the Basic plan, but it is a separate project with a separate
audience.

## Success criteria

- `brand/BRAND.md` and `brand/tokens.css` exist and are committed, defining
  both a dark and a light mode
- `compose/vps/landing/src/style.css` and `og.html` carry identical values for
  background, accent, fonts and spacing, each pointing at `brand/BRAND.md`
- `mkdocs.yml` uses `primary: custom` / `accent: custom`, and
  `docs/stylesheets/extra.css` defines the brand colours for both the
  `default` and `slate` schemes; the light/dark toggle still works
- One SVG logo mark, with favicon and site headers derived from it
- One SVG monogram, plus a selected portrait set for CV header, docs
  authorship mark and GitHub avatar
- Both sites still build and deploy unchanged in structure: `build.sh` runs
  with no new dependency, and the MkDocs build is clean

This spec lives under `docs/superpowers/`, which `mkdocs.yml` lists in
`exclude_docs`. It is not published and needs no `nav` or `docs/README.md`
entry.
