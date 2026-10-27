**Date:** 2026-10-27
**Hostname:** pocket-id (LXC 114)
**IP address:** 192.168.0.114

---

# pocket-id LXC

**Status:** Running, no client apps connected yet. The OIDC provider for the homelab, LAN-only at `https://pocketid.lan`.

## Overview

| Property | Value |
|----------|-------|
| VMID | 114 |
| OS | Alpine Linux 3.23 |
| CPU | 1 core |
| RAM | 512 MB |
| Disk | 2 GB (`nvmethin`) |
| Network | vmbr0, static 192.168.0.114/24 |
| Unprivileged | yes |
| `onboot` | yes |
| Access | `pct exec 114 -- sh` only, no SSH |

## Why a separate LXC

An SSO is the login for everything behind it, so its outage is everyone's outage. LXC 100 carries 37 containers and has had an ARP conflict, a NIC hang and an emergency-mode reboot. Komodo deploys to LXC 100 too, so with Pocket ID there, a Komodo login that depended on it would be circular. The other critical services (Vaultwarden, Caddy, AdGuard, Komodo) are separate for the same reason.

## Install

Pocket ID has no Alpine package, so the release binary is installed by hand:

- Binary and data live in `/opt/pocket-id`, owned by the `pocketid` user (`data/` holds the SQLite database and uploads).
- `/opt/pocket-id/.env` (mode 600) carries `APP_URL=https://pocketid.lan`, `ENCRYPTION_KEY`, `TRUST_PROXY=192.168.0.208` (Caddy) and `ANALYTICS_DISABLED=true`.
- OpenRC service `pocket-id` (supervise-daemon, log in `/var/log/pocket-id.log`, not rotated).
- The binary was verified against the SHA-256 digest of the GitHub release asset.

```bash
pct exec 114 -- rc-service pocket-id status
pct exec 114 -- wget -qO- -S http://127.0.0.1:1411/healthz   # HTTP 204 when healthy
```

## Things that bite

- **`APP_URL` is the passkey identity.** Passkeys bind to the hostname `pocketid.lan`; changing it invalidates every registered passkey.
- **`ENCRYPTION_KEY` guards the database.** Lose it and the data is unreadable. The key is stored in the password manager.
- **The log file must be owned by `pocketid`.** With a root-owned log the supervised service reports `started` while nothing listens on 1411.
- **The first admin is whoever opens `/setup` first.** Do it right after install.

## Update

Download the new binary next to the old one, check it against the digest in the release, stop the service, swap, start. Pocket ID migrates its database on start, so copy `data/` first.

## Backup

LXC 114 is in the daily 02:00 vzdump job on `backup-hdd`, like every other guest except LXC 104.

## Reverse proxy

Caddy (LXC 110) serves `pocketid.lan` with the shared mkcert certificate and proxies to `192.168.0.114:1411`; AdGuard has a DNS rewrite to Caddy. See [caddy](caddy.md).
