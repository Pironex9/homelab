# Homepage Dashboard Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the gethomepage dashboard layout so every row is exactly filled, cutting the page from 2600px to roughly 1200px without removing any service or widget.

**Architecture:** Each topical section becomes two adjacent layout groups — a widget group with a header, and a link-only group with `header: false` that visually attaches to it. `columns` always equals the item count of its group, so no row is ever partially filled. Eleven sections collapse to four plus the calendar.

**Tech Stack:** YAML config for gethomepage v0.13.2, deployed through Komodo GitOps to LXC 100, verified with headless Chrome screenshots.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-28-homepage-dashboard-redesign.md`.
- No service is added or removed. Only grouping and presentation change.
- The `background` block in `settings.yaml` stays byte-identical: `blur: ""`, `saturate: 60`, `brightness: 50`, `opacity: 60`.
- Never add `cardBlur` — it flickers on repaint and was rejected after live testing.
- `theme: dark`, `color: slate`, `headerStyle: boxed`, `title: Proxmox Home Page` all stay.
- Config templating uses `{{HOMEPAGE_VAR_*}}`, which is not valid YAML. Every validation script must substitute those before parsing.
- The live container reads `/etc/komodo/repos/github/compose/proxmox-lxc-100/homepage/config`, not the repo working tree and not `/srv/docker-data/homepage`. Deploy = commit, push, Komodo `PullStack`.
- `iconsOnly` works only on bookmark groups. Never put it on a service group.
- Do not touch `compose/vps/landing/` — unrelated, with uncommitted work in progress.

---

## Task 1: Regroup services and rewrite the layout

Restructures the dashboard. Services move between groups, groups are renamed, and the layout block is rewritten to match. These cannot be split: a service group that has no layout entry renders with default styling, so a half-applied change looks broken.

**Files:**
- Modify: `compose/proxmox-lxc-100/homepage/config/services.yaml` (group names and membership; the calendar integration at lines 325 and 331)
- Modify: `compose/proxmox-lxc-100/homepage/config/settings.yaml` (global keys and the whole `layout` block)
- Create: `/tmp/claude-0/-root-homelab/c554a48f-41b8-4aab-8049-e58028b5555f/scratchpad/check-layout.py` (throwaway validator, not committed)

**Interfaces:**
- Consumes: nothing.
- Produces: the group names `Status`, `Status Links`, `Core`, `Core Links`, `Media`, `Media Links`, `Utilities`, `Utilities Links`, `Calendar`. Tasks 2 and 3 rely on these names existing in both files.

- [ ] **Step 1: Write the validator**

Create `check-layout.py` in the session scratchpad. It fails loudly on the three mistakes that are easy to make here: a layout group with no matching service/bookmark group, a service group with no layout entry, and a group whose `columns` does not equal its item count.

```python
import re, sys, yaml

BASE = "compose/proxmox-lxc-100/homepage/config/"

def load(p):
    return yaml.safe_load(re.sub(r"\{\{(\w+)\}\}", r'"\1"', open(BASE + p).read()))

settings, services, bookmarks = load("settings.yaml"), load("services.yaml"), load("bookmarks.yaml")
counts = {k: len(v) for g in services + bookmarks for k, v in g.items()}
layout = settings["layout"]
errors = []

for name in layout:
    if name not in counts:
        errors.append(f"layout group '{name}' matches no service or bookmark group")
for name in counts:
    if name not in layout:
        errors.append(f"group '{name}' has no layout entry")
for name, cfg in layout.items():
    if name in counts and cfg.get("columns") != counts[name]:
        errors.append(f"'{name}': columns={cfg.get('columns')} but {counts[name]} items")

assert "cardBlur" not in settings, "cardBlur is forbidden, it flickers"
assert settings["background"]["opacity"] == 60, "background must stay unchanged"
for key in ("useEqualHeights", "fullWidth", "hideVersion"):
    assert settings.get(key) is True, f"{key} must be true"

for ref in re.findall(r"service_group:\s*(.+)", open(BASE + "services.yaml").read()):
    assert ref.strip() in counts, f"calendar references missing group '{ref.strip()}'"

