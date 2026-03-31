# Homelab Infrastructure

[![Infrastructure](https://img.shields.io/badge/Infrastructure-Proxmox-orange)](https://www.proxmox.com/)
[![Containers](https://img.shields.io/badge/Containers-Docker-blue)](https://www.docker.com/)
[![Management](https://img.shields.io/badge/Management-Komodo-green)](https://komo.do/)
[![Status](https://img.shields.io/badge/Status-Production-success)]()

Self-hosted infrastructure running 18 Docker stacks + 11 LXC/VMs on Proxmox VE. Built from scratch to learn Linux, networking, and DevOps practices.

## 🛠️ Tech Stack

| Category | Tools |
|----------|-------|
| Hypervisor | Proxmox VE 9.1 |
| Containers | Docker, LXC |
| Management | Komodo |
| Storage | MergerFS + SnapRAID (8.1TB) |
| Backup | Restic (local disk + NFS to Nobara PC) |
| Reverse Proxy | Pangolin (public), Caddy (local .lan HTTPS) |
| VPN | Tailscale |
| DNS | AdGuard Home |
| Monitoring | Scrutiny, Uptime Kuma, Netdata |

## 🏗️ Architecture

```
Proxmox VE 9.1 (HP EliteDesk 800 G4, i5-8400, 32GB RAM)
├── LXC 100  docker-host     192.168.0.110   18 Docker Compose stacks
├── VM  101  haos            192.168.0.202   Home Assistant OS
├── LXC 102  adguard         192.168.0.111   AdGuard Home + Tailscale DNS
├── LXC 103  vaultwarden     -               Vaultwarden password manager
├── LXC 105  komodo          192.168.0.105   Komodo GitOps management
├── LXC 106  karakeep        192.168.0.128   Karakeep bookmarking + AI tagging
├── LXC 107  n8n             192.168.0.112   n8n workflow automation
├── LXC 108  ollama          192.168.0.231   Ollama local LLM (CPU, always on)
├── LXC 109  claude-mgmt     192.168.0.204   Claude Code management node
├── LXC 110  caddy           192.168.0.208   Caddy reverse proxy + mkcert local CA
└── Storage
    ├── MergerFS pool   8.1TB usable (2x internal HDD + 2x USB HDD)
    └── SnapRAID        1 parity drive, automated sync + scrub

Nobara PC (192.168.0.100)
└── Open WebUI + AnythingLLM + Ollama (GPU, not 24/7)

Hetzner VPS (FSN1)
├── Pangolin reverse proxy  (public access)
└── Traefik + WireGuard tunnel to homelab

K3s Cluster (192.168.2.x)
├── opt5060-i5    192.168.2.101  master
├── opt3060-i3    192.168.2.102  worker
├── opt3050-i5    192.168.2.103  worker
└── orangepione   192.168.2.100  WoL server + Tailscale exit node
```

## 📸 Dashboard

![Homepage Dashboard](./assets/dashboard.png)

## 🚀 Featured Projects

### Automated Docker Stack Migration
Migrated 20 Docker Compose stacks from Dockge to Komodo with zero downtime. Built an automated import workflow (Docker → TOML → Komodo) for centralized management and Git-based version control of all stack configs.

📖 [Full Documentation →](./docs/proxmox/16_Komodo_complete_setup.md)

### Resilient Storage Architecture
Pooled 4 disks into a single MergerFS volume with SnapRAID parity protection. Automated sync and scrub via systemd timers. Can survive 1 disk failure with no data loss.

📖 [Storage Setup Guide →](./docs/proxmox/01_Proxmox_VE_9.1_MergerFS_SnapRAID_Installation_Documentation.md)

### Infrastructure as Code
All services version-controlled as Docker Compose files. Secrets in gitignored `.env` files, templates committed as `.env.example`. Full infrastructure rebuild in under 2 hours.

📖 [Compose Files →](./compose/)

## 📚 Documentation

**Host reference** (current config, services, lessons learned):
- [docker-host](./docs/hosts/docker-host.md) · [adguard](./docs/hosts/adguard.md) · [komodo](./docs/hosts/komodo.md) · [karakeep](./docs/hosts/karakeep.md) · [n8n](./docs/hosts/n8n.md) · [ollama](./docs/hosts/ollama.md) · [haos](./docs/hosts/haos.md) · [claude-mgmt](./docs/hosts/claude-mgmt.md) · [caddy](./docs/hosts/caddy.md) · [k3s-cluster](./docs/hosts/k3s-cluster.md)

**Setup guides** (how it was built):
- [Proxmox Initial Setup + Storage](./docs/proxmox/01_Proxmox_VE_9.1_MergerFS_SnapRAID_Installation_Documentation.md)
- [LXC & Docker Setup](./docs/proxmox/02_Proxmox_Docker_LXC_Setup_-_Detailed_Process.md)
- [Komodo Installation & Configuration](./docs/proxmox/16_Komodo_complete_setup.md)
- [Backup System](./docs/proxmox/15_Proxmox_Backup_System_Documentation.md)
- [VPS + Pangolin Reverse Proxy](./docs/vps/01_Hetzner_VPS_Pangolin_Jellyfin_Setup.md)
- [Security Configuration](./docs/vps/02_Security_Configuration_Guide.md)
- [Immich Photo Management](./docs/proxmox/06_Immich_Setup_Full_Installation_Guide.md)
- [Jellyfin Hardware Transcoding](./docs/proxmox/11_Jellyfin_Hardware_Transcoding_Setup.md)
- [AdGuard Home + Tailscale DNS](./docs/proxmox/05_AdGuard_Home_Setup_Dedicated_LXC_Tailscale_DNS_Integration.md)
- [Karakeep, n8n, Ollama LXCs](./docs/proxmox/10_Helper_Script_LXCs.md)

## 🛣️ Roadmap

- [x] Migrate Docker stack management to Komodo GitOps
- [x] K3s Kubernetes cluster (3x Dell OptiPlex)
- [ ] Longhorn storage for K3s
- [ ] Prometheus + Grafana monitoring for K3s
- [ ] ArgoCD GitOps for K3s workloads
- [ ] Add Ansible for configuration management

## 📬 Contact

- **LinkedIn**: [Norbert Csicsay](https://www.linkedin.com/in/norbert-csicsay-497195334)
- **GitHub**: [Pironex9](https://github.com/Pironex9)

---

<sub>Last updated: March 2026 | Infrastructure: Proxmox VE 9.1 | Services: 18 Docker stacks + 11 LXC/VM + K3s cluster</sub>
