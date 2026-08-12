# Backup Verification: Restore Test + Per-Guest vzdump Coverage

**Date:** 2026-08-03
**Hostname:** pve
**IP address:** 192.168.0.109

---

## Overview

The backups described in [15 - Backup System](./15_Proxmox_Backup_System_Documentation.md) had been running for months, and both the vzdump job and the restic script reported success. Neither had ever been verified:

- **Nothing had been restored.** The restic script ends with `restic check`, but that only validates metadata. A data pack rotting on disk would not show up, and no file had ever been pulled back out of a snapshot.
- **The daily digest could not see a missing guest.** It counted filenames carrying today's date in the dump directory. One successful guest was enough to turn the line green.

This documents the two fixes: a restore test for the restic repository, and a coverage check for vzdump.

---

## 1. Restore Test (`restore-test.sh`)

Deployed on pve as `/root/restore-test/restore-test.sh`, with its `.env` beside it (the script sources `.env` from its own directory).

Repositories are discovered, not listed: any subdirectory of `$BACKUP_DEST_NFS` holding `config`, `data/` and `snapshots/` counts as one. Under `/mnt/disk1/backup` that finds `proxmox-host` and correctly skips the sibling `proxmox` directory, which is vzdump output.

Per repository:

| Step | What it proves |
|---|---|
| Age of the newest snapshot | The backup actually ran. Fails past `RESTORE_TEST_MAX_AGE_DAYS`. |
| `restic check --read-data-subset=1%` | Reads real data packs, not just metadata, so silent bit rot surfaces. |
| Restore 3 files from a random snapshot | Size compared against the snapshot tree, sha256 against `restic dump`. Two independent sources inside the repository, so a truncated restore cannot pass both. |

One summary goes to ntfy, and the exit code is non-zero if anything failed so cron surfaces it. Every repository is tested even after an earlier one fails, so one bad repository cannot mask the rest.

### Configuration

```bash
BACKUP_DEST_NFS=/mnt/disk1/backup
RESTIC_PASSWORD_FILE=/root/.secrets/restic-password
NTFY_BASE_URL=http://192.168.0.71:8091
NTFY_TOPIC=homelab-digest
RESTORE_TEST_MAX_AGE_DAYS=8
RESTORE_TEST_FILES=3
RESTORE_TEST_SUBSET=1%
RESTORE_TEST_LOG=/var/log/homelab/restore-test.log
RESTORE_TEST_TMPDIR=/var/tmp
```

Three of these are not defaults, and each has a reason:

- **`RESTORE_TEST_MAX_AGE_DAYS=8`.** The host backup is weekly. The stock 2-day limit would fail on every single run.
- **`RESTORE_TEST_TMPDIR=/var/tmp`.** On pve `/tmp` is tmpfs, 16 GB of RAM. Restoring into it would take memory away from running guests. This would not have failed loudly; it would have worked, badly.
- **`NTFY_BASE_URL` on plain HTTP against the LAN IP.** `ntfy.lan` sits behind Caddy, whose TLS layer currently rejects real TLS clients, so an HTTPS URL would silently never deliver.

### Schedule

```bash
0 6 * * 0 /root/restore-test/restore-test.sh >> /var/log/homelab/restore-test-cron.log 2>&1
```

`restic check` takes an exclusive lock on the repository, so the test has to clear the backup window. The Sunday 04:00 backup (backup + `forget --prune` + `check`) finishes at 04:00:38, about 37 seconds, so 06:00 leaves a wide margin.

### Verification

First live run against the real repository:

```
[2026-08-03 09:12:38] Starting restore test for 1 repositories (max snapshot age 8d)
[2026-08-03 09:12:38] Testing repository: proxmox-host
[2026-08-03 09:12:39] OK proxmox-host: newest snapshot 1d 5h old
[2026-08-03 09:12:43] OK proxmox-host: check --read-data-subset=1% passed
[2026-08-03 09:12:51] OK proxmox-host: restored 3/3 files from 599adae7, checksums match
[2026-08-03 09:12:51] Restic restore test OK (1 repos)
EXIT=0
```

Thirteen seconds. Delivery was confirmed by polling the ntfy topic rather than trusting the curl exit code.

The alarm path was tested too, using a throwaway copy of the config with the age limit set to 1 day so the 1d5h-old snapshot would trip it. The live `.env` was left untouched:

```
FAIL proxmox-host: newest snapshot is 1d 5h old (max 1d)
Restic restore test FAILED (1 problems)
EXIT=1
```

A monitoring script that has only ever been seen passing is not monitoring anything yet.

---

## 2. Per-Guest vzdump Coverage in the Daily Digest

`scripts/homelab-digest.sh` runs on LXC 109 at 07:00 and pushes a summary to ntfy. Its backup section used to be:

