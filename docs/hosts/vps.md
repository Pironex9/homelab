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

#### The database, and what backs it up

`/opt/uptime-kuma/kuma.db` is **743 MB** - almost all of it heartbeat history, one
row per check per monitor. It runs in WAL mode, so anything that copies it must stop
the container first or it silently drops the `-wal` file.

Editing it by hand is a normal operation here, because Uptime Kuma has no write REST
API (see [35 - Cron Job Monitoring](../proxmox/35_Cron_Job_Monitoring_Uptime_Kuma.md)).
The convention is one `kuma.db.bak-<date>` taken immediately before each such edit,
and **only the most recent one is kept**. On 2026-08-25 three had accumulated, 2.2 GB
on a 38 GB disk, and two were deleted.

The one that was deleted for a second reason is worth remembering: `kuma.db.bak-20260814`
predated all nine push monitors. Restoring it would not have undone anything - it would
have deleted every monitor and eleven days of history. A backup old enough to predate
the thing you want to keep is not a rollback point.

!!! warning "The Kuma database has no off-VPS backup"

    The `.bak` copies sit on the same disk as the live database, so they cover a bad
    write and nothing else. The VPS has no cron, no restic, and the homelab's vzdump
    does not reach it. If this disk dies, every monitor definition and all heartbeat
    history goes with it. The monitor *definitions* are cheap to rebuild from the
    documented SQL; the history is not.

### Landing stack

Managed by Komodo.

| Container | Image | Address | Description |
|-----------|-------|---------|-------------|
| `landing` | built from `compose/vps/landing/` | `172.18.0.10` (static, `pangolin` network) | Homelab portfolio landing page |

No host port is published; Traefik reaches the container directly on the `pangolin` Docker network at `172.18.0.10:80`.

`dist/` is gitignored and built on the VPS, so a deploy is two steps, in this order: Komodo `DeployStack` to pull the repo and recreate the container, then `sh build.sh` in `/etc/komodo/repos/github/compose/vps/landing/`. Komodo has no `pre_deploy` command configured for this stack.

!!! warning "Rebuilding `dist/` used to take the site down"

    `build.sh` cleared the directory by removing it. `dist/` is bind-mounted into the running container, so the mount was left pointing at a deleted inode and the container kept serving the old, empty one - every path 404ing while the files sat visibly on disk. Fixed on 2026-08-31 by emptying the directory instead of replacing it, and the fix was then proven the same way it broke: `build.sh` was run against the live container, every path stayed 200, and `docker inspect landing --format '{{.State.StartedAt}}'` was unchanged - the mount survived the rebuild. If a future edit reintroduces `rm -rf "$DIST"`, the recovery is `docker compose up -d --force-recreate`.

Public URL: https://homelabor.net (apex, no subdomain) - **no authentication**, by design. This is the one resource meant to be reachable with no session, the same precedent Jellyfin already set.

Besides the static site, this Caddy proxies four hand-picked paths and nothing else: two Uptime Kuma routes for the status widget, and since 2026-08-31 the Umami tracker (`/script.js` and `/api/send`), which it forwards over the tailnet to the K3s cluster. The Umami dashboard itself is not published here and stays on the tailnet.

A separate `umami.homelabor.net` resource was the obvious alternative and was rejected: it would serve Umami's login page publicly, and narrowing it would depend on Pangolin path rules, which mean "bypass auth" rather than "permit" and are known to misfire on protected resources ([fosrl/pangolin#2551](https://github.com/fosrl/pangolin/issues/2551)). A route table is an allow-list; a rule set here would not have been. Same-origin also means the landing page CSP (`script-src 'self'`, `connect-src 'self'`) needed no exception.

The tailnet target is pinned with `extra_hosts` in the compose file, because this host runs `accept-dns=false` and MagicDNS names do not resolve in the container. Re-creating the cluster's `umami` Ingress gives the Tailscale operator's proxy a **new** address and silently breaks that mapping - the symptom is tracker requests timing out while the dashboard still works.

Pangolin resource setup notes (recorded here because they differ from what was planned):

- The apex resource worked on the first try with a blank subdomain field - the installed Pangolin version did not need the Traefik file-provider fallback that fosrl/pangolin issue #2645 warns about. Anyone adding a future apex-style resource does not need that fallback either.
- The resource was created with Platform SSO enabled by default, which 302-redirected the apex to the Pangolin auth wall even though Authentication was set to off. SSO had to be explicitly disabled on this specific resource before the apex served content directly.
- The target site defaulted to the `HomeLabor` newt (tunnel) site instead of the local `VPS` site. With the tunnel site selected, Traefik was handed a WireGuard tunnel address (`http://100.89.128.4:<port>`) for a container that actually runs on the VPS itself, and every request hung for 25 seconds before failing. Moving the resource's site to `VPS` fixed it immediately. Uptime Kuma is the only other resource on the local `VPS` site; every other resource on this Pangolin instance legitimately goes through the tunnel and should stay there.
- TLS: the Let's Encrypt certificate issued normally over the gray-cloud apex `A` record, no special handling needed.

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

### The LIMIT on 22 locks out the maintainer, and retrying keeps it locked

`LIMIT` is not a synonym for `ALLOW` with a note attached. ufw expands it into

```
-m recent --seconds 30 --hitcount 6 ... -j ufw-user-limit
ufw-user-limit: REJECT --reject-with icmp-port-unreachable
```

so the **sixth new SSH connection from one source IP inside 30 seconds** is
rejected, and a TCP client renders an ICMP port-unreachable as
**`Connection refused`**. That is the trap: refused reads like a dead sshd or a
changed port, not like a firewall - a firewall is supposed to time out.

Hit on 2026-08-29 during a deploy session that opened one SSH connection per
command. Everything else on the box was healthy at the same moment: 443 open,
`https://homelabor.net` returning 200, ICMP fine, and `ss -lntp` showing sshd
listening on `0.0.0.0:22` the whole time.

**The retry is what sustains it.** The rule uses `--update`, which refreshes
`last_seen` on every arriving packet, so the 30-second window restarts with each
attempt and never expires while you keep knocking. Measured: 65 seconds of not
connecting cleared it and the next single attempt succeeded.

Confirm it is this and not something else, in three commands:

```bash
curl -s -4 ifconfig.me                                   # your egress IP
# then, on the VPS over Tailscale:
grep -F "src=<that ip> " /proc/net/xt_recent/DEFAULT      # ours read oldest_pkt: 15
iptables -L ufw-user-limit -n                             # LOG + REJECT icmp-port-unreachable
```

**Rule fail2ban out rather than assuming it.** `fail2ban-client status sshd`
listed two unrelated banned IPs that day, and the `f2b-sshd` chain does not even
appear in `iptables -S` when it holds nothing. The two mechanisms look identical
from the client side and are configured in completely different places.

**The tailnet path is unaffected**, because Tailscale traffic enters through the
`ts-input` chain, which sits ahead of ufw in `INPUT`:

```bash
ssh root@100.118.239.117   # homelab-vps, works throughout
```

That is how to finish an interrupted deploy without waiting, and how to inspect
the firewall that is blocking you. The lasting fix for scripted work is to batch
VPS commands into one SSH invocation instead of one per step, which is also why
the landing-page redeploy in
[compose/vps/landing/README.md](https://github.com/Pironex9/homelab/blob/main/compose/vps/landing/README.md)
is written as a single chained command.

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
