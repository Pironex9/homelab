# komodo LXC

## Overview

| Property | Value |
|----------|-------|
| Hostname | komodo |
| IP Address | 192.168.0.105 (static since 2026-07-06, was DHCP - see proxmox doc 25) |
| VMID | 105 |
| OS | Alpine Linux v3.23 |
| Kernel | 7.0.0-3-pve (shared with Proxmox host - LXCs have no separate kernel; relevant to the RSEQ/mongo incident below) |
| CPU | 2 cores |
| RAM | 2048 MB |
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
| `komodo-mongo-1` | `mongo` (unpinned, `GLIBC_TUNABLES=glibc.pthread.rseq=1` set - see incident below) | 27017 (internal) | MongoDB - stores all Komodo state |
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
| Monitoring interval | 5 minutes (`KOMODO_MONITORING_INTERVAL="5-min"`, raised from default 15 seconds on 2026-07-06) |
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
| LXC 100 | outbound → `http://192.168.0.105:9120` | systemd `periphery.service` | Main Docker host - 18 stacks |
| Nobara | `https://192.168.0.100:8120` | systemd `periphery.service` | Desktop PC, not 24/7 |
| VPS | outbound via Tailscale → `http://100.86.108.33:9120` | systemd `periphery.service` | Hetzner VPS - Pangolin stack |
| Minecraft | outbound → `http://192.168.0.105:9120` | systemd `periphery.service` | LXC 112 - Minecraft server |
| HAOS | - | Not supported | Home Assistant OS is a locked-down Alpine VM - no periphery install possible |

### Periphery PKI configuration (v2)

Each managed host must have the Core public key in its periphery config. Retrieve it from the Core startup log or from **Settings** in the Komodo UI.

**LXC 100 (outbound mode)** (`/etc/komodo/periphery.config.toml`):
```toml
core_public_keys = ["MCowBQYDK2VuAyEAanLhSIyYAQmX7NLhn1PH+fiTClnhp+jrv5BPAnKgdCM="]
core_addresses = ["http://192.168.0.105:9120"]
connect_as = "LXC 100"
```

**Nobara** (`/etc/komodo/periphery.config.toml`):
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

For managed host periphery binary updates (run on each host):

```bash
curl -fsSL https://raw.githubusercontent.com/moghtech/komodo/main/scripts/setup-periphery.py | python3 -
```

Note: On Nobara, `sudo python3 -` is required (writes to `/usr/local/bin`). Use a TTY or run from the Nobara desktop terminal.

**Current version:** v2.2.0

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
- **RAM allocation:** 2048 MB (bumped from 1024 MB on 2026-07-05, see incident below). Shared between MongoDB, Komodo core, Komodo periphery and the Docker daemon - tight but was the deciding factor during troubleshooting, alongside the actual root cause (see below).
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
- **Inbound vs outbound periphery mode:** In inbound mode, Core connects to periphery via HTTP/WebSocket. A known issue (likely reqwest connection pool poisoning) causes Core to stop retrying after a connection drop - only a Core restart recovers it. Solution: switch to outbound mode where periphery initiates the connection and reconnects automatically. LXC 100 was migrated to outbound mode on 2026-04-06.
- **Migrating existing server from inbound to outbound mode:** (1) In Komodo UI, clear the server's Address field and set Periphery Public Key to the periphery's public key (from its startup log). (2) In periphery config, add `core_addresses` and `connect_as = "<exact server name>"`. (3) Restart periphery - it connects without an onboarding key. Do NOT use an onboarding key for existing servers - it creates a duplicate entry. If a duplicate was created, delete it from MongoDB: `db.Server.deleteOne({_id: ObjectId("...")})`.
- **LXC 100 periphery public key:** `MCowBQYDK2VuAyEA9sCPWCwh2XNxmYdmWMKvOiWv729oZmBo+uuVsDqoxk4=`
- **Deno-based Actions with `npm:` imports need scheduling headroom after Global Auto Update:** Actions written as Deno TS scripts that import the Komodo client via `npm:` re-fetch that dependency from `registry.npmjs.org` on every run (no cache/lockfile pin). If scheduled too close after "Global Auto Update" (03:00, pulls images for every managed stack fleet-wide), the two can collide on the same LXC's network/DNS and the npm fetch fails with a DNS resolution error. Give custom scheduled Actions/Procedures at least 30-40 min of buffer after 03:00. See `docs/proxmox/23_Homelable_Setup.md` for the incident (`homelable-git-pull`, moved from 03:10 to 03:40 on 2026-07-09).
- **RE605X bridge loop causes periodic WebSocket disconnects:** When Nobara PC is offline, the TP-Link RE605X wireless extender (in bridge/extender mode) re-broadcasts frames back upstream, corrupting the Archer C6 MAC table. This causes ~16-minute LAN outages at night, dropping the LXC 100 periphery WebSocket connection. Symptom: `Timed out waiting for Ping` logs at ~02:00 CEST. Mitigation: gratuitous ARP script on Proxmox host (`/usr/local/bin/arping-keepalive.sh`) runs every 5 minutes via cron, keeping the MAC table fresh. Tailscale-based connections (VPS periphery) are unaffected since they bypass Layer 2.

