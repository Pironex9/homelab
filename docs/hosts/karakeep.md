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
| Disk | 18 GB (local-lvm, 58% used - grown from 10 GB on 2026-08-13 for the container images) |
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
| karakeep | 0.33.2 | Pinned image tag, bumped via git + Komodo redeploy |
| meilisearch | v1.41.0 | Full-text search and vector store |
| karakeep-chrome | 151.0.7922.47-r1 | Tagged by Chromium version, **not** by Karakeep version |
| docker | 29.7.2 | Installed 2026-08-13 |

## Configuration

**Compose file:** `compose/proxmox-lxc-106/karakeep/docker-compose.yml` (in this repo)
**Secrets:** Komodo Stack Environment (`NEXTAUTH_SECRET`, `MEILI_MASTER_KEY`, `OPENAI_API_KEY`)
**Data directory:** `/opt/karakeep_data/` (65 MB) - bind mounted into the container at `/data`

The old `/etc/karakeep/karakeep.env` and the systemd units are left in place but
disabled, as a rollback path. Data backup before the migration:
`/root/karakeep_data-2026-08-13.tar.gz`.

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

Semantic search (embeddings) arrived in Karakeep 0.33.1. On the older
source install the `EMBEDDING_*` variables were accepted but silently ignored,
because the config schema did not know them yet.

## Lessons Learned

- **Debian 13 (trixie):** This is the only LXC in the homelab running Debian trixie (testing). All others run bookworm (stable) or Alpine. Trixie provided a newer Chromium version needed by Karakeep's browser service.
- **Chromium in a headless LXC:** The `karakeep-browser.service` runs Chromium in headless mode inside an unprivileged LXC. This requires careful attention to sandbox settings - some Chromium sandbox features require kernel capabilities not available in unprivileged containers.
- **SQLite WAL mode:** `DB_WAL_MODE=true` enables Write-Ahead Logging, which improves concurrent read performance and reduces lock contention between the web process and background workers.
- **Disk usage watch:** At 65% of 10 GB, the disk is filling up. The `assets/` directory grows as more pages are snapshotted. Consider increasing the disk or periodically pruning old snapshots.
- **A local model that is not always on is worse than no local model:** Ollama ran on a desktop that is powered off most of the day. Tagging did not fail loudly, it just recorded `taggingStatus: failure` and moved on, so bookmarks quietly accumulated without tags. Privacy was never the deciding factor here - availability was.
- **Prompt guardrails are a symptom of a weak model:** The Ollama-era tagging prompt shouted `HARD LIMIT: Generate EXACTLY 3 to 5 tags total. Never generate more than 5 tags under any circumstances.` With Gemini and a structured output schema, one calm sentence does the same job. The rewritten prompt also uses the `$tags` placeholder, which shows the model the existing tags so it reuses them instead of inventing `LLM`, `LLMs` and `Large Language Model` as three separate tags.
- **`SERVER_VERSION` in the env file lied:** It read `1.37.0`, which is a Meilisearch version, not a Karakeep one - Karakeep is versioned `0.33.x`. The community-script update rewrites this line with `sed`, so a stale value survives indefinitely. Never read the version from there; read it from the running workers log.
- **The helper script rebuilt from source on every update:** `CLEAN_INSTALL=1` wiped `/opt/karakeep`, then `pnpm install && pnpm build` ran for three apps, plus `pnpm rebuild better-sqlite3` and a DB migration. The script also pins Node 22 with a comment pointing at an upstream crash (`karakeep-app/karakeep#2989`). None of that is version controlled, and the build needs a temporary CPU/RAM bump. This is what motivated the move to compose.
- **The two installs cannot run in parallel:** Both write the same SQLite database, so a side-by-side comparison on the same data directory would corrupt it. The migration is a clean cutover with a backup, not a gradual one.
- **Disk:** grown to 18 GB on 2026-08-13. The images are ~3 GB; the 3.5 GB `/opt/karakeep` source tree can be deleted once the compose stack has proven itself.
