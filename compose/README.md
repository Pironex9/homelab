# Docker Compose Configurations

This directory contains all Docker Compose stack definitions for the homelab infrastructure.

## Structure

### proxmox-lxc-100/
Production services running on LXC 100 (docker-host):
- Media services (Jellyfin, Radarr, Sonarr, Prowlarr, qBittorrent, Seerr, Huntarr)
- Photo & library management (Immich, Calibre-Web-Automated)
- Productivity (FreshRSS, Syncthing, BentoPDF)
- Management & monitoring (Dockge, Dozzle, Homepage, Uptime Kuma, Scrutiny)
- Notifications & automation (Notifiarr, SuggestArr + Recommendarr)

### nobara/
Desktop services running on Nobara workstation:
- AI tools (Open WebUI + AnythingLLM)
- Ollama with GPU acceleration (not 24/7 — used for heavy inference tasks)
- Note: A second Ollama instance runs on LXC 108 (always on, CPU, integrated with n8n for light tasks)

## Usage

Each service directory contains:
- `docker-compose.yml` or `compose.yaml` - Main configuration
- `.env.example` - Environment variables template
- `.env` - Your local secrets (gitignored, never committed)

### Deployment

```bash
# Single service
cd proxmox-lxc-100/jellyfin
docker compose up -d

# Update all services on a host
cd proxmox-lxc-100
for dir in */; do
  (cd "$dir" && docker compose pull && docker compose up -d)
done
```

### Management

Services are managed via Komodo UI for:
- Centralized deployment
- Health monitoring
- Log aggregation
- Update management

See [Komodo documentation](../docs/proxmox/17_Komodo_complete_setup.md) for details.

## Standards

### Naming Conventions
- Directory names: lowercase, hyphenated (e.g., `uptime-kuma`)
- Container names: match directory name when possible
- Network names: `{service}_default` (auto-created)

### Environment Variables
All services use:
- `.env` file for secrets (gitignored)
- `.env.example` committed to repo as template
- Consistent variable naming:
  - `PUID=0` / `PGID=0` for user/group IDs
  - `TZ=Europe/Budapest` for timezone
  - `DOCKER_DATA=/srv/docker-data` for config root
  - `MEDIA_ROOT=/mnt/storage/media` for media library

### Volume Mounts
Standard paths:
- Config: `/srv/docker-data/{service}/`
- Media: `/mnt/storage/media/`
- Downloads: `/mnt/storage/media/downloads/`

## Adding New Services

1. Create service directory under appropriate host folder
2. Add `docker-compose.yml` and `.env.example`
3. Test deployment locally
4. Import to Komodo (if applicable)
5. Update this README

## Security Notes

- Never commit `.env` files with real secrets
- Use `.env.example` with placeholder values
- Rotate secrets regularly
- Review exposed ports before deployment
- Use Tailscale/VPN for remote access when possible

## Backup

All service configurations are backed up:
- Git repository (compose files)
- Docker volume backups (data)
- Automated with restic (see `../scripts/backup.sh`)

## Troubleshooting

Common issues:

**Service won't start:**
```bash
# Check logs
docker compose logs -f service_name

# Verify environment variables
docker compose config

# Check port conflicts
ss -tuln | grep PORT
```

**Permission issues:**
```bash
# Fix ownership
sudo chown -R 0:0 /srv/docker-data/service_name
```

**Network issues:**
```bash
# Recreate network
docker compose down
docker network prune
docker compose up -d
```

## Related Documentation

- [Komodo Setup](../docs/proxmox/17_Komodo_complete_setup.md)
- [Storage Configuration](../docs/proxmox/1_Proxmox_VE_9.1_MergerFS_SnapRAID_Installation_Documentation.md)
- [Backup Procedures](../docs/proxmox/16_Proxmox_Backup_System_Documentation.md)
