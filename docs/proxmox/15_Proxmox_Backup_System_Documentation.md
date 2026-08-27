**Date:** 2026-02-11
**Updated:** 2026-08-10
**Hostname:** pve
**IP address:** 192.168.0.109

---

## Overview

Backup strategy - two targets, two types of data:

| What | Tool | Primary location | Secondary (Nobara) |
|---|---|---|---|
| LXC/VM backups | vzdump | `/mnt/storage/backup/proxmox/` | `/mnt/hdd/Backup/proxmox-vms/` |
| Proxmox host OS | Restic | `/mnt/disk1/backup/proxmox-host/` | `/mnt/hdd/Backup/proxmox-host/` |

Nobara is not always on - rsync skips gracefully if offline.

---

## 1. LXC/VM Backups (vzdump)

Configured in the Proxmox GUI under Datacenter - Backup.

**Storage**: `backup-hdd` - path `/mnt/storage/backup/proxmox/`

Backups are stored as `.tar.zst` files (vzdump format).

---

## 2. Proxmox Host OS Backup (Restic)

Backs up the Proxmox root filesystem (`/`) to a local restic repository.

### Script: `/root/backup-proxmox-restic.sh`
```bash
#!/bin/bash
REPO="/mnt/disk1/backup/proxmox-host"
export RESTIC_PASSWORD_FILE="/root/.secrets/restic-password"

restic -r $REPO backup / \
  --exclude /mnt/disk1 \
  --exclude /mnt/disk2 \
  --exclude /mnt/disk3 \
  --exclude /mnt/disk4 \
  --exclude /mnt/storage \
  --exclude /mnt/pve \
  --exclude /var/lib/vz \
  --exclude /tmp \
  --exclude /dev \
  --exclude /proc \
  --exclude /sys \
  --exclude /run \
  --exclude '*.img' \
  --exclude '*.qcow2' \
  --exclude /var/tmp

restic -r $REPO forget \
  --keep-daily 7 \
  --keep-weekly 4 \
  --keep-monthly 3 \
  --prune

restic -r $REPO check
```

### The repository password

Stored in `/root/.secrets/restic-password` (chmod 600) and, since 2026-08-27, also in
Vaultwarden as the secure note **Proxmox host restic backup - repo jelszo**.

Until that date it existed in exactly one place: inside the repository it unlocks. The
host root filesystem was being backed up with a key that only lived on that same host
root filesystem, so a dead system disk would have left ~27 GiB of verified, unopenable
snapshots. This is the same failure the K3s gpg passphrase had until 2026-08-24 and it
was fixed the same way - see `scripts/README.md`.

Do not delete the file thinking the Vaultwarden copy replaces it. The weekly cron reads
the file; the Vaultwarden copy is the human one for the day pve is gone. The note carries
the repo path, the Nobara copy path, and the file-less restore form, because in a real
disaster you will be running restic from some other machine with the USB disk attached:

```bash
# no RESTIC_PASSWORD_FILE - restic prompts for it
restic -r /mnt/disk1/backup/proxmox-host snapshots
restic -r /mnt/disk1/backup/proxmox-host restore latest --target /mnt/restore
```

**The password is 6 characters.** The file is 7 bytes and restic strips the trailing
newline - confirmed on 2026-08-27 by opening the repo with `RESTIC_PASSWORD="$(cat ...)"`,
which succeeds. That is thin for a repository living on the MergerFS pool, which is both a
Samba share and an NFS export to the whole `192.168.0.0/24` with `rw,no_root_squash`, and
which is rsynced to Nobara weekly. Rotation is cheap, since `restic key` re-wraps the
master key rather than re-encrypting the 27 GiB:

```bash
restic -r $REPO key add --new-password-file /root/.secrets/restic-password.new
RESTIC_PASSWORD_FILE=/root/.secrets/restic-password.new restic -r $REPO snapshots --latest 1
# store the new password, verify you can read it back, only then:
restic -r $REPO key list && restic -r $REPO key remove <old-id>
```

