**Date:** 2026-03-14
**Author:** Norbert Csicsay
**GitHub:** [Pironex9/homelab](https://github.com/Pironex9/homelab)

---

# Homelab Infrastructure

Self-hosted infrastructure running 27 services on Proxmox VE. Built from scratch to learn Linux, networking, and DevOps practices.

## Tech Stack

| Category | Tools |
|----------|-------|
| Hypervisor | Proxmox VE 9.1 |
| Containers | Docker, LXC |
| Management | Komodo |
| Storage | MergerFS + SnapRAID (8.1TB) |
| Backup | Restic (local, NFS, Backblaze B2) |
| Reverse Proxy | Pangolin (self-hosted tunnel) |
| VPN | Tailscale |
| DNS | AdGuard Home |
| Monitoring | Scrutiny, Uptime Kuma, Dozzle |

## Architecture

```
Proxmox VE 9.1 (HP EliteDesk 800 G4)
├── LXC 100  docker-host     192.168.0.110   18 Docker Compose stacks
├── VM  101  haos             192.168.0.202   Home Assistant OS
├── LXC 102  adguard         192.168.0.111   AdGuard Home + Tailscale DNS
├── LXC 103  vaultwarden     -               Vaultwarden
├── LXC 104  scanopy         -               Scanopy
├── LXC 105  komodo          192.168.0.105   Komodo GitOps management
├── LXC 106  karakeep        192.168.0.128   Karakeep bookmarking + AI tagging
├── LXC 107  n8n             192.168.0.112   n8n workflow automation
├── LXC 108  ollama          192.168.0.231   Ollama local LLM inference
└── LXC 109  claude-mgmt     192.168.0.204   Claude Code management node
```

## Docker Services (LXC 100)

18 active stacks: bentopdf, calibre-web-automated, dockge, dozzle, docuseal, freshrss, homepage, immich, jellyfin, notifiarr, prowlarr, qbittorrent, radarr, scrutiny, seerr, sonarr, suggestarr, syncthing, uptime-kuma

## Featured Projects

### Komodo GitOps Migration
Migrated 20 Docker Compose stacks from Dockge to Komodo with zero downtime. All stacks now version-controlled in Git; Komodo pulls and deploys from the repo.

[Full Documentation](proxmox/17_Komodo_complete_setup.md)

### Resilient Storage
Pooled 4 USB HDDs into a single MergerFS volume with SnapRAID parity. Can survive 1 disk failure with no data loss. Automated sync via systemd timers.

[Storage Setup Guide](proxmox/01_Proxmox_VE_9.1_MergerFS_SnapRAID_Installation_Documentation.md)

### Self-hosted Tunnel (Pangolin)
Public access to self-hosted services via Pangolin on a Hetzner VPS - no Cloudflare dependency, no port forwarding.

[VPS + Pangolin Guide](vps/Hetzner_VPS_+_Pangolin_+_Jellyfin_Complete_Setup_Guide.md)

### Backup System
Restic backups to local disk, NFS share, and Backblaze B2. Automated via shell script + systemd timers. Multiple retention policies.

[Backup System Documentation](proxmox/16_Proxmox_Backup_System_Documentation.md)

## Navigation

- **Hosts** - Current configuration, running services, and notes for each LXC/VM
- **Setup Guides** - Chronological guides documenting how the homelab was built
- **VPS** - Hetzner VPS and Pangolin reverse proxy setup

## Contact

- **LinkedIn**: [Norbert Csicsay](https://www.linkedin.com/in/norbert-csicsay-497195334)
- **GitHub**: [Pironex9](https://github.com/Pironex9)
