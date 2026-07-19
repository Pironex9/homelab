# Art Portfolio Static Site (Node build + Caddy)

**Date:** 2026-07-19
**Hostname:** docker-host (LXC 100)
**IP address:** 192.168.0.110

Static portfolio site for my daughter's art school application. No backend, no database, no CMS - a Node.js build script turns a folder of images into a single self-contained HTML page, served by Caddy in Docker on port 3008 (`portfolio.lan` via the LAN Caddy proxy).

Source: `compose/proxmox-lxc-100/portfolio/` in this repo.

## Architecture

```
content/<category>/*.jpg + optional *.yml sidecar
bio.yml (name, intro, category display names)
        |
        v
build.js (Node 20, ESM)
  - scan.js: groups images by category folder
  - metadata.js: YAML sidecars (title/technique/date), fail-loud bio parsing
  - resize.js: sharp -> 1600px full + 640px thumb JPEGs
  - render.js: single index.html with embedded JSON, zero runtime requests
        |
        v
dist/  -> mounted into caddy:alpine, port 3008:80
```

Design decisions:

- **Fail loud, never ship a broken site**: the build verifies every category appears in the HTML and every image variant exists on disk; duplicate output basenames (same name, different extension) abort the build with a clear error instead of silently overwriting.
- **YAML gotchas handled**: js-yaml turns unquoted `date: 2026-03-12` into a JS `Date` object - all sidecar values are coerced back to display strings.
- **XSS hardening even for trusted content**: embedded JSON escapes `<` (`</script>` breakout), client-side rendering escapes before `innerHTML`.
- **Accent convention**: category folder names stay accent-free ASCII slugs (they become file paths); accented display names live in `bio.yml` under `categories:` (e.g. `csendelet: "Csendélet"`).

## Frontend

Gallery-paper aesthetic: warm paper background with a subtle SVG grain, images in white "mat" frames like a gallery wall, CSS-columns masonry with natural aspect ratios, Young Serif + Karla typography (Google Fonts, latin-ext). Lightbox with prev/next + keyboard navigation (Esc, arrows), staggered reveal animation with `prefers-reduced-motion` support, image `width`/`height` attributes emitted from the build so the layout never shifts while loading.

## Build and deploy

```bash
cd compose/proxmox-lxc-100/portfolio
npm test        # 15 tests, node:test runner
npm run build   # writes dist/
```

`dist/` is gitignored, so a Komodo pull alone deploys an empty site. Deploy is a build + rsync of `dist/` to the repo clone on LXC 100:

```bash
rsync -a --delete dist/ root@192.168.0.110:/etc/komodo/repos/github/compose/proxmox-lxc-100/portfolio/dist/
```

Caddy serves the mounted volume live - no container restart needed.

## Demo content

For layout testing before real drawings are scanned, the site can be filled with public-domain drawings pulled from the [Metropolitan Museum open access API](https://metmuseum.github.io/) (no key, free): Hokusai sketchbooks for the anime category, still-life/portrait/landscape drawings for the rest. The demo build lives outside the repo; a normal `npm run build` from `content/` replaces it.

## Notes

- Built with Claude Code using subagent-driven development: one implementer subagent per plan task, independent review of each task, whole-branch review at the end. Two real bugs were caught by review before merge (Date-object coercion, basename collision).
- Public exposure via Pangolin is a later step; currently LAN-only.
