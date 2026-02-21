
**Date:** 2025-12-22/23  
**System:** Proxmox VE + Docker LXC (ID: 100, IP: 192.168.0.110)

---

## 📋 Starting State

- **Proxmox server:** Working MergerFS + SnapRAID
  - disk1 (5.5TB HGST) - data
  - disk2 (5.5TB HGST) - parity
- **Raspberry Pi server:** DEAD ❌
- **2 USB HDDs connected:**
  - disk3 (1TB) - "Filmek" label
  - disk4 (2TB) - "Filmek2" label
- **Docker LXC:** Running, but media paths use old structure

---

## 🎯 Goals

1. ✅ Integrate USB HDDs into the MergerFS pool
2. ✅ Update SnapRAID config (3 data disks)
3. ✅ Unify media structure (`/media/movies/hun`, `/media/tv/eng`)
4. ✅ Fix Docker application paths
5. ✅ Resolve DNS issue (RPi AdGuard Home died)

---

## 1️⃣ Identifying and Mounting USB HDDs

### Check disks:
```bash
lsblk
blkid /dev/sdc1
blkid /dev/sdd1
```

**Result:**
```
sdc1: 931GB, ext4, Label="Filmek"
      UUID=YOUR_DISK3_UUID
sdd1: 1.8TB, ext4, Label="Filmek2"
      UUID=YOUR_DISK4_UUID
```

### Mount points and mounting:
```bash
mkdir -p /mnt/disk3 /mnt/disk4
mount /dev/sdc1 /mnt/disk3
mount /dev/sdd1 /mnt/disk4
df -h | grep disk
```

**Data:**
- disk3: 713GB used (82% full)
- disk4: 922GB used (53% full)

### fstab configuration (automount):
```bash
nano /etc/fstab
```

**Lines added:**
```fstab
# USB HDDs (from RPi)
UUID=YOUR_DISK3_UUID  /mnt/disk3  ext4  defaults,noatime  0  2
UUID=YOUR_DISK4_UUID  /mnt/disk4  ext4  defaults,noatime  0  2
```

**Test:**
```bash
umount /mnt/disk3 /mnt/disk4
mount -a
df -h | grep disk
```

---

## 2️⃣ Expanding the MergerFS Pool

### Original MergerFS config:
```
/mnt/disk1 -> /mnt/storage
```

### New MergerFS config (3 disk pool):
```bash
nano /etc/fstab
```

**Modified line:**
```fstab
/mnt/disk1:/mnt/disk3:/mnt/disk4  /mnt/storage  fuse.mergerfs  defaults,allow_other,use_ino,cache.files=partial,dropcacheonclose=true,category.create=mfs  0  0
```

### Remount:
```bash
umount /mnt/storage
systemctl daemon-reload
mount /mnt/storage
df -h /mnt/storage
```

**Result:**
```
1:3:4    8.1T  1.7T  6.1T  21% /mnt/storage
```

✅ **8.1TB unified pool (5.5T + 1T + 2T)**

---

## 3️⃣ Updating SnapRAID Configuration

### Edit SnapRAID config:
```bash
nano /etc/snapraid.conf
```

**New configuration:**
```conf
# SnapRAID Configuration

# Parity file (disk2 = 5.5TB parity)
parity /mnt/disk2/snapraid.parity

# Content files (saved in multiple locations!)
content /var/snapraid.content
content /mnt/disk1/.snapraid.content
content /mnt/disk3/.snapraid.content
content /mnt/disk4/.snapraid.content

# Data disks (3 disks in the pool)
data d1 /mnt/disk1
data d3 /mnt/disk3
data d4 /mnt/disk4

# Exclude patterns
exclude *.unrecoverable
exclude /tmp/
exclude /lost+found/
exclude *.!sync
exclude *.tmp

# Autosave
autosave 500
```

### Run SnapRAID sync:
```bash
snapraid status  # Check before sync
snapraid sync    # Generate parity
```

