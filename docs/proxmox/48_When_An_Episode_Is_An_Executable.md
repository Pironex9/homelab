# When an Episode Is an Executable: Auditing an Indexer Set After a Malware Grab

**Date:** 2026-09-12
**Hostname:** docker-host (LXC 100), komodo (LXC 105)
**IP address:** 192.168.0.110, 192.168.0.105

---

## Overview

The report was: "there's an episode in the Sonarr queue waiting for import, why?"

Three items were waiting, for two unrelated reasons. One was a legitimate file blocked by a metadata mapping nobody has confirmed. The other two were not episodes at all - they were Windows executables padded to roughly a gigabyte each, and the host had been seeding them out for hours.

The useful part is the method: how to tell a fake release from a real one in two commands, how to tell the difference between an indexer that failed and an indexer that was never trustworthy, and how a Cloudflare solver ends up being the fix for the resulting gap.

## Step 1: read the queue, then stop trusting it

Sonarr's queue does not distinguish "waiting on metadata" from "waiting because I refuse to touch this". Both show `importPending` with a warning. The `statusMessages` do distinguish them:

```bash
curl -s "http://localhost:8989/api/v3/queue?apikey=your_sonarr_api_key_here&pageSize=100" \
  | python3 -c "
import sys,json
for r in json.load(sys.stdin)['records']:
    print(r['title'][:70], r['trackedDownloadState'])
    for m in r.get('statusMessages') or []:
        print('   ', m['title'][:70])
        for x in m.get('messages') or []: print('      -', x[:90])
"
```

```
Hazassag.elso.latasra.S04E11...   importPending
    - This show has individual episode mappings on TheXEM but the mapping for
      this episode has not been confirmed yet
MobLand S02E01 ... x265 NTb.exe   importPending
    - Caution: Found executable file with extension: '.exe'
Dark Matter 2024 S02E04 ....exe   importPending
    - Caution: Found executable file with extension: '.exe'
```

Two of the three names end in `.exe`. That is not a mislabelled container - the torrent's single payload file is the executable.

## Step 2: identify the payload, do not reason about it

Two read-only commands settle what a file is. Nothing here executes anything:

```bash
file -b "MobLand S02E01 1080p WEB-DL DDP5 1 x265 NTb.exe"
ffprobe -v error -show_entries format=format_name -of default=nw=1 "$f"
```

```
PE32+ executable (GUI) x86-64, 6 sections, for MS Windows      926 MB
PE32+ executable (GUI) x86-64 (stripped to external PDB)      1011 MB
ffprobe, both: Invalid data found when processing input
```

Genuine Windows binaries, no video stream at all, padded to about a gigabyte so the size column looks like a real episode. Padding also pushes them past the size cap of many AV scanners.

**Do not skip `ffprobe` because `file` already answered.** The pair is the evidence: one says what the header claims, the other says there is no media inside. A real episode with a wrong extension passes the second check.

### The part that was still running

```bash
docker exec qbittorrent sh -c "curl -s 'http://127.0.0.1:8080/api/v2/torrents/info'"
```

```
Dark Matter ... NTb.exe   state=stalledUP  uploaded=75.9 MB  seeding_time=14382
MobLand ... NTb.exe       state=stalledUP  uploaded=24.7 MB  seeding_time=58271
```

Sonarr refusing to import does nothing about the torrent client. Both files had been seeding in the `tv-sonarr` category the whole time, and the host had pushed out 100.6 MB of malware between them. **A blocked import is not containment**; the download client is a separate decision.

Note the access pattern in that command. The container has `WebUI\LocalHostAuth=false`, but a request to the host's own `127.0.0.1:8080` arrives through the port mapping from the Docker gateway address and gets a 403. `docker exec` into the container is what satisfies the localhost exemption.

## Step 3: separate the indexer that failed from the indexer that never could

Both came from the same place:

```bash
curl -s ".../api/v3/history?apikey=...&pageSize=60" # eventType grabbed
```

```
2026-09-12T05:22  Dark Matter 2024 S02E04 ...  indexer: TorrentDownload (Prowlarr)
2026-09-11T17:13  MobLand S02E01 ...           indexer: TorrentDownload (Prowlarr)
```

