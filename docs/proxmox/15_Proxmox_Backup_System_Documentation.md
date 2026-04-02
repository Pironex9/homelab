**Date:** 2026-02-11
**Updated:** 2026-03-04
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