**Sync result:**
```
Scanned d1 in 0 seconds   ✅
Scanned d3 in 3 seconds   ✅
Scanned d4 in 14 seconds  ✅

100% completed, 1766832 MB (1.7TB)
Duration: 2:43 (163 minutes)
Average speed: 165-239 MB/s

Everything OK ✅
```

---

## 4️⃣ Restructuring the Media Directory

### Problem:
- **disk3/disk4:** Movies were directly under `/movies/` and `/tv/`
- **Goal:** `/media/movies/hun`, `/media/movies/eng`, `/media/tv/hun`, `/media/tv/eng`

### Restructure (disk3):
```bash
mkdir -p /mnt/disk3/media
mv /mnt/disk3/movies /mnt/disk3/media/
mv /mnt/disk3/tv /mnt/disk3/media/
ls -lh /mnt/disk3/media/
```

### Restructure (disk4):
```bash
mkdir -p /mnt/disk4/media
mv /mnt/disk4/movies /mnt/disk4/media/
mv /mnt/disk4/tv /mnt/disk4/media/
ls -lh /mnt/disk4/media/
```

**Result:**
```
disk1/media/movies/hun/  ← EMPTY (new)
disk1/media/movies/eng/  ← EMPTY (new)
disk3/media/movies/hun/  ← 262GB movies (144 folders)
disk3/media/movies/eng/  ← Movies (7 folders)
disk4/media/movies/hun/  ← 231GB movies (100 folders)
disk4/media/movies/eng/  ← Movies (3 folders)
```

### Permission fix:
```bash
chmod -R 777 /mnt/disk3/media/
chmod -R 777 /mnt/disk4/media/
```

---

## 5️⃣ Resolving the MergerFS Merge Problem

### Problem:
```bash
ls -lh /mnt/storage/media/movies/hun/  # EMPTY! ❌
```

**Reason:** Empty `hun/eng` folders existed on disk1 → MergerFS was only showing those!

### Solution:
```bash
# Remove empty folders from disk1
rmdir /mnt/disk1/media/movies/hun
rmdir /mnt/disk1/media/movies/eng
# tv/hun remains (Lakásvadászok series)

# Verify
ls -lh /mnt/storage/media/movies/hun/ | head -5
```

**Result:**
```
total 960K
drwxrwxrwx  2 100000 100000 4.0K  101.Dalmatians.1961...
drwxrwxrwx  3 100000 100000 4.0K  101.Dalmatians.1996...
... (654 Hungarian movies total!)
```

✅ **MergerFS now merges the content of all 3 disks!**

---

## 6️⃣ Docker LXC Media Visibility Problem

### Problem:
```bash
# Inside LXC
pct enter 100
ls -lh /mnt/storage/media/movies/hun/  # Only 2 folders! ❌

# On Proxmox host
ls -lh /mnt/storage/media/movies/hun/  # 654 folders! ✅
```

**Reason:** The MergerFS mount was not yet ready when the LXC booted!

### Solution: LXC restart
```bash
# On Proxmox host
pct stop 100
pct start 100
pct enter 100

# Verify
ls -lh /mnt/storage/media/movies/hun/ | wc -l
# Result: 654 ✅
```

---

## 7️⃣ Resolving Jellyfin Problems

### Problem 1: Marker file conflict
```
Error: Expected to find only .jellyfin-data but found marker for /config/.jellyfin-config
```

**Solution:**
```bash
rm /srv/docker-data/jellyfin/.jellyfin-config
docker start jellyfin
```

### Problem 2: Media not visible
```bash
docker exec -it jellyfin ls -lh /media/hun/
# Result: total 0  ❌
```

**Reason:** Container was still using the old path mapping!

**Solution:**
```bash
cd /srv/docker-compose/jellyfin
docker compose down
docker compose up -d
docker exec -it jellyfin ls -lh /media2/hun/
```

**Result:**
```
total 112K
drwxrwxrwx   2 root root 4.0K  Ahsoka.S01...
drwxrwxrwx  12 root root 4.0K  A.Kiraly.S01...
... (28+ series!) ✅
```

