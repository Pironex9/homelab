# claude-mgmt LXC

## Overview

| Property | Value |
|----------|-------|
| Hostname | claude-mgmt |
| IP Address | 192.168.0.204 |
| VMID | 109 |
| OS | Debian GNU/Linux 12 (bookworm) |
| Purpose | Claude Code homelab management container |

## Installed Software

| Package | Version | Notes |
|---------|---------|-------|
| Claude Code | 2.1.101 | Installed via native installer |
| Node.js | 20.20.0 | Required by Claude Code MCP servers |
| uv / uvx | 0.11.6 | Python package runner, used for ha-mcp |
| git | 2.39.5 | Version control |
| ripgrep | - | Fast code search, used by Claude Code |
| tmux | 3.3a | Persistent `claude` session, survives disconnects |
| Docker | latest (get.docker.com) | Runs code-server stack, Komodo-managed |
| Komodo Periphery | v2.2.0 | Outbound mode, `connect_as = "LXC 109"`, systemd `periphery.service` |

## tmux persistent Claude session

A `claude` tmux session runs the Claude Code CLI persistently so it survives SSH disconnects. Reattach from any client (Termux, Nobara, VS Code terminal, code-server browser terminal):

```bash
tmux attach -t claude
```

If the session doesn't exist (e.g. after a reboot):

```bash
tmux new-session -d -s claude "claude"
```

## code-server (browser IDE)

Docker container `code-server` (image `lscr.io/linuxserver/code-server`), compose file `compose/proxmox-lxc-109/code-server/docker-compose.yml`, deployed via Komodo (stack `code-server`, GitOps auto-update).