It was deliberately **not** done on 2026-08-27 - getting the existing password out of its
single point of failure was the whole point of that pass, and a rotation in the same pass
would have meant storing one password and then immediately invalidating it. `restic key
remove` of the last known key is unrecoverable; restic has no master-key escrow, so the
Vaultwarden entry has to exist and be readable before the old key goes.


### Cron (on Proxmox host)
```
0 4 * * 0 /root/backup-proxmox-restic.sh >> /var/log/restic-backup.log 2>&1
```

Runs Sundays at 04:00.

### Check snapshots
```bash
RESTIC_PASSWORD_FILE=/root/.secrets/restic-password restic -r /mnt/disk1/backup/proxmox-host snapshots
```

Note `restic` will not read `REPO` from the backup script's environment, so `-r` is required even when running as root on pve. Without it the command fails with `Fatal: Please specify repository location`, which looks like a broken repo but is not.

Verified 2026-08-10: 7 weekly snapshots, unbroken from 2026-06-28 to 2026-08-09, latest 24.834 GiB. The Sunday run does `backup` then `forget`/`prune` then `check` in one pass, and the log ends with the line worth grepping for:

```
check snapshots, trees and blobs
[0:00] 100.00%  7 / 7 snapshots
no errors were found
```

The restic repo lives on `/mnt/disk1`, not on the NVMe, so it is unaffected by the `pve/data` thin pool problems in section 7.

---

## 3. Rsync to Nobara PC

After local backups run, a cron job rsyncs both the vzdump files and the restic repo to Nobara.

### Script: `/root/sync-to-nobara.sh`
```bash
#!/bin/bash

if mountpoint -q /mnt/pve/nobara-backup; then
  echo "$(date) - Syncing to Nobara..." >> /var/log/nobara-sync.log

  rsync -av --delete /mnt/storage/backup/proxmox/ \
    /mnt/pve/nobara-backup/proxmox-vms/ >> /var/log/nobara-sync.log 2>&1

  rsync -av --delete /mnt/disk1/backup/proxmox-host/ \
    /mnt/pve/nobara-backup/proxmox-host/ >> /var/log/nobara-sync.log 2>&1

  echo "$(date) - Sync done" >> /var/log/nobara-sync.log
else
  echo "$(date) - NFS not mounted, skipping" >> /var/log/nobara-sync.log
fi
```

### Cron (on Proxmox host)
```
0 11,19 * * 0 /root/sync-to-nobara.sh
```

Runs Sundays at 11:00 and 19:00. If Nobara is offline, it logs and skips.

The 11:00 run skipping is normal, not a fault - Nobara is a desktop and is usually still off in the morning. That is exactly why there is a second attempt at 19:00. Both 2026-08-02 and 2026-08-09 followed this pattern: `NFS not mounted, skipping` at 11:00, full sync at 19:00.

While Nobara is off, the soft mount retries in the background and fills the journal with `nfs: server 192.168.0.100 not responding, timed out` (~600/hour), and `mountpoint /mnt/pve/nobara-backup` returns `Input/output error` rather than a clean "is not a mountpoint". Both are expected noise from `soft,x-systemd.automount` and recover on their own when Nobara boots. Do not "fix" this by unmounting or by switching to a hard mount.

### NFS mount
See `15_NFS-Setup_Documentation.md` for mount configuration.

---

## 4. Weekly Schedule (Sundays)

| Time | Job |
|---|---|
| 03:00 | SnapRAID sync |
| 04:00 | Restic host OS backup |
| 11:00 | Rsync to Nobara |
| 19:00 | Rsync to Nobara (second attempt, in case Nobara was offline at 11:00) |

Because the offsite copy is weekly while vzdump is nightly, **the Nobara copy can be up to 7 days behind the local one.** That is by design, but it matters when reading a failure: after the 2026-08-09 outage the Sunday sync ran while 9 of the 10 daily dumps were missing, so Nobara carried 2026-08-08 dumps for those guests until the following Sunday, even though the local copy was already current again on 2026-08-10. When judging whether an incident cost real redundancy, check both copies, not just `/mnt/storage/backup/proxmox/`.

---

## 5. Monitoring

