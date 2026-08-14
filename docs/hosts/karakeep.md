# karakeep LXC

## Overview

| Property | Value |
|----------|-------|
| Hostname | karakeep |
| IP Address | 192.168.0.128 (static since 2026-07-06, was DHCP - see proxmox doc 25) |
| VMID | 106 |
| OS | Debian GNU/Linux 13 (trixie) |
| Kernel | 6.17.4-1-pve |
| CPU | 2 cores |
| RAM | 4 GB |
| Disk | 18 GB (local-lvm, 50% used) - grown from 10 GB on 2026-08-13, see Lessons Learned |
| Purpose | Self-hosted bookmarking and read-later service |

## Running Services

Since 2026-08-13 Karakeep runs as a Docker Compose stack, not systemd units.
The compose file lives in this repo (`compose/proxmox-lxc-106/karakeep/`) and is
deployed by Komodo, like every other stack in the homelab.

| Container | Description |
|-----------|-------------|
| `karakeep-web` | Next.js frontend + all background workers (port 3000) |
| `karakeep-chrome` | Headless Chromium for page snapshots (internal only) |
| `karakeep-meilisearch` | Full-text search and vector index (internal only) |
| `periphery.service` | Komodo agent, connects outbound to Core on 192.168.0.105:9120 |
| `avahi-daemon.service` | mDNS/DNS-SD (local service discovery) |
| `ssh.service` | OpenSSH server |

## Open Ports

| Port | Protocol | Service |
|------|----------|---------|
| 22 | TCP | SSH |
| 3000 | TCP | Karakeep web UI |

## Installed Software

| Package | Version | Notes |
|---------|---------|-------|
| karakeep | `release` | Floating tag, Komodo auto-updates |
| meilisearch | v1.41.0 | **Pinned on purpose** - see Lessons Learned |
| karakeep-chrome | `release` | Tagged by Chromium version when pinned, **not** by Karakeep version |
| docker | 29.7.2 | Installed 2026-08-13 |

## Configuration

**Compose file:** `compose/proxmox-lxc-106/karakeep/docker-compose.yml` (in this repo)
**Secrets:** Komodo Stack Environment (`NEXTAUTH_SECRET`, `MEILI_MASTER_KEY`, `OPENAI_API_KEY`)
**Data directory:** `/opt/karakeep_data/` (65 MB) - bind mounted into the container at `/data`

The old source install (`/opt/karakeep`, 3.5 GB), its four systemd units and the
old Meilisearch index were deleted on 2026-08-13 once the compose stack was
verified. The data backup taken before the migration is kept:
`/root/karakeep_data-2026-08-13.tar.gz` (49 MB).

### Key Settings

| Setting | Value |
|---------|-------|
| `DATA_DIR` | `/opt/karakeep_data/` |
| `NEXTAUTH_URL` | `http://192.168.0.128:3000` |
| `MEILI_ADDR` | `http://meilisearch:7700` (compose network) |
| `BROWSER_WEB_URL` | `http://chrome:9222` (compose network) |
| `DB_WAL_MODE` | `true` |

### Database Layout

```
/opt/karakeep_data/
├── db.db          # SQLite - main application database
├── db.db-shm      # SQLite shared memory
├── db.db-wal      # SQLite WAL journal
├── queue.db       # SQLite - job/task queue
├── queue.db-shm
├── queue.db-wal
└── assets/        # Saved page snapshots, favicons, images
```

### AI Integration

Auto-tagging and summarization run on the **Gemini API** since 2026-08-13
(previously Ollama on the desktop, which was not powered on 24/7, so tagging
silently failed whenever the machine was asleep).

| Setting | Value |
|---------|-------|
| `OPENAI_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta` |
| `INFERENCE_TEXT_MODEL` | `gemini-3.5-flash-lite` |
| `INFERENCE_CONTEXT_LENGTH` | `8000` |
| `EMBEDDING_TEXT_MODEL` | `gemini-embedding-2` (3072 dimensions) |

Gemini exposes an OpenAI-compatible API, so no Gemini-specific support is needed
in Karakeep - it is configured through the `OPENAI_*` variables. Both
`.../v1beta` and `.../v1beta/openai` work as the base URL.

### Tagging: why `$tags` had to go

The custom tagging prompt originally ended with `Reuse an existing tag when it
fits: $tags`. That placeholder is expanded in the worker as:

```js
const tagsString = `[${tags.map((tag) => tag.name).join(", ")}]`;
```

No filter, no sort, no cap. With 873 tags that is 15,972 characters, roughly
4,000 tokens of an 8,000-token `INFERENCE_CONTEXT_LENGTH`. And the content is
what gets sacrificed for it:

```js
const available = Math.max(0, contextLength - promptSize);
const truncatedContent = await truncateContent(content, available);
```

Karakeep already does the same job far better on its own. When `curatedTagIds`
is empty it calls `getPotentiallyRelevantTags()`, which vector-searches the ten
most similar bookmarks and offers only their tags, truncated to 1,000 characters
(`RELEVANT_TAG_TRUNCATE_LENGTH`), injected as *"Similar bookmarks were tagged
with the following tags (reuse if possible, ignore if irrelevant)"*. In practice
that is ~34 relevant tags instead of 873 arbitrary ones. **This path needs
embeddings**, so it did nothing until the backfill below.

The prompt's formatting rule was redundant too: `user.tagStyle` is
`titlecase-spaces`, from which the built-in prompt already generates *"Use title
case with spaces between words"*. The built-in prompt also already says *"Keep
each tag short: ideally 1-3 words. Do not include parenthetical explanations"* -
which is exactly the rule `Artificial Intelligence (AI)` broke while 4,000 tokens
of tag noise drowned it out.

