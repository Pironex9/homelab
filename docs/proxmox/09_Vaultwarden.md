**Date:** 2026-01-04
**System:** Proxmox VE 9.1.2
**LXC ID:** 103
**IP:** 192.168.0.219

---

## Overview

Vaultwarden is a self-hosted Bitwarden-compatible password manager running on Alpine Linux LXC 103.

---

## Installation

```bash
bash -c "$(wget -qO - https://github.com/community-scripts/ProxmoxVE/raw/main/ct/alpine-vaultwarden.sh)"
```

## LXC Specifications

- **Platform:** Alpine Linux LXC (Unprivileged)
- **CPU:** 1 core
- **RAM:** 1GB
- **Disk:** 4GB
- **Network:** vmbr0, DHCP

## Access

- **Web UI:** `http://192.168.0.219:8000`
- **Admin panel:** `http://192.168.0.219:8000/admin`

## Configuration

- Config: `/etc/vaultwarden/config.json` or `/opt/vaultwarden/.env`

## Notes

- SSH access is intentionally disabled - see [Claude Code Mgmt LXC](./19_Claude_Code_Management_LXC_Setup.md) for context
- Vaultwarden requires HTTPS for mobile clients - serve via Caddy reverse proxy (`.lan` domain)

---

## Further Documentation

- [Vaultwarden Wiki](https://github.com/dani-garcia/vaultwarden/wiki)
- [Proxmox Helper Scripts](https://community-scripts.github.io/ProxmoxVE/)
