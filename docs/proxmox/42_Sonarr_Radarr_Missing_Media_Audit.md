# Why 2600 Episodes Went Missing: Auditing Sonarr and Radarr Against the Wrong Suspect

**Date:** 2026-08-24
**Hostname:** pve (Proxmox VE 9.1), docker-host (LXC 100)
**IP address:** 192.168.0.109, 192.168.0.110

---

## Overview

The report was: "shows we watched a while ago are gone, and Sonarr says Missing - but I know I downloaded them." The suspicion was hardlinks: deleting a torrent in qBittorrent had supposedly taken the library copy with it.

The suspicion was wrong, and the way it was wrong is the useful part. Hardlinks were never enabled. qBittorrent never touched those files. Two USB disks in the MergerFS pool were reformatted, eight months apart, and the library was never copied back. Sonarr and Radarr did exactly what they are supposed to do: they rescanned, found nothing, and removed the database rows.

The evidence that settles it is a filesystem creation timestamp compared against an application event log.

## Step 1: eliminate the suspect before investigating anything else

Both applications expose the setting directly. There is no need to open a web UI:

```bash
SK=$(grep -o "<ApiKey>[^<]*" /srv/docker-data/sonarr/config.xml | cut -d">" -f2)
curl -s -H "X-Api-Key: $SK" http://localhost:8989/api/v3/config/mediamanagement
```

```json
{
  "recycleBin": "",
  "recycleBinCleanupDays": 7,
  "copyUsingHardlinks": false,
  "deleteEmptyFolders": true,
  "autoUnmonitorPreviouslyDownloadedEpisodes": true
}
```

Radarr answered the same on port 7878. `copyUsingHardlinks: false` means both applications **copy** on import. The torrent keeps seeding from `/downloads`; the library holds an independent second copy on a different inode. Deleting a torrent with its data physically cannot remove an imported library file.

That closes the reported theory in one request. It does not explain where the files went.

### The hardlink test that lies

A tempting next step is to prove hardlinks would work anyway:

```bash
cd /mnt/storage/media
dd if=/dev/zero of=downloads/.hltest bs=1k count=4
ln downloads/.hltest tv/hun/.hltest && echo OK
```

This printed `OK` - and the conclusion drawn from it was wrong.

MergerFS is mounted with `category.create=mfs` (most free space). A hardlink can only exist inside a single filesystem, so it succeeds precisely when the source and target happen to land on the same branch. A 4 KB test file lands wherever there is the most room; a real 20 GB download does the same, but the destination library folder may already live on a different disk, and then `link()` fails with `EXDEV`. The test proves nothing about the general case.

**A single-file hardlink test across a union filesystem is not evidence.** Either test with the real file on the real branch, or reason about the branch layout instead.

## Step 2: get the deletion history out of the application, not the filesystem

Sonarr records why every file record disappeared. Event type 5 is `episodeFileDeleted` (Radarr uses 6 for `movieFileDeleted`), and the `reason` field is the whole answer:

| reason | Meaning |
|---|---|
| `Manual` | Someone deleted it through the UI |
| `Upgrade` | Replaced by a better release |
| `MissingFromDisk` | The rescan found nothing; the row was removed **after** the file was already gone |

`MissingFromDisk` is the exoneration: it means Sonarr did not delete anything. Something outside Sonarr did.

The API paginates, and Sonarr returns pretty-printed JSON, so a naive line-by-line parse fails. Concatenated pages are read with `raw_decode`:

```python
import json, collections
s = open("/tmp/hist.json").read()
dec = json.JSONDecoder(); i = 0; recs = []
while i < len(s):
    while i < len(s) and s[i].isspace(): i += 1
    if i >= len(s): break
    o, i = dec.raw_decode(s, i)
    recs += o.get("records", [])

cnt = collections.Counter((r["date"][:10], r["data"].get("reason", "?")) for r in recs)
for k, n in sorted(cnt.items()):
    if n >= 10: print(k[0], k[1], n)
```

The output is not a trickle. It is two cliffs:

```
2025-08-16  MissingFromDisk   1466   (Sonarr)
2025-08-16  MissingFromDisk    273   (Radarr)
2025-12-22  MissingFromDisk    966   (Sonarr)
2026-02-09  MissingFromDisk    100
2026-08-12  MissingFromDisk     51
```

