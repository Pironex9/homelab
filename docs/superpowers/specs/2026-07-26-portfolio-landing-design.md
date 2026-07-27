# Homelab Landing Page - Design

## Purpose

A public one-page site at the apex domain `homelabor.net`, built to make a hiring audience take the infrastructure seriously within the first ten seconds. Distinct from the Documentation Site, which serves a different reader - someone who already cares and wants the details.

Motivated by an active job search as of 2026-07-26.

## Positioning

The page states what it can prove and nothing else: a derived count, a measured uptime figure, and named projects that link to their own write-ups. It does not describe the author as a career changer.

The label puts an assumed weakness in the first sentence, before the reader has seen any of the work - while the entire premise of the page is that the work speaks first. That context belongs in an interview or a CV, not in the hero.

## Scope

In scope: the Landing Page - content, visual design, live-status integration, build tooling, deployment - plus the two changes it forces elsewhere: a stripped-down Documentation Site homepage, and a curated Uptime Kuma status page.

Out of scope: a CV file. It does not exist yet. The contact section reserves a slot for a future download button; no placeholder link ships, because a dead link is worse than an absent one.

## Hosting

Self-hosted on the Hetzner VPS, not on GitHub Pages. Rationale and rejected alternatives: `docs/adr/0001-landing-page-hosted-on-vps.md`.

- New Compose Stack at `compose/vps/landing/`, joining `pangolin` and `uptime-kuma` on that host. Named `landing`, not `portfolio` - that name belongs to the daughter's art site on LXC 100, as does the Uptime Kuma monitor called "Portfolio".
- `caddy:alpine` serving static files, following the shape of the `portfolio` and `topology` stacks.
- Deployed by Komodo, which already manages the VPS through a Periphery agent in outbound mode over Tailscale. The repo is checked out there at `/etc/komodo/repos/github/`, so the build can count Compose Stacks from the filesystem.
- Stateless: `dist/` is rebuilt from git and nothing is written at runtime. Nothing for `scripts/backup.sh` to cover.

### Networking

The container attaches to the **existing `pangolin` bridge network as an external network**, with a static address (172.18.0.10). It publishes no host port.

This is not a stylistic choice. UFW on the VPS carries a single rule for Uptime Kuma:

```
3001/tcp   ALLOW IN   172.18.0.0/16   # Uptime Kuma - Traefik internal
```

A stack on its own network would land on 172.17.x or 172.19.x, and its calls to Kuma would be dropped by the firewall. Joining `pangolin` puts the container inside the permitted source range, so the live-status proxy works with **no new firewall rule and no published port on the hardened public gateway**. Traefik reaches it from the same network - it runs inside gerbil's network namespace at 172.18.0.3.

The static address is required because Pangolin addresses resource targets by IP, and a container that picks up a new address on recreate would silently break the route.

### Exposure

A Pangolin resource, not a hand-written Traefik route. The file provider is pinned to the single file `/etc/traefik/dynamic_config.yml`, which the Pangolin installer owns; the `rules/` directory exists but is not wired up as a provider. Editing that file would work but risks being overwritten on upgrade.

