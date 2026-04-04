**Date:** 2026-04-04
**Host:** docker-host (LXC 100)
**IP address:** 192.168.0.110

# 23 - Homelable Network Visualization + MCP Setup

## What is Homelable

[Homelable](https://github.com/Pouzor/homelable) is a self-hosted infrastructure visualization and monitoring tool. It provides an interactive drag-and-drop canvas for mapping homelab topology, live node status checks (ping, HTTP, TCP, SSH), automatic network scanning via nmap, and an MCP server for AI integration.

Chosen over alternatives (Scanopy, homelab-hub, RackPeek) because:
- MCP server allows Claude Code to query infrastructure state directly
- Active development (weekly releases)
- Simpler configuration than Scanopy (which was previously attempted but too complex)
- Live health checks complement Uptime Kuma

## Architecture

Three Docker containers running on LXC 100:

| Container | Image | Role |
|-----------|-------|------|
| `homelable-backend` | `ghcr.io/pouzor/homelable-backend:latest` | Python/FastAPI backend, SQLite DB |
| `homelable-frontend` | `ghcr.io/pouzor/homelable-frontend:latest` | React frontend served via nginx |
| `homelable-mcp` | built from `/opt/homelable/mcp` | FastAPI MCP server for AI clients |

Backend and frontend use prebuilt images from GitHub Container Registry. The MCP service has no prebuilt image and is built from source (cloned separately at `/opt/homelable`).

All three containers share an internal bridge network (`homelable`). Only frontend (3001) and MCP (8001) are exposed to the host network.

## Installation

### Prerequisites

Clone the homelable source (needed for MCP build context):

```bash
git clone https://github.com/Pouzor/homelable.git /opt/homelable
mkdir -p /srv/docker-data/homelable
```

Install passlib for bcrypt hash generation:

```bash
apt-get install -y python3-passlib python3-bcrypt
```

### Generate Secrets

```bash
# SECRET_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"

# MCP_API_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"

# MCP_SERVICE_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"

# AUTH_PASSWORD_HASH (replace 'yourpassword')
python3 -c "from passlib.context import CryptContext; print(CryptContext(schemes=['bcrypt']).hash('yourpassword'))"
```

### Komodo Stack Setup

Compose file is in the homelab git repo at `compose/proxmox-lxc-100/homelable/docker-compose.yml`.

**Stack path in Komodo:** `compose/proxmox-lxc-100/homelable`

**Stack Environment (sensitive values, not in git):**

```
SECRET_KEY=<generated>
AUTH_USERNAME=admin
AUTH_PASSWORD_HASH='$2b$12$...'
MCP_API_KEY=<generated>
MCP_SERVICE_KEY=<generated>
```

Note: `AUTH_PASSWORD_HASH` must be wrapped in single quotes because bcrypt hashes contain `$` characters that Docker would otherwise interpret as variable substitution.

### Deploy

In Komodo: Deploy Stack → homelable. Komodo writes the Stack Environment to `.env`, pulls prebuilt images for backend/frontend, and builds the MCP image from `/opt/homelable/mcp`.

**Access:** `http://192.168.0.110:3001` - default credentials `admin / admin` (change immediately after first login).

## Docker Compose

Key design decisions:

- Service names are `backend`, `frontend`, `mcp` (not `homelable-*`) - the frontend nginx config hardcodes `backend` as the upstream hostname, so Docker DNS must resolve that name
- `env_file: .env` on backend and mcp services - Komodo writes Stack Environment to `.env`, which the containers read for secrets
- Non-sensitive vars (`SCANNER_RANGES`, `STATUS_CHECKER_INTERVAL`, `CORS_ORIGINS`) are hardcoded in the compose file
- `cap_add: NET_RAW` on backend - required for ICMP ping-based status checks

## MCP Integration with Claude Code

The MCP server exposes the homelab topology to Claude Code. This allows Claude to query which nodes are online, trigger network scans, and manage the canvas without the user manually describing the infrastructure.

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `list_nodes` | List all devices on the canvas |
| `get_canvas` | Full topology (nodes + edges) |
| `create_node` | Add a new device |
| `update_node` | Edit device properties |
| `delete_node` | Remove a device |
| `create_edge` | Add a network link |
| `delete_edge` | Remove a link |
| `trigger_scan` | Run nmap scan on configured CIDR ranges |
| `list_pending_devices` | Devices discovered but not yet approved |
| `approve_device` | Add a discovered device to canvas |
| `hide_device` | Dismiss a discovered device |

### Claude Code Configuration

Add to `~/.claude.json` under `mcpServers` for the `/root/homelab` project:

```json
"homelable": {
  "type": "http",
  "url": "http://192.168.0.110:8001/mcp",
  "headers": {
    "X-API-Key": "your_mcp_api_key_here"
  }
}
```

Note: Use `"type": "http"` not `"type": "sse"` - SSE transport is deprecated in Claude Code. The MCP server uses `StreamableHTTP` which is compatible with the HTTP transport type.

## Update Procedure

Since the MCP image is built from source, updates require pulling the upstream repo before redeploying. A Komodo Procedure (`homelable-update`) automates this:

**Stage 1** - Komodo Action `homelable-git-pull`:
```typescript
await komodo.execute_server_terminal({
  server: "LXC 100",
  command: "cd /opt/homelable && git pull",
  init: { command: "bash" },
}, {
  onLine: (line) => console.log(line),
  onFinish: (code) => console.log("Exit code:", code),
});
```

**Stage 2** - Deploy Stack: `homelable`

To update: Komodo > Procedures > `homelable-update` > Run.

## Data

| Path | Description |
|------|-------------|
| `/srv/docker-data/homelable/` | SQLite database (`homelab.db`) |
| `/opt/homelable/` | Upstream source clone (MCP build context) |

## Lessons Learned

- **Service naming matters for Docker DNS:** The frontend nginx config has `proxy_pass http://backend:8000` hardcoded. Naming the backend service `homelable-backend` in docker-compose breaks this - Docker DNS resolves by service name, not container name. Services must be named `backend`, `frontend`, `mcp`.
- **SSE vs HTTP transport in Claude Code:** The MCP server uses `StreamableHTTPSessionManager` (HTTP-based). Configuring Claude Code with `"type": "sse"` causes a "connecting" state that never resolves. Use `"type": "http"` instead - SSE transport is deprecated.
- **MCP has no prebuilt image:** Only backend and frontend are published to `ghcr.io`. The MCP service must be built from source. This requires the upstream repo to be cloned on the Docker host and referenced as an absolute path build context in docker-compose.
- **passlib not available via pip3 on Debian:** The `pip3` command was not installed. Use `apt-get install python3-passlib python3-bcrypt` instead for bcrypt hash generation.
- **Komodo Stack Environment and bcrypt:** When pasting a bcrypt hash into Komodo Stack Environment, wrap it in single quotes in the value field. Bcrypt hashes contain `$2b$` and `$` sequences which are interpreted as shell variable references without quoting.