Totals across the whole history: 2657 `MissingFromDisk`, 309 `Manual`, 42 `Upgrade`.

Two single days account for 2705 of them. Nobody deletes 1739 files by hand in one afternoon across two separate applications.

## Step 3: the timestamp that closes the case

If a whole slice of the library vanished on one day, ask the filesystem when it was born:

```bash
for d in a b c d; do
  echo "=== /dev/sd${d}1 ==="
  tune2fs -l /dev/sd${d}1 | grep -E "Filesystem created|Filesystem volume"
done
```

```
=== /dev/sda1 ===   volume: data1     created: Fri Dec 19 15:17:19 2025
=== /dev/sdb1 ===   volume: data2     created: Fri Dec 19 15:17:57 2025
=== /dev/sdc1 ===   volume: Filmek    created: Wed Oct 30 22:17:27 2024
=== /dev/sdd1 ===   volume: Filmek2   created: Sat Aug 16 11:17:07 2025
```

Cross-checked against the oldest surviving file on each branch:

| Disk | Filesystem created | Oldest file on it | Records purged that day |
|---|---|---|---|
| `/dev/sdd1` = `/mnt/disk4` | **2025-08-16 11:17** | 2025-08-16 15:39 | 1466 episodes + 273 movies |
| `/dev/sda1` = `/mnt/disk1` (+ `/dev/sdb1`, parity) | **2025-12-19 15:17** | 2025-12-22 19:49 | 966 episodes |

Each mass purge follows a `mkfs` on a pool member by hours. The disks were reformatted; their contents were not restored; the applications noticed on the next rescan.

`tune2fs -l` is the fastest way to date a data loss that predates your logs. The system journal on this host only reaches back a month. The superblock remembers years.

## Step 4: what is actually recoverable

Three separate recovery paths were checked, and two of them were already closed:

**Restic does not hold the media.** The host backup script excludes every pool member by design:

```bash
restic -r $REPO backup / \
  --exclude /mnt/disk1 --exclude /mnt/disk2 \
  --exclude /mnt/disk3 --exclude /mnt/disk4 \
  --exclude /mnt/storage
```

**SnapRAID parity no longer holds it either.** `snapraid status` reported the newest block synced one day earlier. Parity reflects the current state of the array, not its state before the wipe. `snapraid fix` would restore exactly what is already there.

This is the real cost of the incident, and it is worth stating plainly: **with one parity disk, a wiped data disk is fully recoverable by `snapraid fix -d dN` right up until the next sync runs.** The sync after the wipe is what destroyed the only remaining copy. Nothing about SnapRAID warns you; a sync is a sync.

**The recycle bin was empty in both applications** (`recycleBin: ""`), so the 309 `Manual` deletions were permanent too.

What did survive: comparing every zero-file series against the filesystem found a handful of folders that still contain video files the applications no longer track.

```python
import json, os
M = {"/tv/": "/mnt/storage/media/tv/", "/anime/": "/mnt/storage/media/anime/",
     "/movies/": "/mnt/storage/media/movies/"}
def real(p):
    for k, v in M.items():
        if p.startswith(k): return p.replace(k, v, 1)
    return p

ser = json.load(open("/tmp/ser.json"))
z = [s for s in ser if s["statistics"]["episodeFileCount"] == 0
                    and s["statistics"]["totalEpisodeCount"] > 0]
gone = [s for s in z if not os.path.isdir(real(s["path"]))]
print(len(z), "series with no files;", len(gone), "whose folder is also gone")
```

```
SONARR: 106 series, 47 with zero files -> 38 folders absent, 9 present
RADARR: 683 movies, 223 without a file -> 222 folders absent, 1 present
```

The nine present folders split further: three still hold 70 video files between them and come back with a manual import. The rest are empty shells left by `deleteEmptyFolders` not having run.

**Path mapping matters when you audit from a third machine.** The API reports container paths (`/tv/hun/...`); the disk is at `/mnt/storage/media/tv/hun/...`. An audit script that skips the translation reports every single title as missing and teaches you nothing.

## Step 5: what the paths reveal about a second, smaller failure mode

Among the 38 vanished series folders, many paths were raw release directory names rather than a clean library layout:

