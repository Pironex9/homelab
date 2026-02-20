# LXC 100 Services

Docker host running production services.

## Infrastructure

- **LXC ID**: 100
- **OS**: Ubuntu 22.04 LTS
- **Hostname**: docker-host
- **IP**: 192.168.0.YOUR_DOCKER_IP
- **Resources**: 8 CPU cores, 16GB RAM, 48GB disk

## Services

### Media Stack
- **jellyfin** - Media server (port 8096)
- **radarr** - Movie management (port 7878)
- **sonarr** - TV show management (port 8989)
- **prowlarr** - Indexer manager (port 9696)
- **qbittorrent** - Torrent client (port 8080)
- **seerr** - Media request management (port 5055)
- **huntarr** - Media hunting automation (port 9705)

### Photos & Library
- **immich** - Photo & video management (port 2283)
- **calibre-web-automated** - eBook library (port 8083)

### Productivity & Utilities
- **freshrss** - RSS reader (port 80)
- **syncthing** - File synchronization (port 8384)
- **bentopdf** - PDF tools (port 3000)
- **homepage** - Service dashboard (port 3002)

### Monitoring & Management
- **dockge** - Docker stack manager (port 5001)
- **dozzle** - Log viewer (port 8888)
- **uptime-kuma** - Uptime monitoring (port 3001)
- **scrutiny** - Disk health monitoring (port 8082)

### Automation & Notifications
- **notifiarr** - Notification hub (port 5454)
- **suggestarr-recommendarr** - AI media suggestions (port 3003)

## Management

Services are managed via [Komodo](../../docs/proxmox/17_Komodo_complete_setup.md).

```bash
# On Proxmox host
pct enter 100

# View running services
docker ps

# View compose projects
docker compose ls
```

## Networking

All services use bridge network with port mappings.
Access via Pangolin reverse proxy, Tailscale VPN, or directly via IP:PORT.

## Storage Mounts

- `/srv/docker-data/` - Service configurations
- `/srv/docker-compose/` - Compose files
- `/mnt/storage/media/` - Media library (NFS from storage server)
- `/mnt/storage/media/downloads/` - Downloads (NFS)

## Updates

Services are updated via Komodo UI or manually:

```bash
cd /srv/docker-compose/{service}
docker compose pull
docker compose up -d
```

## Backup

- Config: Git repository + daily snapshots
- Data: Restic to NFS + cloud storage
- LXC: Proxmox vzdump snapshots (weekly)
