
**Date:** 2025-12-19  
**Hostname:** pve  
**IP address:** 192.168.0.109  
**Web UI:** https://192.168.0.109:8006

---

## 📋 Hardware Configuration

### NVMe SSD (238.5 GB)
```
/dev/nvme0n1
├─ nvme0n1p1: EFI partition (1007K)
├─ nvme0n1p2: /boot/efi (1GB)
└─ nvme0n1p3: LVM physical volume (237GB)
   ├─ pve-swap: 8GB (swap)
   ├─ pve-root: 60GB (/)
   └─ pve-data: ~150GB (VM/LXC storage)
```

### HDD disks
```
/dev/sda: 5.5TB - Data disk
  └─ /dev/sda1: ext4, Label: data1
     UUID: YOUR_DISK1_UUID
     Mount: /mnt/disk1

/dev/sdb: 5.5TB - Parity disk
  └─ /dev/sdb1: ext4, Label: data2
     UUID: YOUR_DISK2_UUID
     Mount: /mnt/disk2
```

---

## 🔧 Proxmox Installation

### Installation parameters
```
Target disk: /dev/nvme0n1 (256GB NVMe SSD)

Options:
├─ Filesystem: ext4
├─ hdsize: [empty] (full disk)
├─ swapsize: 8
├─ maxroot: 60
├─ minfree: 16
└─ maxvz: [empty] (auto)

Network:
├─ Hostname: pve.local
├─ IP Address: 192.168.0.109/24
├─ Gateway: 192.168.0.1
└─ DNS: 192.168.0.1
```

### Resulting layout
```
256GB NVMe SSD:
├─ /boot/efi:      1 GB   (EFI partition)
├─ /boot:          1 GB   (Boot partition)
├─ LVM pve:
│  ├─ pve-root:   60 GB   (OS + Docker images)
│  ├─ pve-swap:    8 GB   (Virtual memory)
│  ├─ pve-data:  ~150 GB  (VM/LXC disks)
│  └─ free:       16 GB   (Expansion reserve)
```

---

## 📦 Repository Configuration

### Disable enterprise repo
```bash
mv /etc/apt/sources.list.d/pve-enterprise.sources /etc/apt/sources.list.d/pve-enterprise.sources.bak
mv /etc/apt/sources.list.d/ceph.sources /etc/apt/sources.list.d/ceph.sources.bak
```

### Enable no-subscription repo
**File:** `/etc/apt/sources.list.d/pve-no-subscription.sources`

```conf
Types: deb
URIs: http://download.proxmox.com/debian/pve
Suites: trixie
Components: pve-no-subscription
```

### System update
```bash
apt update
apt upgrade -y
```

---

## 💾 HDD Configuration

### 1. Partitioning and formatting

#### Disk 1 (Data)
```bash
parted /dev/sda mklabel gpt
parted /dev/sda mkpart primary ext4 0% 100%
mkfs.ext4 -L data1 /dev/sda1
```

#### Disk 2 (Parity)
```bash
parted /dev/sdb mklabel gpt
parted /dev/sdb mkpart primary ext4 0% 100%
mkfs.ext4 -L data2 /dev/sdb1
```

### 2. Create mount points
```bash
mkdir -p /mnt/disk1
mkdir -p /mnt/disk2
mkdir -p /mnt/storage
```

### 3. fstab configuration
**File:** `/etc/fstab`

```bash
# 2x 5.5TB HDD mounts
UUID=YOUR_DISK1_UUID  /mnt/disk1  ext4  defaults,noatime  0  2
UUID=YOUR_DISK2_UUID  /mnt/disk2  ext4  defaults,noatime  0  2
```

### 4. Mount and verify
```bash
systemctl daemon-reload
mount -a
df -h | grep mnt
```

**Expected output:**
```
/dev/sda1       5.5T  2.1M  5.2T   1% /mnt/disk1
/dev/sdb1       5.5T  2.1M  5.2T   1% /mnt/disk2
```

---

## 🔗 MergerFS Installation and Configuration

### Installation
```bash
apt install -y mergerfs
```

**Version:** 2.40.2-5

### fstab configuration
**File:** `/etc/fstab` (added)

```bash
# MergerFS pool (disk1 only, disk2 = parity)
/mnt/disk1  /mnt/storage  fuse.mergerfs  defaults,allow_other,use_ino,cache.files=partial,dropcacheonclose=true,category.create=mfs  0  0
```

### Mount and verify
```bash
systemctl daemon-reload
mount /mnt/storage
df -h | grep storage
```

**Expected output:**
```
/mnt/disk1  5.5T  2.1M  5.2T   1% /mnt/storage
```

### Storage structure
```
Storage layout:
├─ /mnt/disk1:    5.5TB (Data disk)
├─ /mnt/disk2:    5.5TB (Parity disk - SnapRAID)
└─ /mnt/storage:  5.5TB (MergerFS pool - disk1 only)
   └─ Docker DATA volumes will go here later!
```

---

## 🛡️ SnapRAID Installation and Configuration