- Pangolin's configured `base_domain` is already `homelabor.net`, registered as a verified wildcard domain.
- Apex resources are created by leaving the subdomain field blank and adding a separate A record for the apex. All ten existing resources use a subdomain, so there is no local precedent, and this is a known-rough area upstream (fosrl/pangolin issue #2645).
- **Fallback if the installed version refuses an apex resource:** add a router to `dynamic_config.yml` directly, and record it in the VPS docs as a hand-edit that must be re-applied after a Pangolin upgrade.
- Authentication is **off** for this resource - it is the one thing that must be reachable by anyone. Jellyfin is the existing precedent for a public, auth-free resource.
- DNS: an A record for the apex pointing at the VPS, **gray cloud (DNS only)**. Mandatory across this setup, not a preference - orange cloud breaks Traefik's Let's Encrypt challenge (`docs/vps/01_Hetzner_VPS_Pangolin_Jellyfin_Setup.md`). The accepted consequence is that there is no CDN and no stale-on-error cache in front of the page.

## Relationship to the Documentation Site

Two properties, two hosts, one domain root:

- `homelabor.net` - the Landing Page, on the VPS.
- `docs.homelabor.net` - the Documentation Site, unchanged on GitHub Pages.

The Documentation Site's homepage (`docs/index.md`) is **stripped to a navigation index**: the Tech Stack table, Architecture section, Dashboard screenshot and Featured Projects come out, leaving navigation, contact, and a link back to `homelabor.net`.

This is not tidying. Those sections duplicate the Landing Page almost exactly, and duplicated facts drift. After the change each fact has one home: the Landing Page makes the case, the Documentation Site holds the reference material.

## Content structure

One scrolling page:

1. **Hero** - name, a one-line statement of what is being run, and two figures: Compose Stack count and thirty-day Uptime. Buttons: GitHub, LinkedIn, and "Full documentation" to `docs.homelabor.net`.
2. **Tech stack** - icon grid: Proxmox, Docker, Komodo, MergerFS + SnapRAID, Restic, Pangolin, Caddy, Tailscale, AdGuard, Uptime Kuma.
3. **Architecture** - the existing `docs/assets/topology.png` (218 KB). No new diagramming tooling.
4. **Featured Projects** - the four write-ups currently on the Documentation Site's homepage, as cards. This is where those descriptions now live; they are removed from `docs/index.md` rather than copied. Link targets, all verified to return 200:
   - `https://docs.homelabor.net/proxmox/16_Komodo_complete_setup/`
   - `https://docs.homelabor.net/proxmox/01_Proxmox_VE_9.1_MergerFS_SnapRAID_Installation_Documentation/`
   - `https://docs.homelabor.net/vps/01_Hetzner_VPS_Pangolin_Jellyfin_Setup/`
   - `https://docs.homelabor.net/proxmox/15_Proxmox_Backup_System_Documentation/`
5. **Contact / footer** - LinkedIn, GitHub, reserved CV slot.

No blog, no testimonials, no 3D or WebGPU set pieces.

## The two figures

Neither is typed by hand. Hand-maintained counts drift: `AGENTS.md` still claims 22 Docker stacks on LXC 100 where there are 23.

| Figure | Derivation | Current value |
|---|---|---|
| Compose Stacks | `find compose -mindepth 2 -maxdepth 2 -type d \| wc -l` | 29 |
| Uptime | Uptime Kuma badge endpoint, thirty-day window, averaged across the Publicly Monitored Services | live, ~99.9% |

A Proxmox Guest count was specified earlier and is **dropped**. It cannot be derived reliably: the obvious source, the infra table in `AGENTS.md`, packs two guests into single rows (`LXC 110 caddy / 111 uzlet`), so a regex over it silently returns 9 against a true 11. Querying Proxmox directly at build time would require SSH from the public gateway into the hypervisor - a security regression for the sake of one number. A figure that cannot be derived is not asserted; the Proxmox story is carried by the tech stack and architecture sections instead.

The uptime window is thirty days, not twenty-four hours and not instantaneous status. A single overnight outage moves a thirty-day average by a fraction of a percent but sends a twenty-four hour figure toward zero - and the reader arrives at a moment of their choosing. Instantaneous up/down still appears as per-service indicator dots; it is simply not the headline.

## Live status integration

### Remediating the existing status page first

A published status page **already exists** and is publicly reachable without authentication:

```
https://uptime.homelabor.net/status/statuspage1   ->  HTTP 200
```

It carries a single public group containing **all 37 monitors**, so the public API discloses names including qBittorrent, Radarr, Sonarr, Prowlarr, Seerr, SuggestArr, Immich, Syncthing and Dawarich. The `uptime.homelabor.net` hostname appears in this repo's documentation, which is public on GitHub.

This predates the Landing Page and is worth fixing on its own merits. The remediation: **curate the existing page down** to roughly thirteen monitors - AdGuard Home, Home Assistant, Immich, Jellyfin, NetData, Scrutiny, SnapRAID Daemon, Pangolin, Uptime Kuma, code-server, DocuSeal, Kan, FreshRSS.

Removed: the media-acquisition stack (qBittorrent, Prowlarr, Sonarr, Radarr, Seerr, SuggestArr), because this page will be linked from a domain aimed at employers and every name on it is a statement; personal-data services (Syncthing, Dawarich); and the duplicate "(public)" monitors, which are tunnel self-tests rather than distinct services. The full view stays where it belongs - behind login in Kuma itself.

One published status page remains afterward: one place to maintain, one place that matters.

### The widget

- Caddy reverse-proxies `/api/status/*` to Uptime Kuma at **`172.17.0.1:3001`** - the address Pangolin's own resource target uses, verified in its database. (The architecture diagram in `docs/vps/03_Uptime_Kuma_VPS_Migration.md` says `172.18.0.1`; that is wrong and misled an earlier draft of this spec.) Kuma runs on this same host with `network_mode: host`, so this is a local hop and the widget is **same-origin** - no CORS involvement at all.
- The thirty-day figure comes from `/api/badge/<id>/uptime/720h`, one call per Publicly Monitored Service, averaged in the browser. Kuma caches these for five minutes server-side and sets `allowAllOrigin`.
- The badge returns SVG, not JSON. The value appears as text content, e.g. `...textLength="430">99.93%</text>`, so it is extracted with a match on `>([\d.]+)%<`. Verified against a live response.
- The badge endpoint returns `N/A` unless the monitor belongs to a group with `public = 1` (`isMonitorPublic` in `api-router.js`). The curated status page supplies exactly that, so the two decisions are coupled: removing a monitor from the page also removes it from the average.
- Per-service dots come from a single call to `/api/status-page/heartbeat/statuspage1`.
- If Kuma does not answer, the figures are omitted and the surrounding copy stands on its own. No error state, no empty boxes, no fabricated number.

Two upstream constraints found during design, recorded so they are not rediscovered:

- The status-page JSON endpoint sets **no CORS headers**, unlike the badge endpoints. Fetching it cross-origin from a browser fails. Serving the page from the same host sidesteps this; hosting elsewhere would have required a Traefik middleware or a scheduled build baking in stale values.
- That endpoint exposes **only** twenty-four hour uptime - `uptimeList[\`${monitorID}_24\`]` is hardcoded in `status-page-router.js`. The thirty-day window is reachable only through the badge endpoint.

No other live widgets: no GitHub contribution graph, no last-commit timestamp, no Netdata badges, no Grafana embeds, no WakaTime.

The Landing Page itself gets an Uptime Kuma monitor, but is **not** added to the public status page - a page reporting its own availability proves nothing.

## Visual design direction

- Dark theme.
- Indicator dots pulse subtly; the hero figures count up when scrolled into view.
- Project cards lift slightly on hover.
- Sans-serif for body copy, monospace for figures and status text - an engineering feel without a terminal-emulator pastiche.
- Mobile: sections stack; the icon grid drops to two columns.
- Implementation goes through the `design-taste-frontend` skill, to avoid a templated look.

## Build tooling

A single POSIX shell script. No framework, no dependencies, no Node.

Astro was specified in the first draft and is dropped. Its justification was component reuse "if the site grows a second page later" - a speculative need, against the certain cost of a Node toolchain, a lockfile and framework version churn, for one page. This is also simpler than the art portfolio's `build.js` precedent, which needs Node only because it uses `sharp` for image resizing. Nothing here resizes anything.

The script substitutes `{{STACK_COUNT}}` in `index.html` with the derived value and writes the result to `dist/`. The replacement is bare digits, so there is no escaping hazard. Uptime is not built in - it is fetched live at runtime.

**Self-check:** the script fails loudly if the placeholder survives into the output, or if the derived count is zero. Shipping a literal `{{STACK_COUNT}}` to a hiring audience is the failure worth guarding against.

## Deployment

Following the Komodo GitOps flow already used for the VPS:

1. Commit the stack; Komodo pulls.
2. Run the build in the checkout on the VPS.
3. `docker compose up -d`. As with the art portfolio, recreate rather than restart after a rebuild - the build replaces `dist/`, which breaks an existing bind mount.

Content changes are rare and the uptime figure is live, so a manual build is not a recurring cost. No CI workflow, no scheduled job.

## Testing / quality checks

No automated suite - a static page with no backend logic does not warrant one. The build script's self-check covers the only logic present. Before going live:

- Every section checked at desktop and mobile widths.
- One Lighthouse pass: performance, accessibility, basic SEO.
- Every Featured Project card resolves; the four target URLs are listed above and currently return 200.
- The apex resolves over HTTPS with a valid certificate, and is reachable **without** Pangolin auth from a browser with no session.
- The status widget checked in both directions: answering normally, and with Kuma unreachable, confirming the figures are omitted rather than rendered broken.
- After curating the status page, confirm the removed monitors no longer appear in `/api/status-page/statuspage1`.

## Follow-up, not part of this work

- `AGENTS.md` and `CLAUDE.md` both state a stale Docker stack count for LXC 100 (22 against an actual 23).
- `docs/vps/03_Uptime_Kuma_VPS_Migration.md` documents Traefik reaching Kuma at `172.18.0.1:3001`; the configured target is `172.17.0.1:3001`.
- Both `pangolin` and `traefik` on the VPS run floating `latest` tags. Pre-existing, unrelated to this work, but it means an upgrade can arrive unannounced - which matters more once an apex route depends on Pangolin's behaviour.
