# Homelab Landing Page - Design

## Purpose

A public one-page site at the apex domain `homelabor.net`, built to make a hiring audience take the infrastructure seriously within the first ten seconds. Distinct from the Documentation Site, which serves a different reader (someone who already cares and wants the details).

Motivated by an active job search as of 2026-07-26.

## Positioning

The page states what it can prove and nothing else: derived counts, a measured uptime figure, and named projects that link to their own write-ups. It does not describe the author as a career changer.

The reasoning is that the label puts an assumed weakness in the first sentence, before the reader has seen any of the work - while the entire premise of the page is that the work speaks first. That context belongs in an interview or a CV, not in the hero.

## Scope

In scope: the Landing Page itself - content, visual design, live-status integration, build tooling, deployment - plus the two changes it forces elsewhere (a stripped-down Documentation Site homepage, and a public Uptime Kuma status page).

Out of scope: a CV file. It does not exist yet. The contact section reserves a slot for a future download button; no placeholder link is shipped, because a dead link is worse than an absent one.

## Hosting

Self-hosted on the Hetzner VPS, not on GitHub Pages. Rationale and rejected alternatives are recorded in `docs/adr/0001-landing-page-hosted-on-vps.md`.

- New Compose Stack at `compose/vps/landing/`, joining the two that already live there (`pangolin`, `uptime-kuma`).
- `caddy:alpine` serving static files, following the `portfolio` and `topology` stacks' shape. Host port 3010 (3001-3009 are taken on LXC 100; 3010 keeps the numbering readable even though this is a different host).
- Deployed by Komodo, which already manages the VPS through a Periphery agent in outbound mode over Tailscale.
- Exposed through the existing Traefik/Pangolin setup on the apex domain, with **no Badger auth** - this is the one resource that must be reachable by anyone.
- DNS: an A record for the apex pointing at the VPS, **gray cloud (DNS only)**. This is mandatory across this setup, not a preference - orange cloud breaks Traefik's Let's Encrypt challenge (`docs/vps/01_Hetzner_VPS_Pangolin_Jellyfin_Setup.md`). The consequence, accepted knowingly, is that there is no CDN and no stale-on-error cache in front of the page.

The stack is named `landing`, not `portfolio`: that name already belongs to the daughter's art site on LXC 100, as does the Uptime Kuma monitor called "Portfolio".

## Relationship to the Documentation Site

Two properties, two hosts, one shared domain root:

- `homelabor.net` - the Landing Page, on the VPS.
- `docs.homelabor.net` - the Documentation Site, unchanged on GitHub Pages.

The Documentation Site's homepage (`docs/index.md`) is **stripped to a navigation index**: the Tech Stack table, Architecture section, Dashboard screenshot and Featured Projects all come out, leaving navigation, contact, and a link back to `homelabor.net`.

This is not tidying. Those sections duplicate the Landing Page almost exactly, and duplicated facts drift - the same reason the counts below are derived rather than typed. After the change each fact has exactly one home: the Landing Page makes the case, the Documentation Site holds the reference material.

## Content structure

One scrolling page:

1. **Hero** - name, a one-line statement of what is being run, and three figures: Compose Stack count, Proxmox Guest count, and thirty-day Uptime. Buttons: GitHub, LinkedIn, and "Full documentation" pointing at `docs.homelabor.net`.
2. **Tech stack** - icon grid: Proxmox, Docker, Komodo, MergerFS + SnapRAID, Restic, Pangolin, Caddy, Tailscale, AdGuard, Uptime Kuma.
3. **Architecture** - the existing `topology.png` asset. No new diagramming tooling.
4. **Featured Projects** - the four write-ups currently on the Documentation Site's homepage (Komodo GitOps Migration, Resilient Storage, Self-hosted Tunnel, Backup System), as cards linking to their pages on `docs.homelabor.net`. This is where those four descriptions now live; they are removed from `docs/index.md` rather than copied.
5. **Contact / footer** - LinkedIn, GitHub, reserved CV slot.

No blog, no testimonials, no 3D or WebGPU set pieces.

## The three figures

Each has exactly one derivation, and none is typed by hand. Hand-maintained counts drift: `AGENTS.md` still claims 22 Docker stacks on LXC 100 where there are 23, which is precisely the failure being designed out.

| Figure | Derivation | Current value |
|---|---|---|
| Compose Stacks | `find compose -mindepth 2 -maxdepth 2 -type d \| wc -l` | 29 |
| Proxmox Guests | `grep -oE '(LXC\|VM) [0-9]+' AGENTS.md \| sort -u \| wc -l`, plus the hypervisor | 12 |
| Uptime | Uptime Kuma, thirty-day window, averaged across the Publicly Monitored Services | live |

The uptime window is thirty days, not twenty-four hours, and not instantaneous status. A single overnight outage moves a thirty-day average by a fraction of a percent but sends a twenty-four hour figure toward zero - and the reader arrives at a moment of their choosing, not one of ours. Instantaneous up/down still appears, as per-service indicator dots; it is simply not the headline.

