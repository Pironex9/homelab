**Date:** 2026-08-28
**Author:** Norbert Csicsay
**GitHub:** [Pironex9/homelab](https://github.com/Pironex9/homelab)

---

# Homelab Infrastructure

This is the technical documentation. For the infrastructure overview and live status, see [homelabor.net](https://homelabor.net/).

Two sites: a Proxmox VE 9.1 hypervisor running 32 Docker Compose stacks across
ten guests, and a 3-node K3s cluster at a second location, linked by Tailscale.
Both are described by code in the same repository - Compose files deployed by
Komodo, cluster contents reconciled by Argo CD.

## Navigation

- **Proxmox** - Current configuration, running services, and notes for each host (LXCs/VMs, Nobara PC, Hetzner VPS, K3s Cluster)
- **Setup Guides** - Chronological guides documenting how the homelab was built, grouped by topic:
  - *Core Infrastructure* - Proxmox, Docker, storage, HAOS, DNS
  - *Services* - Individual service setups (Immich, Jellyfin, Karakeep...)
  - *Operations* - Troubleshooting, NFS, backup
  - *Platform & Automation* - Komodo, DocuSeal, n8n, MkDocs
- **K3s Cluster** - [The three code layers](k3s/01_K3s_Infrastructure_as_Code.md) that describe the cluster: Ansible for k3s itself, Argo CD for its contents, and the restore proofs behind the backups
- **VPS** - Hetzner VPS and Pangolin reverse proxy setup guides
- **Projects** - Side projects outside the homelab

## Contact

- **LinkedIn**: [Norbert Csicsay](https://www.linkedin.com/in/norbert-csicsay-497195334)
- **GitHub**: [Pironex9](https://github.com/Pironex9)
