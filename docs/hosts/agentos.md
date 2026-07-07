# agentos LXC

## Overview

| Property | Value |
|----------|-------|
| Hostname | agentos |
| IP Address | 192.168.0.71 (DHCP) |
| VMID | 113 |
| OS | Debian GNU/Linux 12 (bookworm) |
| CPU | 2 cores |
| RAM | 4 GB |
| Disk | 20 GB (local-lvm) |
| Features | nesting=1, keyctl=1 (Docker-in-LXC) |
| Purpose | Background "agentic OS" layer - Hermes Agent + Odysseus |

## Running Services

| Service | Description |
|---------|-------------|
| Hermes Agent (native) | Background agent - cron, memory, Telegram gateway, `delegate-to-claude-code` skill |
| Odysseus (Docker Compose) | Web workspace UI at `/opt/odysseus`, port 7000, reverse-proxied at https://agentos.lan |
| chromadb, searxng, ntfy | Odysseus bundled sidecar services (loopback-only) |

## Model Routing

1. Nobara Ollama (`http://192.168.0.100:11434`, model `qwen3:8b`) - primary, free, local
2. DeepSeek API (`deepseek-v4-flash`) - fallback when Nobara is off (`fallback_providers` in `~/.hermes/config.yaml`)
3. LXC 109 Claude Code (via the `delegate-to-claude-code` skill and restricted SSH, `/usr/local/bin/hermes-claude-code.sh`) - deliberate delegation only, not part of the failover chain

Hermes config notes: `model.provider: custom`, `model.context_length: 65536` and
`model.ollama_num_ctx: 65536` (Hermes requires a 64K+ window; it passes `num_ctx`
to Ollama itself), `agent.reasoning_effort: none` (Ollama's qwen3 rejects
OpenAI-style think levels).

## Security

- SSH key `hermes-to-109` (on this host) can only invoke the wrapper script on
  LXC 109, only from this host's IP (`from=` lock in `authorized_keys`,
  verified by attempting the connection from another host) - no interactive
  shell, no other commands
- The wrapper caps task length, sanitizes and logs every invocation to
  `/var/log/hermes-delegate.log` on LXC 109, and runs Claude Code with
  `scripts/hermes-delegate-settings.json` plus `--setting-sources ""` (so the
  interactive session's broad permissions never apply): no arbitrary shell
  (only `git add/commit/status/log/diff` allowed; other commands fail closed
  in headless mode), no network tools, file writes scoped to `/root/homelab`
- Telegram gateway uses DM-pairing - unknown senders get a pairing code, not a response
- Hermes dangerous-command approvals: `approvals.mode: manual`, `approvals.cron_mode: deny`

## Management

- Provisioned manually via `pct create` on pve
- Komodo-integrated: native Periphery agent (systemd, reverse-connect as "LXC 113"); the `odysseus` stack is registered in files_on_host mode (`/opt/odysseus`, `docker-compose.yml`) - status, logs, and redeploy from the Komodo UI, host resource alerts included
- Odysseus updates stay manual by design: `git pull` in `/opt/odysseus`, then redeploy via Komodo (no auto-pull from the third-party upstream repo)
- Homepage tiles: Odysseus (site monitor) and Hermes (ping) in the Automation group
- Hermes updates via `hermes update`
- Odysseus admin login: user `admin`, password in Vaultwarden