And Sonarr's own blocklist showed it was not new:

```
2026-09-05T09:35:09   Dark Matter 2024 S02E03 1080p x265-ELiTe.mkv.exe
```

A third instance, a week earlier, with a `.mkv.exe` double extension. Three for three caught by the extension filter - the guard works, and the supply is continuous.

The distinction that actually predicts this is not size or age. It is **whether the site controls who uploads**:

| class | examples | fake-release risk |
|---|---|---|
| scrape aggregator - indexes whatever it finds, no upload control | TorrentDownload, LimeTorrents, ExtraTorrent, Knaben, kickasstorrents | highest; this is the class that served all three |
| moderated public, verified-uploader system | 1337x | moderate; the risk lives in unverified uploads |
| single-group feed - one publisher, no user submissions | EZTV, YTS, SubsPlease, showRSS | the fake-release vector does not exist |
| private tracker - ratio-gated, moderated | invite-only sites | lowest |

Disabling one aggregator in Prowlarr is a single boolean, and it propagates:

```bash
# GET the indexer, set enable=false, PUT it back
# Prowlarr pushes the change to Sonarr/Radarr within seconds:
TorrentDownload (Prowlarr)   rss=False autoSearch=False interactive=False
```

Clean-up order matters. Disable the indexer **first**, then remove the queue items with `removeFromClient=true&blocklist=true&skipRedownload=false`, so the automatic replacement search cannot go back to the source that served the malware.

## Step 4: the library audit, and the incomplete search that got it wrong

The first pass reported the library clean. It was wrong, because the `find` covered four subdirectories out of ten:

```bash
# wrong: /mnt/storage/media has ten subdirectories, not four
find /mnt/storage/media/tv /mnt/storage/media/movies ... -iname "*.exe"
```

**Enumerate the roots before searching under them.** The correct sweep, across every executable extension:

```bash
find /mnt/storage/media \( -iname "*.exe" -o -iname "*.scr" -o -iname "*.bat" \
  -o -iname "*.cmd" -o -iname "*.msi" -o -iname "*.lnk" -o -iname "*.vbs" \
  -o -iname "*.ps1" -o -iname "*.js" -o -iname "*.jar" \) -printf "%10s %p\n"
```

Four hits, all benign - and each needed its own proof rather than a judgement on the filename:

- **`mkvmerge.exe`** (10 MB) in an anime release's `Language Options` folder. `strings` is not installed on the host, so `grep -a` on the binary does the same job: 273 hits for `libmatroska`, 72 for `MKVToolNix`, 7 for `bunkus.org`, and **zero** for `WinHttp`, `URLDownloadToFile`, `CreateRemoteThread`, `VirtualAllocEx` or `powershell`. Genuine MKVToolNix, shipped by the group with two `.bat` files that call it with track-selection flags, exactly as the folder's `readme.txt` describes.
- **A 2009 `.lnk`** under a TV folder. Parsing the LinkFlags bitfield at offset 20 is enough: `HasArguments: False` means it carries no command line at all, only a relative path to a directory. Malicious shortcuts are malicious because of the command they hide; one that cannot hold a command is clutter, not a threat.

A filename is not evidence in either direction. `mkvmerge.exe` is a real executable and harmless; `MobLand S02E01 ... .mkv` would have been malware if the group had bothered to rename it.

## Step 5: the unrelated blocker - an unconfirmed TheXEM mapping

The third queue item was a legitimate Hungarian episode. Its release numbers seasons one lower than TheTVDB, and Sonarr resolves that through TheXEM. The confirmed map is the whole story:

```bash
curl -s "https://thexem.info/map/all?id=447850&origin=tvdb"
```

34 entries, covering only TVDB seasons 1 and 2. Nothing for seasons 3, 4 or 5. Sonarr sees that a XEM mapping exists, extrapolates the rest, flags those episodes `unverifiedSceneNumbering: true`, and then refuses them. The specification is three lines:

```
1. ExistingFile                     -> Accept   (skips the check entirely)
2. any UnverifiedSceneNumbering      -> Reject
3. otherwise                        -> Accept
```

