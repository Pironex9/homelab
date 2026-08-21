# Shelfmark: Wiring a Book Downloader into an Existing Stack

**Date:** 2026-08-21
**Hostname:** docker-host (LXC 100), komodo (LXC 105)
**IP address:** 192.168.0.110, 192.168.0.105

---

## Overview

A dashboard tile on the Homepage instance pointed at `192.168.0.110:8084`, labelled "Calibre Downloader", showing a dead status dot. The container behind it did not exist. Nothing was listening on the port. The tile had been in the repo since at least 2026-07-19.

That is the most useful piece of data in this whole document: the service had died, and nobody missed it for over a month. The first question was not "how do I bring it back" but "should I".

The answer turned out to be yes, for a reason that had nothing to do with the original tool - and the work that followed exposed a class of failure worth writing down: **every piece of documentation about this software was stale, and only measurement from inside the container revealed it.**

## The project moved and changed shape

The old container was `calibre-web-automated-book-downloader`. The project has since been renamed to **Shelfmark**, and it is no longer a single-purpose downloader. It now does metadata search across multiple providers, multi-user request handling with an approval queue, indexer integration, audiobook support and OIDC login.

The maintenance picture, from the GitHub API rather than the README:

| Signal | Value |
|---|---|
| Latest release | v1.3.11, 2026-08-20 |
| Last push | 2026-08-21 (same day) |
| Stars | 3755 |
| Open issues | 47 |

The README states plainly: *"feature stable and maintained on a best-effort basis... There is no roadmap for new features for now."* Releases are still shipping daily, so that note is about ambition, not abandonment. Worth reading it as written rather than inferring decline from the word "best-effort".

## The compose file, and the one non-obvious line

```yaml
services:
  shelfmark:
    image: ghcr.io/calibrain/shelfmark:latest
    container_name: shelfmark
    environment:
      - PUID=0
      - PGID=0
      - TZ=Europe/Budapest
      - INGEST_DIR=/books
    volumes:
      - /srv/docker-data/shelfmark:/config
      - /mnt/storage/media/konyv_ingest:/books
      - /mnt/storage/media/downloads:/downloads
    ports:
      - 8084:8084
    mem_limit: 2g
    restart: unless-stopped
```

`PUID=0` matches the Calibre-Web-Automated container, which owns the ingest directory and moves and deletes files out of it as root. A downloader writing there as `1000:1000` reproduces the permission failure documented in [38 - Calibre Metadata Cleanup](./38_Calibre_Metadata_Cleanup.md).

`mem_limit: 2g` is the line that needs explaining. The standard image ships a real Chromium and launches it to solve challenge pages. Upstream calls 2 GB the safe minimum. The host had 3.9 GB available with 32 other containers running, so the limit is not a formality - without it, one stuck browser process starves everything else on the box.

The measured reality afterwards, after a successful challenge solve:

```
474MiB / 2GiB   23.14%
```

Roughly a quarter of the documented requirement under this workload. The limit stays anyway: it is there for the pathological case, not the normal one, and the normal case is not what takes a host down.

## Every documented endpoint was dead

The setup wizard asks for at least one source URL. The three domains that every guide and forum post names were all non-functional. Establishing that required care, because of a property of this network documented in the [AdGuard Home setup](./05_AdGuard_Home_Setup_Dedicated_LXC_Tailscale_DNS_Integration.md): **the router intercepts all port 53 traffic, so a local DNS lookup never proves which resolver answered.** A plain `dig` here is not evidence.

DNS-over-HTTPS bypasses the interception entirely and gives a trustworthy answer:

```bash
curl -s -H 'accept: application/dns-json' \
  "https://cloudflare-dns.com/dns-query?name=<domain>&type=A" \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['Status'],[a['data'] for a in d.get('Answer',[])])"
```

Status `3` is NXDOMAIN. Two of the three returned that. The third resolved - which looks like success until you check what it resolved *to*: a well-known domain-parking address. **A domain that resolves is not a domain that works**, and an A record is not a service.

The same pattern repeated for the secondary sources. Reachability had to be measured from inside the container, not from the management host, because the two sit behind different DNS paths:

```bash
docker exec shelfmark sh -c "curl -s -o /dev/null -m 12 -w '%{http_code} %{time_total}s' https://<host>/"
```

The results split into four distinct failure modes, and the distinction matters:

| Response | Meaning | Usable? |
|---|---|---|
| `200` in under a second | working | yes |
| `000` after a 12s timeout | reachable name, dead service | no |
| `000` in 0.001s | no DNS resolution at all | no |
| `410 Gone` | server explicitly retired | no |
| `403` with `cf-mitigated: challenge` | Cloudflare challenge | **yes** |

That last row is the one worth internalising. A bare `403` reads like a block, and the instinct is to drop the host. Checking the response headers instead of the status code alone showed `server: cloudflare` and `cf-mitigated: challenge` - a challenge page, not a refusal. This application ships a browser specifically to solve those, so that host is fully usable. Discarding it on the status code would have silently removed a working source.

