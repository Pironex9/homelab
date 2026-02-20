
**Date:** 2025-12-19  
**Proxmox:** 192.168.0.109  
**Old RPi server:** 192.168.0.102

---

## 📋 Starting State

✅ **Proxmox VE 9.1** installed and configured  
✅ **2x 5.5TB HDD** formatted, mounted  
✅ **MergerFS** configured (`/mnt/storage` = 5.5TB pool)  
✅ **SnapRAID** installed and configured  
✅ **Backup** completed on the old RPi server: `/mnt/hdd2/backup/2025-12-19/`

---

## 🖥️ 1. First Web UI Access

### URL:
```
https://192.168.0.109:8006
```

### Login:
```
User: root
Password: [configured password]
```

**Result:** ✅ Login successful

---

## 📦 2. Downloading Debian Template

### CLI method (used):

```bash
# Update template list
pveam update

# Available Debian templates
pveam available | grep debian

# Download Debian 12 template
pveam download local debian-12-standard_12.12-1_amd64.tar.zst
```

**Result:**
```
downloading http://download.proxmox.com/images/system/debian-12-standard_12.12-1_amd64.tar.zst
...
TASK OK
```

**Template location:**
```
/var/lib/vz/template/cache/debian-12-standard_12.12-1_amd64.tar.zst
```

---

## 🐳 3. Creating Docker LXC Container (Web UI)

### 3.1 Start Create CT
- Left sidebar: **pve** node
- Top right corner: **Create CT** button

### 3.2 General tab
```
CT ID: 100
Hostname: docker-host
Password: [password set]
Unprivileged container: ✅ ENABLED
Nesting: ✅ ENABLED
```

### 3.3 Template tab
```
Storage: local
Template: debian-12-standard_12.12-1_amd64.tar.zst
```

### 3.4 Disks tab
```
Storage: local-lvm
Disk size (GiB): 32
```

### 3.5 CPU tab
```
Cores: 4
```

### 3.6 Memory tab
```
Memory (MiB): 4096
Swap (MiB): 512
```

### 3.7 Network tab
```
Name: eth0
Bridge: vmbr0
IPv4: Static
IPv4/CIDR: 192.168.0.110/24
Gateway (IPv4): 192.168.0.1
```

### 3.8 DNS tab
```
DNS servers: 192.168.0.1
```

### 3.9 Confirm
```
Start after created: ✅ ENABLED
```

**Result:** ✅ LXC container created (ID: 100)

---

## 📁 4. Adding MergerFS Storage Bind Mount

### 4.1 Edit LXC configuration

**On Proxmox host (SSH):**
```bash
nano /etc/pve/lxc/100.conf
```

**Added to end of file:**
```conf
mp0: /mnt/storage,mp=/mnt/storage
```

### 4.2 Restart LXC
```bash
pct stop 100
pct start 100
pct status 100
```

**Result:**
```
status: running
```

---

## 🐋 5. Installing Docker Inside the LXC

### 5.1 Enter the LXC
```bash
pct enter 100
```

**Prompt change:**
```
root@docker-host:~#
```

### 5.2 Verify storage mount
```bash
ls -la /mnt/
df -h | grep storage
```

**Result:**
```
/mnt/disk1  5.5T  2.1M  5.2T   1% /mnt/storage
```
✅ Bind mount working!

### 5.3 System update
```bash
apt update && apt upgrade -y
```

### 5.4 Install Docker
```bash
# Official Docker install script
apt install -y curl
curl -fsSL https://get.docker.com | sh

# Docker Compose plugin
apt install -y docker-compose-plugin

# Verify Docker version
docker --version
docker compose version
```

**Result:**
```
Docker version 27.x.x
Docker Compose version v2.x.x
```

### 5.5 Create user
```bash
# Create user
useradd -m -s /bin/bash nex
usermod -aG docker nex

# Set password
passwd nex
```

### 5.6 Docker volumes directory
```bash
mkdir -p /srv/docker
```

---

## 💾 6. Restoring Backup

### 6.1 First attempt - FAILED

**On Proxmox host:**
```bash
# Attempt to copy to /tmp
scp -r nex@192.168.0.102:/mnt/hdd2/backup/2025-12-19 /tmp/backup
```

