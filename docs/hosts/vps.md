# Hetzner VPS

## Overview

| Property | Value |
|----------|-------|
| Hostname | homelab-vps |
| Provider | Hetzner Cloud |
| Plan | CX23 (2 vCPU, 4GB RAM, 40GB SSD) |
| Location | Falkenstein (FSN1) |
| OS | Ubuntu 24.04 LTS |
| Public IP | redacted |
| Tailscale IP | 100.118.239.117 |
| Purpose | Public reverse proxy (Pangolin), Komodo managed |

## Running Services

| Service | Description |
|---------|-------------|
| `sshd` | OpenSSH server (key-only auth) |
| Docker daemon | Container runtime |
| `tailscaled` | Tailscale daemon (accept-routes enabled) |
| `periphery.service` | Komodo Periphery agent (outbound mode) |

## Docker Stacks

### Pangolin stack

Managed by Komodo.

| Container | Image | Port | Description |
|-----------|-------|------|-------------|
| `pangolin` | `fosrl/pangolin:latest` | 3001 (internal) | Reverse proxy + tunnel manager |
| `gerbil` | `fosrl/gerbil:latest` | 80, 443, 51820/udp, 21820/udp | WireGuard tunnel endpoint |
| `traefik` | `traefik:latest` | via gerbil network | TLS termination + routing |

Compose file: `compose/vps/pangolin/docker-compose.yml`
Config files: `/opt/pangolin/config/` (not in git - contains secrets)

### Uptime Kuma stack

Managed by Komodo.

| Container | Image | Port | Description |
|-----------|-------|------|-------------|
| `uptime-kuma` | `louislam/uptime-kuma:2` | 3001 (host, internal only) | Service monitoring |

Compose file: `compose/vps/uptime-kuma/docker-compose.yml`
Data: `/opt/uptime-kuma/`
Public URL: https://uptime.homelabor.net (Pangolin auth required)

Runs with `network_mode: host` to access the VPS host's Tailscale routes, enabling monitoring of homelab LAN services (192.168.0.x) via the `pve` subnet router.

## Firewall (UFW)

| Port/Source | Protocol | Action | Service |
|-------------|----------|--------|---------|
| 22 | TCP | LIMIT | SSH |
| 80 | TCP | ALLOW | HTTP (Pangolin/Traefik) |
| 443 | TCP | ALLOW | HTTPS (Pangolin/Traefik) |
| 51820 | UDP | ALLOW | WireGuard (Pangolin newt clients) |
| 21820 | UDP | ALLOW | WireGuard (Pangolin newt clients) |
| 3001 from 172.18.0.0/16 | TCP | ALLOW | Uptime Kuma - Traefik internal only |

Port 8120 is NOT open - Komodo Periphery uses outbound mode via Tailscale.

The 3001 rule allows only the pangolin Docker bridge subnet to reach Uptime Kuma on the host. Port 3001 is not reachable from the internet.

## Komodo Integration

Periphery runs in outbound mode, connecting to Komodo Core via Tailscale mesh:

```
VPS Periphery → Tailscale (100.118.239.117) → Core (100.86.108.33:9120)
```

Config (`/etc/komodo/periphery.config.toml`):
```toml
core_public_keys = ["your_core_public_key_here"]
core_address = "http://100.86.108.33:9120"
connect_as = "VPS"
```

## Security

- SSH key-only authentication
- UFW firewall (minimal open ports)
- Tailscale DNS override disabled (`tailscale set --accept-dns=false`)
- Pangolin 2FA enabled
- Fail2ban (SSH + HTTP)
- Cloudflare proxy in front of domain

See [02 - Security Configuration](../vps/02_Security_Configuration_Guide.md) for full details.

## Lessons Learned

- **Tailscale DNS conflict:** After `tailscale up`, systemd-resolved may lose upstream DNS. Fix: `tailscale set --accept-dns=false && systemctl restart systemd-resolved`.
- **Periphery installer needs root:** Run as root, not with sudo pipe, to avoid write permission errors to `/usr/local/bin`.
- **Duplicate TOML keys:** The installer pre-populates some fields (e.g. `connect_as`). Adding the same key again causes a parse error - comment out the original before adding your own.
- **Outbound mode, no inbound port needed:** With `core_address` set, Periphery initiates the connection to Core. Port 8120 does not need to be open in UFW.
- **`connect_as` must be uppercase "VPS":** The server name in Komodo is "VPS" (uppercase). Using `connect_as = "vps"` (lowercase) causes onboarding to create a duplicate "vps" server instead of connecting to the existing "VPS" one. The existing stacks (pangolin, uptime-kuma) stay on the original entry and show as unreachable. See komodo.md Lessons Learned for the full fix procedure.
- **Onboarding key is one-time use:** After successful onboarding, `onboarding_key` is automatically commented out in the config. If you need to re-onboard (e.g. after a Core key rotation), generate a new key in Komodo UI → Settings → Onboarding, add it to the config, restart periphery, then comment it out again.
- **UFW blocks Docker bridge → host traffic:** Containers on a Docker bridge network cannot reach the host on arbitrary ports - UFW applies to this traffic too. Add a scoped rule: `ufw allow from 172.18.0.0/16 to any port PORT proto tcp`.
- **Pangolin local vs tunnel site:** Services running on the VPS itself must be added under a **local** Pangolin site, not the homelab tunnel site. If added to the tunnel site, Pangolin routes the request through the Newt tunnel looking for a container that does not exist there.
- **Pangolin resource target for host-networked containers:** When a container uses `network_mode: host`, use the Docker bridge gateway IP as the Traefik target (`http://172.18.0.1:PORT`), not the container name.
- **AdGuard caches NXDOMAIN:** If the DNS record does not exist when AdGuard first queries it, AdGuard caches the negative response. Even after the real record is created and propagated, AdGuard serves the cached NXDOMAIN until the TTL expires or the cache is cleared manually.
