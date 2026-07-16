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
| Hermes WebUI (native, systemd) | Browser UI for Hermes at `/opt/hermes-webui`, port 8787, reverse-proxied at https://hermes.lan |
| Odysseus (Docker Compose) | Web workspace UI at `/opt/odysseus`, port 7000, reverse-proxied at https://agentos.lan |
| chromadb, searxng, ntfy | Odysseus bundled sidecar services (loopback-only) |

## Model Routing

**Hermes:**
1. Nobara Ollama (`http://192.168.0.100:11434`, model `qwen3:8b`) - primary, free, local
2. DeepSeek API (`deepseek-v4-flash`) - configured in the fallback chain (`~/.hermes/config.yaml`) but **not actually functional**: `DEEPSEEK_API_KEY` was never added to `/root/.hermes/.env`. As of 2026-07-16 there is no working fallback - if Nobara is off, Hermes' primary model call just fails. No cloud LLM subscription (xAI Grok OAuth, Nous Portal - the only two `hermes proxy providers` options) is configured either; user declined to set one up.
3. LXC 109 Claude Code (via the `delegate-to-claude-code` skill and restricted SSH, `/usr/local/bin/hermes-claude-code.sh`) - deliberate delegation only, not part of the failover chain

**Reverse direction - Claude Code (LXC 109/111, `/root/homelab` or `/root/uzlet`) offloading to Hermes:** needs no extra setup beyond the existing `ssh agentos` root access. For simple, mechanical subtasks (log/error summaries, boilerplate, one-off lookups), run `ssh agentos "hermes -t <toolset> -z '<task>'"`. Two things matter for correct results:
- **Always pin an unrelated toolset with `-t`** (e.g. `-t vision`). Without it, Hermes runs with its full default toolset (`file`, `terminal`, `code_execution`, ...) and will actually try to write files or run commands on agentos' own filesystem instead of just answering in text - confirmed even `-t ''` doesn't suppress this.
- **For code-fix drafts specifically, override the model with `-m qwen2.5-coder:7b`** instead of the default `qwen3:8b`, and ask for the corrected function/snippet directly rather than a unified diff. Testing (2026-07-16, two synthetic bug-fix cases) found both models produced *broken* diffs when asked for unified-diff output (bad hunk line-accounting, a stray leaked `qwen3` reasoning token) but both produced *correct* code when asked for the plain corrected snippet instead - diff bookkeeping, not code quality, was the actual failure mode. qwen2.5-coder:7b matched qwen3:8b on correctness and was ~18% faster in this role.
- This offload is a token-savings measure only for genuinely trivial, well-bounded work - the output must still be reviewed and applied by hand, never trusted or applied verbatim.

**Odysseus:** auto-discovers models from Nobara Ollama (`LLM_HOST=192.168.0.100` in `/opt/odysseus/.env`); model choice is a UI setting (Settings -> Model / composer footer), not env-configured. `qwen2.5-coder:7b` (pulled 2026-07-15, ~4.7GB) is available as a coding-focused option alongside `qwen3:8b`.

Nobara Ollama also serves Karakeep tagging, SuggestArr, and Immich - all pin their own model by name (`qwen3:8b`), so adding models for Hermes/Odysseus doesn't disturb them. The GPU (RTX 2060 Super, 8GB VRAM) holds one model at a time; concurrent requests for different models cause a swap delay (a few seconds), not a conflict.

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
- Hermes WebUI: password auth enabled (`HERMES_WEBUI_PASSWORD` in `/opt/hermes-webui/.env.local`, mode 600, password in Vaultwarden); binds 0.0.0.0:8787 because Caddy proxies from another LXC
- Telegram gateway uses DM-pairing - unknown senders get a pairing code, not a response
- Hermes dangerous-command approvals: `approvals.mode: manual`, `approvals.cron_mode: deny`

## Management

- Provisioned manually via `pct create` on pve
- Komodo-integrated: native Periphery agent (systemd, reverse-connect as "LXC 113"); the `odysseus` stack is registered in files_on_host mode (`/opt/odysseus`, `docker-compose.yml`) - status, logs, and redeploy from the Komodo UI, host resource alerts included
- Odysseus updates stay manual by design: `git pull` in `/opt/odysseus`, then redeploy via Komodo (no auto-pull from the third-party upstream repo)
- Homepage tiles: Odysseus (site monitor) and Hermes (ping) in the Automation group
- Hermes updates via `hermes update`
- Hermes WebUI (github.com/nesquena/hermes-webui): runs the agent in-process from `~/.hermes` using the agent venv (`/usr/local/lib/hermes-agent/venv`); systemd unit `hermes-webui.service`; update: `git -C /opt/hermes-webui pull && systemctl restart hermes-webui`
- Odysseus admin login: user `admin`, password in Vaultwarden