The whole custom prompt is now one sentence: `Assign 3-5 tags. Prefer fewer
precise tags over many overlapping ones.`

Cleanup done at the same time (2026-08-14): 410 orphan tags with zero bookmarks
deleted, 88 of them snake_case wreckage from an Ollama-era degenerate loop
(`ai_automation_evolution_evolution_reporting` and about eighty siblings).
873 tags -> 462.

Note that `normalizeTagName` already collapses case, spaces, hyphens and
underscores, so exact duplicates cannot exist. Only semantic near-variants
survive, and those are the ones a bloated candidate list produces.

### Semantic search and the embedding backfill

Semantic search (embeddings) arrived in Karakeep 0.33.1. On the older source
install the `EMBEDDING_*` variables were accepted but silently ignored, because
the config schema did not know them yet. The give-away was that the workers log
contained no embedding job at all - the settings looked applied and did nothing.

After the upgrade, new bookmarks are embedded automatically, but the existing 183
were not. The admin `reindexAllBookmarks` action needs a logged-in admin session
and is not reachable with an API key, so the backfill was done by inserting jobs
straight into the queue database:

```
queue:   embeddings_queue
payload: {"type":"embed","bookmarkId":"...","force":true,"runTaggingOnComplete":false}
```

The payload schema was read out of the shipped worker bundle. All 183 embeddings
were generated with no failures.

**Caveat:** the embeddings exist and are indexed at 3072 dimensions, but the REST
`/api/v1/bookmarks/search` endpoint does not appear to use them - an English query
matches, a Hungarian paraphrase of the same content does not. Semantic search is
most likely a separate mode in the web UI. This has not been confirmed.

## Lessons Learned

- **Debian 13 (trixie):** This is the only LXC in the homelab running Debian trixie (testing). All others run bookworm (stable) or Alpine. Trixie provided a newer Chromium version needed by Karakeep's browser service.
- **Chromium in a headless LXC:** The `karakeep-browser.service` runs Chromium in headless mode inside an unprivileged LXC. This requires careful attention to sandbox settings - some Chromium sandbox features require kernel capabilities not available in unprivileged containers.
- **SQLite WAL mode:** `DB_WAL_MODE=true` enables Write-Ahead Logging, which improves concurrent read performance and reduces lock contention between the web process and background workers.
- **Disk usage watch:** At 65% of 10 GB, the disk is filling up. The `assets/` directory grows as more pages are snapshotted. Consider increasing the disk or periodically pruning old snapshots.
- **A local model that is not always on is worse than no local model:** Ollama ran on a desktop that is powered off most of the day. Tagging did not fail loudly, it just recorded `taggingStatus: failure` and moved on, so bookmarks quietly accumulated without tags. Privacy was never the deciding factor here - availability was.
- **Prompt guardrails are a symptom of a weak model:** The Ollama-era tagging prompt shouted `HARD LIMIT: Generate EXACTLY 3 to 5 tags total. Never generate more than 5 tags under any circumstances.` With Gemini and a structured output schema, one calm sentence does the same job.
- **Read what a template placeholder actually expands to.** `$tags` reads like "show the model the existing tags so it reuses them". It expands to every tag name you own, unsorted and uncapped, and it crowds out the page content it is supposed to help classify. It also fed the model eighty snake_case junk tags as examples while the prompt forbade snake_case. The application's own vector-selected list was already better and was being drowned by it.
- **A feature you enable can silently switch on a second one.** The embedding backfill was done for semantic search. It also activated `getPotentiallyRelevantTags()`, which had been returning `null` on every tagging job until then. Nothing announced this; it is one debug line in the workers log (`Will use N potential tags`).
- **`SERVER_VERSION` in the env file lied:** It read `1.37.0`, which is a Meilisearch version, not a Karakeep one - Karakeep is versioned `0.33.x`. The community-script update rewrites this line with `sed`, so a stale value survives indefinitely. Never read the version from there; read it from the running workers log.
- **The helper script rebuilt from source on every update:** `CLEAN_INSTALL=1` wiped `/opt/karakeep`, then `pnpm install && pnpm build` ran for three apps, plus `pnpm rebuild better-sqlite3` and a DB migration. The script also pins Node 22 with a comment pointing at an upstream crash (`karakeep-app/karakeep#2989`). None of that is version controlled, and the build needs a temporary CPU/RAM bump. This is what motivated the move to compose.
- **The two installs cannot run in parallel:** Both write the same SQLite database, so a side-by-side comparison on the same data directory would corrupt it. The migration is a clean cutover with a backup, not a gradual one.
- **The disk had to grow before it could shrink:** only 3.0 GB was free, and Docker plus the three images needs about 3 GB. Deleting the 3.5 GB source tree first would have freed the space but destroyed the rollback path, so the disk went 10 GB -> 18 GB and the cleanup came afterwards. It is not shrunk back: `pct resize` only grows, and the volume is thin-provisioned anyway, so the unused capacity costs nothing in the pool.
- **Pin the search engine even when everything else floats:** Karakeep and its Chromium image run the `release` tag with Komodo auto-update. Meilisearch does not. A major version bump changes the on-disk index format, and an unattended upgrade would quietly break search - the exact capability the migration was for. The recovery is not catastrophic (Karakeep can rebuild the index from `db.db`), but it should be a deliberate step, not a surprise.
- **A successful deploy that changes nothing:** the first Komodo deploy after switching to the `release` tag reported success while the containers kept running the old pinned images. The deploy had run against the repo clone before the pull landed. Checking `docker ps` image column, not the deploy result, is what catches this.
