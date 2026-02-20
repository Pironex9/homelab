# Docker Compose Configurations

## Structure

### proxmox-lxc-100/
Services running on LXC 100 (docker-host):
- Media: Jellyfin, Radarr, Sonarr, Prowlarr, qBittorrent, Seerr, Huntarr
- Photos & library: Immich, Calibre-Web-Automated
- Productivity: FreshRSS, Syncthing, BentoPDF
- Monitoring & management: Dockge, Dozzle, Homepage, Uptime Kuma, Scrutiny
- Notifications: Notifiarr, SuggestArr + Recommendarr

### nobara/
Desktop services on Nobara workstation:
- Open WebUI + AnythingLLM
- Ollama with GPU acceleration (not 24/7 — for heavy inference)
- Note: A second Ollama instance runs on LXC 108 (always on, CPU, integrated with n8n)

## Conventions

- Directory names: lowercase, hyphenated (e.g. `uptime-kuma`)
- Container names: match directory name
- `.env` for secrets (gitignored), `.env.example` committed as template

### Standard env variables
```bash
PUID=0
PGID=0
TZ=Europe/Budapest
DOCKER_DATA=/srv/docker-data
MEDIA_ROOT=/mnt/storage/media
```

### Standard volume paths
- Config: `/srv/docker-data/{service}/`
- Media: `/mnt/storage/media/`
- Downloads: `/mnt/storage/media/downloads/`

## Deployment

```bash
# Single service
cd proxmox-lxc-100/jellyfin
docker compose up -d

# Update all
cd proxmox-lxc-100
for dir in */; do
  (cd "$dir" && docker compose pull && docker compose up -d)
done
```

Services are managed via [Komodo](../docs/proxmox/17_Komodo_complete_setup.md).

## Troubleshooting

```bash
# Check logs
docker compose logs -f service_name

# Verify env vars
docker compose config

# Port conflicts
ss -tuln | grep PORT

# Permission issues
chown -R 0:0 /srv/docker-data/service_name

# Network issues
docker compose down && docker network prune && docker compose up -d
```

## Related Documentation

- [Komodo Setup](../docs/proxmox/17_Komodo_complete_setup.md)
- [Storage Configuration](../docs/proxmox/01_Proxmox_VE_9.1_MergerFS_SnapRAID_Installation_Documentation.md)
- [Backup Procedures](../docs/proxmox/16_Proxmox_Backup_System_Documentation.md)