Response times became the ordering: the application tries mirrors in listed order, so the fastest measured host goes first. That ordering was later confirmed in the logs, which name the mirror actually chosen at runtime.

## The bypass, proven rather than assumed

A container that starts and reports healthy has proven nothing about whether its core function works. The startup warm-up search settled it:

```
403 detected; switching to bypasser: https://<mirror>/search?...
Chrome browser ready (Pure CDP)
Bypass attempt 1/10 using _bypass_method_cdp_solve    -> failed
Bypass attempt 2/10 using _bypass_method_cdp_gui_click -> Bypass successful
Search warm-up complete: 50 results, source is ready
```

Thirteen seconds, first method failed, second succeeded, ten available. The `X11 display failed! Will use regular xvfb!` line in the same block is not an error - there is no X server in a container, so it falls back to a virtual one, which is the intended path.

**"Healthy" is a liveness probe. "50 results" is a functional test.** Only the second one is worth reporting.

## The find that justified the whole exercise

Enumerating the metadata provider modules inside the container turned up one the interface never mentioned:

```
/app/shelfmark/metadata_providers/moly.py
```

Its docstring:

> *Moly.hu metadata provider. Hungarian book catalog, no API key required.*
> *Scraping approach (search URL, book-page structure, language mapping) adapted from the Calibre Moly_hu plugin.*

This directly answers a problem left open the day before. During [38 - Calibre Metadata Cleanup](./38_Calibre_Metadata_Cleanup.md), Open Library returned nothing for most Hungarian titles and confidently wrong matches for others, leaving 43 books without descriptions and 13 with generated placeholder covers. One book had to be identified by hand because no automatic source knew it.

The setup wizard offers three providers. Reading `core/onboarding.py` shows why the fourth is missing:

```python
onboarding_options = [
    {"value": "hardcover", "label": "Hardcover (Recommended)", ...},
    {"value": "openlibrary", "label": "Open Library", ...},
    {"value": "googlebooks", "label": "Google Books", ...},
]
```

The wizard hardcodes its list. The real settings field builds its options dynamically from registered providers, so the Hungarian catalog is reachable - just never during onboarding. Following the wizard's recommendation and stopping there means never finding it.

After switching, the book that needed manual identification the day before:

```
- moly | Félelem és reszketés | ['Søren Kierkegaard'] | hu
```

First page of results, correct author, correctly tagged language.

**The lesson is not about this application.** A setup wizard is a curated path written for the median user in the maintainer's locale. It is not an inventory. When a wizard's options do not fit, the question is whether the software actually lacks the capability or whether the wizard simply does not surface it - and the source tree answers that in one `ls`.

## Two assumptions that were wrong

Both were stated as guesses at the time, and both were wrong in the same direction: the existing infrastructure was more capable than assumed.

**"The indexer aggregator is probably configured for video only."** Reading its database directly - no API key needed - showed several enabled indexers including a regional tracker with a dedicated ebook category. Querying the running application's release endpoint proved it end to end:

```
Dune           releases: 115
Harry Potter   releases: 2
```

Including Hungarian-language editions. The category mapping works, which no amount of reasoning about configuration would have established.

```bash
docker exec <indexer-container> python3 -c "
import sqlite3
c = sqlite3.connect('/config/<app>.db')
for r in c.execute('select Id,Name,Enable from Indexers order by Id'): print(r)
for r in c.execute('select Name,Implementation,Enable from DownloadClients'): print(r)
"
```

Reading the application's own SQLite database answers "what is configured" without an API key and without a UI. Useful whenever the credential is the thing standing between you and a five-second question.

**"Downloads are handed off through the indexer aggregator."** A community discussion said so, but it described an older release. The current source disagrees:

```
download/clients/qbittorrent.py:197:  raw_url = config.get("QBITTORRENT_URL", "")
download/clients/qbittorrent.py:208:  username = config_text(config.get("QBITTORRENT_USERNAME", ""))
download/clients/qbittorrent.py:209:  password = config_text(config.get("QBITTORRENT_PASSWORD", ""))
```

The application talks to the torrent client **directly**. The aggregator only searches. This changes what credentials are needed and where they go - and the shipped source is the authority, not a forum thread about a previous version.

## The path-matching trap

This is the failure most likely to bite, because it produces no error.

The torrent client reports completed downloads by **absolute path**, as it sees them inside its own container:

```
Session\DefaultSavePath=/downloads
```

The consuming application then opens that exact path to copy the file into the ingest directory. If `/downloads` does not exist in the consumer's namespace, or maps to different content, the file is simply never found. The download succeeds. The torrent seeds. Nothing is logged as broken. The book never appears in the library.

The fix is to mount the same host directory at the identical container path in both containers:

