**Date:** 2026-04-13
**System:** Proxmox VE 9.1
**LXC ID:** 103
**IP:** 192.168.0.219

---

## Overview

Vaultwarden is a self-hosted Bitwarden-compatible password manager running on Alpine Linux LXC 103. It serves as the primary password manager for the homelab, accessible both on the local network and publicly via Pangolin.

---

## Installation

Installed via Proxmox Community Scripts (Alpine variant):

```bash
bash -c "$(wget -qO - https://github.com/community-scripts/ProxmoxVE/raw/main/ct/alpine-vaultwarden.sh)"
```

## LXC Specifications

- **Platform:** Alpine Linux LXC (Unprivileged)
- **CPU:** 1 core
- **RAM:** 256MB
- **Disk:** 1GB
- **Network:** vmbr0, static IP 192.168.0.219

---

## Access

| URL | Context |
|-----|---------|
| `https://vaultwarden.lan` | LAN access via Caddy reverse proxy (LXC 110) |
| `https://vault.yourdomain.com` | Public access via Pangolin (Hetzner VPS) |

---

## Configuration

Config file: `/etc/conf.d/vaultwarden`

```bash
# Enter LXC to edit
pct enter 103
vi /etc/conf.d/vaultwarden
rc-service vaultwarden restart
```

### Key settings

```bash
export DATA_FOLDER=/var/lib/vaultwarden
export WEB_VAULT_ENABLED=true
export WEB_VAULT_FOLDER=/usr/share/webapps/vaultwarden-web
export ADMIN_TOKEN=''        # empty = admin panel disabled
export ROCKET_ADDRESS=0.0.0.0
export SIGNUPS_ALLOWED=false
```

### Important: no ROCKET_TLS

Vaultwarden runs HTTP-only internally (port 8000). TLS is terminated by:
- Caddy (LXC 110) for `vaultwarden.lan`
- Pangolin (Hetzner VPS) for `vault.yourdomain.com`

The built-in Rocket TLS is intentionally disabled - it is not production-ready and causes issues with mobile clients.

---

## Security

- **Signups disabled:** `SIGNUPS_ALLOWED=false`
- **Admin panel disabled:** `ADMIN_TOKEN` is empty
- **2FA:** enabled on the account (TOTP via Google Authenticator)
- **Rate limiting:** built-in, no configuration needed
- **HTTPS:** enforced at reverse proxy level (Let's Encrypt via Pangolin for public access)

---

## Caddy Configuration (LXC 110)

```caddy
@vaultwarden host vaultwarden.lan
handle @vaultwarden {
    reverse_proxy http://192.168.0.219:8000
}
```

---

## Updating

Vaultwarden is installed via Alpine package manager. Update when a new version appears in the Alpine repos:

```bash
pct enter 103
apk update && apk upgrade vaultwarden
rc-service vaultwarden restart
```

Note: Alpine package versions may lag a few days behind upstream releases.

---

## Operations

```bash
# Status
pct exec 103 -- rc-service vaultwarden status

# Logs
pct exec 103 -- tail -f /var/log/vaultwarden/access.log
pct exec 103 -- tail -f /var/log/vaultwarden/error.log

# Restart
pct exec 103 -- rc-service vaultwarden restart
```

---

## Notes

- SSH access is not available - use `pct enter 103` or `pct exec 103` from PVE
- Data stored in `/var/lib/vaultwarden`
- No `.env` file - configuration is in `/etc/conf.d/vaultwarden` (Alpine OpenRC style)

---

## Further Documentation

- [Vaultwarden Wiki](https://github.com/dani-garcia/vaultwarden/wiki)
- [Proxy examples](https://github.com/dani-garcia/vaultwarden/wiki/Proxy-examples)
- [Proxmox Helper Scripts](https://community-scripts.github.io/ProxmoxVE/)
