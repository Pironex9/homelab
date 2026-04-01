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
| `tailscaled` | Tailscale daemon |
| `periphery.service` | Komodo Periphery agent (outbound mode) |

## Docker Stack

All services run as a single Compose stack managed by Komodo.

| Container | Image | Port | Description |
|-----------|-------|------|-------------|
| `pangolin` | `fosrl/pangolin:latest` | 3001 (internal) | Reverse proxy + tunnel manager |
| `gerbil` | `fosrl/gerbil:latest` | 80, 443, 51820/udp, 21820/udp | WireGuard tunnel endpoint |
| `traefik` | `traefik:latest` | via gerbil network | TLS termination + routing |

Compose file: `compose/vps/pangolin/docker-compose.yml`
Config files: `/opt/pangolin/config/` (not in git - contains secrets)

## Firewall (UFW)

| Port | Protocol | Service |
|------|----------|---------|
| 22 | TCP | SSH |
| 80 | TCP | HTTP (Pangolin/Traefik) |
| 443 | TCP | HTTPS (Pangolin/Traefik) |
| 51820 | UDP | WireGuard (Pangolin newt clients) |
| 21820 | UDP | WireGuard (Pangolin newt clients) |

Port 8120 is NOT open - Komodo Periphery uses outbound mode via Tailscale.

## Komodo Integration

Periphery runs in outbound mode, connecting to Komodo Core via Tailscale mesh:

```
VPS Periphery → Tailscale (100.118.239.117) → Core (100.86.108.33:9120)
```

Config (`/etc/komodo/periphery.config.toml`):
```toml
core_public_keys = ["your_core_public_key_here"]
core_address = "http://100.86.108.33:9120"
connect_as = "vps"
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
