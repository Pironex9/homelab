# 🏗️ Production-Grade Homelab Infrastructure

[![Infrastructure](https://img.shields.io/badge/Infrastructure-Proxmox-orange)](https://www.proxmox.com/)
[![Containers](https://img.shields.io/badge/Containers-Docker-blue)](https://www.docker.com/)
[![Management](https://img.shields.io/badge/Management-Komodo-green)](https://komo.do/)
[![Status](https://img.shields.io/badge/Status-Production-success)]()

> Self-hosted infrastructure with 21 services across Proxmox virtualization platform. Focus on automation, Infrastructure as Code, and containerization.

## 🎯 Overview

This repository documents my production homelab environment, showcasing skills in:
- **Virtualization & Containerization**: Proxmox VE, LXC, Docker
- **Infrastructure Management**: Komodo, automated deployments, monitoring
- **Storage Engineering**: MergerFS + SnapRAID with 10.5TB capacity
- **Network Architecture**: Reverse proxy, VPN, secure remote access
- **Automation**: IaC principles, scripted backups

## 🛠️ Tech Stack

### Infrastructure
- **Hypervisor**: Proxmox VE 9.1
- **Containers**: Docker, LXC
- **Management**: Komodo

### Storage
- **File System**: MergerFS (10.5TB pooled storage)
- **Parity**: SnapRAID (single parity protection)
- **Backup**: Restic (encrypted, deduplicated)

### Networking
- **Reverse Proxy**: Pangolin (self-hosted Cloudflare Tunnel alternative)
- **VPN**: Tailscale, WireGuard
- **DNS**: AdGuard Home

### Monitoring & Observability
- **Health**: Scrutiny (disk SMART), Uptime Kuma
- **Logs**: Dozzle (centralized Docker logs)
- **Metrics**: Netdata

## 📊 Key Metrics

- **Services**: 21 Docker Compose stacks
- **Hosts**: 2 LXC containers + 1 desktop
- **Storage**: 10.5TB usable (MergerFS + SnapRAID)
- **Uptime**: 99.9% (last 90 days)
- **Backups**: Automated to 3 locations (local, NFS, cloud)

## 🏗️ Architecture

```
Proxmox VE 9.1
├── LXC 105 (Komodo Core)
├── LXC 100 (Docker Host)
│   └── 20 Docker Compose stacks
└── Storage Server
    └── MergerFS + SnapRAID

Nobara PC
└── Desktop services (Open WebUI, AnythingLLM)

K3s Cluster (Planned)
└── 3x Dell OptiPlex nodes (5060, 3060, 3050)
```

## 🚀 Featured Projects

### 1. Automated Docker Stack Migration
**Challenge**: Managing 20 Docker Compose stacks across multiple hosts without unified control

**Solution**:
- Implemented Komodo with systemd periphery for centralized management
- Created automated import workflow (Docker → TOML → Komodo)
- Migrated from Dockge to Komodo with zero downtime

**Tech**: Docker, systemd, TOML, bash scripting, Python

**Outcome**:
- Single-pane-of-glass management for all services
- Git-based version control for all stack configurations
- Automated health monitoring and alerting

📖 [Full Documentation →](./docs/komodo/komodo-complete-setup.md)

---

### 2. Resilient Storage Architecture
**Challenge**: Protect 10.5TB media library from disk failures without expensive RAID hardware

**Solution**:
- Implemented MergerFS for pooled storage across 4 disks
- Added SnapRAID for single-parity protection
- Automated scrub and sync scheduling

**Tech**: MergerFS, SnapRAID, bash, systemd timers

**Outcome**:
- Can survive 1 disk failure
- Flexible expansion (add disks as needed)
- <1% storage overhead vs traditional RAID

📖 [Storage Setup Guide →](./docs/proxmox/1_Proxmox_VE_9.1_MergerFS_SnapRAID_Installation_Documentation.md)

---

### 3. Infrastructure as Code
**Challenge**: Reproducible infrastructure setup across multiple reinstalls

**Solution**:
- All services defined in version-controlled Docker Compose files
- Documented setup procedures for every service
- Secrets managed via `.env` files (gitignored), templates committed as `.env.example`

**Tech**: Docker Compose, bash, git, markdown

**Outcome**:
- Full infrastructure rebuild in <2 hours
- Git history tracks all configuration changes
- Easy rollback to previous working states

📖 [Compose Files →](./compose/)

---

## 📂 Repository Structure

```
homelab/
├── compose/              # Docker Compose configurations
│   ├── proxmox-lxc-100/ # Main Docker host services (20 stacks)
│   └── nobara/          # Desktop services
├── docs/                # Complete setup documentation
│   ├── proxmox/         # Virtualization & service guides
│   ├── komodo/          # Management platform
│   └── vps/             # VPS & reverse proxy setup
└── scripts/             # Automation scripts
    └── backup.sh
```

## 🔗 Live Services

| Service | Description | Access |
|---------|-------------|--------|
| Homepage | Service dashboard | Local / Tailscale |
| Uptime Kuma | Status monitoring | Local / Tailscale |
| Jellyfin | Media server | Local / Pangolin |
| Vaultwarden | Password manager | Local / Tailscale |

> Note: Services accessible via Tailscale VPN, local network, or Pangolin reverse proxy

## 📚 Documentation

### Setup Guides
- [Proxmox Initial Setup + Storage](./docs/proxmox/1_Proxmox_VE_9.1_MergerFS_SnapRAID_Installation_Documentation.md)
- [LXC & Docker Setup](./docs/proxmox/2_Proxmox_Docker_LXC_Setup_-_Detailed_Process.md)
- [Komodo Installation & Configuration](./docs/komodo/komodo-complete-setup.md)
- [Backup System](./docs/proxmox/16_Proxmox_Backup_System_Documentation.md)
- [VPS + Pangolin Reverse Proxy](./docs/vps/10_Hetzner_VPS_+_Pangolin_+_Jellyfin_Complete_Setup_Guide.md)
- [Security Configuration](./docs/proxmox/12_Security_Configuration_Guide.md)

### Service Guides
- [Immich Photo Management](./docs/proxmox/6_Immich_Setup_Full_Installation_Guide.md)
- [Jellyfin Hardware Transcoding](./docs/proxmox/11_Jellyfin_Hardware_Transcoding_Setup.md)
- [AdGuard Home + Tailscale DNS](./docs/proxmox/5_AdGuard_Home_Setup_Dedicated_LXC_Tailscale_DNS_Integration.md)
- [Scrutiny Disk Health](./docs/proxmox/7_Scrutiny_Disk_Health_Monitoring_Setup_Guide.md)
- [NFS Storage](./docs/proxmox/15_NFS-Setup_Documentation.md)

## 🎓 Skills Demonstrated

**System Administration**
- Linux system administration (Ubuntu, Debian)
- LXC containerization and resource management
- Storage management and data protection strategies

**DevOps & Automation**
- Docker and Docker Compose orchestration
- Infrastructure as Code principles
- Centralized stack management with Komodo

**Networking**
- Reverse proxy and SSL certificate management
- VPN setup and secure remote access (Tailscale, WireGuard)
- Self-hosted tunnel with Pangolin

**Monitoring & Observability**
- Health monitoring and alerting setup
- Log aggregation and analysis
- Disk health and SMART monitoring

## 🛣️ Roadmap

- [ ] Migrate select services to K3s Kubernetes cluster
- [ ] Implement GitOps workflow with ArgoCD
- [ ] Add Ansible for configuration management
- [ ] Set up Grafana + Prometheus monitoring stack
- [ ] Implement automated testing for compose files
- [ ] Create Terraform modules for VPS deployments

## 🤝 Contributing

While this is a personal infrastructure repository, suggestions and questions are welcome! Feel free to:
- Open an issue for questions or suggestions
- Suggest improvements to documentation
- Share your own homelab experiences

## 📜 License

This documentation is provided under the MIT License. See [LICENSE](./LICENSE) for details.

---

## 📬 Contact

- **LinkedIn**: [Norbert Csicsay](https://www.linkedin.com/in/norbert-csicsay-497195334)

---

<sub>Last updated: February 2026 | Infrastructure: Proxmox VE 9.1 | Services: 21 active</sub>
