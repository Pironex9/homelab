# Homepage Dashboard Redesign

Date: 2026-07-28
Status: approved, ready for planning
Target: gethomepage on LXC 100, `http://192.168.0.110:3002`, config in `compose/proxmox-lxc-100/homepage/config/`

## Problem

The dashboard renders 2600px tall at 1920px wide while the right third of the page below the
first section stays empty. A screenshot of the live page (captured headless, see Verification)
shows four distinct defects:

1. **Orphan cards.** Groups mix services that have a widget (tall card, 2 rows of stats) with
   services that have none (short card, name + description). When the item count exceeds the
   column count, a single card wraps onto its own row with 70-75% of that row empty. This
   happens in Monitoring (SnapRAID Daemon), Infrastructure (Landing), Media (Calibre
   Downloader) and Productivity (Kan).
2. **Ragged baselines.** Within one row, widget cards are roughly twice the height of link
   cards. Card tops align, bottoms do not.
3. **Unreadable icon rows.** Quick Links renders nine `si-*` Simple Icons, which are
   monochrome by design, with no labels underneath. Uzlet uses the same `si-metabase` icon for
   two different entries.
4. **Low-contrast body text.** Service descriptions render as `text-xs font-light` in
   `text-theme-300`.

The background photo is **not** a defect; it stays exactly as configured.

## Root cause

The height difference between widget cards and link cards is structural, not cosmetic. Any
group that mixes the two produces either a ragged bottom edge (without `useEqualHeights`) or
inflated, mostly-empty link cards (with it). Tuning columns and colours cannot fix a group
whose members have two different natural heights.

39 services, of which 13 have a widget:

| Widget services (13) | Link-only services (26) |
|---|---|
| Proxmox, Uptime Kuma, Netdata, Scrutiny, AdGuard Home, Komodo, Home Assistant, Radarr, Sonarr, qBittorrent, Seerr, Jellyfin, Immich | the remaining 26 |

## Decisions

Settled during brainstorming, recorded so the plan does not relitigate them:

- **Widgets stay.** The stats are the reason the user opens the dashboard. This rules out
  collapsing everything into a launcher grid.
- **No tabs.** A single scrolling page.
- **Background photo unchanged.** `blur: ""`, `saturate: 60`, `brightness: 50`, `opacity: 60`
  stay as they are.
- **No `cardBlur`.** Per-card `backdrop-blur` flickers on repaint; rejected after testing it
  live.
- **Link-only services stay services**, rendered as a compact strip. They do not become
  bookmarks, because bookmarks lose `siteMonitor` and the status dot. `iconsOnly` is
  bookmarks-only (`src/components/bookmarks/list.jsx:9`; the services list component has no
  equivalent), so a true icon grid is not available to services.

## Design

### Principle

Every row holds cards of one kind only, and `columns` equals the number of items in that row,
so no row is ever partially filled.

Each topical section becomes two adjacent layout groups: a widget group with its header, and a
link group with `header: false` so it visually attaches to the section above it.

### Target structure

```
Status         cols 4  │ Proxmox · Uptime Kuma · Netdata · Scrutiny                 (widget)
               cols 6  │ Notifiarr · SnapRAID · Homelable · Topology · Landing · Pangolin

Core           cols 3  │ AdGuard Home · Komodo · Home Assistant                     (widget)
               cols 6  │ n8n · Dawarich · FreshRSS · Odysseus · Hermes · Minions

Media          cols 6  │ Radarr · Sonarr · qBittorrent · Seerr · Jellyfin · Immich  (widget)
               cols 5  │ Prowlarr · Suggestarr · Enci Portfolio · Calibre-Web · Calibre Downloader

Utilities      cols 6  │ Vaultwarden · Karakeep · BentoPDF · DocuSeal · Code Server · Kan
               cols 3  │ Syncthing PVE · Syncthing Nex-PC · Wake on LAN

Calendar       cols 1  │ full width
```

Eleven sections collapse to four plus the calendar. Two group merges make the arithmetic work:

- **Home Assistant moves to Core.** Automation held exactly one widget service; alone in a row
  it would render as a single full-width card.
- **Arr Stack merges into Media.** Its link strip held two items, which at `columns: 2` would
  be two half-page-wide cards carrying one line of text each. Merged, the six widget services
  form one exact row.

`Infrastructure`, `Network`, `Arr Stack`, `Automation` and `Productivity` disappear as section
names. Productivity contained one card and Network three; each cost a header and a partly
empty row.

### Landing duplication

`homelabor.net` currently appears twice: as the `Portfolio` bookmark in Quick Links and as the
`Landing` service in Infrastructure. The **service is kept**, the **bookmark is removed**.

The service carries `siteMonitor: https://homelabor.net` and a status dot. The Uptime Kuma
public status page was checked and lists 13 monitors, none of which is the landing page, so
removing the service would leave homelabor.net unmonitored everywhere.

