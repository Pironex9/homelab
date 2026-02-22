
**Version:** Immich v2.4.1  
**Date:** 2025-12-26  
**Platform:** Proxmox VE 9.1.2 / LXC 100 (Docker)  
**Hardware:** Intel i5-8400, 16GB RAM, NVMe + HDD

---

## 📋 Table of Contents

1. [System overview](#system-overview)
2. [Prerequisites](#prerequisites)
3. [Swap configuration](#swap-configuration)
4. [iGPU passthrough](#igpu-passthrough)
5. [Storage directories](#storage-directories)
6. [Docker Compose installation](#docker-compose-installation)
7. [Starting Immich](#starting-immich)
8. [First login](#first-login)
9. [ML settings](#ml-settings)
10. [Partner Sharing](#partner-sharing)
11. [Mobile App setup](#mobile-app-setup)
12. [TV App + API Key](#tv-app--api-key)
13. [Troubleshooting](#troubleshooting)

---

## 🖥️ System Overview

### **Infrastructure:**

| ID | Type | Name | IP | Services |
|----|------|------|----|----------|
| **100** | LXC | docker-host | 192.168.0.110 | Docker stack (Nginx, Jellyfin, *arr, **Immich**) |
| **101** | VM | homeassistant | 192.168.0.202 | Home Assistant OS |
| **102** | LXC | adguard-home | 192.168.0.111 | AdGuard Home DNS |

### **Immich Services:**

```
LXC 100 - Docker (192.168.0.110)
├─ Immich Server (port 2283) - WebUI + API
├─ Immich ML (port 3003) - Face recognition, CLIP search
├─ PostgreSQL (port 5432) - Database
├─ Redis (port 6379) - Cache
└─ Storage: /mnt/storage/immich/
```

---

## 🔧 Prerequisites

### **System requirements:**

```
CPU: Intel CPU with iGPU (Quick Sync) - i5-8400 ✅
RAM: 16GB (minimum), 32GB recommended
  Immich usage: ~4-6GB
  
Storage:
  NVMe/SSD: PostgreSQL database (~2-5GB)
  HDD: Photo library (unlimited, MergerFS pool)
  
Network: Gigabit LAN (for photo upload speed)
```

### **Checks (Proxmox host):**

```bash
# Does iGPU device exist?
ls -la /dev/dri/renderD128
# -rw-rw---- 1 root render 226, 128 Dec 26 renderD128 ✅

# Does LXC 100 exist and is running?
pct status 100
# status: running ✅

# Is MergerFS storage working?
ls -la /mnt/storage/
# drwxr-xr-x media, backup, etc. ✅
```

---

## 💾 Swap Configuration

### **Why is swap needed?**

```
On a 16GB RAM system, Immich ML processing:
  - Face recognition: +2-4GB RAM
  - CLIP indexing: +1-2GB RAM
  - PostgreSQL: +500MB RAM
  - Redis: +200MB RAM
  ────────────────────────────
  Peak usage: ~16-18GB → OVERFLOW! ⚠️

Swap solution:
  4GB swap = protection against OOM Killer ✅
```

### **Setting up swap:**

**Proxmox host SSH:**

```bash
# Stop LXC
pct stop 100

# Edit LXC config
nano /etc/pve/lxc/100.conf
```

**Find or add:**

```
swap: 4096
```

**Save:** `Ctrl+O`, `Enter`, `Ctrl+X`

---

**Setting swappiness (emergency only):**

```bash
# Proxmox host
echo "vm.swappiness=10" >> /etc/sysctl.conf
sysctl -p

# Verify
cat /proc/sys/vm/swappiness
# 10 ✅
```

**What does swappiness=10 mean?**
- RAM <90% → Swap NOT used
- RAM >95% → Swap activates
- **Fewer SSD writes, longer lifespan!** ✅

---

**Start LXC:**

```bash
pct start 100

# Enter
pct enter 100

# Check swap
free -h
```

**Expected result:**

```
               total        used        free      shared  buff/cache   available
Mem:           8.0Gi       1.7Gi       4.2Gi       172Mi       2.3Gi       6.3Gi
Swap:          4.0Gi          0B       4.0Gi  ✅ 4GB swap!
```

---

## 🎮 iGPU Passthrough

> **Note:** The Intel UHD 630 is shared between Immich (hardware-accelerated built-in ML - face detection, image search) and Jellyfin (hardware transcoding). Immich runs its own self-contained ML models, no external AI service involved. Both services can use the iGPU simultaneously without conflict.

### **Why is iGPU (Intel Quick Sync) needed?**

```
CPU only (no iGPU):
  1000 photos face detection: ~60-90 minutes 🐌
  
iGPU (Quick Sync):
  1000 photos face detection: ~15-30 minutes ⚡
  
3-4x faster ML processing! ✅
```

### **Setting up iGPU passthrough:**

**Proxmox host SSH:**

```bash
# Stop LXC
pct stop 100

# Edit config
nano /etc/pve/lxc/100.conf
```

**Scroll to the END of the file and add these lines:**

```
lxc.cgroup2.devices.allow: c 226:0 rwm
lxc.cgroup2.devices.allow: c 226:128 rwm
lxc.mount.entry: /dev/dri dev/dri none bind,optional,create=dir
lxc.mount.entry: /dev/dri/renderD128 dev/dri/renderD128 none bind,optional,create=file
```

**Save:** `Ctrl+O`, `Enter`, `Ctrl+X`

---

**Start LXC and verify:**

```bash
# Start
pct start 100

# Enter
pct enter 100

# Is iGPU accessible?
ls -la /dev/dri/
```

**Expected result:**

```
crw-rw---- 1 nobody nogroup 226,   0 Dec 26 card0
crw-rw---- 1 nobody nogroup 226, 128 Dec 26 renderD128  ✅
```

**Is `renderD128` there?** ✅ **iGPU working!**

---

## 📂 Storage Directories

### **Permission mapping (LXC unprivileged):**

```
LXC root (0) → Host 100000
Docker postgres (999) → Host 100999
```

**Create storage from Proxmox host:**

**Proxmox host SSH:**

```bash
# Create directories
mkdir -p /mnt/storage/immich/library
mkdir -p /mnt/storage/immich/pgdata

# Permissions
chown -R 100000:100000 /mnt/storage/immich/library
chown -R 100999:100999 /mnt/storage/immich/pgdata
chmod -R 755 /mnt/storage/immich/library
chmod -R 750 /mnt/storage/immich/pgdata

# Verify
ls -la /mnt/storage/immich/
```

**Expected result:**

```
drwxr-xr-x 2 100000 100000 4096 Dec 26 library  ✅
drwxr-x--- 2 100999 100999 4096 Dec 26 pgdata   ✅
```

---

**Verify inside LXC:**

```bash
pct enter 100

ls -la /mnt/storage/immich/
```

**As seen inside the LXC:**

```
drwxr-xr-x 2 root   root    4096 Dec 26 library  ✅
drwxr-x--- 2 nobody nogroup 4096 Dec 26 pgdata   ✅
```

**Mapping works!** ✅

---

## 🐳 Docker Compose Installation

### **Download Docker Compose files:**

**In LXC 100:**

```bash
# Create directory
mkdir -p /srv/docker-compose/immich
cd /srv/docker-compose/immich

# Download official files
curl -L -o docker-compose.yml https://github.com/immich-app/immich/releases/latest/download/docker-compose.yml

curl -L -o .env https://github.com/immich-app/immich/releases/latest/download/example.env

curl -L -o hwaccel.transcoding.yml https://github.com/immich-app/immich/releases/latest/download/hwaccel.transcoding.yml

# Verify
ls -lha
```

**Expected result:**

```
-rw-r--r-- 1 root root  979 Dec 26 .env  ✅
-rw-r--r-- 1 root root 2.8K Dec 26 docker-compose.yml  ✅
-rw-r--r-- 1 root root 1.7K Dec 26 hwaccel.transcoding.yml  ✅
```

---

### **.env configuration:**

```bash
nano .env
```

**Modify these lines:**

```bash
# Upload location
UPLOAD_LOCATION=/mnt/storage/immich/library

# Database password (CHANGE THIS!)
DB_PASSWORD=YOUR_DB_PASSWORD

# Timezone
TZ=Europe/Bratislava
```

**Save:** `Ctrl+O`, `Enter`, `Ctrl+X`

---

### **Modifying docker-compose.yml:**

**FULL FILE CONTENTS (replace with this!):**

```bash
nano docker-compose.yml
```

**Delete the ENTIRE file and paste this:**

```yaml
#
# WARNING: To install Immich, follow our guide: https://docs.immich.app/install/docker-compose
#
# Make sure to use the docker-compose.yml of the current release:
#
# https://github.com/immich-app/immich/releases/latest/download/docker-compose.yml
#
# The compose file on main may not be compatible with the latest release.

name: immich

services:
  immich-server:
    container_name: immich_server
    image: ghcr.io/immich-app/immich-server:${IMMICH_VERSION:-release}
    extends:
      file: hwaccel.transcoding.yml
      service: quicksync
    devices:
      - /dev/dri:/dev/dri
    deploy:
      resources:
        limits:
          memory: 1G
    volumes:
      - ${UPLOAD_LOCATION}:/usr/src/app/upload
      - /etc/localtime:/etc/localtime:ro
    env_file:
      - .env
    ports:
      - '2283:2283'
    depends_on:
      - redis
      - database
    restart: always
    healthcheck:
      disable: false

  immich-machine-learning:
    container_name: immich_machine_learning
    image: ghcr.io/immich-app/immich-machine-learning:${IMMICH_VERSION:-release}
    devices:
      - /dev/dri:/dev/dri
    deploy:
      resources:
        limits:
          memory: 2G
    volumes:
      - model-cache:/cache
    env_file:
      - .env
    restart: always
    healthcheck:
      disable: false

  redis:
    container_name: immich_redis
    image: docker.io/valkey/valkey:9@sha256:fb8d272e529ea567b9bf1302245796f21a2672b8368ca3fcb938ac334e613c8f
    deploy:
      resources:
        limits:
          memory: 256M
    healthcheck:
      test: redis-cli ping || exit 1
    restart: always

  database:
    container_name: immich_postgres
    image: ghcr.io/immich-app/postgres:14-vectorchord0.4.3-pgvectors0.2.0@sha256:bcf63357191b76a916ae5eb93464d65c07511da41e3bf7a8416db519b40b1c23
    deploy:
      resources:
        limits:
          memory: 512M
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_USER: ${DB_USERNAME}
      POSTGRES_DB: ${DB_DATABASE_NAME}
      POSTGRES_INITDB_ARGS: '--data-checksums'
      DB_STORAGE_TYPE: 'HDD'
    volumes:
      - /mnt/storage/immich/pgdata:/var/lib/postgresql/data
    shm_size: 128mb
    restart: always

volumes:
  model-cache:
```

**Save:** `Ctrl+O`, `Enter`, `Ctrl+X`

---

### **Configuration summary:**

```
✅ immich-server:
   - iGPU passthrough (/dev/dri)
   - Quick Sync video transcoding
   - RAM limit: 1G
   - Volume: /mnt/storage/immich/library

✅ immich-machine-learning:
   - iGPU passthrough (ML acceleration)
   - RAM limit: 2G
   
✅ redis:
   - RAM limit: 256M
   
✅ database:
   - RAM limit: 512M
   - HDD optimization
   - Volume: /mnt/storage/immich/pgdata
```

---

## 🎬 Starting Immich

### **Pull Docker images:**

```bash
cd /srv/docker-compose/immich

# Pull images (3-5 minutes)
docker compose pull
```

**Expected output:**

```
[+] Pulling 4/4
 ✔ immich-server Pulled
 ✔ immich-machine-learning Pulled  
 ✔ redis Pulled
 ✔ database Pulled
```

---

### **Start Immich:**

```bash
docker compose up -d
```

**Expected output:**

```
[+] Running 5/5
 ✔ Network immich_default              Created
 ✔ Volume immich_model-cache           Created
 ✔ Container immich_redis               Started
 ✔ Container immich_postgres            Started
 ✔ Container immich_machine_learning    Started
 ✔ Container immich_server              Started
```

---

### **Check logs:**

```bash
# Wait ~30-60 seconds
sleep 30

# Logs
docker compose logs --tail=50
```

**Signs of successful startup:**

```
immich_postgres          | database system is ready to accept connections  ✅
immich_server            | Immich Microservices is running [v2.4.1]  ✅
immich_machine_learning  | Application startup complete.  ✅
immich_redis             | Ready to accept connections tcp  ✅
```

---

### **Container status:**

```bash
docker compose ps
```

**Expected result (after ~2-3 minutes):**

```
NAME                      STATUS
immich_server             Up (healthy)  ✅
immich_machine_learning   Up (healthy)  ✅
immich_postgres           Up (healthy)  ✅
immich_redis              Up (healthy)  ✅
```

**All "Up (healthy)"?** ✅ **WORKING!**

---

### **Check RAM usage:**

```bash
free -h
```

**Expected result:**

```
Mem:  7.5Gi used / 8.0Gi total  ✅ (normal)
Swap: 0-500Mi used / 4.0Gi total  ✅ (low initially)
```

---

## 🌐 First Login

### **Accessing the WebUI:**

**Browser (Windows/Phone/any device):**

```
http://192.168.0.110:2283
```

**Expected screen:**

```
┌────────────────────────────────┐
│         IMMICH                  │
│                                 │
│    Welcome to Immich            │
│                                 │
│    Getting Started              │
│                                 │
│    [ Sign Up ]                  │
│                                 │
└────────────────────────────────┘
```

---

### **Privacy Settings Wizard:**

**Server Privacy:**

```
☑ Map - ENABLED (shows where photos were taken on a map)
☑ Version Check - ENABLED (checks for updates)
```

**User Privacy:**

```
☐ Google Cast - DISABLED (if no Chromecast)
☐ Storage Template - DISABLED (DO NOT enable! Changes file structure!)
```

**Done** button

---

### **Create admin account:**

**Sign Up form:**

```
Email:    admin@homelab.local
Password: [STRONG PASSWORD - write it down somewhere!]
Name:     Nex
```

**Sign Up** button

**Redirects to Dashboard!** ✅

---

## 🤖 ML Settings

### **ML Settings configuration:**

**Dashboard → top left ⚙️ (Administration) → Machine Learning:**

**Smart Search (CLIP):**

```
☑ Enabled - ON
Model: ViT-B-32__openai (default, leave it!)
```

**Facial Recognition:**

```
☑ Enabled - ON
Model: buffalo_l (default, leave it!)
```

**Scroll down, click "Save" button!** ✅

---

### **Upload first photos (TEST!):**

**From mobile app (RECOMMENDED!):**

```
1. Google Play / App Store → "Immich"
2. Install
3. Server URL: http://192.168.0.110:2283
4. Login: admin@homelab.local + password
5. Backup settings:
   ✅ Foreground backup
   ✅ Background backup
6. Select 10-20 photos (TEST!)
7. Upload!
```

**From WebUI (alternative, one by one):**

```
Dashboard → + (Upload) button
→ Select 5-10 photos (one at a time!)
→ Upload
```

---

### **Start ML Processing:**

**Administration → Jobs:**

**Smart Search:**

```
[Run Job] button ✅
Progress bar visible
```

**Face Detection:**

```
[Run Job] button ✅
Progress bar visible
```

**Wait 2-5 minutes (for 10-20 photos)...**

---

### **ML test - Search:**

**Search bar (top banner):**

**Try:**

```
"person"  → People?
"dog"     → Dogs?
"car"     → Cars?
"sunset"  → Sunsets?
```

**Does it find the photos?** ✅ **AI WORKING!** 🤖

---

**People tab (Faces):**

```
Explore → People
```

**Are faces visible?** ✅ **Face Recognition working!**

---

## 👥 Partner Sharing

### **Creating a second user:**

**Administration → Users → Create User:**

```
Email:    partner@homelab.local
Password: [secure password]
Name:     [Partner's name]
```

**Create** button ✅

---

### **Activating Partner Sharing:**

**Logged in as admin account (admin@homelab.local):**

**Account Settings → Partner Sharing:**

```
☑ Enable Partner Sharing - ON
Select Partner: [partner name]
☑ Show partner's photos in my timeline
```

**Save** ✅

---

**Log in as partner account:**

```
Logout → Login: partner@homelab.local
```

**Account Settings → Partner Sharing:**

```
☑ Enable Partner Sharing - ON
Select Partner: admin
☑ Show partner's photos in my timeline
```

**Save** ✅

---

### **Partner Sharing result:**

```
Admin account:
  ✅ Sees: own + partner's photos
  ✅ Upload: admin photos
  ✅ Face recognition: on admin's photos
  
Partner account:
  ✅ Sees: partner's + admin's photos
  ✅ Upload: partner photos
  ✅ Face recognition: on partner's photos

IMPORTANT:
  ❌ Face recognition NOT shared!
  ✅ Photos shared
  ✅ CLIP search shared
```

---

### **Face Recognition limitation:**

**Partner Sharing does NOT share:**

```
❌ Face recognition data (faces)
❌ People grouping
❌ Face names
```

**ONLY these are shared:**

```
✅ Photos/videos
✅ CLIP search (object search)
✅ Timeline
```

**This is a DESIGN DECISION! (Privacy!)**

---

### **Solution for shared face recognition:**

**OPTION 1: Both upload photos (RECOMMENDED!)** ✅

```
Admin photos → Admin face recognition
Partner photos → Partner face recognition
→ They see each other's photos
→ Faces are separate (privacy!)
```

**OPTION 2: Use 1 shared account** ⚠️

```
Both use: admin@homelab.local
→ Shared timeline ✅
→ Shared face recognition ✅
→ No separate user ❌
```

---

## 📱 Mobile App Setup

### **Installing the Immich Mobile App:**

**Android:**

```
Google Play Store → "Immich"
Install
```

**iOS:**

```
App Store → "Immich"
Install
```

---

### **App configuration:**

**Open app:**

```
1. Server URL: http://192.168.0.110:2283
2. Login: admin@homelab.local (or partner@homelab.local)
3. Password: [password]
4. Login
```

---

**Backup Settings:**

```
Settings → Backup:
  ☑ Foreground backup - ON
  ☑ Background backup - ON
  
  Select albums/folders to backup
```

**Start Backup!** 🚀

**Photos upload automatically!** ✅

---

### **Tailscale remote access (optional):**

**If Tailscale VPN is set up:**

```
Mobile app Server URL: http://192.168.0.110:2283
→ Works through Tailscale VPN! ✅
→ Securely accessible from anywhere!
```

---

## 📺 TV App + API Key

### **Generating an API Key:**

**WebUI (logged in as admin@homelab.local):**

```
Account Settings → API Keys → New API Key
```

**API Key creation:**

```
Name: TV App - Living Room
```

**Permissions:**

**Home use (SIMPLE!):**

```
☑ Select all  ← 1 click, everything works! ✅
```

**OR Read-Only (SECURE!):**

```
☑ asset.read
☑ asset.view
☑ asset.download
☑ album.read
☑ timeline.read
☑ person.read
☑ memory.read
```

**Create** button ✅

---

**API Key appears:**

```
┌────────────────────────────────────────┐
│ API Key Created Successfully!          │
│                                        │
│ xK9mP2vR4nQ8sL7tW6yB3cF5gH1jD0aE... │
│                                        │
│ ⚠️ COPY NOW! Won't be shown again!    │
│                                        │
│ [Copy to Clipboard] [Close]            │
└────────────────────────────────────────┘
```

**⚠️ COPY IT!** Save it to a text file! 📋

---

### **TV App login:**

**Android TV / Google TV:**

```
1. Install: "Immich for Android TV" (Play Store)
2. Open app
3. Server URL: http://192.168.0.110:2283
4. Login method: API Key
5. API Key: [paste the key]
6. Connect!
```

---

**QR Code alternative (easier!):**

```
1. Generate QR Code: https://www.qr-code-generator.com/
2. Paste API Key → Generate QR
3. TV app: Scan QR Code
4. Show QR code with phone
5. Automatic login! ✅
```

---

### **Revoke API Key (if needed):**

**Account Settings → API Keys:**

```
Active API Keys:
┌─────────────────┬──────────────┬────────────┐
│ Name            │ Created      │ Action     │
├─────────────────┼──────────────┼────────────┤
│ TV App          │ 2025-12-26   │ [Revoke]   │
└─────────────────┴──────────────┴────────────┘
```

**Revoke → API Key immediately invalidated!** ✅

---

## ❗ Troubleshooting

### **Problem 1: WebUI not accessible**

**Symptom:** `http://192.168.0.110:2283` timeout

**Check:**

```bash
# Container status
docker compose ps
# immich_server Up? ✅

# Port check
ss -tulpn | grep 2283
# tcp LISTEN 0.0.0.0:2283  ✅

# Logs
docker compose logs immich_server
```

**Solution:**

```bash
docker compose restart
```

---

### **Problem 2: PostgreSQL permission denied**

**Symptom:**

```
immich_postgres | chown: changing ownership: Operation not permitted
immich_postgres exited with code 1
```

**Solution:**

```bash
# Exit LXC
exit

# Proxmox host
chown -R 100999:100999 /mnt/storage/immich/pgdata
chmod -R 750 /mnt/storage/immich/pgdata

# Restart
pct enter 100
cd /srv/docker-compose/immich
docker compose down
docker compose up -d
```

---

### **Problem 3: ML processing slow**

**Symptom:** 1000 photos → 2+ hours

**Check:**

```bash
# Is iGPU passthrough working?
docker exec immich_machine_learning ls -la /dev/dri/
# renderD128 present? ✅

# iGPU usage
docker exec immich_server vainfo
# VAAPI support? ✅
```

**Solution:**

```bash
# If no iGPU passthrough
# Proxmox host: check /etc/pve/lxc/100.conf
# LXC restart
pct stop 100
pct start 100
```

---

### **Problem 4: Partner search not working**

**Symptom:** Partner account → Search empty, People empty

**CAUSE:** Face recognition is NOT shared in Partner Sharing!

**Solution:**

```
Have the partner account upload photos:
→ ML job runs on partner's photos
→ Partner sees faces on their own photos ✅

OR

Use 1 shared account for both
```

---

### **Problem 5: OOM Killer (Out of Memory)**

**Symptom:** Containers crash, "OOMKilled" status

**Check:**

```bash
free -h
# Swap usage high? ⚠️

docker stats
# Memory usage of containers?
```

**Solution:**

```bash
# Increase swap (Proxmox host)
pct set 100 -swap 6144  # 6GB swap
pct reboot 100

# Check resource limits
docker inspect immich_machine_learning | grep Memory
# "Memory": 2147483648  ← 2GB limit? ✅
```

---

## 📊 Performance Metrics

### **Expected performance (i5-8400 + iGPU):**

```
Initial ML processing:
  100 photos:    ~5-10 min (iGPU)
  1,000 photos:  ~30-60 min
  10,000 photos: ~5-8 hours (run overnight!)

Search:
  Face search: <1 sec ✅
  CLIP search: 1-2 sec ✅
  Timeline:    instant ✅

Upload:
  Local WiFi: 50-100 MB/s
  Mobile backup: 5-20 MB/s

RAM usage:
  Idle: ~2.5GB
  ML processing: ~4-5GB
  Peak: ~6-7GB (+ swap)
```

---

## 🔧 Useful Commands

### **Immich management:**

```bash
# Start/Stop
cd /srv/docker-compose/immich
docker compose stop
docker compose start
docker compose restart

# Logs
docker compose logs -f
docker compose logs immich_server --tail=100

# Stats
docker stats
free -h
```

---

### **Database backup:**

```bash
# PostgreSQL backup
docker exec immich_postgres pg_dumpall -U postgres > /mnt/storage/backup/immich-db-$(date +%Y%m%d).sql

# Restore
cat backup.sql | docker exec -i immich_postgres psql -U postgres
```

---

### **Update Immich:**

```bash
cd /srv/docker-compose/immich

# Pull new images
docker compose pull

# Restart with new images
docker compose up -d

# Check version
docker compose logs immich_server | grep "Immich"
# Immich Server is running [v2.x.x]
```

---

## 🎯 Best Practices

### **1. Backup strategy:**

```
Daily:
  - PostgreSQL database dump
  - LXC backup (Proxmox vzdump)

Weekly:
  - Photo library verify (SnapRAID scrub)

Monthly:
  - Offsite backup (photos)
```

---

### **2. ML Job schedule:**

```
Run overnight (less resource competition):
  - Smart Search: 02:00
  - Face Detection: 03:00
  - Duplicate Detection: 04:00

Administration → Jobs → Schedule (if available)
```

---

### **3. Storage management:**

```
Weekly check:
  - Disk usage: df -h /mnt/storage/immich/
  - Database size: du -sh /mnt/storage/immich/pgdata/
  - Photo count: Immich dashboard

If 80%+ usage:
  - Duplicate detection + delete
  - Old photo archiving
  - Storage expansion
```

---

### **4. Security:**

```
API Keys:
  ✅ Separate key for each device
  ✅ Descriptive names (TV App, Phone, CLI)
  ✅ Revoke if compromised

Accounts:
  ✅ Strong passwords
  ✅ 2FA (when available)

Network:
  ✅ Local network only (NO port forward!)
  ✅ Tailscale VPN for remote access
  ❌ DO NOT expose publicly! (security risk)
```

---

### **5. Monitoring:**

```
Weekly check:
  - Container health: docker compose ps
  - RAM usage: free -h
  - Swap usage: swapon --show
  - Logs: docker compose logs --tail=50

Monthly:
  - Immich version check
  - Database performance
  - Storage health (SMART)
```

---

## 📈 System Status Summary

### **Final configuration:**

```
Proxmox Host (192.168.0.109):
├─ Swap: swappiness=10 ✅
│
├─ LXC 100 - Docker (192.168.0.110):
│  ├─ Swap: 4GB ✅
│  ├─ iGPU: Intel QuickSync ✅
│  │
│  └─ Immich (http://192.168.0.110:2283):
│     ├─ Server (1G RAM limit) ✅
│     ├─ ML (2G RAM limit + iGPU) ✅
│     ├─ PostgreSQL (512M limit, HDD optimized) ✅
│     ├─ Redis (256M limit) ✅
│     └─ Storage: /mnt/storage/immich/ ✅
│
├─ LXC 102 - AdGuard (192.168.0.111) ✅
└─ VM 101 - Home Assistant (192.168.0.202) ✅
```

---

### **Features:**

```
✅ Photo/Video management
✅ AI-powered search (CLIP)
✅ Face recognition
✅ Partner Sharing
✅ Mobile app auto-backup
✅ TV app viewing (API Key)
✅ Timeline, Albums, Memories
✅ Geo-location map
✅ RAW support
✅ Hardware acceleration (iGPU)
```

---

## 🎉 Installation Complete!

**What we achieved:**

✅ **Immich installed** - WebUI working (http://192.168.0.110:2283)  
✅ **ML features** - Face detection, CLIP search, object recognition  
✅ **iGPU acceleration** - 3-4x faster ML processing  
✅ **Resource limits** - RAM overflow protection  
✅ **Swap configuration** - OOM Killer protection  
✅ **Partner Sharing** - Family use  
✅ **Mobile app** - Auto-backup from phone  
✅ **TV app** - API Key viewing  
✅ **Storage** - MergerFS pool + SnapRAID protection  

**COMPLETE SELF-HOSTED GOOGLE PHOTOS ALTERNATIVE!** 🏆✨

---

**Created:** 2025-12-26  
**Version:** 1.0  
**System:** Proxmox VE 9.1.2 / Immich v2.4.1 / Docker
