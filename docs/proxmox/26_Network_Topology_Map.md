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