### Incident: mongo SIGSEGV crash-loop after Proxmox host reboot - full timeline and eventual root cause (2026-07-05 to 2026-07-06)

This ran across two days and several false starts before the actual root cause (a Linux kernel bug) was found. Documented in full because the early diagnostic steps and their reasoning are still useful, even though the "fixes" applied on day one were later reverted.

#### Day 1 (2026-07-05): symptom and first (wrong) fixes

**Symptom:** After a Proxmox host reboot at 21:08 CEST, Komodo UI and Jellyfin intermittently unreachable ("works once, doesn't work the next time"). `komodo-mongo-1` was crash-looping with `exitCode=139` (SIGSEGV), roughly every 60-120 seconds, restart count climbing continuously.

**Ruled out during diagnosis:**
- Not OOM-killed - host had 14 GB free, LXC cgroup `memory.events` showed `oom_kill: 0`
- Not disk-related - 5.5 GB free on the LXC rootfs, no I/O errors in `dmesg`
- Not CPU instruction-set incompatibility - host CPU (i5-8400) supports AVX/AVX2/SSE4.2
- Not data corruption - `mongod --repair` found zero corruption; restoring the LXC from the previous night's backup (`vzdump-lxc-105-2026_07_05-02_06_23.tar.zst`, pre-dating the incident) still crashed the same way within ~2 minutes
- Not a stale/updated image - `mongo:latest` had been pulled 7 weeks earlier (2026-05-13) and unchanged since

