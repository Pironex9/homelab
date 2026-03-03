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

All stacks are managed via **Dockge** and stored at `/srv/docker-compose/<stack-name>/`.

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
| `bentopdf` | `bentopdf/bentopdf` | 3000 | PDF reader |

### Other Services

| Container | Image | Port | Description |
|-----------|-------|------|-------------|
| `freshrss` | `freshrss/freshrss` | 8083 | RSS feed reader |
| `seerr` | `ghcr.io/seerr-team/seerr` | 5055 | Media request management |
| `syncthing` | `lscr.io/linuxserver/syncthing` | 8384, 22000 | File synchronization |
| `notifiarr` | `golift/notifiarr` | - | Notification hub |

### Management

| Container | Image | Port | Description |
|-----------|-------|------|-------------|
| `dockge` | `louislam/dockge:1` | 5001 | Docker Compose stack manager |
| `dozzle` | `amir20/dozzle` | 8888 | Real-time Docker log viewer |
| `homepage` | `ghcr.io/gethomepage/homepage` | 3002 | Self-hosted dashboard |
| `uptime-kuma` | `louislam/uptime-kuma` | - | Service uptime monitoring |
| `scrutiny` | `ghcr.io/analogj/scrutiny` | 8082 | Hard drive S.M.A.R.T. monitoring |

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
