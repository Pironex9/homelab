# komodo LXC

## Overview

| Property | Value |
|----------|-------|
| Hostname | komodo |
| IP Address | 192.168.0.105 |
| VMID | 105 |
| OS | Alpine Linux v3.23 |
| Kernel | 6.17.4-1-pve |
| CPU | 1 core |
| RAM | 32 GB |
| Swap | 8 GB |
| Disk | 10 GB (local-lvm, 37% used) |
| Purpose | Komodo deployment and infrastructure management platform |

## Running Services

| Service | Description |
|---------|-------------|
| `sshd` | OpenSSH server |
| `crond` | Scheduled tasks |
| Docker daemon | Container runtime |
| `tailscaled` | Tailscale daemon (Tailscale IP: 100.86.108.33) |

## Open Ports

| Port | Protocol | Service |
|------|----------|---------|
| 22 | TCP | SSH |
| 9120 | TCP | Komodo Core web UI and API |

## Docker Stack

All three Komodo components run as Docker containers from a single Compose stack.

### Containers

| Container | Image | Port | Description |
|-----------|-------|------|-------------|
| `komodo-core-1` | `ghcr.io/moghtech/komodo-core:2` | 9120 | Core API server and web UI |
| `komodo-mongo-1` | `mongo` | 27017 (internal) | MongoDB - stores all Komodo state |
| `komodo-periphery-1` | `ghcr.io/moghtech/komodo-periphery:2` | 8120 (internal) | Local periphery agent |

### Docker Volumes

| Volume | Description |
|--------|-------------|
| `komodo_mongo-data` | MongoDB data directory |
| `komodo_mongo-config` | MongoDB configuration |
| `komodo_keys` | Core/Periphery PKI key storage (v2) |

## Komodo Configuration

| Setting | Value |
|---------|-------|
| Database | MongoDB at `mongo:27017` |
| Auth | Local auth enabled |
| OIDC / OAuth | Disabled |
| Monitoring interval | 15 seconds |
| JWT TTL | 1 day |
| First server | `https://periphery:8120` (local agent) |
| `KOMODO_HOST` | `http://192.168.0.105:9120` |
| `TZ` | `Europe/Budapest` |
| `KOMODO_DISABLE_USER_REGISTRATION` | `true` |
| `KOMODO_ENABLE_NEW_USERS` | `false` |

## Architecture

Komodo is a self-hosted alternative to tools like Portainer or Dockge with a focus on GitOps-style deployments. It consists of:

- **Core** - Central server. Manages resources (servers, stacks, builds). Exposes the web UI on port 9120.
- **Periphery** - Lightweight agent installed on each managed server. Executes actions on behalf of Core (deploy stacks, restart containers, collect stats).
- **MongoDB** - Stores all state: servers, stacks, alerts, resource definitions.

In v2, Core generates a PKI keypair on startup (`/config/keys/core.key` + `core.pub`). Each Periphery must be configured with the Core's public key (`core_public_keys`) to accept incoming connections.

## Managed Servers

| Server | Address | Periphery type | Notes |
|--------|---------|----------------|-------|
| Local | `https://periphery:8120` | Docker container (komodo-periphery-1) | Built-in local agent on the komodo LXC |
| docker-host | `https://192.168.0.110:8120` | systemd `periphery.service` | Main Docker host - 18 stacks |
| nobara | `https://192.168.0.100:8120` | systemd `periphery.service` | Desktop PC, not 24/7 |
| vps | outbound via Tailscale → `100.86.108.33:9120` | systemd `periphery.service` | Hetzner VPS - Pangolin stack |

### Periphery PKI configuration (v2)

Each managed host must have the Core public key in its periphery config. Retrieve it from the Core startup log or from **Settings** in the Komodo UI.

**docker-host and nobara** (`/etc/komodo/periphery.config.toml`):
```toml
core_public_keys = ["your_core_public_key_here"]
```

**Local periphery container** - configured via `/etc/komodo/periphery.config.toml` on LXC 105, mounted into the container at `/config/config.toml`.

## Updating

Use the community addon script (already set up as a shell command):

```bash
update_komodo
```

This downloads the latest upstream `mongo.compose.yaml`, migrates `compose.env` as needed, pulls new images, and restarts the stack. Backups of both files are created before any changes.

