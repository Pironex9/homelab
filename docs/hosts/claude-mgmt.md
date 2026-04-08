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
