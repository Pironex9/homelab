
## Overview

3-2-1 backup strategy:
1. **Original data**: VMs/LXCs on Proxmox
2. **Backup 1**: Local Proxmox storage (disk1)
3. **Backup 2**: Nobara PC via NFS (different physical machine)
4. **Backup 3**: Cloud (later)

---

## 1. Proxmox Host OS Backup (Restic)

### Installation and initialization
```bash
apt install restic
restic init --repo /mnt/disk1/backup/proxmox-host
```

### Backup script: `/root/backup-proxmox-restic.sh`
```bash
#!/bin/bash
REPO="/mnt/disk1/backup/proxmox-host"

restic -r $REPO backup / \
  --exclude /mnt/disk1 \
  --exclude /mnt/disk2 \
  --exclude /mnt/disk3 \
  --exclude /mnt/disk4 \
  --exclude /mnt/storage \
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

### Cron configuration
```bash
# Every Sunday at 03:00
0 4 * * 0 /root/backup-proxmox-restic.sh
```

### Restore procedure
```bash
# 1. Fresh Proxmox install
# 2. Restic install
apt install restic

# 3. List snapshots
restic -r /mnt/disk1/backup/proxmox-host snapshots

# 4. Restore latest
restic -r /mnt/disk1/backup/proxmox-host restore latest --target /

# 5. Update bootloader
update-grub
grub-install /dev/nvme0n1

# 6. Reboot
```

### First backup results
- **Files**: 79,433
- **Original size**: 14.2 GB
- **Compressed**: 7.1 GB
- **Duration**: 1 hour 51 minutes

---

## 2. NFS Configuration

### Nobara PC (NFS Server)

**Export configuration** (`/etc/exports`):
```
/mnt/hdd/Backup 192.168.0.0/24(rw,sync,no_subtree_check,no_root_squash)
```

**Activate export**:
```bash
sudo exportfs -arv
```

**Start service**:
```bash
sudo systemctl enable --now nfs-server
```

### Proxmox (NFS Client)

**Create mount point**:
```bash
mkdir -p /mnt/nobara-backup
```

**Fstab entry** (`/etc/fstab`):
```
192.168.0.YOUR_PC_IP:/mnt/hdd/Backup /mnt/nobara-backup nfs defaults,_netdev 0 0
```

**Mount**:
```bash
mount /mnt/nobara-backup
systemctl daemon-reload
```

---

## 3. Automatic Synchronization

### Sync script: `/root/sync-to-nobara.sh`
```bash
#!/bin/bash

if mountpoint -q /mnt/nobara-backup; then
  echo "$(date) - Syncing to Nobara..." >> /var/log/nobara-sync.log
  
  rsync -av --delete /mnt/disk1/backup/proxmox/dump/ \
    /mnt/nobara-backup/proxmox-vms/ >> /var/log/nobara-sync.log
  
  rsync -av --delete /mnt/disk1/backup/proxmox-host/ \
    /mnt/nobara-backup/proxmox-host/ >> /var/log/nobara-sync.log
else
  echo "$(date) - NFS not mounted" >> /var/log/nobara-sync.log
fi
```

### Cron configuration
```bash
# Sync on Sundays at 11:00 and 19:00, if Nobara is online -> sync
0 11,19 * * 0 /root/sync-to-nobara.sh
```

**Behaviour**:
- If Nobara is powered on -> synchronize
- If Nobara is offline -> skip, write log entry

---

## 4. Backup Locations

### On the Proxmox server
- **Host OS backup**: `/mnt/disk1/backup/proxmox-host/` (restic repo)
- **VM/LXC backups**: `/mnt/disk1/backup/proxmox/dump/` (Proxmox built-in)

### On the Nobara PC
- **Host OS backup**: `/mnt/hdd/Backup/proxmox-host/` (rsync mirror)
- **VM/LXC backups**: `/mnt/hdd/Backup/proxmox-vms/` (rsync mirror)

---

## 5. Monitoring and Maintenance

### Log files
```bash
# Restic backup log (stdout/stderr in cron email)
# Sync log
tail -f /var/log/nobara-sync.log
```

### Checks
```bash
# NFS mount status
df -h | grep nobara

# Restic repo integrity
restic -r /mnt/disk1/backup/proxmox-host check

# Restic snapshot list
restic -r /mnt/disk1/backup/proxmox-host snapshots

# Nobara sync status
ls -lh /mnt/nobara-backup/proxmox-vms/
ls -lh /mnt/nobara-backup/proxmox-host/
```

### Retention Policy
**Restic (host backup)**:
- Daily: 7 days
- Weekly: 4 weeks
- Monthly: 3 months

**Proxmox VM/LXC backups**:
- According to retention set in Proxmox GUI

---

## 6. Network Configuration

- **Proxmox IP**: 192.168.0.YOUR_PROXMOX_IP
- **Nobara PC IP**: 192.168.0.YOUR_PC_IP
- **Subnet**: 192.168.0.0/24
- **Protocol**: NFS v4

---

## 7. Disk Layout

### Proxmox
```
nvme0n1p3 (237GB LVM)
├─ pve-root (60GB) -> /
├─ pve-swap (8GB)
└─ pve-data (150GB) -> VM storage

sda1 (5.5TB) -> /mnt/disk1
sdb1 (5.5TB) -> /mnt/disk2
sdc1 (931GB) -> /mnt/disk3
sdd1 (1.8TB) -> /mnt/disk4
/mnt/storage -> MergerFS pool
```

### Nobara PC
```
/mnt/hdd/Backup (3.7TB) -> NFS export
```

---

## Author
- **Date**: 2026-02-11
- **System**: Proxmox VE + Nobara Linux
- **Backup tools**: Restic + rsync + NFS