**First (incomplete) fix applied 2026-07-05:** Pinned `image: mongo` to `image: mongo:7.0` and wiped `komodo_mongo-data`/`komodo_mongo-config` for a fresh init. This "worked" (no more segfaults) but was actually just avoiding the bug by switching binaries, not fixing it - and it came at real cost: all Server registrations (LXC 100, Nobara, VPS, Minecraft), resource definitions, alerts, and task history were lost, needing full manual re-onboarding (see below). It also introduced a *new*, unrelated-looking symptom: `komodo-core-1` settled into sustained ~60-77% CPU usage after the fresh init, which - combined with only 2 CPU cores allocated to this LXC on a 6-core host - starved other LXCs (notably LXC 100's Jellyfin/DocuSeal/Form/Kanban) of CPU, causing renewed public 503 flapping the next morning. A temporary `pct set 105 --cpulimit 1` was applied to contain the damage while the real cause was still unknown.

#### Day 2 (2026-07-06): the real root cause

Before restoring the pre-incident backup a second time and just re-fighting the same segfault, a **web search for the exact symptom** (`mongod SIGSEGV exit code 139 crash startup docker`) turned up [docker-library/mongo discussion #748](https://github.com/docker-library/mongo/discussions/748): *"Mongod hard-crashes exactly every 30 seconds (SIGSEGV)"* - matching our pattern almost exactly.

**Root cause (confirmed upstream):** A **Linux kernel bug** affecting RSEQ (restartable sequences) support, present in kernel **6.19+**, that crashes MongoDB Docker images **8.0.5 and later** (RSEQ was disabled for glibc / enabled only for Google TCMalloc starting with that release, per [docker-library/mongo commit 7bf2228](https://github.com/docker-library/mongo/commit/7bf22284b34d88f3b4d6a6b5ad6d50297111f691), and disabled from the start in 8.2.x). Confirmed as a genuine kernel regression by a MongoDB/docker-library maintainer, with an upstream kernel mailing list bug report ([lore.kernel.org](https://lore.kernel.org/all/20260428221058.149538293@kernel.org/)). Our Proxmox host runs kernel `7.0.0-3-pve` (built 2026-04-21) - Proxmox's newer kernel series tracks a recent upstream base, squarely in the affected range. LXC containers share the host kernel directly (no separate guest kernel), so this bug applies identically inside any LXC on this host.

**The actual fix:** set `GLIBC_TUNABLES=glibc.pthread.rseq=1` as an environment variable on the mongo container. This re-enables RSEQ for glibc and works around the kernel bug entirely - **no image pin, no data wipe needed.**

**Final resolution (2026-07-06):**
1. Restored LXC 105 from the pre-incident backup (`vzdump-lxc-105-2026_07_05-02_06_23.tar.zst`) a second time - recovering the original data, the unpinned `image: mongo`, and all Server registrations
2. Added `GLIBC_TUNABLES: "glibc.pthread.rseq=1"` to the `mongo` service's `environment:` block in `/opt/komodo/mongo.compose.yaml`
3. Raised `KOMODO_MONITORING_INTERVAL` from the default `15-sec` to `5-min` in `compose.env` (see CPU section below)
4. Restarted the stack - **stable for 4+ minutes with zero mongo restarts**, running the original unpinned `mongo` image against the original data
5. Removed the temporary `pct set 105 --cpulimit 1` (no longer needed - see below)
6. Restarted `periphery` on LXC 100, Minecraft (LXC 112), and the VPS - all reconnected immediately using their existing `connect_as` names, no onboarding key needed since the Server records were back from the restored data

**Result:** `komodo-core-1` CPU dropped from ~60-77% to ~0.01-0.03%, `komodo-mongo-1` from ~33-40% to ~0.35-0.72%, Proxmox host load average from 5.8-6.3 down to 0.55-1.5. All previously-registered servers (Local, LXC 100, Minecraft, VPS) reconnected without any manual re-onboarding. Zero Jellyfin/DocuSeal/Form/Kanban health-check failures since.

**Was the CPU spike part of the same kernel bug, or a separate issue?** Not fully isolated - the CPU fix (`5-min` monitoring interval) was applied at the same time as reverting to the old data/image, so it's possible the high CPU was specific to `komodo-core` polling a freshly-reinitialized, mostly-empty database every 15 seconds (unlikely to be CPU-heavy on its own per the small number of resources), or it may be a second symptom of the same broken-RSEQ kernel bug degrading glibc pthread synchronization in Core's own multi-threaded (tokio) runtime. A [related GitHub issue](https://github.com/moghtech/komodo/issues/277) confirms `KOMODO_MONITORING_INTERVAL` is a legitimate, documented lever for Komodo's baseline CPU/resource usage regardless of cause, so the change is being kept either way.

**Lessons:**
- **Search for the exact error/symptom before assuming it's environment-specific.** A specific web search for "mongod SIGSEGV exit code 139" immediately surfaced a known, upstream-confirmed kernel bug with an official one-line workaround - this would have saved a full day of image-pinning, data-wiping, and CPU-capping band-aids.
- **A kernel bug can look exactly like an application bug.** The segfault pattern (crashes at a fixed-ish interval, no useful logs, reproducible on fresh data) had all the hallmarks of "this specific database version is broken here" - but the actual defect was three layers down, in kernel RSEQ handling.
- **`GLIBC_TUNABLES=glibc.pthread.rseq=1`** is the workaround for MongoDB (and potentially other glibc/tcmalloc-based) containers segfaulting on Linux kernel 6.19+, until distros ship the kernel fix.
- Never leave `image: mongo` unpinned if avoidable, but in this case pinning would have only hidden the real problem (an older mongo binary might not trigger the RSEQ bug, or might hit it differently) rather than fixing it - the env var fix works regardless of mongo version.
- After changing Pangolin health-check settings (DB or UI), restart the Newt service itself (`systemctl restart newt` on the Proxmox host) - a Pangolin-side restart alone does not fully re-sync all health-check parameters like `hcUnhealthyThreshold` to Newt.
- A "healthy N hours uptime" container status says nothing about host-wide CPU contention. Check `uptime`/load average on the Proxmox host itself when multiple *unrelated* public services flap together - that pattern points to shared host resource starvation, not per-service bugs.
- `docker update --cpus` doesn't work inside this Alpine LXC's nested Docker (cgroup CPU controller not delegated) - use `pct set <vmid> --cpulimit N` on the Proxmox host instead if an LXC-wide CPU cap is ever needed again.
- `pct restore ... --force` cleanly reverts an LXC's Proxmox-level config too (memory, cpulimit) - don't forget to reapply any LXC-level settings (e.g. `--memory 2048`) after a restore, since the backup captures whatever was set at backup time.
