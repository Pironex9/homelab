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
| ssh.service | active | OpenSSH server (Restart=always, RestartSec=5) |
| cron.service | active | Scheduled tasks |

## Open Ports

| Port | Protocol | Notes |
|------|----------|-------|
| 22 | TCP | SSH access |

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

## SSHFS Access from Nobara

The `/root` directory (containing `homelab`, `learning`, `youtube`) is accessible from Nobara via SSHFS.

Nobara's root SSH key (`root@nex-pc`) is in `/root/.ssh/authorized_keys` on this LXC. Nobara mounts `/root` via a systemd service - see [NFS Setup Documentation](../proxmox/14_NFS-Setup_Documentation.md) for the client-side config.

### Authorized SSH keys on this LXC

| Key | User | Notes |
|-----|------|-------|
| `xnex88@hotmail.com` | nex (Nobara) | Personal key |
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

## Lessons Learned

- **No root password by default:** Community script-based LXC containers do not receive a root password during provisioning. SSH password login is also disabled. The only way to add SSH keys initially is via `pct exec` from the Proxmox host.
- **`pct exec` interactive commands fail:** Running interactive commands like `passwd` via `pct exec` does not work because there is no TTY. Use `chpasswd` for non-interactive password setting: `echo 'root:password' | chpasswd`.
- **Key-based SSH is the right approach:** Rather than enabling password auth, it's cleaner to inject the public key directly via `pct exec` and keep `PasswordAuthentication` at its default.
- **MCP token security:** Store API tokens in `~/.secrets/` with chmod 600, and use wrapper scripts to pass them as environment variables - never put tokens directly in config files.
- **Tailscale accept-routes breaks LAN SSH:** If pve advertises the homelab LAN subnet (`192.168.0.0/24`) via Tailscale and a container has `accept-routes=true`, all LAN traffic routes through Tailscale (table 52 takes priority). Use `/etc/hosts` entries with Tailscale IPs instead.
- **Static IP is mandatory:** DHCP can cause IP changes after restarts/updates, breaking SSHFS mounts on Nobara. `/etc/network/interfaces` must use `inet static` with address 192.168.0.204. Also update `/etc/pve/lxc/109.conf` on the Proxmox host: `ip=192.168.0.204/24,gw=192.168.0.1`.
- **SSH watchdog:** `/etc/systemd/system/ssh.service.d/restart.conf` with `Restart=always, RestartSec=5` ensures SSH restarts automatically if it crashes after an update.