```bash
# Restic backup log
tail -f /var/log/restic-backup.log

# Nobara sync log
tail -f /var/log/nobara-sync.log

# List LXC backups
ls -lh /mnt/storage/backup/proxmox/dump/

# Check NFS mount
mountpoint /mnt/pve/nobara-backup
```

Backups being written is not the same as backups being restorable. The restic
repository is verified weekly by a restore test, and the daily digest checks
vzdump coverage per guest rather than just counting files: see
[30 - Backup Verification + Restore Test](./30_Backup_Verification_Restore_Test.md).

---

## 5. Immich Database Backup

Immich stores its data at `/mnt/storage/immich`, not in `/srv/docker-data`, and that path reaches LXC 100 as the bind mount `mp0: /mnt/storage,mp=/mnt/storage`. **vzdump skips bind mounts**, so nothing under it has ever been in a container archive - only the 52 GB rootfs is. Until 2026-08-12 the Postgres data directory was therefore protected by SnapRAID parity alone, which for a running database means a torn copy of files that are being written: enough to restore the blocks, not enough to start Postgres from them.

Two things fixed that, in this order.

### The dump

`/root/immich-pgdump.sh` on LXC 100, daily at 00:30 UTC (02:30 CEST) via `/etc/cron.d/immich-pgdump`:

```bash
docker exec immich_postgres pg_dumpall --clean --if-exists -U postgres \
  | gzip > "$D/immich-$(date +%Y%m%d).sql.gz.tmp"
mv "$D/immich-$(date +%Y%m%d).sql.gz.tmp" "$D/immich-$(date +%Y%m%d).sql.gz"
ls -t "$D"/immich-*.sql.gz | tail -n +8 | xargs -r rm -f
```

`$D` is `/mnt/storage/immich/pgdump`, inside the SnapRAID-protected pool, so the weekly sync picks the dump up as an ordinary file. Roughly 61 MB gzipped, seven kept.

Two details that are not decoration. The dump writes to `.tmp` and is renamed only on success, so an interrupted run cannot leave a truncated file under a name that looks complete. And **the cron hour is UTC while the SnapRAID schedule is CEST**: LXC 100 runs on UTC, pve does not, so `30 2` in that crontab would have fired at 04:30 CEST, an hour *after* the Sunday 03:00 sync it is supposed to precede.

### The exclusion

`/etc/snapraid.conf` now carries `exclude /immich/pgdata/` in place of the narrower `exclude /immich/pgdata/pg_stat_tmp/`. This is not only about wasted parity. A live Postgres changes `pg_wal`, `pg_control` and `pg_xact` while SnapRAID reads them, which produces `Unexpected attribute change` soft errors; **any** soft error makes sync exit with `warning`, and the daemon's maintenance chain stops there without running the scrub. One such sync on 2026-08-12 carried 68 of them. Excluding the data directory removes the only recurring source of them.

Changing this exclusion costs one manual run: the 1697 already-indexed `pgdata` files show up as deletions on the next sync and would trip `sync_threshold_deletes`, so the first sync after the change needs `ignore_thresholds`.

### What is NOT backed up by this

The photo library at `/mnt/storage/immich/library` is on the MergerFS pool, protected by SnapRAID parity. Thumbnails and encoded videos are excluded from any offsite backup - they are regenerable via Administration > Jobs in the Immich UI.

---

## 6. Disk Layout

### Proxmox
```
nvme0n1p3 (237GB LVM)
├─ pve-root (60GB) -> /
├─ pve-swap (8GB)
└─ pve-data (150GB) -> VM/LXC disk storage

sda1 (5.5TB) -> /mnt/disk1
sdb1 (5.5TB) -> /mnt/disk2
sdc1 (931GB) -> /mnt/disk3
sdd1 (1.8TB) -> /mnt/disk4
/mnt/storage -> MergerFS pool (backup-hdd lives here)
```

### Nobara PC
```
/mnt/hdd/Backup (3.7TB) -> NFS export, rsync target
```

---

## 7. LVM Thin Pool Capacity Incidents

`pve/data` is a 164.94GB LVM thin pool hosting every guest disk. Being thin-provisioned, its `Data%` reflects actual allocated blocks, not declared guest disk sizes - and vzdump snapshot-mode backups need free pool space to create a temporary LVM snapshot per guest. When the pool gets too full, backups fail outright.

