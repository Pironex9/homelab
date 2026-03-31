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
| Claude Code | 2.1.50 | Installed via native installer |
| Node.js | 20.20.0 | Required by Claude Code |
| git | 2.39.5 | Version control |
| ripgrep | - | Fast code search, used by Claude Code |

## Running Services

| Service | Status | Description |
|---------|--------|-------------|
| ssh.service | active | OpenSSH server |
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

### GitHub MCP

Connects Claude Code to the GitHub API for repository management.

- **Auth:** Personal access token stored in `~/.secrets/github-token` (chmod 600)
- **Config:** bash wrapper script to avoid plaintext token in config file

```json
{
  "mcpServers": {
    "github": {
      "command": "bash",
      "args": ["-c", "GITHUB_PERSONAL_ACCESS_TOKEN=$(cat ~/.secrets/github-token) npx -y @modelcontextprotocol/server-github"]
    }
  }
}
```

### Karakeep MCP

Connects Claude Code to the Karakeep bookmark manager.

- **Auth:** API key stored in `~/.secrets/karakeep-api-key` (chmod 600)
- **Package:** `@karakeep/mcp` (official)

```json
{
  "mcpServers": {
    "karakeep": {
      "command": "bash",
      "args": ["-c", "KARAKEEP_API_ADDR=http://192.168.0.128:3000 KARAKEEP_API_KEY=$(cat ~/.secrets/karakeep-api-key) npx -y @karakeep/mcp"]
    }
  }
}
```

### n8n MCP

Connects Claude Code to the n8n workflow automation instance.

- **Scope:** project-scoped to `/root/homelab`
- **Auth:** API key stored in `~/.secrets/n8n-api-key` (chmod 600)

## SSHFS Access from Nobara

The `/root` directory (containing `homelab`, `learning`, `youtube`) is accessible from Nobara via SSHFS.

Nobara's root SSH key (`root@nex-pc`) is in `/root/.ssh/authorized_keys` on this LXC. Nobara mounts `/root` via a systemd automount unit - see [NFS Setup Documentation](../proxmox/14_NFS-Setup_Documentation.md) for the client-side config.

### Authorized SSH keys on this LXC

| Key | User | Notes |
|-----|------|-------|
| `xnex88@hotmail.com` | nex (Nobara) | Personal key |
| `termux` | nex (Android/Termux) | Mobile access |
| `root@nex-pc` | root (Nobara) | Used by systemd SSHFS automount |

## Lessons Learned

- **No root password by default:** Community script-based LXC containers do not receive a root password during provisioning. SSH password login is also disabled. The only way to add SSH keys initially is via `pct exec` from the Proxmox host.
- **`pct exec` interactive commands fail:** Running interactive commands like `passwd` via `pct exec` does not work because there is no TTY. Use `chpasswd` for non-interactive password setting: `echo 'root:password' | chpasswd`.
- **Key-based SSH is the right approach:** Rather than enabling password auth, it's cleaner to inject the public key directly via `pct exec` and keep `PasswordAuthentication` at its default.
- **MCP token security:** Store API tokens in `~/.secrets/` with chmod 600, and use wrapper scripts to pass them as environment variables - never put tokens directly in config files.