> **⚠️ Superseded (2026-07-25):** the install-from-source method and manual cron below describe the *original* 2026 setup (SnapRAID v12.3). The CLI has since been upgraded to a dpkg-managed v14.9, and the manual sync cron was replaced by SnapRAID Daemon (`snapraidd`), which now handles scheduled sync/scrub/SMART monitoring plus a web dashboard at `http://192.168.0.109:7627`. See **[28 - SnapRAID Daemon Setup](./28_SnapRAID_Daemon_Setup.md)** for the current install method and config. This section is kept as historical record of how the array was originally built.

### Install from source
```bash
# Dependencies
apt install -y git gcc make autoconf automake libtool

# Download and compile
cd /tmp
wget https://github.com/amadvance/snapraid/releases/download/v12.3/snapraid-12.3.tar.gz
tar xzf snapraid-12.3.tar.gz
cd snapraid-12.3
./configure
make
make install
```

**Installed version:** snapraid v12.3

### Configuration
**File:** `/etc/snapraid.conf`

```conf
# SnapRAID Configuration

# Parity file (disk2 = 5.5TB parity disk)
parity /mnt/disk2/snapraid.parity

# Content files (backup to multiple locations)
content /var/snapraid.content
content /mnt/disk1/.snapraid.content

# Data disk (disk1 = 5.5TB data)
data d1 /mnt/disk1

# Exclude patterns
exclude *.unrecoverable
exclude /tmp/
exclude /lost+found/
exclude *.!sync
exclude *.tmp

# Autosave
autosave 500
```

### First sync
```bash
snapraid sync
```

### Automatic sync (cron)
```bash
crontab -e
```

**Added:**
```bash
# SnapRAID sync every Sunday at 03:00
0 3 * * 0 /usr/local/bin/snapraid sync
```

---

## 📊 Useful Commands

### Proxmox
```bash
# Version check
pve-manager --version

# LVM info
lvdisplay
pvdisplay
vgdisplay

# Storage info
df -h
lsblk
```

### MergerFS
```bash
# Storage pool check
df -h /mnt/storage

# MergerFS info
cat /proc/mounts | grep mergerfs
```

### SnapRAID
```bash
# Status
snapraid status

# Manual sync
snapraid sync

# Scrub (data verification)
snapraid scrub

# Check (full verification)
snapraid check

# Recovery (if disk1 fails)
snapraid fix -d d1
```

---

## 🎯 Expansion Options (later)

### Adding a new data disk

**Example: adding disk3 (2TB)**

1. **Format and mount HDD:**
```bash
parted /dev/sdc mklabel gpt
parted /dev/sdc mkpart primary ext4 0% 100%
mkfs.ext4 -L data3 /dev/sdc1

# fstab
UUID=<disk3-uuid>  /mnt/disk3  ext4  defaults,noatime  0  2
```

2. **Expand MergerFS:**
```bash
# Modify /etc/fstab:
/mnt/disk1:/mnt/disk3  /mnt/storage  fuse.mergerfs  defaults,allow_other,use_ino,cache.files=partial,dropcacheonclose=true,category.create=mfs  0  0
```

3. **Expand SnapRAID:**
```conf
# Modify /etc/snapraid.conf:
data d1 /mnt/disk1
data d3 /mnt/disk3  # NEW!
```

### Parity capacity rule
**IMPORTANT:** The parity disk must be at least as large as the LARGEST data disk!

- ✅ 5.5TB parity → protects: any number of data disks ≤5.5TB
- ❌ 5.5TB parity → does NOT protect: data disks ≥6TB

**Example configuration:**
```
Parity: 1x 5.5TB (disk2)
Data disks:
├─ disk1: 5.5TB
├─ disk3: 2TB
├─ disk4: 2TB
├─ disk5: 1TB
└─ disk6: 1TB

Total: 11.5TB usable storage!
```

---

## 🚀 Next Steps

1. ✅ **Proxmox installation** - DONE
2. ✅ **HDD configuration** - DONE
3. ✅ **MergerFS setup** - DONE
4. ✅ **SnapRAID setup** - DONE
5. 🔄 **Docker LXC container creation** - NEXT
6. 🔄 **Docker installation in LXC**
7. 🔄 **Backup restoration**
8. 🔄 **Starting Docker stacks**

---

## 📝 Backup Script Information

**Source:** `/mnt/hdd2/backup/2025-12-19/` *(path as it was on the Raspberry Pi - on Proxmox this disk became `/mnt/disk4`)*

**Contents:**
- Docker volumes: `/srv/docker/`
- User files: `/home/nex/`
- Log files

**Expected backup structure:**
```
/mnt/hdd2/backup/2025-12-19/
├─ docker/
│  ├─ radarr/
│  ├─ sonarr/
│  ├─ jellyfin/
│  ├─ calibre-web-automated/
│  ├─ prowlarr/
│  ├─ bazarr/
│  └─ qbittorrent/
├─ nex_home/
├─ backup.log
├─ rsync_docker.log
└─ rsync_home.log
```

---

## 🔐 Important Passwords and Data

- **Proxmox root password:** [WRITE THIS DOWN!]
- **Web UI:** https://192.168.0.109:8006
- **SSH:** `ssh root@192.168.0.109`

---

**End of documentation**  
**Last updated:** 2025-12-19
