# Claude Code Management LXC Setup

**Date:** 2026-02-22
**Hostname:** claude-mgmt
**IP address:** 192.168.0.204
**VMID:** 109
**System:** Proxmox VE 9.1

---

## Overview

This document describes the creation and configuration of a dedicated management LXC container (`claude-mgmt`, VMID 109) on the Proxmox homelab. The purpose of this container is to run [Claude Code](https://claude.ai/code) - Anthropic's agentic terminal-based AI assistant - and use it to automate documentation of the homelab infrastructure via SSH.

Rather than installing Claude Code directly on the Proxmox host (which would be a security risk), a dedicated, isolated container is used. If something goes wrong, the container can be destroyed and rebuilt in minutes without touching the host.

---

## Infrastructure Overview

The following LXC containers and VMs are under management. For individual service setup guides, see the linked documentation.

| VMID | Name               | IP             | Purpose                                           | Doc |
|------|--------------------|----------------|---------------------------------------------------|-----|
| 100  | docker-host        | 192.168.0.110  | Docker containers (Jellyfin, Immich, etc.)        | [02](./02_Proxmox_Docker_LXC_Setup_-_Detailed_Process.md) |
| 102  | adguard-home       | 192.168.0.111  | DNS-level ad blocking                             | [05](./05_AdGuard_Home_Setup_Dedicated_LXC_Tailscale_DNS_Integration.md) |
| 103  | alpine-vaultwarden | -              | Password manager (excluded from SSH intentionally)| [09](./09_Scanopy_Vaultwarden.md) |
| 104  | scanopy            | -              | Network scanner and topology visualizer           | [09](./09_Scanopy_Vaultwarden.md) |
| 105  | alpine-komodo      | 192.168.0.105  | Komodo deployment manager (Alpine Linux)          | [17](./17_Komodo_complete_setup.md) |
| 106  | karakeep           | 192.168.0.128  | Bookmarking service                               | [10](./10_Helper_Script_LXCs.md) |
| 107  | n8n                | 192.168.0.112  | Workflow automation                               | [10](./10_Helper_Script_LXCs.md) |
| 108  | ollama             | 192.168.0.231  | Local LLM inference                               | [10](./10_Helper_Script_LXCs.md) |
| 109  | claude-mgmt        | 192.168.0.204  | Management node (this container)                  | - |

The Proxmox host itself is reachable at `192.168.0.109`.

---

## Step 1 - Creating the Management LXC

The container was created using the Proxmox web UI with the following parameters. Debian 12 was chosen over Alpine Linux because Claude Code's native installer works out-of-the-box on Debian without requiring additional compatibility packages. Alpine uses `musl libc` instead of `glibc`, which can cause conflicts with Node.js-based tools like MCP servers.

| Parameter       | Value                                      |
|-----------------|--------------------------------------------|
| Template        | `debian-12-standard_12.12-1_amd64.tar.zst` |
| Hostname        | `claude-mgmt`                              |
| CPU cores       | 2                                          |
| Memory          | 2048 MB                                    |
| Disk            | 8 GB on `local-lvm`                        |
| Network         | `vmbr0`, DHCP                              |
| Unprivileged    | Yes                                        |
| Nesting feature | Enabled (`features: nesting=1`)            |
| Start at boot   | Yes                                        |

Nesting is enabled because it exposes `procfs` and `sysfs` to the container, which is required by systemd to properly isolate services - and may be needed if Docker is added to this container in the future.

> For general LXC creation steps, see [Doc 02 - Proxmox Docker LXC Setup](./02_Proxmox_Docker_LXC_Setup_-_Detailed_Process.md).

---

## Step 2 - Installing Claude Code

After entering the container with `pct enter 109`, the following packages were installed first. Node.js 20 is required not for Claude Code itself (the native installer is standalone), but for MCP servers, which are typically distributed as Node.js packages run via `npx`.

```bash
apt update && apt upgrade -y
apt install -y curl git ripgrep openssh-client

# Node.js 20 via NodeSource (the default Debian repo has outdated versions)
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install -y nodejs
```

Claude Code was then installed using the official native installer. The `sudo`-less install is intentional - the installer places the binary in user space (`~/.local/bin/`), and using `sudo` would cause permission issues.

```bash
curl -fsSL https://claude.ai/install.sh | bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

Installation was verified with:

```bash
claude --version  # returned: 2.1.50 (Claude Code)
claude doctor     # all checks passed
```

Authentication was completed using a Claude Pro subscription. Because the LXC has no display, `claude` printed a URL to the terminal which was opened in a browser on the local workstation. After logging in, the session token was automatically passed back to the container.

---

## Step 3 - Project Directory and CLAUDE.md

A project directory was created to serve as the root for all homelab documentation. Git was initialised here so that documentation can be version-controlled and published to GitHub as part of a portfolio.

```bash
mkdir -p /root/homelab/docs/lxc
cd /root/homelab
git init
```

Claude Code was then started inside this directory (`claude`), the folder was trusted, and `/init` was run to generate a starter `CLAUDE.md`. This file is the persistent memory system for Claude Code - it is automatically read at the start of every session, which solves the context-window exhaustion problem that occurs with browser-based Claude when working through long installation sessions.

The `CLAUDE.md` was extended with homelab-specific instructions including SSH hostnames, documentation structure, language preference (English, for portfolio use), and a requirement to include a "Lessons Learned" section at the end of every document.

---

## Step 4 - SSH Key Infrastructure

For Claude Code to be genuinely useful - connecting to other containers, reading their configs, and writing documentation based on the real state of the system - it needs passwordless SSH access to every container it manages. A dedicated SSH keypair was generated on `claude-mgmt`:

```bash
ssh-keygen -t ed25519 -C "claude-mgmt" -f ~/.ssh/id_ed25519 -N ""
```

The `ed25519` algorithm was chosen because it produces smaller keys than RSA while being more secure.

### Distributing the key

Most containers were created with community scripts that do not set a root password, making `ssh-copy-id` fail. The solution was to inject the public key directly from the Proxmox host using `pct exec`, which runs a command inside a container without needing SSH at all:

```bash
# Run on the Proxmox host for each VMID
for VMID in 100 102 106 107 108; do
  pct exec $VMID -- bash -c 'mkdir -p /root/.ssh && chmod 700 /root/.ssh && \
    echo "ssh-ed25519 AAAA...claude-mgmt" >> /root/.ssh/authorized_keys && \
    chmod 600 /root/.ssh/authorized_keys'
done
```

The `alpine-komodo` container (105) required a different approach because it runs Alpine Linux, which uses `apk` and `rc-service` instead of `apt` and `systemctl`. See [Doc 17 - Komodo Setup](./17_Komodo_complete_setup.md) for more on Alpine-specific differences.

```bash
pct exec 105 -- bash -c "apk add openssh && rc-update add sshd && rc-service sshd start && \
  mkdir -p /root/.ssh && chmod 700 /root/.ssh && \
  echo 'ssh-ed25519 AAAA...claude-mgmt' >> /root/.ssh/authorized_keys && \
  chmod 600 /root/.ssh/authorized_keys"
```

The Proxmox host itself was added via standard `ssh-copy-id` from within the claude-mgmt container. This allows Claude Code to run `pct list`, `pct exec`, and other Proxmox management commands directly over SSH.

### Security decision - Vaultwarden excluded

The `alpine-vaultwarden` container (VMID 103) was deliberately excluded from SSH access. It stores all passwords and secrets for the homelab. Granting any automated tool access to it would be an unnecessary risk - documentation for that container is written manually. See [Doc 09 - Vaultwarden](./09_Scanopy_Vaultwarden.md) and [Doc 12 - Security Configuration](./12_Security_Configuration_Guide.md) for background on the security posture.

### Verification

All connections were tested from `claude-mgmt`:

```bash
ssh root@192.168.0.109 "hostname && pct list"   # Proxmox host - OK
ssh root@192.168.0.110  "hostname && uptime"     # docker-host - OK
ssh root@192.168.0.111 "hostname && uptime"     # adguard-home - OK
ssh root@192.168.0.128 "hostname && uptime"    # karakeep - OK
ssh root@192.168.0.112     "hostname && uptime"     # n8n - OK
ssh root@192.168.0.231  "hostname && uptime"     # ollama - OK
ssh root@192.168.0.105  "hostname && uptime"     # alpine-komodo - OK
```

All returned output without prompting for a password.

---

## Step 5 - SSH Config Aliases

To avoid using raw IP addresses in commands and in `CLAUDE.md`, a `~/.ssh/config` file was created on `claude-mgmt` with named aliases for every managed host:

```bash
cat > ~/.ssh/config << 'EOF'
Host proxmox
    HostName 192.168.0.109
    User root
    IdentityFile ~/.ssh/id_ed25519

Host docker-host
    HostName 192.168.0.110
    User root
    IdentityFile ~/.ssh/id_ed25519

Host adguard
    HostName 192.168.0.111
    User root
    IdentityFile ~/.ssh/id_ed25519

Host komodo
    HostName 192.168.0.105
    User root
    IdentityFile ~/.ssh/id_ed25519

Host karakeep
    HostName 192.168.0.128
    User root
    IdentityFile ~/.ssh/id_ed25519

Host n8n
    HostName 192.168.0.112
    User root
    IdentityFile ~/.ssh/id_ed25519

Host ollama
    HostName 192.168.0.231
    User root
    IdentityFile ~/.ssh/id_ed25519
EOF

chmod 600 ~/.ssh/config
```

The `chmod 600` is mandatory - SSH silently ignores the config file if permissions are too open.

---

## Step 6 - CLAUDE.md Configuration

The `CLAUDE.md` file at `/root/homelab/CLAUDE.md` serves as Claude Code's persistent memory. It is automatically read at the start of every session, eliminating the need to re-explain the infrastructure each time. This also solves the context exhaustion problem that occurs with browser-based Claude during long installation sessions.

```bash
cat > /root/homelab/CLAUDE.md << 'EOF'
# CLAUDE.md - Homelab Management

This file is automatically read by Claude Code at the start of every session.

## Infrastructure

- Proxmox host: `proxmox` (192.168.0.109)
- This container: `claude-mgmt` (192.168.0.204, VMID 109)
- All SSH connections use `~/.ssh/config` aliases, key-based auth, no passwords

## Managed Hosts

| Alias       | IP            | OS     | Purpose                    |
|-------------|---------------|--------|----------------------------|
| proxmox     | 192.168.0.109 | Debian | Proxmox VE host            |
| docker-host | 192.168.0.110 | Debian | Docker containers          |
| adguard     | 192.168.0.111 | Debian | AdGuard Home DNS           |
| komodo      | 192.168.0.105 | Alpine | Komodo deployment manager  |
| karakeep    | 192.168.0.128 | Debian | Bookmarking service        |
| n8n         | 192.168.0.112 | Debian | Workflow automation        |
| ollama      | 192.168.0.231 | Debian | Local LLM inference        |

## Excluded from Automation

- `alpine-vaultwarden` (VMID 103) - password manager, never access via SSH or automation

## Documentation Workflow

- Documentation root: `/root/homelab/docs/`
- LXC docs: `/root/homelab/docs/lxc/<hostname>.md`
- Language: English (portfolio purpose)
- When documenting an LXC:
  1. SSH in and check OS: `cat /etc/os-release`
  2. Collect: installed packages, running services, open ports, docker containers if any, important config files
  3. Write markdown documentation to `docs/lxc/<hostname>.md`
  4. Every document must end with a "Lessons Learned" section

## Important Notes

- Always check OS before running commands: `cat /etc/os-release`
- Alpine Linux: use `apk` and `rc-service` instead of `apt` and `systemctl`
- When context gets long, use `/compact` before continuing
- Before starting a new doc, read existing docs in `/root/homelab/docs/` for consistency
- Proxmox management commands (pct list, pct exec) run via: `ssh proxmox "pct list"`
EOF
```

---

## Step 7 - GitHub MCP Server

The GitHub MCP server was configured on the local workstation inside the portfolio repo. This gives Claude Code direct access to 26 GitHub API tools - reading commits, managing issues, creating PRs, and more - without needing manual `git` commands for every operation.

### Prerequisites - Node.js

The workstation did not have Node.js installed. The GitHub MCP server runs via `npx`, so Node.js was installed first (example for Fedora/Nobara):

```bash
sudo dnf install nodejs npm -y
npx --version
```

### GitHub Personal Access Token

A token was generated at GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic), with `repo`, `read:org`, and `workflow` scopes. Added to shell config for persistence:

```bash
echo 'export GITHUB_PERSONAL_ACCESS_TOKEN=your_github_token_here' >> ~/.bashrc
source ~/.bashrc
```

### MCP Server configuration

The token must be explicitly passed in the MCP server env block - simply having it as a shell variable is not enough, as Claude Code spawns the MCP server as a subprocess and does not inherit the parent shell environment automatically.

```bash
claude mcp remove github  # remove if already added without token
claude mcp add github \
  -e GITHUB_PERSONAL_ACCESS_TOKEN=$GITHUB_PERSONAL_ACCESS_TOKEN \
  -- npx -y @modelcontextprotocol/server-github
```

This writes to `~/.claude.json` scoped to the project directory - the MCP server is only active when Claude Code is started from that directory.

### Verification

```
/mcp → github · ✔ connected · 26 tools
```

> **Note:** The package `@modelcontextprotocol/server-github` shows a deprecation warning as of version 2025.4.8. It still functions correctly but may need to be replaced with an alternative in the future.

---

## Container Reference

Current state of the `claude-mgmt` container, auto-documented by Claude Code running inside it.

### System Overview

| Property   | Value                                    |
|------------|------------------------------------------|
| Hostname   | claude-mgmt                              |
| IP Address | 192.168.0.204                            |
| VMID       | 109                                      |
| OS         | Debian GNU/Linux 12 (bookworm)           |
| Purpose    | Claude Code homelab management container |

### Installed Software

| Package     | Version | Notes                                 |
|-------------|---------|---------------------------------------|
| Claude Code | 2.1.50  | Installed via native installer        |
| Node.js     | 20.20.0 | Required by Claude Code MCP servers   |
| git         | 2.39.5  | Version control                       |
| ripgrep     | latest  | Fast code search, used by Claude Code |

### Running Services

| Service          | Status | Description                     |
|------------------|--------|---------------------------------|
| ssh.service      | active | OpenSSH server                  |
| cron.service     | active | Scheduled tasks                 |
| postfix.service  | active | Mail transport (localhost only) |
| systemd-networkd | active | Network configuration           |

### Open Ports

| Port | Protocol | Process | Notes                |
|------|----------|---------|----------------------|
| 22   | TCP      | sshd    | SSH access           |
| 25   | TCP      | postfix | SMTP, localhost only |

### SSH Access

SSH uses key-based authentication only. Password login for root is disabled by default (`PermitRootLogin prohibit-password`).

One authorized key is registered (comment: `termux`), stored in `/root/.ssh/authorized_keys`.

**Adding a new SSH key** - since password login is disabled, new keys must be added via the Proxmox host:

```bash
ssh proxmox "pct exec 109 -- bash -c 'echo \"<public-key>\" >> /root/.ssh/authorized_keys'"
```

### MCP Servers

| Server   | Scope   | Description                                      |
|----------|---------|--------------------------------------------------|
| github   | project | GitHub API - 26 tools (issues, PRs, commits)    |
| n8n-mcp  | project | Connects to the n8n workflow automation instance |

Config stored in `/root/.claude.json` under the project's `mcpServers` key.

---

## Lessons Learned

**Community scripts and unknown passwords.** Several containers created by [Proxmox VE Helper Scripts](https://community-scripts.github.io/ProxmoxVE/) do not set a root password during installation. When `ssh-copy-id` fails with "Permission denied", the correct approach is to use `pct exec` from the Proxmox host rather than attempting to recover or reset the password. This is faster and does not require modifying the container's authentication configuration.

**Shell quoting with `pct exec`.** When passing a complex bash command through `pct exec`, the outer string must use single quotes and any inner strings must use double quotes. If both use the same quote style, the shell on the Proxmox host misinterprets the command before passing it to the container. The first attempts silently failed - the key was printed to the terminal but never written to the file - which was only caught by running `cat /root/.ssh/authorized_keys` to verify.

**Alpine vs Debian.** Two containers run Alpine Linux (`alpine-vaultwarden`, `alpine-komodo`). Alpine uses `apk` instead of `apt`, and `rc-service`/`rc-update` instead of `systemctl`. Any automation or documentation script that assumes Debian-style tooling will fail silently or with confusing errors on Alpine containers. It is worth checking the OS before running commands: `pct exec <VMID> -- cat /etc/os-release`.

**Proxmox host vs management container IP.** During setup, the Proxmox host IP was briefly confused with the claude-mgmt container IP, since both share part of the address scheme, and the VMID (`109`) matched the last octet of the host IP. Always verify with `pct list` on the host and `ip a` inside the container.

**SSH password login is disabled on claude-mgmt.** The container runs with `PermitRootLogin prohibit-password`, meaning SSH key-based auth is required. If you cannot connect, do not try to reset the SSH password - add your public key via the Proxmox host instead:

```bash
ssh proxmox "pct exec 109 -- bash -c 'echo \"<public-key>\" >> /root/.ssh/authorized_keys'"
```

**`pct exec` cannot run interactive commands.** Running `passwd` via `pct exec` fails because there is no TTY attached. Use `chpasswd` for non-interactive password setting if a password is ever needed:

```bash
pct exec 109 -- bash -c 'echo "root:newpassword" | chpasswd'
```