- **Bound to Tailscale-only:** `100.98.146.14:8443` - not reachable from LAN or public internet, only via Tailscale mesh
- **HTTPS via Tailscale Serve:** `tailscale serve --bg 8443` proxies `https://claude-mgmt.tailc6abe2.ts.net/` -> `http://127.0.0.1:8443`, giving a real Let's Encrypt cert (Tailscale HTTPS certs feature, not Funnel - stays tailnet-only). Plain `http://100.98.146.14:8443` still works but triggers a browser insecure-context warning (clipboard/service worker APIs degraded)
- **Password:** set via Komodo Stack Environment (`CODE_SERVER_PASSWORD`), not in the compose file or git
- **Workspace:** `/root` mounted whole at `/config/workspace/root` (single parent bind mount - covers `homelab`, `uzlet`, `learning`, `youtube`; standard practice over per-project mounts, since Docker can't merge multiple host dirs into one path anyway). Default editor workspace opens at `/config/workspace/root/homelab`
- **Why Docker over native install:** chosen for consistency with the homelab's GitOps/IaC approach (auto-update via Komodo like every other stack) despite the extra Docker+Periphery layer for a single container - deliberate tradeoff, not to be "simplified" back to a native install
- Access: browser to `https://claude-mgmt.tailc6abe2.ts.net/` while connected to Tailscale

## Network Configuration

| Property | Value |
|----------|-------|
| IP | 192.168.0.204/24 (static) |
| Gateway | 192.168.0.1 |
| DNS | 192.168.0.111 (AdGuard), 192.168.0.1 |
| Config | `/etc/network/interfaces` - `inet static` |
| Proxmox config | `/etc/pve/lxc/109.conf` - `ip=192.168.0.204/24,gw=192.168.0.1` |

## Running Services

| Service | Status | Description |
|---------|--------|-------------|
| ssh.socket | active | Owns port 22, triggers `ssh.service` on connection (`Accept=no`) |
| ssh.service | active | OpenSSH server, socket-activated. **Must stay `disabled`** - see the 2026-08-03 incident |
| cron.service | active | Scheduled tasks |
| docker.service | active | Runs code-server container |
| periphery.service | active | Komodo agent, outbound to Core (LXC 105) |
| tailscaled.service | active | Bound to UDP **41642**, not the default 41641 - see the 2026-08-03 incident |

`run-rpc_pipefs.mount` is permanently in `failed` state (NFS pseudo-filesystem cannot be mounted in an unprivileged LXC). Pre-existing and harmless - ignore it when reading `systemctl --failed`.

## Open Ports

| Port | Protocol | Notes |
|------|----------|-------|
| 22 | TCP | SSH access |
| 8443 | TCP | code-server, bound to Tailscale IP only (100.98.146.14) |
| 41642 | UDP | Tailscale WireGuard/peer traffic (`PORT=` in `/etc/default/tailscaled`) |

## SSH Access

SSH uses key-based authentication only. Password login for root is disabled by default (`PermitRootLogin prohibit-password`).

### Adding a New SSH Key

Since password login is disabled, new keys must be added via the Proxmox host:

```bash
ssh proxmox "pct exec 109 -- bash -c 'echo \"<public-key>\" >> /root/.ssh/authorized_keys'"
```

## MCP Servers

MCP servers are registered via `claude mcp add` and stored in `~/.claude.json` under the project's `mcpServers` key - NOT in `~/.claude/settings.json`. Use `claude mcp list` to verify.

API tokens are never stored in config files. All secrets live in `~/.secrets/` (chmod 600) and are read at runtime by wrapper scripts.

### GitHub MCP

Connects Claude Code to the GitHub API for repository management.

- **Auth:** Personal access token at `~/.secrets/github-token` (chmod 600)
- **Tools:** 26 (issues, PRs, commits, file contents)

```bash
claude mcp add github -- bash -c \
  "GITHUB_PERSONAL_ACCESS_TOKEN=\$(cat ~/.secrets/github-token) npx -y @modelcontextprotocol/server-github"
```

### Karakeep MCP

Connects Claude Code to the Karakeep bookmark manager.

- **Auth:** API key at `~/.secrets/karakeep-api-key` (chmod 600)
- **Package:** `@karakeep/mcp` (official)

```bash
claude mcp add karakeep -- bash -c \
  "KARAKEEP_API_ADDR=http://192.168.0.128:3000 KARAKEEP_API_KEY=\$(cat ~/.secrets/karakeep-api-key) karakeep-mcp"
```

### n8n MCP

Connects Claude Code to the n8n workflow automation instance via n8n's built-in official MCP server (HTTP transport).

- **Transport:** HTTP (not stdio)
- **Endpoint:** `http://192.168.0.112:5678/mcp-server/http`
- **Auth:** JWT access token at `~/.secrets/n8n-official-token` (chmod 600), sent as Bearer header
- **Token generated in:** n8n UI - Settings > API > MCP Server

```bash
claude mcp add --transport http n8n http://192.168.0.112:5678/mcp-server/http \
  --header "Authorization: Bearer $(cat ~/.secrets/n8n-official-token)"
```

Available tools: `search_workflows`, `get_workflow_details`, `create_workflow_from_code`, `update_workflow`, `execute_workflow`, `get_execution`, `get_node_types`, `search_nodes`, `get_suggested_nodes`, `get_sdk_reference`, `publish_workflow`, `unpublish_workflow`, `archive_workflow`, `search_projects`, `search_folders`

> **Note:** Previously used the unofficial `n8n-mcp` npm package (czlonkowski/n8n-mcp) via stdio wrapper `~/.secrets/n8n-mcp.sh`. Migrated 2026-05-01 to the official built-in MCP server which offers SDK-based workflow creation with type-safe node parameters.

### Homelable MCP

Connects Claude Code to the Homelable network topology visualizer (HTTP transport).

- **Transport:** HTTP (not stdio)
- **Endpoint:** `http://192.168.0.110:8001/mcp`
- **Auth:** API key in X-API-Key header

```bash
claude mcp add --transport http homelable http://192.168.0.110:8001/mcp \
  --header "X-API-Key: your_homelable_api_key_here"
```

### Home Assistant MCP

Connects Claude Code directly to Home Assistant with 92+ tools (entity control, automation management, dashboard editing, system health, etc.).

- **Auth:** Long-lived access token at `~/.secrets/haos-api-key` (chmod 600)
- **Wrapper:** `~/.secrets/ha-mcp.sh` (chmod 700) - reads token dynamically, runs `uvx ha-mcp@latest`
- **Requires:** `uv`/`uvx` at `~/.local/bin/uvx`

```bash
# Install uvx first (one-time)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create wrapper script
cat > ~/.secrets/ha-mcp.sh << 'EOF'
#!/bin/bash
export HOMEASSISTANT_URL=http://192.168.0.202:8123
export HOMEASSISTANT_TOKEN=$(cat /root/.secrets/haos-api-key)
exec /root/.local/bin/uvx ha-mcp@latest
EOF
chmod 700 ~/.secrets/ha-mcp.sh

# Register
claude mcp add home-assistant -- /root/.secrets/ha-mcp.sh
```

## Claude Code Skills

Skills are domain-specific knowledge packs loaded automatically when relevant. They live in `~/.claude/skills/<name>/SKILL.md`.

| Skill | Source | Activates when |
|-------|--------|----------------|
| `system-check` | local | running homelab health checks |
| `home-assistant-best-practices` | homeassistant-ai/skills | writing HA automations, helpers, dashboards |

Install a skill manually:

```bash
mkdir -p ~/.claude/skills/home-assistant-best-practices
curl -s "https://raw.githubusercontent.com/homeassistant-ai/skills/main/skills/home-assistant-best-practices/SKILL.md" \
  -o ~/.claude/skills/home-assistant-best-practices/SKILL.md
```

---

## Memsearch plugin: recap token budget and vector store

The [memsearch](https://github.com/memsearch-plugins) plugin gives Claude Code semantic recall over past sessions. Its `SessionStart` hook also injects a "Recent Memory" recap of the most recent daily journals into **every** session start, including `--resume`. That injection is invisible in normal use and is paid for on every single start.

Measured on this machine, stock settings cost **10.5 KB, roughly 2650 tokens**, per session start - more than the entire hand-written memory index it sits next to.

### What the audit found

Two problems, only one of which is about size:

1. **The recap was showing the wrong end of the day.** Version 0.4.6 truncated with a chronological `head -40`, so with 119 matching lines in the day's journal the injection stopped at the 05:15 session while work had continued to 09:05. The most relevant context was systematically cut away.
2. **The payload was mostly prose.** Of 80 content lines only 25 were headings; the rest were bullets averaging 155 characters, longest 472.

Upstream 0.4.17 fixes the recency bug with a `tail`-based extractor, but keeps the 2 files x 40 lines budget. Simulated on the real journals it produces **11 996 bytes** - the upgrade alone makes the recap slightly *larger*, just finally with the right content.

### Current settings

Three edits in the plugin's `hooks/session-start.sh`: 1 journal file instead of 2, 20 lines instead of 40, and `cut -c1-200` to clip the long bullets.

| Configuration | Injection size | Tokens |
|---|---|---|
| 0.4.6 stock | 10 563 B | ~2650 |
| 0.4.17 stock | 11 996 B | ~3000 |
| **0.4.17 patched** | **3 083 B** | **~770** |

Detailed lookups are unaffected: they go through the pull-based `/memory-recall` skill, which is what the hook's own comments say the recap is only meant to bootstrap.

### Re-apply after every plugin update

The plugin cache path is version-pinned (`~/.claude/plugins/cache/memsearch-plugins/memsearch/<version>/`), so `claude plugin update` installs a fresh unpatched copy and the recap silently returns to full size. `scripts/memsearch-trim-recap.sh` in the homelab repo re-applies the patch to whichever version is current:

```bash
./scripts/memsearch-trim-recap.sh          # apply (idempotent)
./scripts/memsearch-trim-recap.sh --check  # report status, write nothing
```

It exits 2 if upstream reshapes the hook, rather than silently doing nothing - a quiet no-op is the failure that would go unnoticed for months. The hook change takes effect on the next session start, not the current one.

### The same upgrade silently killed all search

Trimming the recap was the intended change. The version bump that carried it also broke the vector store, and that went unnoticed for a day.

`memsearch 0.4.6 -> 0.4.17` pulled in `milvus-lite 3.1.1`, which changed on-disk storage from a **single SQLite file** to a **directory** (lock file, `collections/`, `databases/`). There is no in-place migration. `MilvusLite.__init__` opens with:

```python
os.makedirs(data_dir, exist_ok=True)
```

`exist_ok=True` tolerates an existing *directory*, not an existing *file*. With the old-format `~/.memsearch/milvus.db` still in place, every memsearch invocation - `search`, `stats`, `index` - died at startup:

```
FileExistsError: [Errno 17] File exists: '/root/.memsearch/milvus.db'
```

**Why it stayed hidden for a day:** the SessionStart recap is plain bash reading the journal markdown directly, so it kept rendering perfectly while the semantic index underneath was dead. A healthy-looking recap says nothing about the index. The authoritative check is per project:

```bash
python3 -c "import json;print(json.load(open('.memsearch/.index-state.json'))['status'])"
```

The journals are the source of truth and the vectors are derived, so the fix is to rotate the old file and rebuild:

```bash
mv ~/.memsearch/milvus.db ~/.memsearch/milvus.db.v2-sqlite-$(date +%Y%m%d)
memsearch index -c "$(derive-collection.sh /root/homelab)" /root/homelab/.memsearch/memory
```

Rebuilding 137 journals across four projects took about an hour of CPU: homelab 1199 chunks, uzlet 2951, rails 4, learning 0 (its only journal is a 19-byte stub).

### Gotchas

- The plugin update needs the fully qualified name: `claude plugin update memsearch@memsearch-plugins`. The bare name returns "not found".
- Bare `memsearch stats` fails with `collection not found`. The plugin uses per-project collections, so the correct call here is `memsearch stats -c ms_homelab_3bf86670`.
- **Never type a collection name from memory.** Derive it: `~/.claude/plugins/cache/memsearch-plugins/memsearch/<version>/scripts/derive-collection.sh <project-dir>`. A bare `memsearch index` writes to the default `memsearch_chunks` collection, reports success, and the hooks then find nothing.
- **milvus-lite holds an exclusive `flock`** - one process at a time, for reads too. A `stats` call during an index run fails with `BlockingIOError`. Check `pgrep -f "memsearch index"` first; a SessionStart hook may already be rebuilding.
- Opening a session in a project makes its own hook re-index it automatically. Projects you rarely open stay broken until you do it by hand.
- `GOAWAY / too_many_pings` (gRPC) and `pthread_setaffinity_np failed` (ONNX) during indexing are cosmetic.
- There is nothing to gain by changing the summarize model. The per-turn summarizer already defaults to `haiku` in both 0.4.6 and 0.4.17.

---

## SSHFS Access from Nobara

The `/root` directory (containing `homelab`, `learning`, `youtube`) is accessible from Nobara via SSHFS.

Nobara's root SSH key (`root@nex-pc`) is in `/root/.ssh/authorized_keys` on this LXC. Nobara mounts `/root` via a systemd service - see [NFS Setup Documentation](../proxmox/14_NFS-Setup_Documentation.md) for the client-side config.

### Authorized SSH keys on this LXC

| Key | User | Notes |
|-----|------|-------|
| personal key (comment is an email address) | nex (Nobara) | Personal key |
| `termux` | nex (Android/Termux) | Mobile access |
| `root@nex-pc` | root (Nobara) | Used by systemd SSHFS service |
| `claude-mgmt` | root (LXC 109) | Outbound SSH to Nobara (nex@192.168.0.100) |

## Incidents

### 2026-04-08 - SSH/NFS outage after Proxmox + LXC update

**Symptom:** After updating Proxmox and all LXCs, SSH to LXC 109 hung (no error, no refused - just timeout). NFS/SSHFS from Nobara also failed. All other LXCs were fine. Ping from outside showed 100% packet loss, but from inside LXC 109, ping to LAN hosts worked fine.

**Root cause:** `tailscale set --accept-routes=true` had been set on LXC 109 for k3s cluster access. pve advertises `192.168.0.0/24` as a Tailscale subnet route. After the LXC restart (update), Tailscale re-applied the route: `192.168.0.0/24 dev tailscale0` appeared in routing table 52. Policy rule `5270: from all lookup 52` runs before the main table (32766), so all outbound packets to LAN IPs were routed through Tailscale instead of eth0. TCP SYN-ACK replies went via Tailscale → pve subnet router → back to originator, which broke the TCP handshake. ICMP ping appeared to work asymmetrically (roundabout via Tailscale), masking the problem.

**Fix:**
```bash
ip route del 192.168.0.0/24 table 52          # immediate fix
tailscale set --accept-routes=false           # permanent fix
systemctl restart tailscaled
```

Also removed `firewall=1` from LXC 109's Proxmox config (`/etc/pve/lxc/109.conf`) as part of diagnosis - this had no effect on the issue but the fwbr is no longer needed.

**Prevention:** Never use `accept-routes=true` on LXC 109. Use `/etc/hosts` entries for Tailscale hostname resolution instead. See k3s-cluster.md step 5.

---

### 2026-08-03 - Tailscale sessions freezing, and a silently failed sshd

**Symptom:** Remote SSH and code-server sessions to this LXC over Tailscale froze for seconds at a time and sometimes dropped, while every other host on the same LAN was fine. Separately, the phone lost all internet for a while after disabling Tailscale, with a "DNS unavailable" warning from the app.

**Root cause 1 - UDP port collision.** Four Tailscale nodes (pve, this LXC, docker-host, alpine-komodo) were all bound to the default UDP 41641 behind a single Archer C6 whose UPnP runs in `method=single` mode, so only one of them could hold the external port mapping. pve won it; this LXC kept flapping between a direct path and a DERP relay, and each switch is a few seconds of blackholed packets. Mobile carrier symmetric CGNAT (a new source port on every negotiation) made it worse.

**Root cause 2 - tailnet DNS.** The tailnet's global nameserver was 192.168.0.111 (AdGuard), a LAN-only address, so every DNS query from a remote device had to traverse the tunnel. When the path above flapped, all name resolution died, not just homelab names.

**Fix:** one UDP port per node (this LXC moved to 41642), and the global nameserver removed from the Tailscale admin console, keeping only the `lan -> 192.168.0.111` split DNS route.

**Root cause 3 - found while hardening, unrelated.** Both `ssh.service` and `ssh.socket` were enabled, so sshd bound port 22 standalone at boot while the socket also owned it. A `systemctl reload ssh` made sshd re-exec, fail to rebind (`Address already in use`) and die - but logins kept working because the socket re-triggered the service, so the failed unit went unnoticed. Fixed with `systemctl disable ssh.service` (socket activation retained). Under socket activation, prefer `systemctl restart ssh.socket ssh.service` over `reload`.

**Hardening applied:** `ClientAliveInterval 30` + `ClientAliveCountMax 6` in `/etc/ssh/sshd_config` (was `0`, so a session behind a blackholed path hung indefinitely).

Full write-up with diagnostic commands: [31 - Tailscale Port Collision + DNS Audit](../proxmox/31_Tailscale_Port_Collision_DNS_Audit.md).

---

## Lessons Learned

- **No root password by default:** Community script-based LXC containers do not receive a root password during provisioning. SSH password login is also disabled. The only way to add SSH keys initially is via `pct exec` from the Proxmox host.
- **`pct exec` interactive commands fail:** Running interactive commands like `passwd` via `pct exec` does not work because there is no TTY. Use `chpasswd` for non-interactive password setting: `echo 'root:password' | chpasswd`.
- **Key-based SSH is the right approach:** Rather than enabling password auth, it's cleaner to inject the public key directly via `pct exec` and keep `PasswordAuthentication` at its default.
- **MCP token security:** Store API tokens in `~/.secrets/` with chmod 600, and use wrapper scripts to pass them as environment variables - never put tokens directly in config files.
- **Tailscale accept-routes breaks LAN SSH:** If pve advertises the homelab LAN subnet (`192.168.0.0/24`) via Tailscale and a container has `accept-routes=true`, all LAN traffic routes through Tailscale (table 52 takes priority). Use `/etc/hosts` entries with Tailscale IPs instead.
- **Static IP is mandatory:** DHCP can cause IP changes after restarts/updates, breaking SSHFS mounts on Nobara. `/etc/network/interfaces` must use `inet static` with address 192.168.0.204. Also update `/etc/pve/lxc/109.conf` on the Proxmox host: `ip=192.168.0.204/24,gw=192.168.0.1`.
- **SSH watchdog:** `/etc/systemd/system/ssh.service.d/restart.conf` with `Restart=always, RestartSec=5` ensures SSH restarts automatically if it crashes after an update.
- **One Tailscale UDP port per node behind the same router:** the Archer C6's UPnP is `method=single`, so it maps external UDP 41641 to exactly one internal host. Nodes that lose the race cannot hold a direct path and keep flapping to DERP, which interactive sessions feel as freezes. There is no `tailscale set --port` - set `PORT=` in `/etc/default/tailscaled` (or `port=` in `/etc/conf.d/tailscale` on Alpine) and restart the daemon.
- **Never point the tailnet global nameserver at a LAN-only IP:** it makes every remote DNS query depend on the subnet router being reachable. Use a split DNS route scoped to the `lan` domain instead, and leave the global resolver empty so clients fall back to their own.
- **A failed systemd unit can hide behind a working service:** with socket activation `ssh.socket` keeps serving even when `ssh.service` is dead, so `systemctl --failed` is not enough. Verify SSH with an actual connection from another host.
- **Don't trust `systemctl reload ssh` on a socket-activated host:** sshd re-execs on SIGHUP and tries to bind port 22 itself, which systemd already owns.
- **`/etc/resolv.conf` doesn't match the documented static DNS:** the network config above lists `192.168.0.111` (AdGuard) as the DNS server, but Tailscale's MagicDNS (`accept-dns`) rewrites `/etc/resolv.conf` at runtime to point at public resolvers (`8.8.8.8`, `1.1.1.1`) with a `tailc6abe2.ts.net` search domain. In practice this means `*.lan` hostnames don't resolve from this host at all. Scripts that need a `*.lan` name from here (e.g. the homelab digest script below) should use `curl --resolve host.lan:443:<caddy-ip>` rather than relying on system DNS.

## Scheduled Tasks

`scripts/homelab-digest.sh` runs daily at 07:00 via root's crontab (`0 7 * * * /root/homelab/scripts/homelab-digest.sh`). It's a plain bash script (no LLM involved - see the agentos doc's "Homelab Monitoring" section for why) that SSHes into pve and the docker host to collect LVM thin-pool usage, SnapRAID sync/scrub/SMART status, LXC/VM up state, today's backup status, and Docker container health, then posts a summary to the `homelab-digest` ntfy topic (`https://ntfy.lan`, proxied via Caddy from agentos/LXC 113).
