# Raspberry Pi 4 - Origin Homelab

**Status:** Retired (December 2025 - replaced by HP EliteDesk 800 G4 + Proxmox)

## Overview

| Property | Value |
|----------|-------|
| Device | Raspberry Pi 4 Model B |
| RAM | 4 GB |
| OS | Raspberry Pi OS Lite 64-bit, later DietPi |
| IP Address | 192.168.0.102 (static) |
| Active | August 2024 - December 2025 |
| Purpose | All-in-one home server: media, DNS, monitoring, sync |

## Hardware

| Component | Detail |
|-----------|--------|
| Board | Raspberry Pi 4 Model B (4 GB) |
| Boot drive | USB SSD (OS + Docker volumes) |
| Storage | 2x USB HDD merged via MergerFS |
| Power | Powered USB hub (stable HDD power delivery) |
| Network | Gigabit Ethernet to TP-Link Archer C6 |

## Storage

Two external HDDs were combined into a single unified volume using **MergerFS**:

```
/mnt/hdd1    - USB HDD 1
/mnt/hdd2    - USB HDD 2
/mnt/merged  - MergerFS union mount (used by all services)
```

Network shares were exposed via **Samba (SMB)** for Windows and cross-device access.

This MergerFS setup was later carried over to the Proxmox migration and is still in use today (scaled to 4 HDDs, 8.1 TB usable).

## Services

All services ran as Docker Compose stacks. Management was handled via Portainer and Dockge.

### Media

| Service | Description |
|---------|-------------|
| Jellyfin | Media server |
| Plex | Media server (ran alongside Jellyfin during testing) |
| Sonarr | TV show automation |
| Radarr | Movie automation |
| Prowlarr | Indexer management |
| Overseerr | Media request management |
| Bazarr | Subtitle management |
| qBittorrent | Torrent client |
| Tautulli | Plex statistics |
| Readarr | Book automation |

### Network and DNS

| Service | Description |
|---------|-------------|
| AdGuard Home | DNS-level ad blocking and filtering |
| Tailscale | Secure remote access (replaced Cloudflare Tunnel) |
| Nginx Proxy Manager | Reverse proxy (installed, not actively configured) |

### Monitoring and Management

| Service | Description |
|---------|-------------|
| Uptime Kuma | Service uptime monitoring |
| Scrutiny | HDD S.M.A.R.T. health monitoring |
| Dozzle | Real-time Docker log viewer |
| Watchtower | Automatic container image updates |
| Portainer | Container management UI |
| Dockge | Docker Compose stack manager |
| Homepage | Self-hosted dashboard |

### Sync and Books

| Service | Description |
|---------|-------------|
| Syncthing | Cross-device file synchronization |
| Calibre-Web (automated) | E-book library management |

## Automation

- **Watchtower** handled automatic Docker image updates on a schedule
- **Cron** ran a bare-metal backup script every 14 days
- Ansible and Semaphore were installed on the desktop PC for automation experiments but never actively integrated with the Pi

## Networking

- Static IP: `192.168.0.102`
- Remote access: Tailscale (replaced Cloudflare Tunnel - simpler, no open ports)
- AdGuard Home handled LAN-wide DNS filtering (later moved to its own dedicated LXC on Proxmox)

## Backup

Backups ran via a custom bash script on a 14-day cron schedule. The script used `rsync` to back up Docker volumes and the home directory to a second HDD (`/mnt/hdd2/backup`), keeping the last 2 snapshots.

Key design decisions:
- **Containers with databases were stopped before backup** - ensures consistent state (no partial DB writes)
- **`trap cleanup EXIT`** - if the script failed mid-run, containers were automatically restarted
- **`sync` + cache drop** - filesystem cache flushed before and after for clean state on a memory-constrained device
- **`set -euo pipefail`** - script aborts on any error, unset variable, or pipe failure