**Problem:**
```
scp: write local "...": No space left on device
```

**Reason:** `/tmp` is on the root filesystem (60GB), and the backup (~40-50GB) **FILLED IT UP!**

### 6.2 Check root filesystem

```bash
df -h /
```

**Result during problem:**
```
/dev/mapper/pve-root   59G  55G   1G  98% /
```

### 6.3 Solution: Copy directly to storage

**On Proxmox host:**
```bash
# Clean up /tmp
rm -rf /tmp/backup

# Copy directly to storage
scp -r nex@192.168.0.102:/mnt/hdd2/backup/2025-12-19/docker /mnt/storage/backup-restore/compose
scp -r nex@192.168.0.102:/mnt/hdd2/backup/2025-12-19/docker /mnt/storage/backup-restore/config
```

**OR simpler:**
```bash
scp -r nex@192.168.0.102:/mnt/hdd2/backup/2025-12-19/docker/* /mnt/storage/backup-restore/
```

### 6.4 Check backup size

**On Proxmox host:**
```bash
du -sh /mnt/storage/backup-restore/
ls -lh /mnt/storage/backup-restore/
```

**Result:**
```
total 7.6G

drwxr-xr-x 24 root root 4.0K Dec 20 18:25 compose
drwxr-xr-x 25 root root 4.0K Dec 20 18:31 config
```

✅ **Backup successfully copied: 7.6GB**

### 6.5 Recheck root filesystem

```bash
df -h /
```

**Result after copying:**
```
/dev/mapper/pve-root   59G  5.3G   51G  10% /
```

✅ Free space restored!

---

## 📂 7. Restoring Docker Volumes in the LXC

### 7.1 Enter the LXC
```bash
pct enter 100
```

### 7.2 Verify backup visibility
```bash
ls -lh /mnt/storage/backup-restore/
```

**Result:**
```
total 8.0K
drwxr-xr-x 24 nobody nogroup 4.0K Dec 20 17:25 compose
drwxr-xr-x 25 nobody nogroup 4.0K Dec 20 17:31 config
```

### 7.3 Copy Docker volumes back

```bash
# Copy backup to /srv/docker/
cp -a /mnt/storage/backup-restore/compose/* /srv/docker/
cp -a /mnt/storage/backup-restore/config/* /srv/docker/

# Verify
ls -lh /srv/docker/
```

**Result - Docker applications list:**
```
total 100K
drwxr-xr-x  4 nobody nogroup 4.0K Dec 20 17:27 adguardhome
drwxr-xr-x  9 nobody nogroup 4.0K Dec 20 17:28 bazarr
drwxr-xr-x  2 nobody nogroup 4.0K Dec 20 17:25 calibre-web-automated
drwxr-xr-x  6 nobody nogroup 4.0K Dec 20 17:27 calibrewebauto
drwxr-xr-x  2 nobody nogroup 4.0K Dec 20 17:31 dockge
drwxr-xr-x  2 nobody nogroup 4.0K Dec 20 17:28 dozzle
drwxr-xr-x  9 nobody nogroup 4.0K Dec 20 17:26 homeassistant
drwxr-xr-x  4 nobody nogroup 4.0K Dec 20 17:27 homepage
drwxr-xr-x 15 nobody nogroup 4.0K Dec 20 17:31 huntarr
drwxr-xr-x  9 nobody nogroup 4.0K Dec 20 17:31 jellyfin
drwxr-xr-x  7 nobody nogroup 4.0K Dec 20 17:27 mealie
drwxr-xr-x  4 nobody nogroup 4.0K Dec 20 17:31 nginx-proxy-manager
drwxr-xr-x  3 nobody nogroup 4.0K Dec 20 17:31 notifiarr
drwxr-xr-x  5 nobody nogroup 4.0K Dec 20 17:31 overseerr
drwxr-xr-x  3 nobody nogroup 4.0K Dec 20 17:31 portainer
drwxr-xr-x  7 nobody nogroup 4.0K Dec 20 17:27 prowlarr
drwxr-xr-x  5 nobody nogroup 4.0K Dec 20 17:28 qbittorrent
drwxr-xr-x  7 nobody nogroup 4.0K Dec 20 17:26 radarr
drwxr-xr-x  4 nobody nogroup 4.0K Dec 20 17:31 scrutiny
drwxr-xr-x  5 nobody nogroup 4.0K Dec 20 17:31 seerr
drwxr-xr-x  7 nobody nogroup 4.0K Dec 20 17:31 sonarr
drwxr-xr-x  2 nobody nogroup 4.0K Dec 20 17:25 stirling-pdf
drwxr-xr-x  4 nobody nogroup 4.0K Dec 20 17:28 trainingData
drwxr-xr-x  5 nobody nogroup 4.0K Dec 20 17:27 uptime-kuma
drwxr-xr-x  2 nobody nogroup 4.0K Dec 20 17:26 watchtower
```