## Live status integration

- Create an Uptime Kuma public status page (slug `homelab`). None exists today - `/api/entry-page` returns `entryPage: null`.
- It carries a **curated subset**, roughly thirteen of the thirty-seven active monitors: AdGuard Home, Home Assistant, Immich, Jellyfin, NetData, Scrutiny, SnapRAID Daemon, Pangolin, Uptime Kuma, code-server, DocuSeal, Kan, FreshRSS.
- Deliberately excluded: the media-acquisition stack (qBittorrent, Prowlarr, Sonarr, Radarr, Seerr, SuggestArr), because this page exists to be read by employers and every name on it is a statement; personal-data services (Syncthing, Dawarich); and the duplicate "(public)" monitors, which are tunnel self-tests rather than distinct services.
- Caddy reverse-proxies `/api/status/*` to Uptime Kuma on the Docker bridge gateway (`172.18.0.1:3001`, the address Traefik already uses to reach it). Because Kuma runs on this same host, this is a local hop, and the widget is **same-origin** - no CORS involvement at all.
- The thirty-day figure comes from Kuma's badge endpoint (`/api/badge/<id>/uptime/720h`), one call per Publicly Monitored Service, averaged in the browser. Kuma caches these for five minutes server-side. The badge returns SVG rather than JSON, so the number is extracted from the response text.
- Per-service dots come from a single call to `/api/status-page/heartbeat/homelab`.
- If Kuma does not answer, the figures are omitted and the surrounding copy stands on its own. No error state, no empty boxes, and no fabricated number.

Two constraints found during design that shaped the above, recorded so they are not rediscovered:

- The status-page JSON endpoint sets **no CORS headers** (unlike the badge endpoints, which call `allowAllOrigin`). Fetching it cross-origin from a browser fails. Serving the page from the same host sidesteps this entirely; hosting elsewhere would have required a Traefik middleware or a scheduled build baking in stale values.
- The status-page JSON exposes **only** twenty-four hour uptime - `uptimeList[\`${monitorID}_24\`]` is hardcoded in `status-page-router.js`. The thirty-day window is reachable only through the badge endpoint.

No other live widgets: no GitHub contribution graph, no last-commit timestamp, no Netdata badges, no Grafana embeds, no WakaTime.

## Visual design direction

- Dark theme.
- Indicator dots pulse subtly; the three hero figures count up when scrolled into view.
- Project cards lift slightly on hover.
- Sans-serif for body copy, monospace for figures and status text - an engineering feel without a terminal-emulator pastiche.
- Mobile: sections stack; the icon grid drops to two columns.
- Implementation goes through the `design-taste-frontend` skill, to avoid a templated look.

## Build tooling

A single POSIX shell script, no framework and no dependencies at all.

Astro was specified earlier and is dropped. Its justification was component reuse "if the site grows a second page later" - a speculative need, against the certain cost of a Node toolchain, a lockfile and framework version churn on a host that has no npm, for one page. The repo already has the pattern that fits: the art portfolio's hand-written build script.

The script does two things: substitute `{{STACK_COUNT}}` and `{{GUEST_COUNT}}` in `index.html` with the derived values, and write the result to `dist/`. Because both replacements are bare digits, there is no escaping hazard. Uptime is not built in - it is fetched live at runtime.

This is simpler than the art portfolio's precedent, which needs Node only because it uses `sharp` for image resizing. Nothing here resizes anything, so there is no reason to pull a Node image to substitute two numbers.

**Self-check:** the script fails loudly if either placeholder survives into the output, or if either derived count is zero. A build that silently ships `{{STACK_COUNT}}` to a hiring audience is the failure worth guarding against.

## Deployment

Following the Komodo GitOps flow already used for the VPS:

1. Commit the stack; Komodo pulls.
2. Run the build in the checkout on the VPS.
3. `docker compose up -d`. As with the art portfolio, recreate rather than restart the container after a rebuild - the build replaces `dist/`, which breaks an existing bind mount.

Content changes are rare and the uptime figure is live, so a manual build step is not a recurring cost. There is no CI workflow and no scheduled job.

## Testing / quality checks

No automated suite - a static page with no backend logic does not warrant one. The build script's self-check covers the one piece of logic that exists. Before going live:

- Every section checked at desktop and mobile widths.
- One Lighthouse pass: performance, accessibility, basic SEO.
- Every Featured Project card resolves to the right page on `docs.homelabor.net`.
- The apex resolves over HTTPS with a valid certificate, and is reachable **without** Pangolin auth from a browser with no session.
- The status widget checked in both directions: answering normally, and with Kuma unreachable, confirming the figures are omitted rather than rendered broken.

## Follow-up, not part of this work

`AGENTS.md` and `CLAUDE.md` both state a stale Docker stack count for LXC 100. Worth correcting, but separate.