For manual updates:

```bash
cd /opt/komodo
docker compose -p komodo -f mongo.compose.yaml --env-file compose.env pull
docker compose -p komodo -f mongo.compose.yaml --env-file compose.env up -d
```

**Current version:** v2.0.0

## Adding a new managed server

1. Install periphery on the target host:
   ```bash
   curl -fsSL https://raw.githubusercontent.com/moghtech/komodo/main/scripts/setup-periphery.py | sudo python3
   ```
2. Add the Core public key to `/etc/komodo/periphery.config.toml`:
   ```toml
   core_public_keys = ["MCowBQYDK2VuAyEAanLhSIyYAQmX7NLhn1PH+fiTClnhp+jrv5BPAnKgdCM="]
   ```
3. Restart and enable the service:
   ```bash
   sudo systemctl restart periphery && sudo systemctl enable periphery
   ```
4. Add the server in Komodo UI: **Servers → New Server → `https://<ip>:8120`**

## Lessons Learned

- **Alpine does not have `ss`:** Use `netstat` from the `net-tools` package instead, or install `iproute2` with `apk add iproute2`.
- **High RAM allocation:** 32 GB RAM is allocated to this LXC, but actual usage is lower. This may be intentional for MongoDB's working set cache or could be reduced after profiling.
- **Swap is configured:** Unlike most other LXCs in this homelab, komodo has 8 GB swap - useful because MongoDB can have large memory requirements during indexing.
- **Periphery on managed hosts:** Each host managed by Komodo must run the `periphery` agent. The agent opens an outbound connection to Core - no inbound firewall rules are needed on the managed host.
- **KOMODO_HOST must be set correctly:** The default value in the community script template is `https://demo.komo.do`. This must be changed to the actual host URL (`http://192.168.0.105:9120`), otherwise webhooks and OAuth redirects will be broken.
- **v2 PKI auth:** v2 removed passkey auth in favour of PKI. The Core public key must be added to every periphery config. The local container periphery needs the key via a mounted config file (`/etc/komodo/periphery.config.toml:/config/config.toml`) since env vars are not picked up for this field.
- **`restart` vs `up -d`:** `docker compose restart` does not recreate containers - new volume mounts require `up -d`.
- **Port conflict on Nobara:** Nobara had an old v1 periphery container running on port 8120. Stop and remove it before starting the systemd service.
- **Nobara periphery install needs sudo:** The installer writes to `/usr/local/bin` - run with `sudo python3`, not as a regular user.
- **`update_komodo` needs a TTY:** Running it via plain SSH fails. Use `type=update bash <(curl -fsSL ...)` for non-interactive execution, or SSH with `-t`.
- **Tailscale on LXC 105 (Alpine):** Requires TUN device in `/etc/pve/lxc/105.conf` (same as LXC 109). Install via `apk add tailscale`, start with `rc-service tailscale start`, enable with `rc-update add tailscale default`. Use `--accept-dns=false` to avoid DNS conflicts.
- **VPS periphery outbound mode:** The VPS periphery connects outbound to Core via Tailscale (`core_address = "http://100.86.108.33:9120"`). No inbound port needs to be opened on the VPS. Requires an onboarding key generated in Settings → Onboarding.
- **Onboarding key is one-time use:** After the periphery successfully onboards, comment out the `onboarding_key` line in the periphery config. If left in, the next periphery restart will attempt to re-onboard and may create a duplicate server entry.
- **`connect_as` is case-sensitive:** The value must exactly match the server name in Komodo (e.g. `connect_as = "VPS"` not `"vps"`). A mismatch causes the onboarding flow to create a NEW server instead of connecting to the existing one. If this happens, a duplicate server entry will appear in the database and the original server will show as unreachable even though periphery reports "Logged in". Fix: correct the case in the config, delete the duplicate from MongoDB (`db.Server.deleteOne({_id: ObjectId("...")})`), restart periphery.
- **Periphery backoff after network outage:** After a network outage, periphery on managed hosts (e.g. LXC 100) enters exponential backoff and may not reconnect automatically. If a server shows as unreachable in Komodo after a network event, SSH to the host and run `systemctl restart periphery`. The services themselves keep running - only Komodo visibility is lost.
