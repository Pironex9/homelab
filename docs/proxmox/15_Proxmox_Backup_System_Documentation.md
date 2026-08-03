**Date:** 2026-02-11
**Updated:** 2026-07-16
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

Password stored in `/root/.secrets/restic-password` (chmod 600).

### Cron (on Proxmox host)
```
0 4 * * 0 /root/backup-proxmox-restic.sh >> /var/log/restic-backup.log 2>&1
```

Runs Sundays at 04:00.

### Check snapshots
```bash
RESTIC_PASSWORD_FILE=/root/.secrets/restic-password restic -r /mnt/disk1/backup/proxmox-host snapshots
```

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

Immich stores its data outside `/srv/docker-data/`, so it is not covered by the standard Docker volume backup. A dedicated routine runs `pg_dumpall` before the main restic sweep.

### How it works

1. `pg_dumpall` dumps the entire Immich Postgres instance to `/tmp/immich-db-dump/`
2. Restic backs up the dump to `$BACKUP_DEST_NFS/immich-db`
3. Temp dump is deleted after backup

### Usage

```bash
# Run Immich DB backup only
./scripts/backup.sh immich-db

# Runs automatically as part of full backup
./scripts/backup.sh --all
```

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

### Status

fstrim is a recurring stopgap, not a fix - the pool will fill again within days/weeks under normal guest disk growth. Second NVMe purchase/install is the actual fix and remains open in `private/todo.md`. The weekly fstrim cron (above) now runs automatically, so this should only need manual attention again if the pool approaches the 80% autoextend threshold between runs.
