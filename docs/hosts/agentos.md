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
| SkillClaw proxy (native, systemd via `skillclaw start --daemon`) | Session-capture + skill-injection proxy in front of Hermes' LLM calls, loopback-only (`127.0.0.1:30000`) |
| skillclaw-evolve.service (native, systemd) | Background skill-refinement loop, reads captured sessions every 6h and proposes skill updates |

## Model Routing

**Hermes:**
1. Google Gemini (`gemini-flash-latest`) - primary as of 2026-07-25, `GEMINI_API_KEY` in `/root/.hermes/.env`. **Since SkillClaw was activated the `model:` block no longer names Gemini directly** - `config.yaml` reads `model.provider: custom`, `model.default: skillclaw-model`, `model.base_url: http://127.0.0.1:30000/v1`, because `skillclaw start` rewrites it to route every call through the proxy (see the SkillClaw section). Gemini is still the upstream that answers; anyone reading the config for the first time will not see that. Flipped from the original order (see history below) once the fallback had proven itself reliable, so the always-on cloud model is the default path and the local GPU is the backup.
2. Nobara Ollama (`http://192.168.0.100:11434`, model `qwen3:8b`) - fallback, configured under `fallback_providers` (`provider: custom`, `base_url`, plus `context_length`/`ollama_num_ctx: 65536` carried onto the fallback entry since Hermes requires a 64K+ window and Ollama won't provide it by default). Not always on (desktop PC, powered off outside active use), but free and private when available.
3. LXC 109 Claude Code (via the `delegate-to-claude-code` skill and restricted SSH, `/usr/local/bin/hermes-claude-code.sh`) - deliberate delegation only, not part of the failover chain

**History:** Ollama was primary / Gemini was fallback from 2026-07-24 until the swap on 2026-07-25. Original provider evaluation, kept for context:
- **Why Gemini, not DeepSeek/Groq:** DeepSeek was the first candidate but was dropped over data-sovereignty concerns (PIPL/National Intelligence Law compel Chinese companies to hand over data on request, no independent judicial review). Groq was tried next (US-based, no such concern) but its free tier caps at 6-8K tokens/minute, and Hermes' full agent request (system prompt + tool schemas) runs ~20K tokens - every fallback call hit a 413 "request too large" error. It also isn't a bundled provider plugin in Hermes v0.18 (only wired for Whisper STT), so it needs a `custom_providers` entry (`base_url: https://api.groq.com/openai/v1`, `key_env: GROQ_API_KEY`, referenced as `provider: custom:groq`) rather than a bare `provider: groq`. Gemini is a first-class Hermes provider, has a 250K TPM free tier (12x the requirement), and - for EU-based accounts specifically - the free tier inherits the paid tier's stricter data-use terms (no training on prompts/responses), which the US free tier does not get.

**Swap verification (2026-07-25):** confirmed both directions live before relying on it:
- Gemini as primary: `hermes chat -q "..."` answered correctly.
- Forced failover: added a bogus `/etc/hosts` entry for `generativelanguage.googleapis.com` (simulates Gemini being unreachable) - Hermes correctly fell through to the local Ollama fallback and answered. Reverted immediately after.
- **Cron jobs snapshot their provider/model at creation time and do NOT follow later changes to the global default** - by design, so an unattended job can't silently start spending on a different (possibly paid) model. After the swap, the existing `homelab-digest-review` job would have skipped every run and alerted instead of running, since it still pointed at the old Ollama snapshot. Fixed by removing and recreating the job so it re-snapshots the new default (`hermes cron remove` + `hermes cron create` with identical parameters). No CLI flag exists in this Hermes version to re-pin a job's provider/model in place.
- **Found an upstream bug while testing:** an invalid `GEMINI_API_KEY` returns Gemini HTTP 400 (`INVALID_ARGUMENT: API key not valid`), which is **not** in Hermes' fallback-trigger list (429/500/502/503/401/403/404 only) - so a bad/revoked key does not fail over to Ollama, it crashes the session instead. Worse, the crash itself is a secondary bug: Hermes' own error-summary code tries to read `response.text` on a streaming httpx response that was never `.read()`'d, so the real "API key not valid" message never reaches the user - only a confusing `httpx.ResponseNotRead: Attempted to access streaming response content` shows up. Reproduced and confirmed via `~/.hermes/logs/errors.log`; not filed upstream yet. **Practical implication: if the Gemini key ever expires/gets revoked, Hermes will NOT quietly fall back to Ollama - it'll error out.** Worth an occasional manual check that the key is still valid.

**Reverse direction - Claude Code (LXC 109, `/root/homelab`) offloading to Hermes:** needs no extra setup beyond the existing `ssh agentos` root access. For simple, mechanical subtasks (log/error summaries, boilerplate, one-off lookups), run `ssh agentos "hermes -t <toolset> -z '<task>'"`. Two things matter for correct results:
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

### Timezone (changed 2026-08-26)

The container OS stays on `Etc/UTC` on purpose. **Hermes resolves its own timezone and ignores the host's** unless nothing else is set, in this order (`hermes_time.py`):

1. `HERMES_TIMEZONE` environment variable
2. the `timezone` key in `~/.hermes/config.yaml`
3. fallback: the server's local time

Key 2 was unset, so `homelab-digest-review`'s `5 7 * * *` was being read as 07:05 UTC and the Telegram post arrived at 09:05 local. Fixed with the app's own CLI, which handles the `_config_version` migration:

```bash
hermes config set timezone Europe/Budapest
systemctl restart hermes-gateway    # the gateway hosts the cron scheduler and caches the zone
```

**The restart is not enough on its own.** Hermes stores an absolute `next_run_at` per job, and the offset-repair path (`_timezone_offset_mismatch` / `_stored_wall_clock_is_future` in `cron/jobs.py`) only runs when the job becomes due - so the *next* run still fires at the old wall-clock time, and only the one after that is correct. Verified on the live job: after the config change and a gateway restart, `next_run_at` was still `2026-08-27T07:05:00+00:00`. Forcing the recompute takes a no-op edit with the same expression:

```bash
hermes cron edit d2306bd1a730 --schedule "5 7 * * *"
# next_run_at: 2026-08-27T07:05:00+00:00 -> 2026-08-27T07:05:00+02:00
```

The resulting `jobs.json` diff is exactly two fields, `next_run_at` and `updated_at`; prompt, script, `deliver` and `repeat.completed` are untouched.

**`last_run_at` is written at completion, not at fire time** (`mark_job_run` sets it together with `last_status`), so the difference between it and the schedule is the run duration. Useful for spotting a slow provider: on 2026-08-26 the job took 8m13s against a 4-35 s baseline, and the agent log pinned it on a Gemini 503 through the SkillClaw proxy - the first streaming request hung 5m08s before the error surfaced, then the retry took 3m01s. Three such days in eleven, every one of them a 503 day, and the retry policy carried all three.

## SkillClaw (added 2026-07-25)

Third-party skill-evolution layer for Hermes (`github.com/AMAP-ML/SkillClaw`, unofficial/community project, not affiliated with NousResearch). Installed after the user asked Hermes to install a skill from this repo directly, which triggered a source-code review before activation - the project isn't audited upstream, and by its own design it (a) proxies all Hermes LLM traffic and (b) can autonomously rewrite `SKILL.md` files the agent later treats as trusted instructions, so both were reviewed before turning anything on.

**Two components, reviewed and configured separately:**

1. **Proxy** (`skillclaw-proxy.service`, real systemd unit as of 2026-07-30 - originally started by hand with `skillclaw start --daemon` and no supervision, which meant an unrelated LXC reboot on 2026-07-29 silently killed it with no auto-restart and broke the next day's `homelab-digest-review` cron run with `RuntimeError: Connection error.` after the Nobara-Ollama fallback also failed to answer; fixed by writing a unit modeled on the pre-existing evolve-server unit, `Type=simple`/foreground start/`Restart=always`/`RestartSec=10`/`enable`d) - sits between Hermes and its LLM provider to capture session traces (prompts/responses/tool I/O) into `~/.skillclaw/records/conversations.jsonl`, and injects skill content from `~/.hermes/skills` into the agent's context.
   - **Default config is unsafe and was overridden**: binds `0.0.0.0` with no proxy auth key by default - source review found `_check_auth()` explicitly skips authentication when no key is set (`skillclaw/api_server.py`), meaning anyone on the LAN could relay requests through the owner's Gemini key with zero auth. Fixed in `~/.skillclaw/config.yaml`: `proxy.host: 127.0.0.1`, `proxy.api_key` set to a random token. Verified: unauthenticated `curl` to `127.0.0.1:30000/v1/models` returns 401; `ss -tlnp` confirms loopback-only bind.
   - `skillclaw start` silently rewrites `~/.hermes/config.yaml`'s `model:` block to route through the proxy (backs up the previous config first, under `~/.skillclaw/backups/hermes/`) - `skillclaw doctor hermes` confirms `proxy_match: True` and zero issues after activation.
   - Session data is 100% local by default (`sharing.enabled: false`, left off) - the `skill_hub`/nacos cross-device sharing mechanism has no hardcoded remote and raises an error if `sharing.nacos_server` isn't explicitly set, so nothing phones home unless deliberately configured.
   - Conversation captures (`records/conversations.jsonl`) are plaintext, no file-permission hardening beyond default umask - treat that directory as sensitive (it will contain anything typed into a Hermes session).

2. **Evolve server** (`skillclaw-evolve.service`, real systemd unit since this needs to persist/restart like the other native services) - periodically reads captured sessions and uses an LLM to propose skill refinements.
   - **`--engine agent` was explicitly avoided**: source review found it launches a real OpenClaw agent subprocess with `sandbox.mode: off` and *always* auto-publishes regardless of `--publish-mode` (no verifier gate, unlike the `workflow` engine) - confinement to its workspace dir is a prompt instruction to the LLM, not a technical control. This is the same class of risk as the cron-toolset incident above (an agent with real write/exec access and no hard boundary), so it's not used here.
   - Configured instead with `--engine workflow --publish-mode validated --skill-verifier --skill-verifier-min-score 0.85 --validation-required-results 1 --validation-required-approvals 1 --interval 21600 --storage-backend local --local-root /root/.skillclaw/evolve-store --use-skillclaw-config`. `validated` mode queues candidates instead of writing live `SKILL.md` files directly; on a single-user install with no other validation clients, this is effectively a manual-approval gate. Candidates land in the separate `evolve-store` staging directory, not directly in `~/.hermes/skills/` - review/promotion is a manual step.
   - `--use-skillclaw-config` reuses the same already-reviewed, billing-enabled Gemini key as the proxy, instead of the tool's own default (`gpt-4o` via `api.openai.com`) - avoids opening a second, unreviewed data-egress path for captured session content.
   - **Known residual risk, accepted as low-severity for now:** the evolve LLM call treats captured session "evidence" (including tool-call outputs, which can contain text from web pages or other untrusted sources, not just what the user typed) as ordinary context with no explicit untrusted/instruction-vs-data marking - a theoretical prompt-injection-into-skills vector. Mitigated in practice by `validated` publish mode requiring manual promotion out of staging before anything reaches a live skill file.
   - First cycle ran clean (0 sessions queued yet, systemd unit healthy). Verified end-to-end with `hermes -z` through the proxy before enabling the evolve loop.

**Learning pipeline never actually ran (found and fixed 2026-08-18):** the proxy outage above prompted a check of whether the evolve server had produced anything since setup - it hadn't. `evolve_history.jsonl` showed 97 cycles (every 6h since 2026-07-29) all logging `0 sessions, 0 skill groups`, and `evolve_skill_registry.json` was still `{}`.

- **Root cause, found via source review** (`/root/SkillClaw`, editable install, v0.4.0): `~/.skillclaw/config.yaml` had `sharing.enabled: false` (the documented-safe default from the initial setup above). Both session-upload paths in `api_server.py` - the on-close upload and the periodic mid-session snapshot - are gated by `if self.config.sharing_enabled`, so with it `false` no session was ever written to the object store the evolve server reads from (`/root/.skillclaw/evolve-store/default/sessions/*.json`), regardless of how much real traffic went through the proxy. This is a *local* filesystem store, not a cross-device leak - "sharing" is SkillClaw's name for "write anywhere the evolve server can read," local included. `prm.enabled: false` compounded it: every session closed with `scored_turns=0` (visible in `skillclaw.log`), since PRM scoring never ran.
- **Fix:** `skillclaw config sharing.enabled true`, `skillclaw config sharing.backend local`, `skillclaw config sharing.local_root /root/.skillclaw/evolve-store` (must match the evolve server's own `--local-root` so both sides resolve to the same `default/sessions/` prefix - confirmed by reading `list_session_keys()` in `evolve_server/storage/oss_helpers.py`), `skillclaw config prm.enabled true`, then `systemctl restart skillclaw-proxy.service`. No new API key needed: `prm.url`/`prm.model`/`prm.api_key` were left blank, which falls back to the already-configured Gemini creds (`config_store.py`) - cost/latency impact is one extra Gemini judge call per Hermes turn.
- **Backfilled the ~3 weeks of already-captured sessions** rather than only fixing it forward: `~/.skillclaw/records/conversations.jsonl` (21 turn-records, 7 sessions) was never going to reach the evolve store on its own, since the upload paths only fire from live in-memory session state, not by replaying old logs. Reused the tool's own `dashboard_ingest._load_record_sessions()` (already builds the exact `{session_id, timestamp, turns}` shape the evolve store expects, normally used for the local dashboard) in a one-off script to write all 7 as `evolve-store/default/sessions/*.json`.
- **First real cycle (2026-08-18, manually triggered via `systemctl restart skillclaw-evolve.service`), 313s, no errors:** all 7 sessions drained and judged (`session_judge` mean score 0.591, range 0.0-1.0), but **0 skills produced** - all 7 landed in the "no-skill" bucket (the backfilled sessions carry empty `read_skills`/`modified_skills`, since they predate any skill injection), and `create_skill_from_sessions()` returned an explicit LLM decision to skip: 7 single-turn, mechanically similar cron-digest summaries didn't give it enough of a repeated trajectory (attempt -> error -> fix) to generalize into a skill. Expected outcome, not a bug - the pipeline is confirmed working end-to-end; multi-step Hermes debugging sessions are the more likely source of an actual skill candidate going forward.

## Agent Capabilities (audited and enabled 2026-08-22)

Full write-up: [41 - Hermes Agent Capability Hardening](../proxmox/41_Hermes_Agent_Capability_Hardening.md).

- **Memory provider: `holographic`** - local SQLite fact store (`~/.hermes/memory_store.db`), FTS5 + HRR compositional algebra + trust scoring, layered on top of the always-active built-in `MEMORY.md`/`USER.md`. Not an embedding-based semantic memory; that would be the `mem0` provider in OSS mode (Ollama embedder + qdrant). Capacity ceiling: `SNR = sqrt(dim / n_items)` degrades below 2.0 once `n_items > dim / 4`, i.e. ~256 facts at the default `dim = 1024`. `auto_extract` left at `false`. Off switch: `hermes memory off`.
- **NumPy had to be added for the HRR algebra**, and the venv has no `pip` (uv-created, `include-system-site-packages = false`, no `ensurepip`). Use the bundled uv, same as for the Telegram adapter: `/root/.hermes/bin/uv pip install --python /usr/local/lib/hermes-agent/venv/bin/python numpy`.
- **`web` toolset was completely dead until 2026-08-22** - no search provider key was ever set, so an agent with cron jobs and a Telegram gateway had no web access. `TAVILY_API_KEY` and `FIRECRAWL_API_KEY` added to `/root/.hermes/.env`. Note `odysseus-searxng-1` (loopback `127.0.0.1:8080`, JSON API already enabled) can serve search for free; the intended end state is a per-capability split with SearXNG for `web_search` and Firecrawl for `web_extract`, since the Hermes default routes both to Firecrawl and burns its 500-credit monthly quota on plain lookups.
- **`homeassistant` tool enabled** via `HASS_URL=http://192.168.0.202:8123` + `HASS_TOKEN`. Side effect: the gateway also loads a Home Assistant *platform* adapter. It currently drops every event (`No watch_domains, watch_entities, or watch_all configured`) - deliberately left that way, because `watch_all` would wake the agent on every state change in the house. Use `watch_entities` with an explicit list if that is ever wanted.
- **`GITHUB_TOKEN` added** - without it the Skills Hub is capped at 60 requests/hour unauthenticated, which already broke the 2026-07-26 skill-install round partway through.
- **`agent.verify_on_stop: true`** - injects a verification pass before the agent declares itself done.
- **`tool_loop_guardrails.hard_stop_enabled: true`** - upstream defaults this to `false` for interactive sessions with a human watching; this host runs a gateway and cron jobs unattended, where a warning alone does not stop a stuck tool loop.
- Restarting `hermes-gateway.service` sends a Telegram "⚠️ Gateway shutting down" notice whether or not a task is actually running, and the process exits `1` on SIGTERM, so systemd logs `Failed with result 'exit-code'` on every clean restart.

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
- SkillClaw proxy: loopback-only bind + auth token (default is `0.0.0.0` with no auth - overridden, see SkillClaw section); evolve server restricted to `--engine workflow` with `--publish-mode validated` (the `agent` engine runs unsandboxed and bypasses validation entirely - not used)

## Management

- Provisioned manually via `pct create` on pve
- Komodo-integrated: native Periphery agent (systemd, reverse-connect as "LXC 113"); the `odysseus` stack is registered in files_on_host mode (`/opt/odysseus`, `docker-compose.yml`) - status, logs, and redeploy from the Komodo UI, host resource alerts included
- Odysseus updates stay manual by design: `git pull` in `/opt/odysseus`, then redeploy via Komodo (no auto-pull from the third-party upstream repo)
- Homepage tiles: Odysseus (site monitor) and Hermes (ping) in the Automation group
- Hermes updates via `hermes update`
- Hermes WebUI (github.com/nesquena/hermes-webui): runs the agent in-process from `~/.hermes` using the agent venv (`/usr/local/lib/hermes-agent/venv`); systemd unit `hermes-webui.service`; update: `git -C /opt/hermes-webui pull && systemctl restart hermes-webui`
- Odysseus admin login: user `admin`, password in Vaultwarden