```bash
backup_count=$(pve "ls /mnt/storage/backup/proxmox/dump/ | grep -c '$today'")
if [[ "${backup_count:-0}" -eq 0 ]]; then
    lines+=("⚠️ Nincs mai vzdump backup")
```

Two problems:

- **A yes/no answer for the whole run.** One guest backed up meant green, even if the other nine had failed.
- **The number meant nothing.** A successful guest leaves three files (`.tar.zst`, `.log`, `.notes`), and a *failed* run still leaves a `.log`. "12 files" could be four successes or twelve failures.

It now compares the vzdump job's `vmid` list from `/etc/pve/jobs.cfg` against the archives that actually exist for today, and names what is missing:

```
Backup: 10/10 guest ma lementve
⚠️ Backup hiányzik: 106, 113
```

Only archives count as success, never logs. If `jobs.cfg` cannot be read, it falls back to the old "did anything run today" check rather than failing.

### The trap: LXC and VM archives have different extensions

The first version matched `.tar.zst` only. Containers do write `.tar.zst`, but QEMU VMs write `.vma.zst`, so VM 101 (Home Assistant) would have been reported missing every single morning despite being backed up correctly. The check matches both.

This is the failure mode that matters most for a monitoring change: a daily false alarm is worse than no alarm, because it is what teaches you to ignore the notification.

### Known limit

The comparison is against the job's `vmid` list, so it catches a backup that failed. It does not catch a guest being removed from the job entirely, since the list shrinks along with it. That is a deliberate exclusion in this homelab rather than an accident, so no separate inventory is maintained for it.

---

## 3. Restic Freshness in the Daily Digest

The weekly restore test proves the repository is *sound*. It does not tell you the backup still *runs*: a broken cron or a full disk would leave the last good snapshot verifiable for months while nothing new arrived. The digest now reports the age of the newest snapshot every morning:

```bash
restic_out=$(pve "RESTIC_PASSWORD_FILE=... timeout 60 restic -r ... snapshots --latest 1 --no-lock")
restic_dt=$(echo "$restic_out" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}' | tail -1)
restic_age=$(( ( $(date +%s) - $(date -d "$restic_dt" +%s) ) / 86400 ))
```

Three deliberate choices:

- **`--no-lock`.** This is a read, and the digest runs at 07:00 while the backup starts at 04:00 and the restore test at 06:00. Taking a lock would put a monitoring check in a position to block a backup, which inverts the point of monitoring.
- **8-day threshold.** The backup is weekly, so one skipped run still passes and two do not. A 7-day threshold would fire on normal jitter.
- **An unreadable repository is its own warning,** separate from a stale one. A wrong password, an unmounted NFS share and a dead cron are different failures, and collapsing them into "stale" would send you looking in the wrong place.

Both warning branches were tested by injecting a fake timestamp rather than waiting for a real failure:

```
⚠️ Restic: a legutolsó snapshot 12 napos
⚠️ Restic: nem olvasható a repo
```

Normal output is one line: `Restic: friss (2 napos snapshot)`.

---

## What This Still Does Not Cover

Worth stating plainly, because partial verification invites false confidence:

| Layer | Size | Verified? |
|---|---|---|
| vzdump, all guests, daily | ~4.1 TB | Coverage and freshness automated; restore exercised ad hoc, never scheduled |
| restic, pve host root, weekly | ~24 GiB | Fully, as of this document |
| SnapRAID, media | ~8.1 TB | Sync and scrub |

The restic layer is the best-verified, and it is also the smallest and the least critical, since a host filesystem is rebuildable in a way that application data is not. Everything that actually matters lives in the vzdump layer.

A scheduled restore test was considered for that layer and deliberately not built. `pct restore` is not an untried path here: containers have been restored from these archives several times, as ordinary recovery after breaking something inside one. Real recoveries are stronger evidence than a synthetic test would be, and adding a ceremonial one would mostly produce a green check. What stays unverified is narrower than "can we restore at all": whether a guest that is never touched would restore correctly after a long gap, which no test short of actually doing it can answer.

`scripts/backup.sh` in the repository used to describe a third setup, one restic repository per Docker service, that was not deployed anywhere: docker-host has no restic installed. Docker data is covered by the daily vzdump of LXC 100 instead. A note saying so was added to the script and to `scripts/README.md`, and it was not enough - on 2026-08-12 the script was still read as evidence that Immich's database was being dumped, which it was not. The file was deleted rather than annotated again. **An unused script that describes a backup is worse than no script**, because the reader who finds it stops looking. `scripts/README.md` now carries a table of the four layers that actually run.

---

## Related Documentation

- [15 - Backup System](./15_Proxmox_Backup_System_Documentation.md) - what is backed up, where, and on what schedule
- [28 - SnapRAID Daemon Setup](./28_SnapRAID_Daemon_Setup.md) - the media parity layer
