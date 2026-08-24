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

Homepage is also GitOps-managed at the application config level. Its YAML/CSS/JS config lives in `compose/proxmox-lxc-100/homepage/config/` and is mounted from the Komodo checkout to `/app/config`. Runtime-only data remains on host volumes: `/srv/docker-data/homepage/images` and `/srv/docker-data/homepage/logs`. Secrets stay in Komodo Stack Environment (`stack.env`) and are referenced in config with `{{HOMEPAGE_VAR_*}}` placeholders.

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
| `immich_server` | `ghcr.io/immich-app/immich-server:v3` | 2283 | Photo/video backup and management |
| `immich_postgres` | `ghcr.io/immich-app/postgres:14-vectorchord0.4.3-pgvectors0.2.0` | 5432 | PostgreSQL with pgvectors extension |
| `immich_redis` | `valkey/valkey:9` | 6379 | Redis-compatible cache |

ML (face recognition, smart search) is offloaded to Nobara GPU at `http://192.168.0.100:3003` (CLIP model: `nllb-clip-large-siglip__mrl`).

### Books

| Container | Image | Port | Description |
|-----------|-------|------|-------------|
| `calibre-web-automated` | `ghcr.io/new-usemame/calibre-web-nextgen` (digest-pinned) | 8085 | Calibre library with auto-import; migrated off `crocodilestick/calibre-web-automated` 2026-08-21 after upstream stopped releasing |
| `shelfmark` | `ghcr.io/calibrain/shelfmark` | 8084 | Book search and download manager, drops results into the Calibre ingest folder; added 2026-08-21 (formerly `calibre-web-automated-book-downloader`) |
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

### Static Sites

| Container | Image | Port | Description |
|-----------|-------|------|-------------|
| `portfolio` | `caddy:alpine` | 3008 | Art portfolio static site (Node build, `portfolio.lan`) |
| `topology` | `caddy:alpine` | 3009 | Interactive network topology map (Node build, `topology.lan`) |

### Management

| Container | Image | Port | Description |
|-----------|-------|------|-------------|
| `homepage` | `ghcr.io/gethomepage/homepage` | 3002 | Self-hosted dashboard |
| `uptime-kuma` | `louislam/uptime-kuma` | - | Service uptime monitoring |
| `scrutiny` | `ghcr.io/starosdev/scrutiny` | 8082 | Hard drive S.M.A.R.T. monitoring |
| `homelable-backend` | `ghcr.io/pouzor/homelable-backend` | - | Network topology backend (internal) |
| `homelable-frontend` | `ghcr.io/pouzor/homelable-frontend` | 3001 | Network diagram and live status UI |
| `homelable-mcp` | built from `/opt/homelable/mcp` | 8001 | MCP server - Claude Code integration |

### Development

| Container | Image | Port | Description |
|-----------|-------|------|-------------|
| `rails-lab-web` | built from `ruby:3.4-slim` | 3300 | Rails 8 learning sandbox (see [Rails Learning Lab](../proxmox/29_Rails_Learning_Lab.md)) |
| `rails-lab-db` | `postgres:17-alpine` | - | PostgreSQL for the Rails sandbox |

Not Komodo-managed. Manual stack at `/opt/rails-lab`, source of truth is
`/root/learning/rails/lab` on LXC 109.

## Docker Volumes

Most containers use **bind mounts** to `/mnt/storage` for persistent data.

## Open Ports

| Port | Protocol | Service |
|------|----------|---------|
| 22 | TCP | SSH |
| 2283 | TCP | Immich |
| 3000 | TCP | BentoPDF |
| 3002 | TCP | Homepage |
| 5000 | TCP | Suggestarr |
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
| 3008 | TCP | Portfolio static site |
| 3009 | TCP | Topology map static site |
| 3003 | TCP | DocuSeal |
| 3005 | TCP | Dawarich |
| 3300 | TCP | Rails learning lab |
| 8001 | TCP | Homelable MCP server |
| 9696 | TCP | Prowlarr |
| 21027 | UDP | Syncthing discovery |
| 22000 | TCP/UDP | Syncthing sync |