print("\n".join(errors) or "OK")
sys.exit(1 if errors else 0)
```

- [ ] **Step 2: Run the validator to verify it fails**

Run: `cd /root/homelab && python3 /tmp/claude-0/-root-homelab/c554a48f-41b8-4aab-8049-e58028b5555f/scratchpad/check-layout.py`

Expected: FAIL. The current config has `Monitoring` with 6 items but `columns: 5`, `Infrastructure` with 5 items but `columns: 4`, and several more. This confirms the validator detects real mismatches rather than passing vacuously.

- [ ] **Step 3: Regroup `services.yaml`**

Keep every service entry's fields exactly as they are — `icon`, `href`, `description`, `siteMonitor`, `statusStyle`, `widget`. Only the group each entry sits under changes. The resulting group order and membership:

| Group | Members, in order |
|---|---|
| `Status` | Proxmox, Uptime Kuma, Netdata, Scrutiny |
| `Status Links` | Notifiarr, SnapRAID Daemon, Homelable, Topology, Landing, Pangolin |
| `Core` | AdGuard Home, Komodo, Home Assistant |
| `Core Links` | n8n, Dawarich, FreshRSS, Odysseus, Hermes Agent, Minions |
| `Media` | Radarr, Sonarr, qBittorrent, Seerr, Jellyfin, Immich |
| `Media Links` | Prowlarr, Suggestarr, Enci Portfolio, Calibre-Web, Calibre Downloader |
| `Utilities` | Vaultwarden, Karakeep, BentoPDF, DocuSeal, Code Server, Kan |
| `Utilities Links` | Syncthing (PVE), Syncthing (Nex-PC), Wake on LAN |
| `Calendar` | Arr Calendar |

Two entries are currently both named `Syncthing`, which makes them indistinguishable in the UI. Rename them to `Syncthing (PVE)` (the one at `http://syncthing.lan`, description `Proxmox`) and `Syncthing (Nex-PC)` (the one at `http://syncthing-nex.lan`, description `Nex-PC`).

Delete the stray blank lines inside the old `Media` and `Automation` groups while moving entries.

- [ ] **Step 4: Repoint the calendar integration**

`Arr Stack` no longer exists, and the calendar looks its sources up by group name. Without this the calendar renders empty with no error. At `services.yaml:325` and `:331`:

```yaml
                - type: sonarr
                  service_group: Media
                  service_name: Sonarr
                  color: blue
                  params:
                      unmonitored: false
                - type: radarr
                  service_group: Media
                  service_name: Radarr
                  color: yellow
                  params:
                      unmonitored: false
```

- [ ] **Step 5: Rewrite `settings.yaml`**

```yaml
---
# For configuration options and examples, please see:
# https://gethomepage.dev/configs/settings/

title: Proxmox Home Page

headerStyle: boxed
fullWidth: true
useEqualHeights: true
hideVersion: true

background:
  image: https://www.traveltalktours.com/wp-content/smush-webp/2024/04/Best-Places-for-Cherry-Blossoms-in-Japan-1536x1024.jpg.webp
  blur: ""
  saturate: 60 # 0, 50, 100... see https://tailwindcss.com/docs/backdrop-saturate
  brightness: 50 # 0, 50, 75... see https://tailwindcss.com/docs/backdrop-brightness
  opacity: 60 # 0-100

theme: dark
color: slate

# Every group's `columns` equals its item count, so no row is ever partially
# filled. The `Links` groups carry `header: false` so they attach visually to
# the widget group above them instead of reading as separate sections.
layout:
  Quick Links:
    icon: mdi-link-variant
    style: row
    columns: 8
    iconsOnly: true
  Uzlet:
    icon: mdi-chart-line
    style: row
    columns: 3
    iconsOnly: true

  Status:
    icon: mdi-heart-pulse
    style: row
    columns: 4
  Status Links:
    header: false
    style: row
    columns: 6

  Core:
    icon: mdi-server
    style: row
    columns: 3
  Core Links:
    header: false
    style: row
    columns: 6

  Media:
    icon: mdi-play-circle
    style: row
    columns: 6
  Media Links:
    header: false
    style: row
    columns: 5

  Utilities:
    icon: mdi-tools
    style: row
    columns: 6
  Utilities Links:
    header: false
    style: row
    columns: 3

  Calendar:
    icon: mdi-calendar
    style: row
    columns: 1
```

`Quick Links` is set to 8 columns because Task 2 removes the ninth bookmark. Running the validator before Task 2 will therefore report `Quick Links: columns=8 but 9 items` — that one is expected and clears in Task 2. Every other group must already balance.

- [ ] **Step 6: Run the validator to verify it passes**

Run: `cd /root/homelab && python3 /tmp/claude-0/-root-homelab/c554a48f-41b8-4aab-8049-e58028b5555f/scratchpad/check-layout.py`

Expected: only the known `Quick Links` line, nothing else. Any other mismatch is a real error — fix it before deploying.

- [ ] **Step 7: Commit and deploy**

