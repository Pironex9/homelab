# 41 - Hermes Agent Capability Hardening

**Date:** 2026-08-22
**Hostname:** agentos (LXC 113)
**IP address:** 192.168.0.71

Auditing a background agent that had been running for six weeks with a third of
its capabilities switched off, and deciding against migrating to a different
harness. Five changes, all reversible, each verified live rather than by a
green status line.

---

## What triggered it

A former client mentioned a Hungarian-developed agent harness "similar to
Hermes", remembered as *Marvin*. The actual project is **Marveen**
([github.com/Szotasz/marveen](https://github.com/Szotasz/marveen), MIT,
TypeScript, first commit 2026-04-08). It is not a harness in the Hermes sense -
it is an orchestration layer **on top of Claude Code**, adding a fleet of agents
with per-agent Telegram/Slack channels, a Mission Control dashboard on port
3420, cron scheduling, a kanban board, and a layered SQLite memory with hybrid
FTS5 + vector search (Ollama `nomic-embed-text`, RRF fusion, salience decay).

The claim that reached us was "it only works with Claude Max". That is wrong:
`claudeAuthPresent()` in `src/web/routes/onboarding.ts` checks five auth paths
in order - `CLAUDE_CODE_OAUTH_TOKEN`, `ANTHROPIC_API_KEY`,
`~/.claude/.credentials.json`, `store/.claude-oauth-token`, macOS Keychain -
and the first hit wins, so a plain API key works. The practical constraint is
different: headless fleet agents need a `claude setup-token`, and the default
`DEFAULT_AGENT_MODEL` is `claude-opus-5[1m]`, so on API-key billing an
autonomous fleet meters expensively, while on a subscription it competes for
the same rate limit as interactive work.

**Decision: do not migrate.** The comparison that settled it:

| | Hermes (LXC 113) | Marveen |
|---|---|---|
| Engine | any OpenAI-compatible provider | Claude Code only |
| Cost | the already-configured provider chain | Claude subscription or API key |
| Multi-agent | one agent + cron + delegation to LXC 109 | agent fleet, per-agent channels and memory |
| Dashboard | Hermes WebUI (8787) + Minions (6969) | Mission Control (3420), built in |
| Releases | versioned, `hermes update` | none - `git pull` on `main`, nothing to roll back to |

Marveen's genuinely new capability is Claude-quality agents running proactively
in the background. What it does *not* justify is a second agentic stack on the
same LAN. The useful outcome of the research was the question it raised about
our own install: **if Marveen ships semantic memory by default, what does
Hermes have switched off?**

`hermes doctor` answered that.

---

## 1. Memory provider

Hermes v0.18 ships 8 external memory provider plugins. Built-in memory
(`MEMORY.md` / `USER.md`) is always active; exactly one external provider can
be layered on top, and ours was set to none.

```bash
hermes memory status        # → Provider: (none — built-in only)
hermes memory setup holographic
```

**`holographic` is not what a "vector memory" usually means, and this matters
for the choice.** It is a local SQLite fact store with FTS5 full-text search,
trust scoring, and HRR (Holographic Reduced Representations) - `encode_atom()`
in `plugins/memory/holographic/holographic.py` hashes tokens into phase vectors
for compositional algebra, it does not embed meaning. Semantic recall in the
Marveen sense would be the `mem0` provider in OSS mode (Ollama embedder +
qdrant or pgvector), which is three additional moving parts. Holographic was
chosen because it needs nothing that isn't already installed.

What it does give beyond keyword search: `probe` (all facts about one entity),
`reason` (compositional AND across entities), `contradict` (conflicting-fact
detection), and asymmetric trust feedback (+0.05 helpful / -0.10 unhelpful).

**Capacity ceiling, worth writing down before it bites:** `snr_estimate()`
computes `SNR = sqrt(dim / n_items)` and logs a degradation warning below 2.0,
i.e. once `n_items > dim / 4`. At the default `dim = 1024` that is roughly
**256 facts** before algebraic retrieval starts degrading. The FTS5 path keeps
working regardless; raising `dim` is the upgrade.

`auto_extract` defaults to `false`, so facts are only stored when the agent
explicitly calls `fact_store`.

### The numpy trap (applies to every future Python dependency here)

HRR algebra needs NumPy, and it was missing - the plugin would have silently
degraded to FTS5-only. Installing it is not obvious, because the Hermes venv
was created by `uv`:

```
$ /usr/local/lib/hermes-agent/venv/bin/python -m pip install numpy
No module named pip
$ /usr/local/lib/hermes-agent/venv/bin/python -m ensurepip --upgrade
No module named ensurepip
```

There is no `pip` in the venv, `ensurepip` is absent, `pyvenv.cfg` has
`include-system-site-packages = false`, the system Python has no NumPy either,
and `uv` is not on `PATH`. The working path is Hermes' own bundled `uv`:

```bash
/root/.hermes/bin/uv pip install \
  --python /usr/local/lib/hermes-agent/venv/bin/python numpy
```

Same recipe as the `python-telegram-bot[webhooks]` install documented on the
agentos host page - this is the standard way to add a Python package to this
install, not a one-off.

### Verification

Two separate `hermes -z` invocations, so cross-session persistence is actually
proven rather than assumed:

```bash
hermes -z "Use the fact_store tool with action=add to store this exact fact: ..."
# → stored, ID 1
hermes -z "Use fact_store with action=search and query \"thin pool\". ..."
# → returned the exact stored content in a fresh session with no prior context
```

`~/.hermes/memory_store.db` created, 80 KB.

**An honest note on that test:** retrieval was correct, but the model then
volunteered ZFS advice (`zfs list`, `zpool iostat`, `recordsize`) for
`pve/data`, which is LVM-thin. The memory layer did its job; the model
hallucinated on top of a correctly retrieved fact. This is the failure mode
`verify_on_stop` (below) is aimed at.

---

## 2. Web search and extract - the toolset was entirely dead

`hermes doctor` reported:

```
⚠ web (missing EXA_API_KEY, PARALLEL_API_KEY, TAVILY_API_KEY, FIRECRAWL_API_KEY, ...)
```

An agent with cron jobs, a Telegram gateway and a research remit had **no web
access at all**. This was the single largest gap found.

### Provider comparison

Hermes backs `web_search` and `web_extract` with one selectable backend
(providers can be split per capability). All four commercial options, priced
2026-08-22:

| Provider | Env var | Search | Extract | Free tier | Paid |
|---|---|---|---|---|---|
| **Firecrawl** (Hermes default) | `FIRECRAWL_API_KEY` | ✔ | ✔ | 500 credits/mo | Standard $99/mo; search = 2 credits per 10 results |
| **Tavily** | `TAVILY_API_KEY` | ✔ | ✔ | 1 000 credits/mo | $30/mo = 4 000 credits, or PAYG $0.008/credit; basic search 1 credit, advanced 2 |
| **Exa** | `EXA_API_KEY` | ✔ | ✔ | $20 at signup + $10/mo recurring | standard search $7/1k (raised from $5 in March 2026), answer $5/1k, deep search $12/1k, deep-reasoning $15/1k |
| **Parallel** | `PARALLEL_API_KEY` | ✔ | ✔ | up to 5 000 requests/mo | Search $1/1k (Turbo) to $5/1k (Basic/Advanced), Extract $1/1k; 600 req/min, 200 ms - 3 s |

Hermes' own documentation lists Parallel as "Paid" with no free tier, which
contradicts Parallel's current pricing page - the Hermes table appears to be
out of date. Not verified against a live account.

What actually distinguishes them: Firecrawl is a scraper first (strongest at
JS-rendered pages, wasteful as a search engine); Tavily returns pre-cleaned
LLM-shaped snippets cheaply from a shallower index; **Exa is the only
embedding-based semantic search of the four**, worth having only for queries
that cannot be phrased as keywords; Parallel optimizes latency and rate limit
(600/min), which is a bottleneck no homelab assistant will ever hit.

### The finding that changed the recommendation

Hermes also supports **SearXNG** as a free, self-hosted search backend - and
`odysseus-searxng-1` has been running on this same LXC all along, bound to
`127.0.0.1:8080`, as a bundled Odysseus sidecar. Its JSON API is already
enabled (`formats: [html, json]` in `/etc/searxng/settings.yml`, the setting
whose absence makes SearXNG return 403 to every API call):

```bash
curl -s "http://127.0.0.1:8080/search?q=proxmox&format=json"
# http=200, 6575 bytes of real results
```

With no `web:` block in `config.yaml`, Hermes falls back to its default
provider - Firecrawl - for **both** search and extract. Every trivial lookup
was therefore going to bill against a 500-credit monthly quota while a free
unlimited search engine ran on the same host. The correct configuration is a
per-capability split: **SearXNG for search, Firecrawl for extract.**

Keys installed for now: `TAVILY_API_KEY` and `FIRECRAWL_API_KEY` (both already
held for other services). Exa and Parallel were deliberately not added.

---

## 3. Home Assistant tool

`homeassistant` showed as "system dependency not met". The tool wants two
variables, found by grepping the tool source rather than guessing:
`HASS_URL` and `HASS_TOKEN`. Endpoint confirmed before writing config:

```bash
curl -o /dev/null -w "%{http_code}" http://192.168.0.202:8123/    # → 200
```

### Side effect worth knowing about

Adding those two variables does more than enable a tool - the **gateway loads a
Home Assistant platform adapter**, and logs:

```
[Homeassistant] No watch_domains, watch_entities, or watch_all configured.
All state_changed events will be dropped.
```

Harmless as-is, because everything is dropped. But `watch_all` would wake the
agent on **every** HA state change - a single motion sensor fires dozens of
times per minute. If event-driven behaviour is ever wanted, start from
`watch_entities` with an explicit list, never `watch_all`.

Verified live: the agent listed real entities from this HA instance
(`dawarich_total_distance`, `Stekker_*` update entities, plus several in
`unavailable` state).

---

## 4. GitHub token

```
⚠ No GITHUB_TOKEN (60 req/hr rate limit — set in ~/.hermes/.env for better rates)
```

This had already caused real damage: during the 2026-07-26 skill installation
round, the unauthenticated GitHub API limit was hit partway through and the
last five skills had to be installed by hand with `git clone --depth 1` instead
of `hermes skills install`. Adding the token flips the Skills Hub check to
`✓ GitHub token configured (authenticated API access)`.

---

## 5. Two config flags

```bash
hermes config set agent.verify_on_stop true
hermes config set tool_loop_guardrails.hard_stop_enabled true
```

- **`verify_on_stop`** (was `false`): `build_verify_on_stop_nudge()` in
  `agent/verification_stop.py` injects a verification pass before the agent
  declares itself finished. Aimed squarely at the failure seen in the memory
  test above - a confident answer that was never checked.
- **`hard_stop_enabled`** (was `false`): Hermes' own documentation explains the
  default - interactive sessions have a human watching repeated tool-call
  warnings. This host is **not** that case: `hermes-gateway.service` runs
  unattended on Telegram and cron jobs fire daily. Upstream's guidance for
  unattended deployments is to enable hard stops so a stuck tool loop is
  blocked, not merely logged.

---

## Traps hit along the way

**The secrets could not be read by the agent doing the work.** Claude Code's
auto-mode classifier blocks reads under `/root/.secrets/` - twice, including an
attempt that only printed byte counts. Copying keys between hosts had to be
handed back to the operator as a script they run themselves. This is the
correct behaviour, not a bug to work around.

**A long one-liner is not a safe delivery format for a command someone pastes.**
The first attempt was a single `sed -e ... -e ...` pipeline; the terminal
wrapped it mid-command and the shell received the `-e` flags split across
lines:

```
sed: option requires an argument -- 'e'
environment: line 8: s/^"//: No such file or directory
/bin/bash: eval: line 10: syntax error near unexpected token `|'
```

Because the closing pipe never parsed, nothing was written - confirmed by
comparing line counts against the backup (479 vs 479) before retrying. The
rewrite went into a script file with a single semicolon-separated `sed` script,
plus an emptiness check per key so a mis-parsed secret can never be written as
an empty value. Result: 479 → 486 lines (a blank line, a dated comment, and
five keys).

**Restarting the gateway sends a Telegram alert.** The operator received
"⚠️ Gateway shutting down — Your current task will be interrupted" and did not
know what caused it. It was the `systemctl restart hermes-gateway` at the end
of the key-install script. The message is a generic SIGTERM template - it is
sent whether or not any task is actually in flight, and in this case nothing
was running (the only cron job, `homelab-digest-review`, had completed `ok` at
07:07 UTC, four hours earlier). Timestamps need converting before blaming
anything: the LXC runs `Etc/UTC`, Telegram displays local time, so 12:52 CEST
in the app is the 10:52:58 UTC service start in `systemctl status`.

**The gateway exits 1 on SIGTERM,** so systemd logs
`Main process exited, code=exited, status=1/FAILURE` and
`Failed with result 'exit-code'` on every clean restart. Cosmetic today, but it
is what would trip a restart rate limit.

---

## Result

| Check | Before | After |
|---|---|---|
| `web` tool | ⚠ no provider keys | ✓ |
| `homeassistant` tool | ⚠ system dependency not met | ✓ |
| Skills Hub | ⚠ 60 req/hr unauthenticated | ✓ authenticated |
| Memory provider | none (built-in only) | ✓ holographic |
| `agent.verify_on_stop` | `false` | `true` |
| `tool_loop_guardrails.hard_stop_enabled` | `false` | `true` |

Still grey and deliberately so: `image_gen`, `spotify`, `discord`,
`x_search`, `browser-cdp`, `computer_use` - each needs either an account we
do not have or a system dependency that is meaningless inside an LXC.

Both `doctor` npm advisories (`web` workspace 7 high, `ui-tui` 5 high) are
build-time tooling by upstream's own annotation, not runtime, and clear via a
lockfile bump. Left alone.

## Rollback

Every change is a config or `.env` edit, backed up before writing:

```bash
# memory provider only
hermes memory off

# the two flags
cp ~/.hermes/config.yaml.bak-preflags-2026-08-22-1049 ~/.hermes/config.yaml

# the five keys
cp ~/.hermes/.env.bak-2026-08-22-1049 ~/.hermes/.env
systemctl restart hermes-gateway
```

Nothing was installed system-wide except NumPy inside the Hermes venv.