### 2026-07-07: first hit (96.14%)

Grew to 96.14% (NetData alert). Extended manually:
```bash
lvextend -L +15G pve/data
```
brought it to 87.39%, but VG (`pve`, 237GB total) had only ~1GB free afterward - not a real fix, just breathing room. Enabled thin pool autoextend as a safety net in `/etc/lvm/lvm.conf`:
```
thin_pool_autoextend_threshold = 80
thin_pool_autoextend_percent = 10
```
Note: autoextend can only pull from *VG free space* - with the VG nearly full, it has nothing to extend into. The only durable fix is physical disk expansion (see `private/todo.md` - second NVMe in the HP EliteDesk 800 G4's free M.2 SSD2 slot).

### 2026-07-16: pool full again, nightly backup failed for 9/10 guests

Pool had grown back to 89.51% (above the 80% autoextend threshold), and with VG free space still ~1GB, LVM's safety check blocked new thin volume creation entirely. The 02:00 vzdump job failed for LXCs 100, 102, 103, 105, 106, 107, 109, 110, 111 (only the HAOS VM 101 succeeded - QEMU snapshot mode doesn't need an LVM snapshot the way LXC rootfs backups do):
```
ERROR: Backup of VM XXX failed - lvcreate snapshot 'pve/snap_vm-XXX-disk-X_vzdump' error:
  Cannot create new thin volume, free space in thin pool pve/data reached threshold.
```

**Recovery - fstrim to reclaim already-freed-but-unreturned blocks:**
```bash
# Per container (safe - only discards blocks the guest filesystem already marked free)
pct fstrim <vmid>
```
Run across all running LXCs, this reclaimed enough space to drop the pool from 89.51% to 74.35% (no guest data touched - fstrim only returns blocks the guest filesystem itself already considers free, e.g. deleted files that were never discarded back to the thin pool). Re-ran the failed backups manually afterward:
```bash
vzdump <vmid1> <vmid2> ... --storage backup-hdd --mode snapshot --compress zstd \
  --prune-backups keep-daily=7,keep-last=7,keep-monthly=3,keep-weekly=4
```

**Also found and fixed:** the 2026-07-07 `lvm.conf` edit had left a duplicate `thin_pool_autoextend_percent` line (both uncommented), causing `WARNING: Ignoring duplicate config value` on every LVM command. Removed the duplicate.

### 2026-07-24: automated the fstrim stopgap, `discard=on` does not apply to LXC

Pool was at 69.93%. Tried enabling `discard=on` on all 10 LXC rootfs entries so trim would happen live instead of needing periodic `pct fstrim`:
```bash
pct set <vmid> -rootfs local-lvm:vm-<vmid>-disk-0,size=<X>G,discard=on
```
Rejected by the Proxmox API on every container:
```
400 Parameter verification failed.
rootfs.discard: property is not defined in schema and the schema does not allow additional properties
```
**`discard=on` is a QEMU/VM disk option only.** It works for VMs because the guest talks to a virtual scsi/virtio disk and the discard flag lets that passthrough reach the host's thin volume. LXC containers share the host kernel and mount the thin LV's filesystem directly - there's no virtual disk layer to carry a discard flag, so the option doesn't exist for `rootfs` at all. There is no live-discard equivalent for LXC; periodic `fstrim` is the only mechanism.

Automated the existing manual workaround instead - added `/etc/cron.weekly/lxc-fstrim` on the Proxmox host:
```bash
#!/bin/bash
for id in $(pct list | awk 'NR>1 && $2=="running"{print $1}'); do
  pct fstrim $id
done
```
First run reclaimed ~25.3GB (69.93% -> 65.65%); CT 100 (docker-host, 13.2GB) and CT 109 (6.4GB) were the largest single reclaims.

### 2026-08-09: backup failed again, and the weekly fstrim cron had never run

Pool hit 81.24% and the nightly vzdump failed for the same 9/10 guests with the identical `Cannot create new thin volume` error. The 10th guest (VM 101, haos) succeeded because it is a QEMU VM and uses `vma` streaming, not an LVM snapshot.