```
/tv/hun/Show.Name.S02.BDRip.x264.HUN-GROUP
/tv/hun/Other.Show.S01-S05.Complete.HUN.DVDRip
```

These were never imported by Sonarr. They are download folders that were adopted as library folders - the series was added in Sonarr pointing directly at the torrent's own directory. For those, and only those, the original suspicion is real: the library copy *is* the torrent copy, and deleting the torrent with its data does destroy it.

This is possible because qBittorrent has the library folders mounted alongside `/downloads`:

```yaml
volumes:
  - /mnt/storage/media/downloads:/downloads
  - /mnt/storage/media/tv/hun:/tv/hun
  - /mnt/storage/media/movies/hun:/movies/hun
```

That is deliberate here: when the automatic search fails to find a Hungarian release, the download is saved into the library by hand. The mount stays. The workflow depends on it.

A snapshot of the current torrents confirms the risk is dormant rather than active. Save paths can be read without the WebUI password, straight from the resume data:

```bash
grep -aoE "save_path[0-9]+:[^:]{0,80}" \
  /srv/docker-data/qbittorrent/data/BT_backup/*.fastresume
```

All 18 active torrents resolve to `/downloads` or `/downloads/delete`. Nothing is currently seeding out of the library.

## The fix: a recycle bin that does not copy across disks

Nothing recovers the lost titles. The change worth making is the one that makes the *next* accidental deletion reversible - and hardlinks stay off, because on a `category.create=mfs` pool they are unreliable by construction.

The naive approach is to point the recycle bin at a path both containers already mount, such as `/downloads/.recyclebin`. On this pool that is a trap: `/mnt/storage/media/downloads` exists only on `disk1`, so deleting a season that lives on `disk4` becomes a cross-disk copy of tens of gigabytes over USB, followed by a delete.

MergerFS resolves a rename inside a single branch when the destination directory exists on that branch. So create it on **every** branch, not through the pool:

```bash
for b in 1 3 4; do mkdir -p /mnt/disk$b/media/.recyclebin; done
```

The LXC is unprivileged, so host UID 0 appears as `nobody` inside the container. The new directory must match the rest of the media tree, or the application logs `Permission denied` and silently skips the recycle bin:

```bash
stat -c "%u:%g %n" /mnt/disk1/media/tv        # 100000:100000
for b in 1 3 4; do chown 100000:100000 /mnt/disk$b/media/.recyclebin; done
```

Mount it into both stacks:

```yaml
volumes:
  - /mnt/storage/media/downloads:/downloads
  - /mnt/storage/media/.recyclebin:/recyclebin
```

Then set it through the API, preserving every other field:

```bash
curl -s -H "X-Api-Key: $KEY" http://localhost:$PORT/api/v3/config/mediamanagement \
  | python3 -c 'import sys,json;d=json.load(sys.stdin);d["recycleBin"]="/recyclebin";d["recycleBinCleanupDays"]=14;print(json.dumps(d))' > /tmp/mm.json
curl -s -X PUT -H "X-Api-Key: $KEY" -H "Content-Type: application/json" \
  -d @/tmp/mm.json http://localhost:$PORT/api/v3/config/mediamanagement
```

Verify that the branch-local rename actually happens, rather than assuming it:

```bash
dd if=/dev/zero of=/mnt/disk4/media/tv/.branchtest bs=1M count=200
time mv /mnt/storage/media/tv/.branchtest /mnt/storage/media/.recyclebin/.branchtest
for b in 1 3 4; do [ -f /mnt/disk$b/media/.recyclebin/.branchtest ] && echo "landed on disk$b"; done
```

```
landed on disk4
real	0m0.003s
```

200 MB in 3 ms, same branch. A cross-disk fallback would have taken seconds and doubled the space.

Finally, keep the bin out of parity so a fortnight of pending deletions does not churn every sync - in `/etc/snapraid.conf`, where paths are relative to each data disk root:

```
exclude /media/.recyclebin/
```

## Verifying, and what stays open

```
port 8989 (sonarr) -> recycleBin='/recyclebin'  cleanupDays=14  hardlinks=False
port 7878 (radarr) -> recycleBin='/recyclebin'  cleanupDays=14  hardlinks=False
```

Two items looked open at the end of the audit. Both turned out to be wrong, and the way they were wrong is worth keeping.

