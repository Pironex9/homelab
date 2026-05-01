# n8n LXC

## Overview

| Property | Value |
|----------|-------|
| Hostname | n8n |
| IP Address | 192.168.0.112 |
| VMID | 107 |
| OS | Debian GNU/Linux 13 (trixie) |
| Purpose | Workflow automation platform |
| Web UI | http://192.168.0.112:5678 |

## Installed Software

| Package | Version | Notes |
|---------|---------|-------|
| Node.js | 22.22.0 | Installed via NodeSource repository |
| npm | 11.8.0 | |
| n8n | 2.4.8 | Installed globally via npm |

## Running Services

| Service | Status | Description |
|---------|--------|-------------|
| n8n.service | active | n8n workflow automation |
| ssh.service | active | OpenSSH server |
| cron.service | active | Scheduled tasks |

## Open Ports

| Port | Protocol | Process | Notes |
|------|----------|---------|-------|
| 5678 | TCP | node (n8n) | Web UI, accessible from LAN |
| 22 | TCP | sshd | SSH access |

## n8n Configuration

### Systemd Service

Path: `/etc/systemd/system/n8n.service`

```ini
[Unit]
Description=n8n

[Service]
Type=simple
EnvironmentFile=/opt/n8n.env
ExecStart=n8n start

[Install]
WantedBy=multi-user.target
```

### Environment Variables

Path: `/opt/n8n.env`

```env
N8N_SECURE_COOKIE=false
N8N_PORT=5678
N8N_PROTOCOL=http
N8N_HOST=192.168.0.112
```

> **Note:** `N8N_SECURE_COOKIE=false` is required because the web UI is served over plain HTTP (no HTTPS/reverse proxy). Without this setting, session cookies would fail on non-HTTPS connections.

### Binary Location

n8n is installed globally via npm:

```
/usr/lib/node_modules/n8n/  →  symlinked as  /usr/bin/n8n
```

## Data Directory

Path: `/.n8n/` (root of the filesystem)

| File/Directory | Description |
|----------------|-------------|
| `database.sqlite` | Main SQLite database (workflows, credentials, executions) |
| `database.sqlite-shm` | SQLite shared memory file |
| `database.sqlite-wal` | SQLite write-ahead log |
| `config` | Encrypted credentials key |
| `binaryData/` | Binary attachments from workflow executions |
| `nodes/` | Custom/community nodes |
| `n8nEventLog.log` | Current event log |

## Service Management

```bash
# Check status
systemctl status n8n

# Restart
systemctl restart n8n

# View logs
journalctl -u n8n -f

# View logs (last 100 lines)
journalctl -u n8n -n 100
```

## MCP Integration

This n8n instance is connected to Claude Code via n8n's **built-in official MCP server** (HTTP transport). Claude Code can create, read, update, and trigger workflows directly from the terminal.

- **Endpoint:** `http://192.168.0.112:5678/mcp-server/http`
- **Auth:** JWT token generated in n8n UI under Settings > API > MCP Server
- **Token stored:** `~/.secrets/n8n-official-token` on LXC 109 (claude-mgmt), chmod 600

The official MCP server uses an SDK-based workflow builder: Claude first reads node type definitions (`get_node_types`), then writes TypeScript workflow code, validates it, and only then saves it - avoiding invalid parameter names that the old unofficial package was prone to.

See [claude-mgmt.md](claude-mgmt.md) for the `claude mcp add` registration command.

## Lessons Learned

- **Data directory at filesystem root:** n8n stores its data in `/.n8n/` (filesystem root), not in a home directory. This is because the service runs as root and n8n defaults to `$HOME/.n8n` - on this system `$HOME` is `/`. Be mindful when planning backups or migrations.
- **`N8N_SECURE_COOKIE=false` is mandatory for plain HTTP:** Without this setting, the browser refuses to store the session cookie over HTTP, making login impossible. Only remove this flag if HTTPS is configured (e.g., via a reverse proxy).
- **SQLite as backend:** n8n uses SQLite by default (no PostgreSQL setup). Suitable for a single-node homelab deployment, but SQLite WAL files (`-shm`, `-wal`) must be included together when backing up the database, or the backup will be corrupt.
- **NodeSource repository:** Node.js was installed from the NodeSource apt repository (not Debian's default), providing a much newer version (v22 vs Debian's older packages). Check the repository when planning updates.
