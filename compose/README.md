# Docker Compose Configurations

## Structure

One directory per host, one directory per stack under it. 32 Compose Stacks in
total, counted the way `CONTEXT.md` defines the unit: a directory holding a
compose file, in any of its three spellings. `compose/vps/landing/build.sh`
derives the number the same way and prints it on the public landing page, so a
stack added here moves that figure on the next build.

### proxmox-lxc-100/ (24)
Services on LXC 100 (docker-host), the main Docker host:
- Media: Jellyfin, Radarr, Sonarr, Prowlarr, qBittorrent, Seerr, SuggestArr
- Books & photos: Immich, Calibre-Web-Automated, Shelfmark
- Productivity: FreshRSS, Syncthing, BentoPDF, DocuSeal, Form, Kan, Dawarich
- Sites: Homepage, Portfolio, Homelable, Topology
- Storage & monitoring: Garage (S3, the Longhorn backup target), Scrutiny
- Notifications: Notifiarr

`uptime-kuma/` under this host is a leftover holding only a gitignored `.env`;
Kuma itself moved to the VPS. It has no compose file, so it is not a Compose
Stack and `build.sh` deliberately does not count it.

One more stack runs on this host without living here: `rails-lab`, at
`/opt/rails-lab` on LXC 100. That is deliberate and documented in
[29 - Rails Learning Lab](../docs/proxmox/29_Rails_Learning_Lab.md) - a
throwaway sandbox with no proxy, no backups and no Komodo management.

### proxmox-lxc-106/ (1)
Karakeep on LXC 106, migrated off a community-script source install on
2026-08-13. AI tagging runs on Gemini, not a local Ollama.

### proxmox-lxc-109/ (1)
code-server on claude-mgmt (LXC 109), reachable over Tailscale only.

### vps/ (3)
Hetzner VPS: Pangolin (the public reverse proxy), Uptime Kuma, and the
`landing` static site behind it.

### nobara/ (3)
GPU services on the Nobara workstation, not 24/7: `codeformer`, `deoldify` and
`immich-ml`, which serves Immich's machine learning back to LXC 100.

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

Services are managed via [Komodo](../docs/proxmox/16_Komodo_complete_setup.md).

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

- [Komodo Setup](../docs/proxmox/16_Komodo_complete_setup.md)
- [Storage Configuration](../docs/proxmox/01_Proxmox_VE_9.1_MergerFS_SnapRAID_Installation_Documentation.md)
- [Backup Procedures](../docs/proxmox/15_Proxmox_Backup_System_Documentation.md)