## Storage Layout

```
/                    → local-lvm (52 GB LVM thin volume, ~86% used)
/mnt/storage         → the pve MergerFS pool, passed in as mp0 (8.1 TB)
```

Most Docker container data (media, photos, books) lives on `/mnt/storage` to avoid filling the root disk.

**`/mnt/storage` is the only storage path that exists here.** The four member disks of the pool - `/mnt/disk1` through `/mnt/disk4` - are mounts on **pve**, not in this container; `mp0: /mnt/storage,mp=/mnt/storage` passes in the merged view alone. Writing to a `/mnt/diskN` path from inside LXC 100 therefore does not fail. It silently creates an ordinary directory on the 52 GB root filesystem, which is the trap described in Lessons Learned below.

## Komodo Integration

The `periphery.service` agent connects this host to Komodo Core (LXC 105). This allows centralized deployment and monitoring of Docker stacks without direct SSH access.

## Lessons Learned

- **`No space left on device` on a disk with 2.7 TB free (2026-08-12):** a `mv` into `/mnt/disk1/media/anime/tv/...` from inside LXC 100 filled the container's root filesystem to 100% and aborted partway through a 14 GB move. The path was chosen deliberately, to keep the operation on one member disk of the pool instead of letting MergerFS decide - which is sound reasoning on **pve**, where `/mnt/disk1` is a mounted 5.5 TB disk, and wrong here, where it is nothing at all. `mkdir -p` created a plain directory on the 52 GB rootfs and `mv` copied into it until the space ran out.

    Two things make this hard to read from the error alone. The message names a disk that genuinely has terabytes free, so the natural next step - `df -h /mnt/disk1` - is misleading unless you notice it reports the *root* filesystem. And `mv` deletes each source file only after copying it successfully, so the failure leaves the set split in two: the files that made it are on the wrong filesystem and gone from the source, while the rest are untouched. The last file attempted is a third case, partially written and present in both places at different sizes.

    Recovery is to move the rescued files onward to their real destination through `/mnt/storage`, delete the truncated one and re-copy it from the source, then remove the bogus tree. Verify the result against something outside the filesystem rather than by counting files - for a torrented set the `.torrent` metadata carries every declared length:

    ```python
    for f in info[b"files"]:
        name = f[b"path"][-1].decode()
        if os.path.getsize(os.path.join(target, name)) != f[b"length"]:
            print("MISMATCH:", name)
    ```

    The general rule: **before writing to an absolute path inside a container, confirm it is a mount and not just a name.** `findmnt /mnt/disk1` answers this in one line and says nothing when the path is an ordinary directory. A `df` of the target does too, but only if you read which filesystem it names rather than how much room it reports.