```yaml
# torrent client
- /mnt/storage/media/downloads:/downloads
# consumer
- /mnt/storage/media/downloads:/downloads
```

Verification is one command, and skipping it is how this trap survives to production:

```bash
docker exec shelfmark ls /downloads | head -4
```

**Any two containers exchanging absolute paths must agree on those paths.** Bind mounts make container paths arbitrary, which is exactly why they need to be deliberately aligned rather than assumed.

The post-import action was left at `keep`, so completed torrents continue seeding from `/downloads` while a copy travels to the library. On a private tracker, an action that removes or relocates the file destroys ratio.

## Configuring it from the command line

The application exposes a full HTTP API, and when the authentication method is `none` it needs no token:

```bash
# read a settings tab
curl -s http://192.168.0.110:8084/api/settings/mirrors

# write to it
curl -s -X PUT http://192.168.0.110:8084/api/settings/mirrors \
  -H 'Content-Type: application/json' \
  -d '{"LIBGEN_MIRROR_URLS":["https://..."],"ZLIB_MIRROR_URLS":["https://..."]}'
```

```json
{"message":"Updated 3 setting(s)","requiresRestart":false,"updated":[...],"success":true}
```

The response reports whether a restart is required, which makes it safe to script. The same route pattern runs the interface's own test buttons:

```bash
curl -s -X POST http://192.168.0.110:8084/api/settings/<tab>/action/test_<service> -d '{}'
```

```
{"message":"Connected to Prowlarr 2.5.2.5491","success":true}
{"message":"Connected to qBittorrent (API v2.15.1)","success":true}
```

Settings written this way persist to `/config/plugins/<tab>.json` and survive container recreation, because that directory is a bind mount. Confirmed by redeploying and re-reading the files.

Credentials were deliberately left to the web interface. Secrets typed into a browser form do not pass through a shell history, a terminal scrollback or a chat transcript.

## Registering the stack in Komodo

The stack was first started manually, which left it running but invisible to the GitOps controller. Registering it after the fact is one API call, and the reliable way to build the payload is to copy an existing stack's configuration rather than compose one from documentation:

```bash
# read a known-good stack
curl -s -X POST "$KOMODO/read" -H "X-Api-Key: $KEY" -H "X-Api-Secret: $SECRET" \
  -d '{"type":"GetStack","params":{"stack":"<existing-stack>"}}'

# create the new one with the same shape, changing only run_directory
curl -s -X POST "$KOMODO/write" -H "X-Api-Key: $KEY" -H "X-Api-Secret: $SECRET" \
  -d '{"type":"CreateStack","params":{"name":"shelfmark","config":{ ... }}}'
```

Verification that it actually took ownership:

```json
{"state": "running", "deployed_hash": "fb8c865", "latest_hash": "fb8c865", "project_missing": false}
```

`deployed_hash` equal to `latest_hash` means the running containers match the committed compose file. `project_missing: false` means the controller found the project it expects. The container's own label confirms it from the other side:

```
com.docker.compose.project.working_dir = /etc/komodo/repos/github/compose/proxmox-lxc-100/shelfmark
```

### One race worth knowing about

Firing `PullStack` and `DeployStack` back to back does not work. Both return immediately with `status: InProgress`, so the deploy runs against the *old* checkout and silently produces a container built from the previous compose file. The symptom was a newly added volume simply not being present:

```
/srv/docker-data/shelfmark -> /config
/mnt/storage/media/konyv_ingest -> /books
        <- the new mount, absent
```

The repository clone on disk already contained the new commit, which is what makes this confusing: the file was right, the container was wrong. Deploying a second time, after the pull had finished, applied it. **When an asynchronous API returns "in progress", chaining the next call to it is a race, and the failure mode is a stale success rather than an error.**

## What is verified and what is not

Verified by measurement:

- Service running, HTTP 200, v1.3.11, registered in Komodo with matching hashes
- Challenge bypass functional - 50 results returned on a live search
- Memory ceiling adequate with large margin - 474 MiB against a 2 GiB limit
- Both external service connections tested through the application's own test actions
- Indexer search end to end - 115 releases for a common title, including regional-language editions
- Settings persistence across container recreation
- The consumer container can read the torrent client's download directory

Not yet verified, and stated as such: **a complete download has not been run.** Whether a torrent is added, completes, and is copied into the ingest directory where Calibre-Web picks it up is the one link still untested. Every component in that chain has been tested individually, which is not the same thing as the chain working.

## Notes

- Details of specific external sources are kept out of this public document; the working configuration lives in the private notes.
- The image is tracked on a moving tag with automatic updates enabled, matching the other stacks on this host. That trades review for currency: a broken release lands unreviewed. The digest of the known-good build is recorded in the private notes for rollback.
- The application contains an OIDC implementation and a proxy-auth mode. Authentication is currently `none`, which is why the API needs no token - acceptable on a LAN-only port, and the thing to change first if the port is ever published.