```bash
cd /root/homelab
git add compose/proxmox-lxc-100/homepage/config/services.yaml compose/proxmox-lxc-100/homepage/config/settings.yaml
git commit -m "refactor(homepage): regroup services so every row fills exactly

Splits each section into a widget group and a header-less link strip, with
columns matched to item count. Merges Arr Stack into Media and moves Home
Assistant to Core so both widget rows come out exact. Repoints the calendar
integration at the renamed group."
git push origin main
set -a; . /root/.secrets/komodo-api; set +a
curl -s -X POST http://192.168.0.105:9120/execute \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $KOMODO_KEY" -H "X-Api-Secret: $KOMODO_SECRET" \
  -d '{"type":"PullStack","params":{"stack":"homepage"}}' > /dev/null
sleep 8
ssh root@192.168.0.110 'cd /etc/komodo/repos/github && git log --oneline -1'
```

Expected: the clone reports the commit just pushed.

- [ ] **Step 8: Screenshot and inspect**

```bash
node /tmp/claude-0/-root-homelab/c554a48f-41b8-4aab-8049-e58028b5555f/scratchpad/shot.js "http://192.168.0.110:3002/" after-task1.png
```

Read the image and confirm all four:
1. No card sits alone on a row with empty space beside it.
2. The `Status Links`, `Core Links`, `Media Links` and `Utilities Links` strips sit tight under their section with no header of their own.
3. The calendar shows July 2026 with coloured release dots — if it is empty, Step 4 was missed.
4. The page is roughly 1200px tall, down from 2600px.

Also run `ssh root@192.168.0.110 'docker logs --since 5m homepage 2>&1 | grep -i "error" | grep -v httpProxy'` and expect no output. Two `httpProxy` failures are pre-existing and unrelated: Calibre Downloader (`:8084`, ECONNREFUSED) and Hermes (`:8787/health`, ECONNRESET).

If the six-across `Media` widget row reads as cramped, the single knob to flip is `fullWidth: true` → remove it, or drop `Media` to `columns: 5` and move one service into `Media Links`. Do not reach for `cardBlur`.

---

## Task 2: Fix the bookmark icons

Quick Links renders nine `si-*` Simple Icons, which are monochrome by design and unlabelled, so they are indistinguishable. Dashboard Icons serve the same brands in full colour under a bare filename.

**Files:**
- Modify: `compose/proxmox-lxc-100/homepage/config/bookmarks.yaml`

**Interfaces:**
- Consumes: the `Quick Links: columns: 8` entry written in Task 1.
- Produces: an 8-item `Quick Links` group, which is what makes the validator pass cleanly.

- [ ] **Step 1: Verify every icon name resolves before using it**

A missing icon renders as a blank tile rather than an error, so this cannot be checked visually with confidence.

```bash
for n in github tailscale hetzner cloudflare reddit mkdocs linkedin metabase fastapi; do
  printf '%s -> %s\n' "$n" \
    "$(curl -s -o /dev/null -w '%{http_code}' -I "https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/$n.png")"
done
```

Expected: all 200. `resend` is deliberately absent from this list — it returns 404 from both Dashboard Icons and selfh.st, so it keeps its Simple Icon with an explicit colour suffix instead.

- [ ] **Step 2: Rewrite `bookmarks.yaml`**

```yaml
---
- Quick Links:
    - GitHub Homelab:
        - icon: github.png
          href: https://github.com/Pironex9/homelab
    - Tailscale:
        - icon: tailscale.png
          href: https://login.tailscale.com/admin/machines
    - Hetzner:
        - icon: hetzner.png
          href: https://console.hetzner.com/projects/13016027/dashboard
    - Cloudflare:
        - icon: cloudflare.png
          href: https://dash.cloudflare.com/47bd0954876ebc191ce6b29e6ba0df65/home/domains
    - Resend:
        - icon: si-resend-#ffffff
          href: https://app.resend.com
    - r/selfhosted:
        - icon: reddit.png
          href: https://www.reddit.com/r/selfhosted
    - Docs:
        - icon: mkdocs.png
          href: https://docs.homelabor.net
    - LinkedIn:
        - icon: linkedin.png
          href: https://www.linkedin.com/in/norbert-csicsay-497195334
- Uzlet:
    - Scraper API:
        - icon: fastapi.png
          href: http://192.168.0.115:8001/
    - Metabase:
        - icon: metabase.png
          href: http://192.168.0.115:3000/question#eyJkYXRhc2V0X3F1ZXJ5Ijp7ImRhdGFiYXNlIjoyLCJ0eXBlIjoicXVlcnkiLCJxdWVyeSI6eyJzb3VyY2UtdGFibGUiOjExN319LCJkaXNwbGF5IjoidGFibGUiLCJ2aXN1YWxpemF0aW9uX3NldHRpbmdzIjp7fX0=
    - Dashboard:
        - icon: mdi-chart-box-outline
          href: https://uzlet.homelabor.net/public/dashboard/d0830a24-16bf-4a0a-922e-d24f25692141
```