The important part is not the pool percentage but why it climbed back at all: **the `/etc/cron.weekly/lxc-fstrim` job added on 2026-07-24 had never executed once.** Two lines had been appended to `/etc/crontab` without the username field:

```
0 4 * * 0 /root/backup-proxmox-restic.sh
0 11,19 * * 0 /root/sync-to-nobara.sh
```

`/etc/crontab` and `/etc/cron.d/*` take six fields, where the sixth is the user to run as. A user crontab (`crontab -e`) takes five. Cron parsed `/root/backup-proxmox-restic.sh` as a username, failed, and **discarded the entire file** rather than just the bad lines. Everything driven from `/etc/crontab` stopped: `cron.hourly`, `cron.daily`, `cron.weekly`, `cron.monthly`, and with them `logrotate`, `apt-compat`, `man-db`, `netdata-updater`, `sysstat` and `lxc-fstrim`.

Nothing about this is visible from the outside. `systemctl is-active cron` reports `active`, and jobs in `/etc/cron.d/` and in root's user crontab keep running normally, so the scheduler looks healthy. The one reliable check:

```bash
# 0 means /etc/crontab is being rejected wholesale
journalctl --since '30 days ago' | grep -c run-parts
```

Both offending lines were duplicates of entries already present and correct in root's user crontab, so removing them lost no functionality:

```bash
cp /etc/crontab /etc/crontab.bak
sed -i '/backup-proxmox-restic.sh/d; /sync-to-nobara.sh/d' /etc/crontab
```

Cron logged `(*system*) RELOAD (/etc/crontab)` within a minute. Confirmed working when `cron.hourly` fired at the next `:17` and logged `(root) CMD (cd / && run-parts --report /etc/cron.hourly)`.

Manual `pct fstrim` across all 10 containers in the meantime took the pool from 79.89% to 68.02%, about 19.6GB reclaimed (CT 100 13.1GB, CT 111 10.6GB, CT 113 7.4GB).

The 9 missed backups were deliberately **not** re-run by hand. The 2026-08-10 nightly job completed all 10/10 on its own, so every guest has a current restore point and retention (`keep-daily=7`) still covers the window. A manual catch-up would only have added a duplicate of a day already covered, at the cost of pushing the pool back up while it was the thing being fixed.

### Why 80% is a hard failure line, not a warning

`/etc/lvm/lvm.conf` has `thin_pool_autoextend_threshold = 80`, but VG `pve` has only 1.00GB free, so the autoextend can never actually fire. Above 80% LVM refuses to create any new thin volume, which means every `vzdump` LXC snapshot fails immediately. The whole backup job aborts in about 70 seconds.

With a 164.94GB pool, the gap between "backups fine" and "no backups at all" is roughly 0.1%, about 180MB. Observed growth is around 1%/day, so from a post-trim 68% there are roughly 12 days of headroom.

### Status

fstrim is a recurring stopgap, not a fix - the pool will fill again within days/weeks under normal guest disk growth. Second NVMe purchase/install is the actual fix and remains open in `private/todo.md`.

The trim job was moved off `run-parts` entirely on 2026-08-10, because both `cron.weekly` (Sundays 06:47) and `cron.daily` (06:25) fire *after* the 02:00 vzdump. If the pool crossed 80% overnight the backup would still fail once before the trim cleaned up. It now runs daily at 01:30, half an hour before the backup:

```bash
mv /etc/cron.weekly/lxc-fstrim /usr/local/bin/lxc-fstrim
# in root's crontab:
30 1 * * * /usr/local/bin/lxc-fstrim >> /var/log/homelab/lxc-fstrim.log 2>&1
```

Growth is roughly 1%/day against a ~12% cushion from a post-trim 68%, so a daily trim keeps the pool clear of the threshold with room to spare. Check `/var/log/homelab/lxc-fstrim.log` if the pool climbs anyway.

### 2026-08-14: the daily trim ran every night and trimmed nothing

The daily digest reported the pool at 78.69%, up 9.2 points in the three days since the 2026-08-11 low of 69.49%. The trim job was supposed to be holding it flat.

