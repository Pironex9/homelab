# karakeep LXC

## Overview

| Property | Value |
|----------|-------|
| Hostname | karakeep |
| IP Address | 192.168.0.128 |
| VMID | 106 |
| OS | Debian GNU/Linux 13 (trixie) |
| Kernel | 6.17.4-1-pve |
| CPU | 2 cores |
| RAM | 4 GB |
| Disk | 10 GB (local-lvm, 65% used) |
| Purpose | Self-hosted bookmarking and read-later service |

## Running Services

| Service | Description |
|---------|-------------|
| `karakeep-web.service` | Next.js web frontend (port 3000) |
| `karakeep-workers.service` | Background workers - crawling, AI tagging, link processing |
| `karakeep-browser.service` | Headless Chromium for webpage snapshots and full-page screenshots |
| `meilisearch.service` | Full-text search engine |
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
| karakeep | 0.30.0 | Main application (web + workers + browser) |
| meilisearch | 1.31.0 | Full-text search backend |
| chromium | 143.0.7499.169 | Headless browser for page snapshots |

## Configuration

**Config file:** `/etc/karakeep/karakeep.env`
**Data directory:** `/opt/karakeep_data/` (22 MB)

### Key Settings

| Setting | Value |
|---------|-------|
| `DATA_DIR` | `/opt/karakeep_data/` |
| `NEXTAUTH_URL` | `http://localhost:3000` |
| `MEILI_ADDR` | `http://127.0.0.1:7700` |
| `BROWSER_WEB_URL` | `http://127.0.0.1:9222` |
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

Karakeep can auto-tag and summarize bookmarks using an LLM. Currently configured to use the local **Ollama** instance:

| Setting | Value |
|---------|-------|
| `OLLAMA_BASE_URL` | `http://192.168.0.100:11434/` |
| `OLLAMA_KEEP_ALIVE` | `5m` |
| `INFERENCE_TEXT_MODEL` | `qwen2.5:7b` |

Meilisearch listens only on `127.0.0.1:7700` - not exposed externally.

## Lessons Learned

- **Debian 13 (trixie):** This is the only LXC in the homelab running Debian trixie (testing). All others run bookworm (stable) or Alpine. Trixie provided a newer Chromium version needed by Karakeep's browser service.
- **Chromium in a headless LXC:** The `karakeep-browser.service` runs Chromium in headless mode inside an unprivileged LXC. This requires careful attention to sandbox settings - some Chromium sandbox features require kernel capabilities not available in unprivileged containers.
- **SQLite WAL mode:** `DB_WAL_MODE=true` enables Write-Ahead Logging, which improves concurrent read performance and reduces lock contention between the web process and background workers.
- **Disk usage watch:** At 65% of 10 GB, the disk is filling up. The `assets/` directory grows as more pages are snapshotted. Consider increasing the disk or periodically pruning old snapshots.
- **Ollama over cloud APIs:** Using the local Ollama instance for AI tagging avoids sending bookmark content to external APIs. The tradeoff is slower inference compared to cloud APIs.