### settings.yaml

Unchanged: `title`, `headerStyle: boxed`, `theme: dark`, `color: slate`, the whole
`background` block.

Added:

| Key | Value | Why |
|---|---|---|
| `useEqualHeights` | `true` | Rows are homogeneous now, so this only straightens the bottom edge; it can no longer inflate a short card next to a tall one. |
| `fullWidth` | `true` | The six-across widget row needs the width. This is the first knob to flip back if that row reads as cramped. |
| `hideVersion` | `true` | Removes the version string from the footer. |

Each layout group gains an `icon:`, so section headers are identifiable at a glance.

### bookmarks.yaml

`si-*` icons are monochrome by design. Replaced with Dashboard Icons (bare filename, full
colour). All names below were verified to return HTTP 200 from
`cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/<name>.png`:

| Entry | Was | Becomes |
|---|---|---|
| GitHub Homelab | `si-github` | `github.png` |
| Tailscale | `si-tailscale` | `tailscale.png` |
| Hetzner | `si-hetzner` | `hetzner.png` |
| Cloudflare | `si-cloudflare` | `cloudflare.png` |
| Reddit | `si-reddit` | `reddit.png` |
| Docs | `si-materialformkdocs` | `mkdocs.png` |
| LinkedIn | `si-linkedin` | `linkedin.png` |
| Portfolio | `mdi-server-network` | *removed* |
| Resend | `si-resend` | `si-resend-#ffffff` |

`resend` exists in neither Dashboard Icons nor selfh.st (both 404), so it keeps the Simple
Icon with an explicit colour suffix, which the docs support for `si-` and `mdi-` prefixes.

In Uzlet, `Scraper API` keeps `si-fastapi`; `Metabase` and `Dashboard` currently share
`si-metabase`. `Dashboard` becomes `mdi-chart-box-outline`, since it points at a published
Metabase dashboard rather than at Metabase itself.

### custom.css

The file exists and is empty. Service descriptions render at `text-xs font-light`, which is
what makes them hard to read; the fix is size and weight, not colour, since `theme-300` on
slate is already a light grey:

```css
.service-description {
  font-size: 0.8rem;
  font-weight: 400;
}
```

The hook class is emitted by the component already (`src/components/services/item.jsx:71`).

## Verification

The previous attempt at this redesign failed because it was designed without ever seeing the
page. Every change is now screenshotted before it is judged.

A headless Chrome script in the session scratchpad captures the live dashboard, invoked as
`node shot.js "http://192.168.0.110:3002/" out.png`:

```js
const { chromium } = require('/usr/lib/node_modules/@playwright/cli/node_modules/playwright-core');
(async () => {
  const b = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--no-sandbox'] });
  const p = await b.newPage({ viewport: { width: 1920, height: 2600 } });
  await p.goto(process.argv[2], { waitUntil: 'networkidle', timeout: 60000 });
  await p.waitForTimeout(6000);
  await p.screenshot({ path: process.argv[3], fullPage: true });
  await b.close();
})();
```

Three details are load-bearing. The bundled Playwright browser is version-mismatched
(`chromium_headless_shell-1217` installed, 1232 expected), so it points at the system Chrome
instead. Chrome refuses to run as root without `--no-sandbox`. And the dashboard renders
inside a fixed-height container, so `fullPage` stops at the fold — the viewport height is set
to 2600 to capture the whole page.

Checks after deploy:

1. Screenshot at 1920 wide and confirm no row is partially filled and no card is orphaned.
2. Confirm the rendered page height dropped from 2600px toward ~1200px.
3. Confirm every icon resolves — a broken icon renders as a blank tile, not an error.
4. `docker logs --since 5m homepage` is free of config parse errors. Two pre-existing
   `siteMonitor` failures are expected and unrelated: Calibre Downloader (`:8084`,
   ECONNREFUSED) and Hermes (`:8787/health`, ECONNRESET).

## Deployment and rollback

The container mounts the Komodo git clone
(`/etc/komodo/repos/github/compose/proxmox-lxc-100/homepage/config`), not
`/srv/docker-data/homepage`. Changes therefore require commit, push, then a Komodo `PullStack`
against the `homepage` stack. Homepage picks the config up without a container restart.

Rollback is `git revert` plus another PullStack, roughly 30 seconds, proven twice during this
session. A tarball of the pre-change config also exists at
`private/backups/homepage-config-20260728-1356.tar.gz` (gitignored).

## Out of scope

- The landing site at `compose/vps/landing/` — unrelated, and has uncommitted work in progress.
- Adding or removing services. Only their grouping and presentation change.
- Adding an Uptime Kuma monitor for homelabor.net. Worth doing, but it is a Kuma change, not a
  dashboard change.