- **Homepage config source of truth (Jul 2026):** Homepage app config moved from live `/srv/docker-data/homepage/*.yaml` files into git under `compose/proxmox-lxc-100/homepage/config/`. Komodo deploy now mounts `/etc/komodo/repos/github/compose/proxmox-lxc-100/homepage/config` to `/app/config`, with logs and images kept on `/srv/docker-data/homepage/`. Any dashboard change should be made in git, committed, pushed, then deployed through Komodo.
- **Komodo repo credential hygiene:** The LXC 100 Komodo checkout currently uses a tokenized HTTPS remote. Treat that token as a secret, avoid copying it into docs or logs, and migrate to a GitHub deploy key or SSH remote when practical; rotate the old PAT afterwards.
- **LVM thin pool vs filesystem usage:** The Proxmox LVM thin pool `Data%` tracks historically allocated blocks, not current usage. Old Docker images, deleted files, and rotated logs leave "phantom" allocations until TRIM runs. In one incident LXC 100 showed 99.73% thin pool usage while `df` only showed 72% filesystem usage - `pct fstrim 100` freed 14 GB instantly and dropped it to 74%.
- **fstrim: use `pct fstrim <id>` from the Proxmox host:** Running `fstrim` inside an unprivileged LXC fails with "Operation not permitted". The correct method is `pct fstrim <vmid>` run as root on the Proxmox host. A weekly cron runs this for all LXCs automatically: `/etc/cron.weekly/lxc-fstrim`.
- **Docker image pruning is essential:** With 20+ containers, dangling images accumulate quickly. `docker image prune -f` reclaimed ~390 MB in one session. Schedule this regularly.
- **Swap is not configured:** Neither the LXC nor Docker containers have swap. A heavily memory-loaded container (e.g., postgres during Immich indexing) will be OOM-killed instead of swapping. Monitor memory headroom.
- **GPU passthrough for Jellyfin requires `dev0`/`dev1` in LXC config:** The `/dev/dri/card0` and `/dev/dri/renderD128` devices must be explicitly passed through in the Proxmox LXC config for hardware transcoding to work.
- **Huntarr security incident (Feb 2026):** Huntarr v9.4.2 was found to have critical unauthenticated API endpoints - any attacker could call every API endpoint and dump the full config including API keys for Sonarr, Radarr, Prowlarr, and other *arr apps. The developer deleted the GitHub repo and their account without any public statement. Huntarr was removed immediately. All *arr API keys were rotated after removal.
- **\*arr recycle bin and the deliberate non-use of hardlinks (Aug 2026):** Sonarr and Radarr both run with `copyUsingHardlinks: false` **on purpose**. `/mnt/storage` is a MergerFS pool with `category.create=mfs` across three branches, so a download and its library folder can land on different physical disks, where `link()` fails with `EXDEV`. A single-file `ln` test can pass and still prove nothing - it only tests the branch it happened to hit. Both apps use a recycle bin at `/recyclebin` (14 days), whose backing directory must exist on **every** branch (`/mnt/disk{1,3,4}/media/.recyclebin`) and be owned by `100000:100000`; otherwise a delete becomes a cross-disk copy, or fails with `Permission denied` because an unprivileged LXC sees a host-root directory as `nobody`. Full reasoning and the incident that produced it: [42 - Sonarr/Radarr Missing Media Audit](../proxmox/42_Sonarr_Radarr_Missing_Media_Audit.md).
- **qBittorrent's library mounts are intentional - do not "clean them up":** the qBittorrent stack mounts `/tv/hun`, `/tv/eng`, `/movies/hun`, `/movies/eng`, `/anime/tv` and `/anime/movies` alongside `/downloads`. They exist so a release the \*arr apps cannot find (typically a Hungarian dub) can be saved into the library by hand. Removing them looks like a safety improvement and breaks a working manual workflow.
- **Recommendarr removal (Mar 2026):** The Recommendarr GitHub repo (`qdread/recommendarr`) disappeared around the same time as the Huntarr incident with no explanation. Service removed as a precaution.
- **Periphery mode: outbound (since 2026-04-06):** Periphery runs in outbound mode - it initiates the connection to Core (`http://192.168.0.105:9120`) and reconnects automatically if the connection drops. Config: `core_addresses = ["http://192.168.0.105:9120"]`, `connect_as = "LXC 100"`. If unreachable after a network outage, `systemctl restart periphery` still works as a manual fix.
- **Homelable healthcheck OOM/I/O incident (Apr 2026):** The homelable-backend healthcheck used `curl` which is not present in the container image. This caused a failed healthcheck every 10 seconds, generating continuous dockerd log writes to the LXC 100 thin pool. After several hours this saturated the disk I/O (Netdata: `disk_backlog` WARNING on `pve-vm--100--disk--0`, CPU iowait, load average), causing the entire LXC 100 to become unresponsive. Fix: replaced `curl` with `python3 -c "import urllib.request; urllib.request.urlopen(...)"` (Python is available in the image) and raised the interval from 10s to 30s. Lesson: always verify that the healthcheck binary exists in the target container image before deploying.