The `Portfolio` entry is gone. `homelabor.net` stays reachable as the `Landing` service in `Status Links`, which additionally carries `siteMonitor` — and the Uptime Kuma status page was checked and monitors none of the 13 entries against homelabor.net, so the service card is the only thing watching it.

`Metabase` and `Dashboard` previously shared `si-metabase`. `Dashboard` now uses `mdi-chart-box-outline` because it points at a published dashboard rather than at Metabase itself.

- [ ] **Step 3: Run the validator to verify it passes cleanly**

Run: `cd /root/homelab && python3 /tmp/claude-0/-root-homelab/c554a48f-41b8-4aab-8049-e58028b5555f/scratchpad/check-layout.py`

Expected: `OK` with no lines at all. The `Quick Links` mismatch carried over from Task 1 is now resolved — 8 bookmarks against `columns: 8`.

- [ ] **Step 4: Commit and deploy**

```bash
cd /root/homelab
git add compose/proxmox-lxc-100/homepage/config/bookmarks.yaml
git commit -m "feat(homepage): colour brand icons in Quick Links

Simple Icons are monochrome by design; Dashboard Icons serve the same brands
in colour. Drops the Portfolio bookmark, which duplicated the Landing service."
git push origin main
set -a; . /root/.secrets/komodo-api; set +a
curl -s -X POST http://192.168.0.105:9120/execute \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $KOMODO_KEY" -H "X-Api-Secret: $KOMODO_SECRET" \
  -d '{"type":"PullStack","params":{"stack":"homepage"}}' > /dev/null
sleep 8
```

- [ ] **Step 5: Screenshot and confirm no blank tiles**

```bash
node /tmp/claude-0/-root-homelab/c554a48f-41b8-4aab-8049-e58028b5555f/scratchpad/shot.js "http://192.168.0.110:3002/" after-task2.png
```

Read the image. All 8 Quick Links tiles and all 3 Uzlet tiles must show a recognisable coloured logo. A blank tile means that icon name did not resolve — go back to Step 1 for that name.

---

## Task 3: Raise description legibility

Service descriptions render at `text-xs font-light`, which is what makes them hard to read. The colour is already a light grey on slate, so size and weight are the fix.

**Files:**
- Modify: `compose/proxmox-lxc-100/homepage/config/custom.css` (currently a single blank line)

**Interfaces:**
- Consumes: nothing.
- Produces: nothing later tasks depend on.

- [ ] **Step 1: Write the stylesheet**

The `.service-description` hook class is already emitted by the component at `src/components/services/item.jsx:71`, so no markup change is needed.

```css
/* Homepage renders descriptions at text-xs font-light, which is too faint to
   scan. Colour is already light grey on slate, so size and weight are enough. */
.service-description {
  font-size: 0.8rem;
  font-weight: 400;
}
```

- [ ] **Step 2: Commit and deploy**

```bash
cd /root/homelab
git add compose/proxmox-lxc-100/homepage/config/custom.css
git commit -m "style(homepage): make service descriptions legible"
git push origin main
set -a; . /root/.secrets/komodo-api; set +a
curl -s -X POST http://192.168.0.105:9120/execute \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $KOMODO_KEY" -H "X-Api-Secret: $KOMODO_SECRET" \
  -d '{"type":"PullStack","params":{"stack":"homepage"}}' > /dev/null
sleep 8
```

- [ ] **Step 3: Screenshot and compare against the baseline**

```bash
node /tmp/claude-0/-root-homelab/c554a48f-41b8-4aab-8049-e58028b5555f/scratchpad/shot.js "http://192.168.0.110:3002/" after-task3.png
```

Read the image alongside `homepage-current.png` (the pre-change baseline). Descriptions must be visibly larger and easier to scan, and no card may have grown tall enough to break the row rhythm established in Task 1. If a row did grow ragged, drop the size to `0.775rem`.

---

## Rollback

Any task can be undone with `git revert <sha>` followed by another `PullStack`. This takes about 30 seconds and was exercised twice while investigating this redesign. A tarball of the pre-change config also sits at `private/backups/homepage-config-20260728-1356.tar.gz`, which is gitignored.

## Deliberately not in this plan

- Adding an Uptime Kuma monitor for homelabor.net. The status page monitors 13 endpoints and none is the landing page, so the gap is real — but it is a Kuma change, not a dashboard change.
- `iconStyle: theme`. The mdi group-header icons render as gradients by default; whether that clashes with the colour brand icons is a judgement call best made from the Task 2 screenshot rather than decided up front.