So it is not this episode - every remaining episode of the season will stall the same way. The season's imported episodes got in by **manual import**, which bypasses the specification; the two that nobody got around to are simply still missing.

There is no Sonarr setting for this. Requests #5316, #3385 and #8337 are open, and the wiki records the status as "Unlikely". Renaming the file does not help either: the specification reads the *episode record's* flag, not the filename.

The one real bypass is in `ImportDecisionMaker.cs`:

```csharp
ExistingFile = series.Path.IsParentPath(file),
```

A file already inside the series folder takes the accept branch. So a script that places the episode with correct TVDB numbering and then triggers a rescan would import automatically - but with the season's scheduled run ending in under a week, hand-importing the remainder is less work than a script that encodes a season offset and needs re-aiming next year. The durable fix is to get the mapping extended on TheXEM, which is external and slow enough to be worth starting before the next season rather than during it.

## Step 6: filling the gap - and why not FlareSolverr

Replacing one aggregator with single-group feeds meant adding EZTV (TV) and YTS (movies). YTS went in and worked immediately. EZTV did not:

```
https://eztvx.to/      blocked by CloudFlare Protection
https://eztv.wf/       blocked by CloudFlare Protection
https://eztv.tf/       blocked by CloudFlare Protection
https://eztv.yt/       blocked by CloudFlare Protection
https://eztv1.xyz/     blocked by CloudFlare Protection
```

All five official mirrors from the Cardigann definition, so not a domain problem. The documented answer is FlareSolverr - except TRaSH Guides records it as *"currently non-functional. It is also being monitored by the Cloudflare team, so it is unlikely to ever be fixed."* Installing it would have added a dead container.

