# LXC 100 — docker-host

- **OS**: Ubuntu 22.04 LTS
- **Resources**: 8 CPU cores, 16GB RAM, 48GB disk
- **Management**: [Komodo](../../docs/proxmox/17_Komodo_complete_setup.md)

## Services

### Media
| Service | Description | Port |
|---------|-------------|------|
| jellyfin | Media server | 8096 |
| radarr | Movie management | 7878 |
| sonarr | TV show management | 8989 |
| prowlarr | Indexer manager | 9696 |
| qbittorrent | Torrent client | 8080 |
| seerr | Media requests | 5055 |
| huntarr | Media hunting automation | 9705 |

### Photos & Library
| Service | Description | Port |
|---------|-------------|------|
| immich | Photo & video management | 2283 |
| calibre-web-automated | eBook library | 8083 |

### Productivity & Utilities
| Service | Description | Port |
|---------|-------------|------|
| freshrss | RSS reader | 80 |
| syncthing | File synchronization | 8384 |
| bentopdf | PDF tools | 3000 |
| homepage | Service dashboard | 3002 |

### Monitoring & Management
| Service | Description | Port |
|---------|-------------|------|
| dockge | Docker stack manager | 5001 |
| dozzle | Log viewer | 8888 |
| uptime-kuma | Uptime monitoring | 3001 |
| scrutiny | Disk health (SMART) | 8082 |

### Automation & Notifications
| Service | Description | Port |
|---------|-------------|------|
| notifiarr | Notification hub | 5454 |
| suggestarr-recommendarr | AI media suggestions | 3003 |

## Storage Mounts

- `/srv/docker-data/` — service configs
- `/srv/docker-compose/` — compose files
- `/mnt/storage/media/` — media library (MergerFS)
- `/mnt/storage/media/downloads/` — downloads

## Access

```bash
# Enter LXC from Proxmox host
pct enter 100

# View running services
docker ps
docker compose ls
```

## Backup

- Configs: Git + daily snapshots
- Data: Restic → NFS + cloud
- LXC: Proxmox vzdump (weekly)