```bash
#!/bin/bash
set -euo pipefail
export PATH=/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin

# === CONFIG ===
BACKUP_BASE="/mnt/hdd2/backup"
DATE=$(date +%Y-%m-%d)
BACKUP_DIR="$BACKUP_BASE/$DATE"
LOG_FILE="$BACKUP_DIR/backup.log"

# Containers with databases to stop
DB_CONTAINERS=("radarr" "sonarr" "jellyfin" "calibre-web-automated" "prowlarr" "bazarr" "qbittorrent")

# === LOGGING ===
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# === CLEANUP ON EXIT ===
cleanup() {
    if [ $? -ne 0 ]; then
        log "ERROR: Script failed, starting all containers..."
        for c in "${DB_CONTAINERS[@]}"; do
            docker start "$c" 2>/dev/null || true
        done
    fi
}
trap cleanup EXIT

mkdir -p "$BACKUP_DIR"

# === STOP DATABASE CONTAINERS ===
log "=== Stopping database containers ==="
for c in "${DB_CONTAINERS[@]}"; do
    if docker ps -q -f name="^${c}$" | grep -q .; then
        docker stop "$c" || log "WARNING: Failed to stop $c"
    fi
done
sleep 5
sync

# === BACKUPS ===
rsync -aAXHv --delete --stats /srv/docker/ "$BACKUP_DIR/docker/" >> "$BACKUP_DIR/rsync_docker.log" 2>&1
rsync -aAXHv --delete --stats /home/nex/  "$BACKUP_DIR/nex_home/" >> "$BACKUP_DIR/rsync_home.log" 2>&1

# === CLEAR SYSTEM CACHE ===
sync
echo 3 > /proc/sys/vm/drop_caches

# === START DATABASE CONTAINERS ===
for c in "${DB_CONTAINERS[@]}"; do
    docker start "$c" || log "WARNING: Failed to start $c"
done
sleep 10

# === DOCKER CLEANUP ===
docker image prune -a -f
docker volume prune -f
docker network prune -f

# === CLEANUP OLD BACKUPS (keep last 2) ===
cd "$BACKUP_BASE"
ls -1t | tail -n +3 | xargs -r rm -rf
```

This approach (rsync + manual container lifecycle) was replaced by **Restic** on Proxmox, which provides deduplication, encryption, and cloud offload to Backblaze B2 without requiring service downtime.

## Why I Migrated to Proxmox

By late 2025 the Pi was running at its limits - 4 GB RAM with 20+ containers, no hardware transcoding, all services on a single OS with no isolation. The main pain points:

- **No hardware transcoding** - Jellyfin ran software-only on the Pi's CPU, causing buffering on high-bitrate content
- **Resource contention** - all services competed for the same 4 GB RAM with no isolation
- **Single point of failure** - one bad container update or config change could affect every service
- **USB storage reliability** - HDDs on a powered hub occasionally had mount issues that required manual recovery
- **Limited upgrade path** - adding more RAM or storage to a Pi 4 is not possible

In December 2025, the Pi was replaced by an **HP EliteDesk 800 G4** (Intel i5-8400, 32 GB RAM) running **Proxmox VE 9.1**. Every service migrated to dedicated LXC containers, gaining proper isolation, GPU passthrough for Jellyfin, and reliable ZFS-backed storage.

The Pi itself was the proof of concept. Everything learned there - MergerFS, the arr stack, AdGuard, Tailscale - was carried forward to the current setup.

## Lessons Learned

- **MergerFS is the right tool for multi-HDD pooling without RAID** - simple, reliable, still in use at larger scale
- **Tailscale beats Cloudflare Tunnel for private access** - no open ports, works transparently, zero config
- **Watchtower is risky in production** - automatic updates caused at least one broken stack; replaced with manual updates via Komodo in the Proxmox era
- **USB HDDs need a powered hub** - bus-powered drives on a Pi cause random disconnects under load
- **Overseer/Jellyfin without hardware transcoding is painful** - transcoding on Pi 4 CPU maxed it out at 1 stream
- **Port mapping gets unmanageable fast** - 20+ services with manually tracked ports pushed me toward a reverse proxy; this was solved properly with Pangolin on the VPS in the Proxmox era
