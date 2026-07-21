# AGENTS.md

Codex working notes for this repository. These instructions apply to the whole
repo unless a more specific `AGENTS.md` exists deeper in the tree.

Infrastructure-as-code for a self-hosted homelab on Proxmox VE 9.1: Docker Compose stacks, setup docs, automation scripts - not application code.

## Key Directories

- `compose/` - all Docker Compose stacks; also read `compose/CLAUDE.md` before editing there
- `docs/` - published MkDocs portfolio site; also read `docs/CLAUDE.md` before editing there
- `scripts/backup.sh` - Restic backup automation
- `private/` - gitignored personal files (never commit); `private/todo.md` = planned tasks

## Infrastructure Overview

| Host | IP | Role |
|---|---|---|
| pve (Proxmox 9.1, HP EliteDesk 800 G4) | 192.168.0.109 | hypervisor |
| LXC 100 docker-host | 192.168.0.110 | 22 Docker stacks |
| VM 101 haos | 192.168.0.202 | Home Assistant OS |
| LXC 102 adguard | 192.168.0.111 | DNS |
| LXC 103 vaultwarden | 192.168.0.219 | passwords (Alpine, `pct exec` only) |
| LXC 105 komodo | 192.168.0.105 | GitOps deploy, port 9120 (Alpine) |
| LXC 106 karakeep / 107 n8n | .128 / .112 | apps |
| LXC 109 claude-mgmt | 192.168.0.204 | this machine |
| LXC 110 caddy / 111 uzlet | .208 / .115 | proxy / scraper |
| LXC 113 agentos | 192.168.0.71 | Hermes + Odysseus agentic OS |

Storage: MergerFS 8.1TB + SnapRAID (4 USB HDDs). Remote: Tailscale (private) + Pangolin on Hetzner VPS (public). Backups: Restic (local + NFS). K3s: 3x Dell OptiPlex (192.168.2.x, separate location, kubectl from this LXC).

## LXC Access

- Most LXCs: `ssh root@<ip>`; community-script containers (e.g. 103): `pct exec <id> -- bash` from pve, no SSH
- Always `cat /etc/os-release` first - Alpine uses `apk` + `rc-service`, not `apt` + `systemctl`

## Rules

- **Never `git push` unless explicitly asked.** Commit locally freely.
- Use Context7 MCP proactively for any library/framework/CLI question - `resolve-library-id` then `query-docs` before answering.
- Never rely solely on training knowledge for technical questions - search or inspect current docs first for versions, pricing, and third-party configs.
- Never use em dashes; use plain hyphens.
- `.env` and `private/` are gitignored - never commit them; keep `.env.example` updated.
- Docs/commits: redact API keys with placeholders; private LAN IPs (192.168.0.x) are NEVER redacted.

## Codex Workflow

- Start by checking `git status --short` and avoid overwriting unrelated local changes.
- Prefer `rg` / `rg --files` for repo discovery.
- Use `apply_patch` for manual file edits when sandboxing permits it; otherwise use the smallest equivalent patch command.
- Keep changes scoped: this repo is infrastructure documentation and deployment config, not an application codebase.
- When changing compose stacks, validate YAML where possible and preserve existing deployment conventions.
- When changing docs, keep MkDocs navigation and `docs/README.md` in sync.