---

## 8️⃣ Resolving DNS Problem

### Problem:
```bash
# Inside LXC
ping google.com  # Timeout ❌
ping 8.8.8.8     # Works ✅
cat /etc/resolv.conf
```

**Result:**
```
nameserver 192.168.0.102  ← OLD RPi AdGuard Home!
```

### Temporary fix (inside LXC):
```bash
nano /etc/resolv.conf
```

```
nameserver 8.8.8.8
nameserver 1.1.1.1
```

**PROBLEM:** Proxmox auto-generates this → resets after restart!

### Permanent fix (on Proxmox host):
```bash
nano /etc/pve/lxc/100.conf
```

**Change:**
```
# OLD:
nameserver: 192.168.0.102

# NEW:
nameserver: 8.8.8.8
```

**LXC restart:**
```bash
pct stop 100
pct start 100
pct enter 100
cat /etc/resolv.conf
ping google.com  # Works! ✅
```

---

## 📊 Final State

### Disk usage:
```
Disk      Size    Used    Free   Use%  Purpose
────────────────────────────────────────────────
disk1     5.5TB   7.6GB   5.2TB   1%   Data (MergerFS)
disk2     5.5TB   11GB    5.2TB   1%   Parity
disk3     916GB   713GB   158GB   82%  Data (MergerFS)
disk4     1.8TB   922GB   818GB   53%  Data (MergerFS)
────────────────────────────────────────────────
MergerFS  8.1TB   1.7TB   6.1TB   21%  Unified pool
```

### Media structure:
```
/mnt/storage/media/
├── movies/
│   ├── hun/  (654 movies - disk3+disk4 merged)
│   └── eng/  (12 movies - disk3+disk4 merged)
├── tv/
│   ├── hun/  (28+ series - disk1+disk3+disk4)
│   └── eng/  (6 series - disk3+disk4)
├── downloads/
├── books/
└── music/
```

### Docker compose volume mappings (updated):
```yaml
volumes:
  - /srv/docker-data/jellyfin:/config
  - /mnt/storage/media/movies:/media
  - /mnt/storage/media/tv:/media2:ro
```

### SnapRAID protection:
- **3 data disks protected** (disk1, disk3, disk4)
- **Parity:** disk2 (5.5TB)
- **Content files:** saved in 4 locations
- **Sync status:** OK, 1.7TB protected

---

## ⚠️ Important Notes

### Boot order:
1. **MergerFS mount** (`/mnt/storage`)
2. **LXC start** (this is why a restart was needed!)
3. **Docker containers** start

### DNS strategy:
- **Currently:** Google DNS (8.8.8.8)
- **Later:** Start AdGuard Home on new server (192.168.0.110)
- **Then:** Modify LXC config: `nameserver: 192.168.0.110`

### Scrutiny problem:
❌ **Does not work inside LXC** (device access restricted)
✅ **Solution:** Run Scrutiny on the Proxmox host

---

## 🚀 Next Steps

### Urgent:
1. ✅ Run Jellyfin library scan
2. ⏳ Fix paths for other Docker apps (Radarr, Sonarr, etc.)
3. ⏳ Start AdGuard Home on the new server

### Later:
- SnapRAID automation (cronjob)
- Monitoring setup (Grafana + Prometheus)
- Finalize backup strategy
- Fine-tune network segmentation (arr_stack vs utils)

---

## 📝 Lessons Learned

### What worked well:
✅ MergerFS flexibility - easy to add new disks  
✅ SnapRAID scalability - smoothly scaled from 1 to 3 disks  
✅ ext4 filesystem - cross-platform compatibility  
✅ Docker compose - simple path modification  

### Problems and solutions:
❌ **Empty folders in MergerFS** → Deletion required  
❌ **LXC mount timing** → Restart required  
❌ **DNS Proxmox auto-config** → LXC config modification needed  
❌ **Docker caches old mounts** → Compose down/up required  

---

**Session end:** 2025-12-23 01:00  
**Document created by:** Claude (Anthropic)