✅ **25 Docker applications restored!**

---

## 📊 Current State

### Proxmox Host
```
IP: 192.168.0.109
Storage:
├─ NVMe SSD: 60GB root, 8GB swap, ~150GB data
├─ HDD #1 (sda): 5.5TB data (/mnt/disk1)
├─ HDD #2 (sdb): 5.5TB parity (/mnt/disk2)
└─ MergerFS pool: /mnt/storage (5.5TB)
```

### Docker LXC (ID: 100)
```
Hostname: docker-host
IP: 192.168.0.110
Resources: 4 cores, 4GB RAM, 32GB disk
Storage: /mnt/storage (bind mount)
Docker: ✅ Installed
Docker Compose: ✅ Installed
Applications: 25 stacks restored
```

### Backup
```
Source: 192.168.0.107:/mnt/hdd2/backup/2025-12-19/
Destination: /mnt/storage/backup-restore/ (7.6GB)
Docker volumes: /srv/docker/ (25 applications)
```

---

## 🎯 Next Steps

### 1. Check Docker compose files
```bash
# Does docker-compose.yml exist everywhere?
find /srv/docker/ -name "docker-compose.yml" -o -name "compose.yaml"
```

### 2. Media file location
- **Question:** Where were the movies/series on the old server?
- **New location:** `/mnt/storage/media/` (recommended)

### 3. Create media directory structure
```bash
mkdir -p /mnt/storage/media/movies
mkdir -p /mnt/storage/media/tv
mkdir -p /mnt/storage/media/downloads
```

### 4. Modify Docker compose files
- Update volume paths to new locations
- Example:
```yaml
volumes:
  - /mnt/storage/media/movies:/movies
  - /mnt/storage/media/downloads:/downloads
```

### 5. Set permissions
```bash
chown -R root:root /srv/docker/
# OR
chown -R nex:nex /srv/docker/
```

### 6. Start Docker stacks
```bash
cd /srv/docker/[application-name]
docker compose up -d
```

---

## ⚠️ Lessons Learned and Important Notes

### /tmp problem
**Problem:**
- `/tmp` is part of the root filesystem (60GB)
- Copying a large backup to `/tmp` → filesystem filled up
- SSH/HTTP connection dropped

**Solution:**
- **NEVER** copy large files to `/tmp` or `/root`
- Use the dedicated storage (`/mnt/storage` = 5.5TB)

### Debian version choice
**Proxmox host:** Debian 13 (trixie) - base of Proxmox 9.1  
**LXC container:** Debian 12 (bookworm) - stable, production-ready  

This is **NOT a problem!** The host and container OS are **independent** of each other.

### Backup storage size
**Full backup:** ~40-50GB (docker + nex_home)  
**Docker volumes:** 7.6GB  
**Difference:** user files, images, PDFs, Syncthing DB, Git repos

---

## 📝 Useful Commands

### Proxmox host
```bash
# Enter LXC
pct enter 100

# LXC status
pct status 100

# LXC start/stop
pct start 100
pct stop 100

# Storage check
df -h
lsblk
```

### LXC container
```bash
# Docker version
docker --version
docker compose version

# Running containers
docker ps

# Docker logs
docker logs [container-name]

# Start Docker compose
cd /srv/docker/[app]
docker compose up -d

# Stop Docker compose
docker compose down
```

---

**End of documentation**  
**Last updated:** 2025-12-19, 20:00