It was not broken in any of the ways the previous incident taught us to check. The crontab entry was correct, `journalctl -u cron` showed the job firing at 01:30 on the 12th, 13th and 14th, and the log file was being written. The log content was the problem:

```
/usr/local/bin/lxc-fstrim: line 2: pct: command not found
```

**`pct` lives in `/usr/sbin`, and cron's default `PATH` is `/usr/bin:/bin`.** The script had always been called with a bare `pct`, which works in an interactive root shell because the login profile puts `/usr/sbin` on the path, and fails silently under cron. The job had therefore never once succeeded since being moved to root's crontab on 2026-08-10 - the ten successful trim lines at the top of the log were the manual run from that day, into the same file.

Fixed with the absolute path, plus a timestamp line so the log says which run produced which numbers:

```bash
#!/bin/bash
# FIGYELEM: abszolut utvonal kell. A cron PATH-jaban nincs /usr/sbin, ahol a pct lakik.
echo "=== $(date +%F\ %T) ==="
for id in $(/usr/sbin/pct list | awk 'NR>1 && $2=="running"{print $1}'); do
  /usr/sbin/pct fstrim "$id"
done
```

Verified by running it under a stripped environment rather than from the current shell, which is the only way to reproduce what cron actually does:

```bash
env -i PATH=/usr/bin:/bin HOME=/root /usr/local/bin/lxc-fstrim
```

13.4GB came back, 78.71% to 70.59%. CT 100 alone gave up 12.5GiB and CT 106 (karakeep) 7GiB.

### Proving it, without waiting for 01:30

`env -i` reproduces cron's environment, but it is still not cron. Given that this job had already been declared fixed twice before, the fix was verified end to end with a temporary every-minute entry, then the crontab restored from a backup taken first:

```bash
crontab -l > /root/crontab.bak-20260814
(crontab -l; echo '* * * * * /usr/local/bin/lxc-fstrim >> /var/log/homelab/lxc-fstrim.log 2>&1  # TEMP') | crontab -
# wait for one firing, then:
crontab /root/crontab.bak-20260814
diff <(crontab -l) /root/crontab.bak-20260814   # must be empty
```

The evidence is the pairing of the two logs - cron says it launched the wrapper, the job's own log says what the command inside it did:

```
Aug 14 10:56:01 pve CRON[2388286]: (root) CMD (/usr/local/bin/lxc-fstrim ...)

=== 2026-08-14 10:56:01 ===
/var/lib/lxc/100/rootfs/: 7 GiB (7519141888 bytes) trimmed
/var/lib/lxc/109/rootfs/: 1.2 GiB (1241018368 bytes) trimmed
```

The same run confirmed `arping-keepalive.sh`: six real cron firings, and its new error log still 0 bytes, which it could not be if `arping` were unresolvable.

**`fstrim` does not always finish in one pass on a live filesystem.** The second run twenty minutes later reclaimed another 7GiB from CT 100, which looks like runaway growth and is not - the container's own `df` went 38G to 37G across both runs, so nothing was consuming space. The first pass simply had five days of backlog to work through. Daily runs do not hit this.

Two things worth carrying forward:

- **This is the third distinct way the same job has failed to run**, after a malformed `/etc/crontab` and a `run-parts` schedule that fired after the backup. The verification that would have caught all three is the same one: read the log for *output*, not for existence. "The file is there and cron logged the CMD" proves the wrapper ran, not the command inside it.
- **Test cron jobs with `env -i`.** Running the script by hand proves nothing about the environment it will actually execute in. The identical bug hit the `ai-digest` job two days earlier with `claude` in `~/.local/bin`, so every script in a crontab on this host was audited in the same pass rather than waiting for the next incident.

**The audit found a second one.** `/usr/local/bin/arping-keepalive.sh`, which sends a gratuitous ARP every five minutes to keep the router's MAC table from being corrupted by the RE605X extender, calls a bare `arping` - also `/usr/sbin`. It had never worked either, and it was better hidden than the trim job, because of these two lines together:

```bash
arping -c 1 -U -I vmbr0 192.168.0.109 > /dev/null 2>&1
exit 0
```

