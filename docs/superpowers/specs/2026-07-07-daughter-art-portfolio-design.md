# Daughter's Art Portfolio Site - Design

## Purpose

A portfolio website for a 13-year-old's drawings, for admission to a fine arts middle/high school (kepzomuveszeti kozepiskola). ~2 years until the actual admission. Most artwork is on paper (photographed/scanned), 1-2 pieces are already digital. Expected scale: 40+ drawings by the time of admission, growing continuously over the next 2 years.

## Scope

In scope: the website itself (build tooling, gallery page, hosting).
Out of scope: the digitization workflow (photographing/scanning the paper drawings) - handled separately, offline, not part of this project.

## Hosting

- New Docker Compose stack on the main docker-host LXC (192.168.0.110), following the existing `compose/proxmox-lxc-100/form/` pattern: Caddy serving static files, no backend.
- Exposed externally via Pangolin (VPS), on its own subdomain.
- Public but not indexed: `robots.txt` disallows all crawlers. No password protection - simple, still effectively private since nobody stumbles on it without the link.
- Managed by the parent (Norbert) technically; the daughter is not expected to self-serve uploads.

## Architecture

Fully static site, no database, no backend logic, no runtime API calls.

```
compose/proxmox-lxc-100/portfolio/
  Caddyfile
  docker-compose.yml
  build.js            <- custom Node script, sharp for thumbnails
  content/
    csendelet/
      01-alma.jpg
      01-alma.yml      <- title, technique, date
    tajkep/
    anime-karakter/
    ...                <- categories grow over time as new work is made
  bio.yml              <- name, age, short intro
  dist/                <- build output, served by Caddy, gitignored
```

Workflow for adding a new drawing: copy the image into the right category folder, optionally add a sidecar `.yml` with title/technique/date, run `node build.js`, restart/reload Caddy (or just let it re-serve the fresh `dist/`).

## Components

- **`build.js`** - single responsibility: walk `content/` by category, generate two sizes per image via `sharp` (full ~1600px, thumb ~400px), read sidecar metadata (falls back to a title derived from the filename if missing), and emit a single static `dist/index.html` with the image data embedded (no runtime fetch/API).
- **`dist/index.html`** - single page, vanilla JS. Bio section at top (name, age, short intro). Category tabs (All / Csendelet / Tajkep / Anime-karakter / ...) filter the grid client-side, no page reload. Click a thumbnail -> lightbox with full image + title/technique/date.
- **Metadata sidecar** (`<image>.yml` next to each image):
  ```yaml
  title: "Csendelet almaval"
  technique: "ceruza"
  date: "2026-03-12"
  ```
  Missing sidecar -> build derives a basic title from the filename; the build never fails because of missing metadata.
- **Caddyfile** - static file server for `dist/`, plus a `robots.txt` route disallowing all crawlers. Mirrors the existing `form/` stack's Caddyfile pattern.

## Build tooling choice

Custom minimal Node.js script (~50-100 lines, using `sharp` for image resizing) rather than adopting a full static site generator framework (Eleventy/Astro). Rationale: the content (category-organized image grid) doesn't need templating, routing, or plugin systems a framework provides - a plain script covers it with zero framework learning curve and minimal dependencies for something this size.

## Data flow

```
1. Image added to content/<category>/xy.jpg (+ optional xy.yml)
2. node build.js runs:
   a. Walk content/ by category
   b. For each image: sharp resize -> dist/images/<category>/xy-full.jpg, xy-thumb.jpg
   c. Collect metadata (yml or filename fallback) into an in-memory array
   d. Emit dist/index.html with the metadata array embedded inline (no fetch at runtime)
3. Caddy re-serves the fresh dist/ (restart not required, just a fresh directory)
4. content/ and build.js are version-controlled in the repo; dist/ is gitignored (build artifact)
```

## Error handling

Low-risk hobby project for a minor, no user input at runtime, no auth, no form submissions - no real attack surface to defend. Error handling is scoped to what can actually break the build:

- Missing `.yml` sidecar -> fallback title from filename, build continues
- Non-image files in a category folder (e.g. `.DS_Store`) -> skipped via extension filter
- Empty category folder -> simply produces no tab for that category

## Testing

`build.js` ends with a self-check: verifies every image under `content/` produced a matching thumb+full pair under `dist/images/`, and that the generated `index.html` contains every category name found in `content/`. If either check fails, the script exits with an error instead of silently emitting a broken/incomplete site.

## Deployment

Follows the existing Komodo GitOps flow documented in `compose/CLAUDE.md`: commit `content/`, `build.js`, `Caddyfile`, `docker-compose.yml` to this repo (only `dist/` is gitignored), Komodo pulls and deploys, manual fallback is `docker compose up -d` on the LXC.