[Byparr](https://github.com/ThePhaseless/Byparr) serves `POST /v1` with the same `LinkRequest`/`LinkResponse` shape on the same port 8191, which is what makes Prowlarr's built-in FlareSolverr proxy type drive it with no modification. Confirm that from the source rather than a blog post - the README does not mention FlareSolverr at all:

```python
@router.post("/v1")
async def read_item(request: LinkRequest, dep: BrowserDep) -> LinkResponse:
```

### The compose file, and the network discovery that shaped it

```yaml
services:
  byparr:
    image: ghcr.io/thephaseless/byparr:latest
    container_name: byparr
    environment:
      - TZ=Europe/Budapest
    shm_size: 512mb          # required in LXC; the headless browser dies without it
    restart: unless-stopped
    networks:
      - prowlarr_default     # Prowlarr calls POST /v1 through it
      - arr_stack            # homepage polls /health for the status dot
networks:
  prowlarr_default:
    external: true
  arr_stack:
    external: true
```

Two decisions worth the words:

**Two networks, because Prowlarr is not where its compose file says it is.** The prowlarr stack declares `arr_stack` as an external network at the bottom of the file, but the service block never joins it - so Prowlarr actually runs alone on `prowlarr_default`. A solver placed on `arr_stack` would have been invisible to it. Joining both networks reaches Prowlarr and the dashboard without recreating the working Prowlarr container.

**No published port.** The only page Byparr serves is FastAPI's Swagger UI (`/` redirects to `/docs`), and the API behind it fetches arbitrary URLs with a real browser. Publishing that on the LAN is an unauthenticated fetch proxy, which is a poor trade for API documentation. Both consumers reach it by container name instead.

Measured after: 143 MiB resident, 0.07% CPU idle.

### Proof it does the work

Byparr's log is the confirmation that the challenge is real and being cleared, not that the site simply stopped checking:

```
INFO: From: 172.21.0.2: https://1337x.to/cat/Movies/1/
INFO: Challenge detected, waiting for it to clear...
INFO: Done https://1337x.to/cat/Movies/1/ in 6.62s
INFO: 172.21.0.2 - "POST /v1 HTTP/1.1" 200 OK
```

And live searches, which a connection test does not prove:

```
EZTV   "Silo"     -> 199 results (Silo S03E08, 416 seeders)
1337x  "MobLand"  ->  80 results
YTS    "Dune..."  ->   6 results, 1.60-7.95 GB
```

One quirk to know before it looks like a fault: 1337x returns 0 for the bare query `Dark Matter` while `Dark Matter 2024`, `Breaking Bad` and other multi-word queries all return 80. It is not systemic, and Sonarr searches with a season or year appended anyway.

## Step 7: the GitOps handover that looked done and was not

The stack was created in Komodo against the shared repo resource - all stacks here link one `Repo` resource rather than each carrying a URL, which is why their `repo` field is empty and `linked_repo` holds the id:

```json
{"type":"CreateStack","params":{"name":"byparr","config":{
  "linked_repo":"<repo resource id>",
  "run_directory":"compose/proxmox-lxc-100/byparr/",
  "file_paths":["docker-compose.yml"],
  "auto_pull":true, "auto_update":true
}}}
```

`DeployStack` then reported success, `deployed_hash` matched `latest_hash` - and the container was still running from the manual deployment path:

```
project=byparr
workdir=/srv/docker-compose/byparr        <- not the Komodo clone
```

Compose had been handed the same project name and a byte-identical service definition, so it correctly decided there was nothing to do. The deploy succeeded at the only thing it was asked to do and changed nothing. **A green deploy is not evidence that the running container came from the repo** - check `com.docker.compose.project.working_dir` on the container itself.

The fix is to remove the competing source outright: `docker compose down` from the manual path, delete that directory, then deploy again. Leaving it in place leaves a second `docker-compose.yml` that anyone could `up -d` from later, silently fighting the GitOps owner.

```
workdir=/etc/komodo/repos/github/compose/proxmox-lxc-100/byparr
status=running health=healthy
```

## Step 8: the dashboard tile

The homepage reads its config directly out of the Komodo clone, so the config change ships through the same push-and-pull path as the compose file, followed by `POST /api/revalidate` because the dashboard is statically generated.

The tile went next to Prowlarr, its only consumer, and carries no `href` - the same reasoning as the unpublished port. `siteMonitor` uses the container name rather than an `IP:port` like every neighbour, precisely because nothing is published:

```yaml
- Byparr:
    icon: https://cdn.jsdelivr.net/gh/selfhst/icons/png/byparr.png
    description: Cloudflare solver for EZTV and 1337x
    siteMonitor: http://byparr:8191/health
    statusStyle: dot
```

This dashboard holds one layout rule - every group's `columns` equals its item count, so no row is ever partially filled - and a new tile means both numbers move:

```
Media Links:  5 items, columns: 5   ->   6 items, columns: 6
```

Verify it by counting, then verify it by looking. Parent items and nested-subgroup items have to be counted separately, and `yaml.safe_load` cannot parse these files at all because the `{{HOMEPAGE_VAR_*}}` placeholders read as unhashable keys - an indent-based count works. Then screenshot: the count proves the grid is full, only the image proves the icon is visible on a dark theme, which is a defect this dashboard has shipped before.

## Takeaways

- `file` plus `ffprobe` identifies a fake release in seconds. Run both: one reads the header, the other proves there is no media inside.
- A blocked import is not containment. Sonarr refusing a file says nothing about the torrent client, which may still be seeding it out.
- Check the blocklist before concluding an incident is the first one. It keeps the history that the queue does not.
- Judge an indexer by whether it controls who uploads, not by its catalogue size. Single-group feeds have no fake-release vector at all.
- Disable the bad indexer before clearing the queue, or the replacement search goes straight back to it.
- Enumerate the directory roots before searching under them; a sweep over four of ten subdirectories returns a clean result that means nothing.
- A filename argues in neither direction. Prove a suspect binary with `grep -a` for library identifiers and for network and injection APIs; prove a `.lnk` from its LinkFlags.
- `unverifiedSceneNumbering` blocks automatic import unconditionally, and no Sonarr setting disables it. Only a file already inside the series folder takes the accept branch.
- Before installing the documented tool, check that it still works. TRaSH Guides had marked FlareSolverr non-functional; the drop-in replacement shares its port and API.
- A compose file's `networks:` declaration proves nothing about the running container - the service block has to join the network. Check with `docker inspect`, not the YAML.
- A successful `DeployStack` whose container still carries the old `working_dir` label deployed nothing. Delete the competing compose directory rather than leaving two sources of truth.
