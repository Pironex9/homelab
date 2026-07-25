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
1. Google Gemini (`gemini-flash-latest`) - primary as of 2026-07-25 (`~/.hermes/config.yaml`: `model.provider: gemini`, `model.default: gemini-flash-latest`), `GEMINI_API_KEY` in `/root/.hermes/.env`. Flipped from the original order (see history below) once the fallback had proven itself reliable, so the always-on cloud model is the default path and the local GPU is the backup.
2. Nobara Ollama (`http://192.168.0.100:11434`, model `qwen3:8b`) - fallback, configured under `fallback_providers` (`provider: custom`, `base_url`, plus `context_length`/`ollama_num_ctx: 65536` carried onto the fallback entry since Hermes requires a 64K+ window and Ollama won't provide it by default). Not always on (desktop PC, powered off outside active use), but free and private when available.
3. LXC 109 Claude Code (via the `delegate-to-claude-code` skill and restricted SSH, `/usr/local/bin/hermes-claude-code.sh`) - deliberate delegation only, not part of the failover chain

**History:** Ollama was primary / Gemini was fallback from 2026-07-24 until the swap on 2026-07-25. Original provider evaluation, kept for context:
- **Why Gemini, not DeepSeek/Groq:** DeepSeek was the first candidate but was dropped over data-sovereignty concerns (PIPL/National Intelligence Law compel Chinese companies to hand over data on request, no independent judicial review). Groq was tried next (US-based, no such concern) but its free tier caps at 6-8K tokens/minute, and Hermes' full agent request (system prompt + tool schemas) runs ~20K tokens - every fallback call hit a 413 "request too large" error. It also isn't a bundled provider plugin in Hermes v0.18 (only wired for Whisper STT), so it needs a `custom_providers` entry (`base_url: https://api.groq.com/openai/v1`, `key_env: GROQ_API_KEY`, referenced as `provider: custom:groq`) rather than a bare `provider: groq`. Gemini is a first-class Hermes provider, has a 250K TPM free tier (12x the requirement), and - for EU-based accounts specifically - the free tier inherits the paid tier's stricter data-use terms (no training on prompts/responses), which the US free tier does not get.

**Swap verification (2026-07-25):** confirmed both directions live before relying on it:
- Gemini as primary: `hermes chat -q "..."` answered correctly.
- Forced failover: added a bogus `/etc/hosts` entry for `generativelanguage.googleapis.com` (simulates Gemini being unreachable) - Hermes correctly fell through to the local Ollama fallback and answered. Reverted immediately after.
- **Cron jobs snapshot their provider/model at creation time and do NOT follow later changes to the global default** - by design, so an unattended job can't silently start spending on a different (possibly paid) model. After the swap, the existing `homelab-digest-review` job would have skipped every run and alerted instead of running, since it still pointed at the old Ollama snapshot. Fixed by removing and recreating the job so it re-snapshots the new default (`hermes cron remove` + `hermes cron create` with identical parameters). No CLI flag exists in this Hermes version to re-pin a job's provider/model in place.
- **Found an upstream bug while testing:** an invalid `GEMINI_API_KEY` returns Gemini HTTP 400 (`INVALID_ARGUMENT: API key not valid`), which is **not** in Hermes' fallback-trigger list (429/500/502/503/401/403/404 only) - so a bad/revoked key does not fail over to Ollama, it crashes the session instead. Worse, the crash itself is a secondary bug: Hermes' own error-summary code tries to read `response.text` on a streaming httpx response that was never `.read()`'d, so the real "API key not valid" message never reaches the user - only a confusing `httpx.ResponseNotRead: Attempted to access streaming response content` shows up. Reproduced and confirmed via `~/.hermes/logs/errors.log`; not filed upstream yet. **Practical implication: if the Gemini key ever expires/gets revoked, Hermes will NOT quietly fall back to Ollama - it'll error out.** Worth an occasional manual check that the key is still valid.

**Reverse direction - Claude Code (LXC 109/111, `/root/homelab` or `/root/uzlet`) offloading to Hermes:** needs no extra setup beyond the existing `ssh agentos` root access. For simple, mechanical subtasks (log/error summaries, boilerplate, one-off lookups), run `ssh agentos "hermes -t <toolset> -z '<task>'"`. Two things matter for correct results:
- **Always pin an unrelated toolset with `-t`** (e.g. `-t vision`). Without it, Hermes runs with its full default toolset (`file`, `terminal`, `code_execution`, ...) and will actually try to write files or run commands on agentos' own filesystem instead of just answering in text - confirmed even `-t ''` doesn't suppress this.
- **For code-fix drafts specifically, override the model with `-m qwen2.5-coder:7b`** instead of the default `qwen3:8b`, and ask for the corrected function/snippet directly rather than a unified diff. Testing (2026-07-16, two synthetic bug-fix cases) found both models produced *broken* diffs when asked for unified-diff output (bad hunk line-accounting, a stray leaked `qwen3` reasoning token) but both produced *correct* code when asked for the plain corrected snippet instead - diff bookkeeping, not code quality, was the actual failure mode. qwen2.5-coder:7b matched qwen3:8b on correctness and was ~18% faster in this role.
- This offload is a token-savings measure only for genuinely trivial, well-bounded work - the output must still be reviewed and applied by hand, never trusted or applied verbatim.

**Odysseus:** auto-discovers models from Nobara Ollama (`LLM_HOST=192.168.0.100` in `/opt/odysseus/.env`); model choice is a UI setting (Settings -> Model / composer footer), not env-configured. `qwen2.5-coder:7b` (pulled 2026-07-15, ~4.7GB) is available as a coding-focused option alongside `qwen3:8b`.

Nobara Ollama also serves Karakeep tagging, SuggestArr, and Immich - all pin their own model by name (`qwen3:8b`), so adding models for Hermes/Odysseus doesn't disturb them. The GPU (RTX 2060 Super, 8GB VRAM) holds one model at a time; concurrent requests for different models cause a swap delay (a few seconds), not a conflict.

Hermes config notes: the Ollama fallback entry carries `provider: custom`,
`context_length: 65536` and `ollama_num_ctx: 65536` (Hermes requires a 64K+
window; it passes `num_ctx` to Ollama itself) - these moved from `model:` to
`fallback_providers:` when Gemini became primary (2026-07-25). `agent.reasoning_effort: none`
(Ollama's qwen3 rejects OpenAI-style think levels) stays global.

## Homelab Monitoring (ntfy)

The bundled `ntfy` sidecar (Odysseus stack) is used as the push channel for a daily homelab status digest. It's bound to `0.0.0.0:8091` (not loopback-only, unlike chromadb/searxng) so it can be reached over the LAN and proxied through Caddy at `https://ntfy.lan`.

`scripts/homelab-digest.sh` (runs via cron on LXC 109, not on agentos - see the claude-mgmt doc) collects Proxmox/SnapRAID/Docker health over SSH and posts a plain-text summary to the `homelab-digest` topic. This is deliberately a plain bash script, not a Hermes agent task: the data collection is fully deterministic (disk percentages, service up/down, SMART numbers), so routing it through an LLM would add cost and hallucination risk for zero benefit. Hermes/Gemini fallback is reserved for tasks that actually need judgment.

**Message persistence:** `ntfy` mounts a `ntfy-cache` volume at `/var/cache/ntfy`, but by default ntfy keeps its message cache in memory only - the volume sits unused unless a cache file is explicitly configured. Fixed 2026-07-25 by adding `NTFY_CACHE_FILE=/var/cache/ntfy/cache.db` to the `ntfy` service environment in `/opt/odysseus/docker-compose.yml`. Discovered when a manual `pve` reboot (triggered from Nobara, 192.168.0.100) cascaded into an agentos/Docker restart minutes after the 07:00 digest had already published successfully - the message was gone because the container restart wiped the in-memory cache. Verified fix: published a test message, `docker restart odysseus-ntfy-1`, message still present in `/homelab-digest/json?poll=1`.

**Hermes review layer (added 2026-07-25):** the WebUI's scheduled-jobs feature needs the gateway daemon running, which wasn't set up on this native (systemd, not Docker) install - fixed with `hermes gateway install --system --run-as-user root --start-now --start-on-login` (root is fine here since this is a single-purpose LXC; the CLI normally refuses root without an explicit override, and the official security checklist's "never run as non-root" item is a deliberate, documented exception here). A Hermes cron job (`homelab-digest-review`, `hermes cron create '5 7 * * *' ... --script homelab-digest-fetch.sh --deliver origin,telegram`) now runs 5 minutes after the LXC 109 digest, pulls the latest ntfy message via `~/.hermes/scripts/homelab-digest-fetch.sh`, and asks the LLM to compare it against a trend history and flag regressions - delivered to both the WebUI and Telegram (see Telegram Gateway below).

- **Cron jobs don't get Hermes' built-in memory** - `cron/scheduler.py` passes `skip_memory=True` on purpose ("Cron system prompts would corrupt user representations"), confirmed by the `memory` tool returning `"Memory is not available"` when called from a cron run. Day-to-day trend comparison is instead handled by the fetch script itself: it appends a compact one-line summary per day to `~/.hermes/digest-history.log`, which grows unbounded on disk (a daily one-liner costs ~100 bytes - years of it is nothing), while only the last 30 days get injected into the LLM prompt each run, to keep token cost flat over time. The 30-day window is just a constant in the script (`PROMPT_DAYS`), not a hard limit - raise it any time.
- **`approvals.cron_mode: deny` does not block ordinary shell commands** - only a denylist of clearly-destructive patterns (confirmed against the official docs: `rm -r`, `dd`, `mkfs`, `systemctl stop/restart`, SQL `DROP`/`DELETE` etc. - not infra tools like `snapraid`/`lvremove`). First test run gave the cron job its full default toolset (`hermes-cron` mirrors `hermes-cli`: terminal, code_execution, file, browser, computer_use, delegation all enabled) and, unprompted, it wrote a todo list then ran `snapraid scrub && lvs -o+metadata && df -h /backup` as a background terminal process on agentos - a host with no SnapRAID array of its own. Harmless here (wrong host, command just errored out), but a real gap. Fixed two ways:
  1. Per-platform toolset gating: `hermes tools disable terminal code_execution computer_use browser file delegation --platform cron` (the officially documented mechanism, `platform_toolsets.cron` in `config.yaml`) - this job now has read/summarize/memory-adjacent tools only. Verified: re-ran the job, confirmed zero tool calls in the session transcript (`sqlite3 ~/.hermes/state.db`, `messages` table), just a text analysis.
  2. Defense-in-depth `approvals.deny` glob rules (apply to **every** Hermes session, not just cron) for the specific infra commands that caused the incident and aren't in the built-in dangerous-pattern list: `*snapraid sync*`, `*snapraid scrub*`, `*snapraid fix*`, `*snapraid -d*`, `*lvremove*`, `*vgreduce*`, `*pvremove*`. These are hard-blocked unconditionally, even before `--yolo`/`approvals.mode: off` are consulted.
  
  **Lesson: any new Hermes cron job should get its toolset explicitly reviewed with `hermes tools list --platform cron` before the first real (non-test) run - the "deny" approval mode is not a substitute for scoping tools.**
- **Cost optimization - `wakeAgent` pre-check gate:** the fetch script now compares today's digest text against the most recently stored line in the history file *before* invoking the LLM. If identical, it prints `{"wakeAgent": false}` as its last line (the officially documented pattern for "cheap pre-run gates") and Hermes skips the agent turn entirely - zero tokens spent, not even a `[SILENT]` reply. Verified live: an unchanged-day re-run produced no new session in `hermes sessions list --source=cron`.
- **`security.allow_private_urls: true`** added (default is `false`, blocks RFC1918/loopback/CGNAT targets as SSRF protection) so Hermes' own `web`/`browser`/`vision` tools can reach `*.lan` and `192.168.0.x` - needed for any future job that has Hermes browse internal dashboards directly instead of going through a wrapper script.

### Telegram Gateway (added 2026-07-25)

Bot: `@homelabor_hermes_bot`, token in `TELEGRAM_BOT_TOKEN` (`/root/.hermes/.env`). Setup notes:
- The Telegram platform adapter needs `python-telegram-bot[webhooks]==22.6`, which is **not** in the base Hermes venv and doesn't auto-install on gateway startup despite `security.allow_lazy_installs: true` (lazy-install applies to some backends, not the messaging platform adapters). Installed manually: `~/.hermes/bin/uv pip install --python /usr/local/lib/hermes-agent/venv/bin/python 'python-telegram-bot[webhooks]==22.6'`, then `hermes gateway restart --system`. Without this the gateway logs `Platform 'Telegram' requirements not met` and silently drops all incoming messages (still shows `active` in systemd - not an obvious failure).
- Authorized via **DM pairing**, not a hardcoded user-ID allowlist: the owner DMs the bot, gets an 8-char pairing code, owner approves with `hermes pairing approve telegram <code>`. No `TELEGRAM_ALLOWED_USERS` set - matches the documented safe default (all senders denied until paired).
- Home channel set from inside the DM with `/sethome`, so cron deliveries land there. `homelab-digest-review`'s `deliver` is `origin,telegram`.

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
- Telegram gateway uses DM-pairing - unknown senders get a pairing code, not a response; no user-ID allowlist configured (pairing is the allowlist)
- Hermes dangerous-command approvals: `approvals.mode: manual`, `approvals.cron_mode: deny`, plus custom `approvals.deny` glob rules for snapraid/lvm commands (see Homelab Monitoring section - these aren't in Hermes' built-in denylist)
- `security.allow_private_urls: true` - deliberate opt-out of SSRF protection for RFC1918 addresses, safe here because every private-range target is our own LAN, not an attacker-controlled internal service
- Gateway daemon (`hermes-gateway.service`) runs as root - contradicts the official "never run the gateway as non-root" recommendation, but accepted here (same reasoning as the `hermes-to-109` SSH key restriction) because this is a single-purpose, single-user LXC with no other accounts

## Management

- Provisioned manually via `pct create` on pve
- Komodo-integrated: native Periphery agent (systemd, reverse-connect as "LXC 113"); the `odysseus` stack is registered in files_on_host mode (`/opt/odysseus`, `docker-compose.yml`) - status, logs, and redeploy from the Komodo UI, host resource alerts included
- Odysseus updates stay manual by design: `git pull` in `/opt/odysseus`, then redeploy via Komodo (no auto-pull from the third-party upstream repo)
- Homepage tiles: Odysseus (site monitor) and Hermes (ping) in the Automation group
- Hermes updates via `hermes update`
- Hermes WebUI (github.com/nesquena/hermes-webui): runs the agent in-process from `~/.hermes` using the agent venv (`/usr/local/lib/hermes-agent/venv`); systemd unit `hermes-webui.service`; update: `git -C /opt/hermes-webui pull && systemctl restart hermes-webui`
- Odysseus admin login: user `admin`, password in Vaultwarden
