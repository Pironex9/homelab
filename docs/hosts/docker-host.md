# docker-host LXC

## Overview

| Property | Value |
|----------|-------|
| Hostname | docker-host |
| IP Address | 192.168.0.110 |
| VMID | 100 |
| OS | Debian GNU/Linux 12 (bookworm) |
| Kernel | 6.17.4-1-pve |
| CPU | 4 cores |
| RAM | 8 GB |
| Disk | 48 GB (local-lvm, LVM thin) |
| Storage mount | `/mnt/storage` → ZFS pool (8.1 TB) |
| Purpose | Primary Docker host - all self-hosted services |

## Features

- `nesting=1` - required for Docker inside LXC
- GPU passthrough: `/dev/dri/card0` and `/dev/dri/renderD128` (for Jellyfin hardware transcoding)
- Unprivileged container

## Running Services

| Service | Description |
|---------|-------------|
| `docker.service` / `containerd.service` | Docker container runtime |
| `periphery.service` | Komodo agent - connects this host to Komodo Core for remote management |
| `ssh.service` | OpenSSH server |
| `cron.service` | Scheduled tasks |
| `rpcbind.service` | Required for NFS mounts |

## Docker Stacks

All stacks are managed via **Komodo** (GitOps mode). Compose files are stored in the [homelab git repo](https://github.com/Pironex9/homelab) under `compose/proxmox-lxc-100/<stack-name>/`. Komodo clones the repo to `/etc/komodo/repos/github/` on this host and runs deploys from there. Legacy compose files remain at `/srv/docker-compose/<stack-name>/` but are no longer used.

### Media

| Container | Image | Port | Description |
|-----------|-------|------|-------------|
| `jellyfin` | `jellyfin/jellyfin` | 8096 | Media server with hardware transcoding |
| `sonarr` | `ghcr.io/hotio/sonarr` | 8989 | TV show management |
| `radarr` | `ghcr.io/hotio/radarr` | 7878 | Movie management |
| `prowlarr` | `ghcr.io/hotio/prowlarr` | 9696 | Indexer manager |
| `qbittorrent` | `ghcr.io/hotio/qbittorrent` | 8080, 6881 | Torrent client |
| `suggestarr` | `ciuse99/suggestarr` | 5000 | Media suggestion bot |

### Photos

| Container | Image | Port | Description |
|-----------|-------|------|-------------|
| `immich_server` | `ghcr.io/immich-app/immich-server:v2` | 2283 | Photo/video backup and management |
| `immich_machine_learning` | `ghcr.io/immich-app/immich-machine-learning:v2` | - | ML backend (face recognition, CLIP) |
| `immich_postgres` | `ghcr.io/immich-app/postgres:14-vectorchord0.4.3-pgvectors0.2.0` | 5432 | PostgreSQL with pgvectors extension |
| `immich_redis` | `valkey/valkey:9` | 6379 | Redis-compatible cache |

### Books

| Container | Image | Port | Description |
|-----------|-------|------|-------------|
| `calibre-web-automated` | `crocodilestick/calibre-web-automated` | 8085 | Calibre library with auto-import |
| `bentopdf` | `bentopdfteam/bentopdf` | 3000 | PDF reader |

### Location Tracking

| Container | Image | Port | Description |
|-----------|-------|------|-------------|
| `dawarich_app` | `freikin/dawarich` | 3005 | Self-hosted GPS location history and family tracking |
| `dawarich_sidekiq` | `freikin/dawarich` | - | Background job worker for Dawarich |
| `dawarich_db` | `postgis/postgis:17-3.5-alpine` | - | PostGIS database for Dawarich |
| `dawarich_redis` | `redis:7.4-alpine` | - | Redis cache for Dawarich |

### Other Services

| Container | Image | Port | Description |
|-----------|-------|------|-------------|
| `freshrss` | `freshrss/freshrss` | 8083 | RSS feed reader |
| `seerr` | `ghcr.io/seerr-team/seerr` | 5055 | Media request management |
| `syncthing` | `lscr.io/linuxserver/syncthing` | 8384, 22000 | File synchronization |
| `notifiarr` | `golift/notifiarr` | - | Notification hub |
| `docuseal` | `docuseal/docuseal` | 3003 | Self-hosted e-signature platform |

### Management

| Container | Image | Port | Description |
|-----------|-------|------|-------------|
| `homepage` | `ghcr.io/gethomepage/homepage` | 3002 | Self-hosted dashboard |
| `uptime-kuma` | `louislam/uptime-kuma` | - | Service uptime monitoring |
| `scrutiny` | `ghcr.io/analogj/scrutiny` | 8082 | Hard drive S.M.A.R.T. monitoring |
| `homelable-backend` | `ghcr.io/pouzor/homelable-backend` | - | Network topology backend (internal) |
| `homelable-frontend` | `ghcr.io/pouzor/homelable-frontend` | 3001 | Network diagram and live status UI |
| `homelable-mcp` | built from `/opt/homelable/mcp` | 8001 | MCP server - Claude Code integration |

## Docker Volumes

| Volume | Used by | Description |
|--------|---------|-------------|
| `immich_model-cache` | immich_machine_learning | CLIP and face recognition models |

Most containers use **bind mounts** to `/mnt/storage` for persistent data.

## Open Ports

| Port | Protocol | Service |
|------|----------|---------|
| 22 | TCP | SSH |
| 2283 | TCP | Immich |
| 3000 | TCP | BentoPDF |
| 3002 | TCP | Homepage |
| 5000 | TCP | Suggestarr |
| 5001 | TCP | Dockge |
| 5055 | TCP | Seerr |
| 6881 | TCP/UDP | qBittorrent torrent |
| 7878 | TCP | Radarr |
| 8080 | TCP | qBittorrent web UI |
| 8082 | TCP | Scrutiny |
| 8083 | TCP | FreshRSS |
| 8085 | TCP | Calibre-Web |
| 8096 | TCP | Jellyfin |
| 8384 | TCP | Syncthing web UI |
| 8888 | TCP | Dozzle |
| 8989 | TCP | Sonarr |
| 3001 | TCP | Homelable web UI |
| 3003 | TCP | DocuSeal |
| 3005 | TCP | Dawarich |
| 8001 | TCP | Homelable MCP server |
| 9696 | TCP | Prowlarr |
| 21027 | UDP | Syncthing discovery |
| 22000 | TCP/UDP | Syncthing sync |

## Storage Layout

```
/                    → local-lvm (48 GB LVM thin volume, 70% used)
/mnt/storage         → ZFS pool via Proxmox mountpoint (8.1 TB, 34% used)
```

Most Docker container data (media, photos, books) lives on `/mnt/storage` to avoid filling the root disk.

## Komodo Integration

The `periphery.service` agent connects this host to Komodo Core (LXC 105). This allows centralized deployment and monitoring of Docker stacks without direct SSH access.

## Lessons Learned

- **LVM thin pool vs filesystem usage:** The Proxmox LVM thin pool `Data%` for this LXC showed 96.51% while the actual filesystem was only 70% full. Thin pool percentages track historically allocated blocks, not current usage - old Docker images and deleted files leave "phantom" allocations until TRIM runs.
- **fstrim must run from the Proxmox host via nsenter:** Running `fstrim` from inside an unprivileged LXC fails with "Operation not permitted". Running it on the host at `/var/lib/lxc/100/rootfs` also doesn't work because LVM-backed containers are not mounted there. The correct method is: `nsenter --target $(pgrep -a lxc-start | grep '\\b100\\b' | awk '{print $1}') --mount -- fstrim -v /`
- **Docker image pruning is essential:** With 20+ containers, dangling images accumulate quickly. `docker image prune -f` reclaimed ~390 MB in one session. Schedule this regularly.
- **Swap is not configured:** Neither the LXC nor Docker containers have swap. A heavily memory-loaded container (e.g., postgres during Immich indexing) will be OOM-killed instead of swapping. Monitor memory headroom.
- **GPU passthrough for Jellyfin requires `dev0`/`dev1` in LXC config:** The `/dev/dri/card0` and `/dev/dri/renderD128` devices must be explicitly passed through in the Proxmox LXC config for hardware transcoding to work.
- **Huntarr security incident (Feb 2026):** Huntarr v9.4.2 was found to have critical unauthenticated API endpoints - any attacker could call every API endpoint and dump the full config including API keys for Sonarr, Radarr, Prowlarr, and other *arr apps. The developer deleted the GitHub repo and their account without any public statement. Huntarr was removed immediately. All *arr API keys were rotated after removal.
- **Recommendarr removal (Mar 2026):** The Recommendarr GitHub repo (`qdread/recommendarr`) disappeared around the same time as the Huntarr incident with no explanation. Service removed as a precaution.
- **Periphery mode: outbound (since 2026-04-06):** Periphery runs in outbound mode - it initiates the connection to Core (`http://192.168.0.105:9120`) and reconnects automatically if the connection drops. Config: `core_addresses = ["http://192.168.0.105:9120"]`, `connect_as = "LXC 100"`. If unreachable after a network outage, `systemctl restart periphery` still works as a manual fix.
- **Homelable healthcheck OOM/I/O incident (Apr 2026):** The homelable-backend healthcheck used `curl` which is not present in the container image. This caused a failed healthcheck every 10 seconds, generating continuous dockerd log writes to the LXC 100 thin pool. After several hours this saturated the disk I/O (Netdata: `disk_backlog` WARNING on `pve-vm--100--disk--0`, CPU iowait, load average), causing the entire LXC 100 to become unresponsive. Fix: replaced `curl` with `python3 -c "import urllib.request; urllib.request.urlopen(...)"` (Python is available in the image) and raised the interval from 10s to 30s. Lesson: always verify that the healthcheck binary exists in the target container image before deploying.