`2>&1` to `/dev/null` discards the `command not found`, and the hard-coded `exit 0` means cron sees a success and never mails. **A script that discards stderr and forces exit 0 cannot report that it did nothing** - it is indistinguishable from one that works, in the logs, in cron's mail, and in its own exit status. Fixed with the absolute path and stderr redirected to `/var/log/homelab/arping-keepalive.err` instead of `/dev/null`, keeping `exit 0` so a transient failure does not mail every five minutes. An empty error log now means it ran.

Everything else in root's crontab (`restic`, `sync-to-nobara.sh`, `restore-test.sh`) resolves under `PATH=/usr/bin:/bin` and was left alone. Quick check for the whole set:

```bash
env -i PATH=/usr/bin:/bin bash -c 'command -v restic arping pct qm vzdump'
```

---

## 8. Bare-Metal Restore of pve

Not written down until 2026-08-27, and it is the procedure you need on the worst day.

Restic restores files, not a bootable disk. There is no one-click bare-metal restore in
Proxmox VE 9 - the [Proxmox wiki](https://pve.proxmox.com/wiki/Backup_and_Restore) covers
guests, not the host. The path is reinstall, then restore over it:

1. Install PVE 9.1 on the new system disk with **the same hostname (`pve`) and the same IP
   (192.168.0.109)**. The node name is baked into the `/etc/pve/nodes/<name>/` tree and
   into the SSH host keys, so a different one turns a restore into a migration.
2. Attach the USB disks, mount `/mnt/disk1`, restore the snapshot to a staging directory
   rather than straight over `/`.
3. Copy back `/etc/network/interfaces`, `/etc/fstab`, `/etc/hosts`, `/etc/default/grub`,
   `/etc/snapraid.conf`, `/root/.secrets`, `/root/*.sh` and `/var/spool/cron/crontabs/root`.
4. Restore the cluster config. Stop `pve-cluster` first - `config.db` is a live SQLite
   database and overwriting it under a running pmxcfs corrupts it:
   ```bash
   systemctl stop pve-cluster
   cp /mnt/restore/var/lib/pve-cluster/config.db /var/lib/pve-cluster/config.db
   rm -f /var/lib/pve-cluster/config.db-wal /var/lib/pve-cluster/config.db-shm
   systemctl start pve-cluster
   ```
   The snapshot also carries `/etc/pve` as plain files, because restic was never given
   `--one-file-system` and follows the pmxcfs FUSE mount. If `config.db` turns out to be
   torn - it is copied live - that file tree is the better source: recreate the guest
   configs from `/etc/pve/lxc/*.conf` and `/etc/pve/qemu-server/*.conf` by hand.
5. Restore the guests from `/mnt/storage/backup/proxmox/dump/` with `pct restore` /
   `qmrestore`. This is the only step that has been exercised for real, several times.

Verified on 2026-08-27 that the weekly snapshot actually contains every file this
procedure needs (`restic ls latest`): `/etc/pve` including `priv/`, `lxc/`, `qemu-server/`
and `jobs.cfg`; `/var/lib/pve-cluster/config.db`; `/etc/network/interfaces`; `/etc/fstab`;
`/etc/default/grub`; `/etc/snapraid.conf`; `/root/.secrets`; `/var/spool/cron/crontabs/root`.
The published host-backup checklists ([saturnme](https://www.saturnme.com/how-to-back-up-and-restore-proxmox-ve-9-host-configuration-step-by-step-guide/),
[aremesch/pve-host-backup](https://github.com/aremesch/pve-host-backup)) name nothing that
is not already inside it, so no extra config-dump script is needed here.

### What this still does not solve

Every copy is in the same flat on the same power feed: the vzdump target on the MergerFS
pool, the restic repo on `/mnt/disk1`, and the Sunday rsync to Nobara at 192.168.0.100.
Section 3 calls Nobara "offsite" and that is wrong - it is a second machine, not a second
site. Fire, theft or one surge takes all three. Vaultwarden is on LXC 103, in the same
flat, so the password custody above has the same shape of hole: the Bitwarden mobile
client keeps a read-only offline cache of the vault, but only while logged in and only for
90 days of offline use.

Fixing this needs a real offsite target and is tracked separately, not in this document.
