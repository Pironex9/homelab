# Interactive Network Topology Map (Static Build + Caddy)

**Date:** 2026-07-19
**Hostname:** docker-host (LXC 100)
**IP address:** 192.168.0.110

Interactive topology map of the whole homelab, replacing the static `topology.png` screenshot. Same pattern as the art portfolio site: no backend, no runtime API calls - a Node build script bakes a YAML inventory into a single self-contained HTML page, served by Caddy in Docker on port 3009.

Source: `compose/proxmox-lxc-100/topology/` in this repo.

## Architecture

```
nodes.yml (sites, kinds, nodes: badge/name/ip/role/detail)
        |
        v
build.js (Node 20, ESM, js-yaml only)
  - validates every node: required fields, known kind, known site,
    exactly one head node per site - fail loud, never ship a broken map
  - renders one index.html with the inventory embedded as JSON
  - post-build check: every node card and IP present in the output
        |
        v
dist/  -> mounted into caddy:alpine, port 3009:80
```

The map is data-driven: adding a host is one YAML block + `npm run build`. Kinds (hypervisor / LXC / VM / K3s node) define the color coding, sites define the network blocks.

## Frontend

Control-room blueprint aesthetic: deep navy grid-paper background, Big Shoulders Display + IBM Plex Mono typography, color-coded node cards with status-bar accents.

- **Two network blocks**: SITE A (home LAN, 192.168.0.0/24) with the Proxmox host on top fanning out to all LXCs/VM, and SITE B (K3s cluster, 192.168.2.0/24) as a dashed "remote" panel, joined by a Tailscale mesh uplink marker.
- **SVG wires** are drawn client-side from actual card positions (no network calls) and redrawn on resize, so the tree survives any viewport.
- **Click a node** - a detail panel shows ID, IP, role, hardware and a description; the selected card glows and its wire animates as a dashed "traffic" line. On mobile the panel becomes a bottom sheet.
- Keyboard accessible (cards are buttons), `prefers-reduced-motion` respected, `<` escaped in the embedded JSON.

## Build and deploy

```bash
cd compose/proxmox-lxc-100/topology
npm test        # node:test - build verification + fail-loud validation
npm run build   # writes dist/
```

`dist/` is gitignored; deploy is a build + rsync to the repo clone on LXC 100, same as the portfolio:

```bash
rsync -a --delete dist/ root@192.168.0.110:/etc/komodo/repos/github/compose/proxmox-lxc-100/topology/dist/
```

Caddy serves the mounted volume live - no container restart needed. LAN name (`topology.lan`) goes through the usual AdGuard rewrite + LXC 110 Caddy proxy pair.

## Also published publicly at homelabor.net/topology/

**Date:** 2026-07-28

The same build is served a second time from the Hetzner VPS, at `https://homelabor.net/topology/`, where the landing page's `topology.png` links to it. The public copy is not this container: `dist/index.html` is copied into `compose/vps/landing/src/topology/index.html` and shipped with the landing page.

The duplication is deliberate. `dist/` is gitignored, so it does not exist in the Komodo checkout on the VPS that `build.sh` runs against - there is nothing there to copy from at build time. Serving the LAN container through a tunnel instead would have made a portfolio page depend on the homelab being up, which is the exact failure the landing page was moved to the VPS to avoid.

**Consequence:** editing `nodes.yml` now moves one more thing. After `npm run build`, copy the output across:

```bash
cp compose/proxmox-lxc-100/topology/dist/index.html \
   compose/vps/landing/src/topology/index.html
```

then re-export `topology.png` and rebuild the landing page. The full five-step checklist, including the PNG export command, is in `compose/vps/landing/README.md`; nothing enforces it, and a missed copy shows up only as a public map with a stale date stamp.

The public copy carries the same content as the LAN one, including every private LAN IP. That is not new exposure - the host pages on `docs.homelabor.net` list the same addresses, and the landing page's own alt text names `192.168.0.109`.