### The absent cron line was not a regression

Root's crontab on pve carries the comment but not the job:

```
# SnapRAID sync minden vasárnap hajnali 3-kor
0 11,19 * * 0 /root/sync-to-nobara.sh
```

`journalctl -u cron` confirms nothing ran at 03:00, yet `snapraid status` reported the newest block synced a day earlier. The obvious reading - a job that silently stopped being scheduled - was wrong. SnapRAID has not been driven by cron here since 2026-07-25. It runs under `snapraidd`, whose own scheduler owns the slot, and the cron line was removed on purpose as part of that migration:

```console
root@pve:~# grep maintenance_schedule /etc/snapraidd.conf
maintenance_schedule = Sun 03:00
```

That value read `Sun 03:00` at the time of this audit. It became a nightly `03:00` on
2026-08-29 - see [28 - SnapRAID Daemon Setup](./28_SnapRAID_Daemon_Setup.md) for why a
week between syncs was the wrong end of the range.

The log directory shows the chain actually running, week by week:

```
20260823-030003-up.log
20260823-030014-sync.log
20260823-034411-scrub.log
20260823-040848-down.log
```

**An orphaned comment in a crontab is not evidence that a job stopped running.** It is evidence that something else took the job over and nobody deleted the comment. Check for a daemon, a systemd timer, and the tool's own scheduler before concluding anything. See [28 - SnapRAID Daemon Setup](./28_SnapRAID_Daemon_Setup.md).

### The delete guard exists, under a different name in a different file

`grep deletethreshold /etc/snapraid.conf` finds nothing, because that is `snapraid-runner`'s key in the CLI's config. The daemon spells it differently and keeps it in its own file:

```console
root@pve:~# grep threshold /etc/snapraidd.conf
sync_threshold_deletes = 1000
sync_threshold_updates = 100
```

**Grepping the wrong config file for the wrong key name reads exactly like an absent feature.** When a tool has both a CLI and a daemon wrapper, they do not share a config or a vocabulary.

The threshold is set high on purpose: weekly `vzdump` rotation and download cleanup on `d1` routinely remove several hundred files, and at the original value of 50 the sync aborted on ordinary housekeeping - which then blocked the scrub too, because the daemon runs maintenance as a chain. At 1000 it still catches what matters here: both mass losses in this incident removed more than 1700 and 966 files respectively. The guard simply did not exist yet in 2025.

### What is genuinely open: nothing tells anyone when the chain fails

`notify_result` is commented out in `/etc/snapraidd.conf`. The only sink configured is syslog:

```
notify_syslog_enabled = 1
notify_syslog_level = info
#notify_result = curl --narrow -f --max-time 30 --retry 3 -H "Title: %s" ... https://ntfy.sh/your_private_topic
notify_result_level = error
```

This is not theoretical. On 2026-08-09 the sync aborted on the old 50-delete threshold, the chain stopped, and parity sat ten days stale while `systemctl is-active` stayed green and the dashboard looked healthy. Nobody was told. Every other scheduled job in this homelab either pushes to an Uptime Kuma monitor as a dead man's switch or posts to ntfy; the SnapRAID daemon does neither, and it guards the only parity copy of the array.

## Lessons

- **`MissingFromDisk` is an alibi, not a cause.** It proves the application removed a row *after* the file was already gone. The investigation starts outside the application.
- **`tune2fs -l` dates a data loss that predates every log you keep.** The superblock's creation timestamp outlives journald retention by years.
- **A hardlink test on a union filesystem only tests the branch it happened to land on.** `category.create=mfs` decides per file; a 4 KB probe and a 20 GB release do not necessarily agree.
- **A recycle bin on the wrong branch turns a delete into a cross-disk copy.** Create the directory on every branch so the rename resolves locally, and measure it once to confirm.
- **On an unprivileged LXC, a new host directory defaults to `nobody` inside the container.** Match the UID of the surrounding tree or the feature fails quietly.
- **One parity disk protects a wiped data disk only until the next sync.** The recovery window closes on a schedule, unattended - so the delete threshold that refuses to sync after a mass removal is the guard that matters, and it has to be loud enough to reach a human.
- **A leftover comment is not evidence of a missing job, and a missing key is not evidence of a missing feature.** Both false alarms in this audit came from reading one config file and stopping there.
