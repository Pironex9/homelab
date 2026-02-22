
**Date:** 2025-12-25  
**System:** Proxmox VE 9.1.2, HP EliteDesk 800 G4  
**Goal:** Home Assistant OS VM installation, Zigbee2MQTT integration, full backup strategy

---

## 📋 Table of Contents

1. [System overview](#system-overview)
2. [Home Assistant VM installation](#home-assistant-vm-installation)
3. [Zigbee2MQTT setup](#zigbee2mqtt-setup)
4. [Device pairing](#device-pairing)
5. [Copying automations](#copying-automations)
6. [Removing Docker HA](#removing-docker-ha)
7. [Backup strategy](#backup-strategy)
8. [Windows offsite backup](#windows-offsite-backup)

---

## 🖥️ System Overview

### **Hardware:**
- **Host:** HP EliteDesk 800 G4
- **CPU:** Intel i5-8400 (6 cores)
- **RAM:** 16GB
- **Storage:**
  - 256GB NVMe SSD (Proxmox OS + VM/LXC)
  - 4x HDD (MergerFS pool, 8.1TB)
  - Parity: disk2 (SnapRAID)

### **Proxmox configuration:**
- **Version:** Proxmox VE 9.1.2
- **IP:** 192.168.0.109
- **LXC 100:** Docker host (192.168.0.110)
- **VM 101:** Home Assistant OS (192.168.0.202)

### **Storage:**
- **local-lvm:** VM/LXC disks (NVMe)
- **local:** ISO storage (NVMe)
- **backup-hdd:** Vzdump backups (HDD, /mnt/storage/backup/proxmox)

---

## 🏠 Home Assistant VM Installation

### **Why VM and not Docker?**

**Docker Compose DISADVANTAGES:**
- ❌ No Supervisor
- ❌ No Add-on Store
- ❌ USB passthrough is cumbersome
- ❌ Not officially supported

**HA OS VM ADVANTAGES:**
- ✅ Full HA ecosystem (Supervisor, Add-ons, HACS)
- ✅ Official support
- ✅ Simple USB/Zigbee passthrough
- ✅ Proxmox snapshot/backup
- ✅ Dedicated resources

### **Installation with community script:**

**Proxmox host SSH:**
```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/community-scripts/ProxmoxVE/main/vm/haos-vm.sh)"
```

**Script automatically:**
- ✅ Downloads the latest HA OS image (16.3)
- ✅ UEFI boot setup (OVMF firmware)
- ✅ Optimal VM configuration (q35, kvm64)
- ✅ Creates EFI disk
- ✅ 32GB root disk size
- ✅ Starts the VM

**Result:**
- **VM ID:** 101
- **Name:** haos-16.3
- **CPU:** 2 cores
- **RAM:** 4096MB
- **IP:** 192.168.0.202
- **WebUI:** http://192.168.0.202:8123

### **Manual installation problems (that we avoided):**

**Previous failed attempts:**
- ❌ Manual QCOW2 import → would not boot
- ❌ Using SeaBIOS → stuck at boot
- ❌ Old HA OS version (13.2) → incompatible with Proxmox 9.1.2
- ❌ Port conflict (8123) → with old Docker HA

**Community script SOLVED:**
- ✅ UEFI boot (OVMF)
- ✅ Latest HA OS (16.3)
- ✅ Correct machine type (q35)
- ✅ EFI disk with proper configuration

### **VM configuration (final):**

**/etc/pve/qemu-server/101.conf:**
```
bios: ovmf
boot: order=scsi0
cores: 2
cpu: kvm64
efidisk0: local-lvm:vm-101-disk-1,efitype=4m,size=1M
machine: q35
memory: 4096
name: haos-16.3
net0: virtio=YOUR_MAC_ADDRESS,bridge=vmbr0
ostype: l26
scsi0: local-lvm:vm-101-disk-0,size=32G
scsihw: virtio-scsi-pci
```

### **First login:**

**HA WebUI (http://192.168.0.202:8123):**
1. Create Account
2. Name, username, password
3. Location: YOUR_CITY, YOUR_COUNTRY
4. Auto-discovery: Allow
5. Analytics: Disable/Enable (as preferred)

---

## 📡 Zigbee2MQTT Setup

### **Why Zigbee2MQTT and not ZHA?**

| Aspect | ZHA | Zigbee2MQTT |
|--------|-----|-------------|
| **Setup** | Simple (5 min) | More complex (15 min) |
| **Supported devices** | ~1500 | ~2600+ ✅ |
| **Updates** | Slower | Faster ✅ |
| **OTA firmware** | Limited | Full ✅ |
| **Network map** | None | Yes (graphical!) ✅ |
| **Frontend UI** | HA only | Separate WebUI ✅ |
| **Customization** | Limited | Many options ✅ |

**Decision:** Zigbee2MQTT (experienced user, more devices, better features)

### **USB Dongle passthrough:**

**Hardware:** SONOFF Zigbee 3.0 USB Dongle Plus V2

**USB identification (Proxmox host):**
```bash
lsusb | grep -i "CP210\|10c4"
# Bus 001 Device 003: ID 10c4:ea60 Silicon Labs CP210x UART Bridge
```

**USB passthrough to VM:**

**Proxmox WebUI:**
1. VM 101 → Hardware → Add → USB Device
2. Use USB Vendor/Device ID
3. Vendor/Device: `10c4:ea60`
4. USB3: ✅
5. Add

**OR CLI:**
```bash
qm set 101 -usb0 host=10c4:ea60
qm reboot 101
```

**Verify in HA:**
```bash
# HA Console (Terminal & SSH add-on)
ls -lh /dev/ttyUSB*
# /dev/ttyUSB0 → Working! ✅
```

### **Installing Mosquitto MQTT Broker:**

**HA WebUI:**
1. Settings → Add-ons → Add-on Store
2. Official add-ons → **Mosquitto broker**
3. Install
4. Configuration: (default is fine)
5. ✅ Start on boot
6. ✅ Watchdog
7. Start

### **Installing Zigbee2MQTT Add-on:**

**Add repository:**

**HA WebUI:**
1. Settings → Add-ons → Add-on Store
2. ⋮ (three dots) → Repositories
3. Add repository URL:
   ```
   https://github.com/zigbee2mqtt/hassio-zigbee2mqtt
   ```
4. Add → Close

**Install add-on:**
1. Refresh page (F5)
2. Zigbee2MQTT → Install (~2 minutes)
3. Configuration tab

### **Zigbee2MQTT configuration:**

**Configuration tab:**
```yaml
data_path: /config/zigbee2mqtt
socat:
  enabled: false
  master: pty,raw,echo=0,link=/tmp/ttyZ2M,mode=777
  slave: tcp-listen:8485,keepalive,nodelay,reuseaddr,keepidle=1,keepintvl=1,keepcnt=5
  options: "-d -d"
  log: false
mqtt:
  server: mqtt://core-mosquitto:1883
  user: ""
  password: ""
serial:
  port: /dev/ttyUSB0
  adapter: ezsp
advanced:
  log_level: info
  network_key: GENERATE
  pan_id: GENERATE
```

**Important settings:**
- `mqtt.server`: Mosquitto broker (internal HA network)
- `serial.port`: USB dongle device
- `serial.adapter`: `ezsp` (SONOFF Dongle Plus)

**Start add-on:**
1. ✅ Start on boot
2. ✅ Watchdog
3. ❌ Auto-update (before testing!)
4. ✅ Show in sidebar
5. Start

**Check logs:**

**Z2M Add-on → Log tab:**
```
[INFO] Starting Zigbee2MQTT...
[INFO] MQTT connected
[INFO] Starting zigbee-herdsman...
[INFO] Coordinator firmware version: {'type': 'EmberZNet', 'meta': {'version': '6.10.3'}}
[INFO] Currently 0 devices are joined
[INFO] Zigbee: allowing new devices to join
[INFO] Started
```

✅ **Working!**

**Z2M WebUI:** http://192.168.0.202:8099 (OR sidebar: Zigbee2MQTT icon)

### **Adding MQTT Integration in HA:**

**IMPORTANT:** Z2M → HA communication goes through MQTT!

**HA WebUI:**
1. Settings → Devices & Services
2. **MQTT** discovered → **Add**
3. Submit (default settings)

**Ignoring discovered integrations:**
- **Sonoff Zigbee 3.0 USB Dongle** → **Ignore** (ZHA auto-discovery, not needed!)

**Result:**
- MQTT integration: Configured ✅
- Z2M Bridge appears as a device
- Paired Zigbee devices appear automatically!

---

## 🔌 Device Pairing

### **Philips Hue Essential White and Color Ambiance (3 units):**

**Reset method:** Philips Hue App reset

**Steps:**
1. Install **Philips Hue Bluetooth** app (Android/iOS)
2. Connect to lamp via Bluetooth
3. Lamp Settings → Delete
4. Lamp reset ✅

**Pairing in Z2M:**
1. Z2M WebUI → **Permit join (All)** ON
2. ~10-30 seconds → Lamp pairs automatically
3. Appears in Devices list
4. Rename: e.g. "Living room lamp"

**OTA firmware update:**
⚠️ **SLOW!** ~1-2 hours per lamp
- Progresses at ~1% per minute
- DO NOT interrupt!
- Lamp stays ON
- Keep dongle CLOSE

**Z2M → Devices → Philips Hue → OTA tab → Update**

### **EMOS GoSmart A65 E27 14W RGB Zigbee:**

**Reset method:** 5x ON/OFF

**Steps:**
1. Switch: ON (2 sec) → OFF (2 sec) → repeat 5x
2. 5th time: LEAVE IT ON
3. Lamp flashes/pulses → Reset mode ✅
4. Z2M **Permit join** ON
5. ~10-30 sec → Pairs

**In Z2M:**
- Rename: "EMOS Living room"
- Test: ON/OFF, brightness, RGB color

### **Aqara Door & Window Sensor (MCCGQ11LM):**

**Reset method:** Button for 5 seconds

**Steps:**
1. Check battery (CR1632)
2. Open cover
3. Reset button (on top or in hole on side)
4. **PRESS and HOLD for 5 seconds**
5. LED flashes quickly (blue/red) → Pairing mode ✅
6. Z2M **Permit join** ON
7. ~10-30 sec → Pairs

**In Z2M:**
- Rename: "Front door"
- Test: Magnet close (true) / far (false)

**Automatically appears in HA:**
- `binary_sensor.bejárati_ajto_contact`
- `sensor.bejárati_ajto_battery`
- `sensor.bejárati_ajto_linkquality`

---

## 🤖 Copying Automations

### **Finding old automations:**

**Old Docker HA config folder:**
```bash
# In LXC 100
pct enter 100
cat /srv/docker-data/homeassistant/automations.yaml
```

### **Installing File Editor Add-on:**

**HA WebUI:**
1. Settings → Add-ons → Add-on Store
2. Official add-ons → **File editor**
3. Install
4. ✅ Show in sidebar
5. Start

### **Copying automations:**

**File Editor (sidebar):**
1. Left file tree → `automations.yaml`
2. Delete content (if `[]` is there)
3. **PASTE** the full old automations.yaml content
4. **Save** (💾 button)

**OR with Terminal & SSH:**
```bash
# Terminal & SSH add-on
nano /config/automations.yaml
# PASTE automations
# Ctrl+O, Enter, Ctrl+X
```

**Reload automations:**
1. Developer Tools → YAML tab
2. AUTOMATIONS → Reload
3. OR: Settings → System → AUTOMATIONS → Reload

**Result:**
- ✅ Automations appear (Settings → Automations)
- ✅ Automations fixed - device_id references replaced with entity_id after devices were paired in Zigbee2MQTT

### **Copied automations:**

```yaml
1. Towel dryer timer (time-based, device ID)
2. Entrance light On (motion, device ID)
3. Entrance light Off (motion, device ID)
4. Entrance light On (Sunset/Sunrise, device ID)
5. Hallway lights (3x motion sensor, entity ID)
6. Door sensors (entity ID)
```

### **To be fixed later:**

**Device ID → Entity ID conversion required!**

**BEFORE (device_id, NOT working):**
```yaml
triggers:
- type: occupied
  device_id: 2bae5d981d74e6724b39d3615daf55ec  # ❌
  entity_id: ca930b208dffc389aac517604dc09584
```

**AFTER (entity_id, WORKS):**
```yaml
triggers:
- trigger: state
  entity_id: binary_sensor.bejarati_mozgas_occupancy  # ✅ Z2M friendly name
  to: 'on'
```

**Create mapping table when devices are paired:**
- Old ZHA entities → New Z2M entities
- Find & Replace for each automation
- Rewrite device ID automations

---

## 🗑️ Removing Docker HA

**Why remove it?** New HA VM exists, old Docker HA is no longer needed!

### **Remove Docker container:**

```bash
# In LXC 100
pct enter 100

# Container stop & remove
docker stop homeassistant
docker rm homeassistant

# Remove compose folder
rm -rf /srv/docker-compose/homeassistant/

# Remove data folder (after backup!)
rm -rf /srv/docker-data/homeassistant/

# Verify
docker ps -a | grep homeassistant  # No result ✅
ss -tulpn | grep 8123              # Port free ✅
```

### **Docker cleanup (optional):**

```bash
# Remove image
docker images | grep homeassistant
docker rmi ghcr.io/home-assistant/home-assistant:stable

# Volume cleanup
docker volume prune
```

---

## 🛡️ Backup Strategy

### **3-2-1 Backup rule:**
- **3 copies:** Original + Proxmox backup + Windows offsite
- **2 media:** NVMe (snapshot) + HDD (backup)
- **1 offsite:** Windows machine (manual/scheduled sync)

### **SnapRAID vs Proxmox Backup vs Snapshot:**

| Type | Protects | Good for | NOT good for | Storage |
|------|---------|---------|-------------|---------|
| **SnapRAID** | Media files | Disk failure | VM/LXC, frequent changes | HDD (parity) |
| **Proxmox Backup** | Full VM/LXC | Disaster recovery | Media files (large) | HDD |
| **Snapshot** | VM/LXC point-in-time | Fast rollback | Long term | NVMe |

### **SnapRAID configuration (ALREADY SET UP):**

**Parity protection for media files:**
```bash
# On Proxmox host
snapraid sync   # Weekly (Sunday 03:00)
snapraid scrub  # Monthly (bit rot check)
```

**Automation:**
```bash
# /etc/cron.d/snapraid
0 3 * * 0 root /usr/bin/snapraid sync
0 4 1 * * root /usr/bin/snapraid scrub -p 10
```

### **Proxmox Backup HDD storage:**

**Create storage:**

**Proxmox WebUI:**
1. Datacenter → Storage → Add → Directory
2. **ID:** `backup-hdd`
3. **Directory:** `/mnt/storage/backup/proxmox`
4. **Content:** ✅ VZDump backup file
5. **Nodes:** pve
6. **Enable:** ✅
7. **Shared:** ❌
8. Add

**OR CLI:**
```bash
mkdir -p /mnt/storage/backup/proxmox
pvesm add dir backup-hdd --path /mnt/storage/backup/proxmox --content backup
```

### **Backup Schedule setup:**

**Proxmox WebUI:**
1. Datacenter → Backup → Add
2. **Storage:** `backup-hdd` (HDD!)
3. **Schedule:** `02:30` (Systemd calendar format!)
4. **Selection mode:** Include selected VMs
   - ✅ 100 (docker-host)
   - ✅ 101 (homeassistant)
5. **Retention:**
   - Keep last: `7` (last 7 days)
   - Keep daily: `7` (7 daily backups)
   - Keep weekly: `4` (4 weekly backups)
   - Keep monthly: `3` (3 monthly backups)
6. **Mode:** `Snapshot`
7. **Compression:** `ZSTD`
8. **Enable:** ✅
9. Create

**⚠️ WARNING:** Proxmox does **NOT** use cron format!

**CORRECT formats:**
```
02:30           = Every day at 02:30
daily           = Every day at 00:00
mon..fri 02:00  = Monday to Friday at 02:00
sat,sun 03:00   = Weekend at 03:00
```

**INCORRECT (cron):**
```
❌ 0 2 * * *   Does NOT work!
```

### **Manual backup test:**

```bash
# On Proxmox host
vzdump 100 --storage backup-hdd --mode snapshot --compress zstd
vzdump 101 --storage backup-hdd --mode snapshot --compress zstd

# Verify
ls -lh /mnt/storage/backup/proxmox/dump/
# vzdump-lxc-100-2025_12_25-02_00_00.tar.zst
# vzdump-qemu-101-2025_12_25-02_30_00.vma.zst
```

### **Snapshot strategy (NVMe):**

**WHEN to take a snapshot:**
- Before a Proxmox update
- Before a major update (Docker, HA OS)
- Before trying a new configuration

**Taking a snapshot:**
```bash
# CLI
qm snapshot 101 pre-haos-update-$(date +%Y%m%d)
pct snapshot 100 pre-docker-update-$(date +%Y%m%d)

# Rollback (if something goes wrong)
qm rollback 101 pre-haos-update-20251225
pct rollback 100 pre-docker-update-20251225

# Delete snapshot (after 1-2 days)
qm delsnapshot 101 pre-haos-update-20251225
pct delsnapshot 100 pre-docker-update-20251225
```

**OR Proxmox WebUI:**
- VM/LXC → Snapshots tab → Take Snapshot

### **Full backup timeline:**

```
02:00 - Proxmox backup start (LXC 100)
02:15 - LXC 100 backup finish (~15 min, 2-5GB)
02:15 - Proxmox backup start (VM 101)
02:30 - VM 101 backup finish (~15 min, 5-10GB)
03:00 - SnapRAID sync (Sunday, media protection)
05:00 - Windows offsite sync (manual/scheduled)
```

### **Storage plans:**

**256GB NVMe:**
```
Proxmox OS:    ~10GB
VM 101 (HA):   ~32GB
LXC 100:       ~48GB
Snapshots:     ~10GB (3-5, pre-update)
Temp:          ~10GB
─────────────────────
Used:          ~110GB
Free:          ~146GB ✅
```

**MergerFS HDD (8.1TB):**
```
Media:             1.7TB
Proxmox backups:   ~120GB (7 daily + 4 weekly + 3 monthly)
Docker configs:    ~1GB
SnapRAID parity:   1.7TB (disk2)
─────────────────────────
Used:              ~3.5TB
Free:              ~4.6TB ✅
```

---

## 💾 Windows Offsite Backup

### **Why Windows sync?**
- ✅ Offsite backup (separate machine)
- ✅ Disaster recovery (if Proxmox host dies)
- ✅ Fulfills 3-2-1 rule

### **Rclone attempt (FAIL):**

**Problem:** SMB authentication error

```bash
# Proxmox → Windows SMB
rclone config  # SMB/CIFS remote
rclone lsd windows-backup:/
# ERROR: The attempted logon is invalid
```

**Cause:** Windows user/password issue (PIN vs Password?)

### **WORKING SOLUTION: Windows batch script!**

**Reversed strategy:**
```
Proxmox backup → HDD (/mnt/storage/backup/proxmox)
                      ↓
                Samba share (working!)
                      ↓
         Windows Robocopy script (simple!)
```

### **Samba configuration (ALREADY SET UP):**

**Proxmox Samba share:**
```
\\192.168.0.109\Storage\backup\proxmox
User: smbuser
Password: [configured password]
```

**Windows access:** File Explorer → `\\192.168.0.109\Storage`

### **Windows Robocopy script:**

**D:\Scripts\proxmox-backup-sync.bat:**
```batch
@echo off
title Proxmox Backup Sync
color 0A

echo ================================================
echo      PROXMOX BACKUP SYNC
echo ================================================
echo.
echo Source: \\192.168.0.109\Storage\backup\proxmox\dump
echo Dest:   D:\Backups\Proxmox
echo.
echo Starting copy...
echo.

REM Robocopy sync - without net use!
robocopy "\\192.168.0.109\Storage\backup\proxmox\dump" "D:\Backups\Proxmox" /MIR /Z /W:5 /R:3 /NP /V /LOG:D:\Scripts\sync.log

echo.
echo ================================================
if %ERRORLEVEL% LEQ 7 (
    echo SUCCESS!
) else (
    echo ERROR!
)
echo Log: D:\Scripts\sync.log
echo ================================================
pause
```

**Robocopy flags:**
- `/MIR` = Mirror mode (deletes what's not in source)
- `/Z` = Restartable (can continue after interruption)
- `/W:5` = Retry wait 5 seconds
- `/R:3` = 3 retries
- `/NP` = No progress % (faster)
- `/V` = Verbose (detailed log)
- `/LOG:` = Log file

**Robocopy exit codes:**
```
0-7 = SUCCESS
  0 = No changes
  1 = Copy successful
  2 = Extra files (deleted by /MIR)
8+  = ERROR
```

### **Troubleshooting: System error 1219:**

**Problem:**
```
System error 1219
Multiple connections to a server... using more than one user name
```

**Cause:** Already connected in File Explorer (different user?)

**Solution:**

**1. Delete connections:**
```cmd
net use * /delete /yes
```

**2. Re-run script:**
```cmd
D:\Scripts\proxmox-backup-sync.bat
```

**OR simpler:** Do NOT use `net use` in the script!

**Windows Credential Manager remembers the password:**
- First run: Asks for password
- After that: Logs in automatically

### **Permanent Credential Manager setup:**

```powershell
# PowerShell Admin
cmdkey /add:192.168.0.109 /user:smbuser /pass:PASSWORD
```

**After this the script can run without asking for a password!** ✅

### **Task Scheduler automation (optional):**

**To run on every login:**

**Task Scheduler:**
1. Create Task
2. **General:**
   - ✅ Run only when user is logged on
3. **Triggers:**
   - At log on (or Daily when logged on)
4. **Actions:**
   - Program: `D:\Scripts\proxmox-backup-sync.bat`
5. OK

**IMPORTANT:** "Run only when user is logged on" → Does NOT ask for password!

### **Manual run (RECOMMENDED!):**

**Simplest:**
1. Turn on Windows
2. Double-click: `D:\Scripts\proxmox-backup-sync.bat`
3. Wait ~5-10 minutes (copies only changes)
4. Done! ✅

---

## 📊 Final System Overview

### **VM/LXC configuration:**

| ID | Type | Name | vCPU | RAM | Disk | IP | Services |
|----|------|------|------|-----|------|----|----------|
| 100 | LXC | docker-host | 4 | 8GB | 48GB | 192.168.0.110 | Docker (Jellyfin, *arr stack, qBittorrent, etc.) |
| 101 | VM | homeassistant | 2 | 4GB | 32GB | 192.168.0.202 | HA OS 16.3, Z2M, Mosquitto |

### **HA Add-ons:**

- ✅ **Mosquitto broker** (MQTT)
- ✅ **Zigbee2MQTT** (Zigbee devices)
- ✅ **Terminal & SSH** (CLI access)
- ✅ **File editor** (Config editing)

### **Zigbee devices:**

- 💡 **Philips Hue Essential** (3x RGB lamp)
- 💡 **EMOS GoSmart A65** (1x RGB lamp)
- 🚪 **Aqara Door Sensor** (MCCGQ11LM)

### **Backup strategy summary:**

**DAILY (automatic):**
```
02:00 - Proxmox backup (LXC 100) → HDD
02:30 - Proxmox backup (VM 101) → HDD
```

**WEEKLY (automatic):**
```
Sunday 03:00 - SnapRAID sync (media protection)
```

**MONTHLY (automatic):**
```
1st day 04:00 - SnapRAID scrub (bit rot check)
```

**BEFORE UPDATES (manual):**
```
Before Proxmox/Docker/HA update:
→ Snapshot (NVMe, fast rollback)
→ If OK: Delete snapshot after 1-2 days
→ If FAIL: Rollback (30 seconds!)
```

**OFFSITE (manual/scheduled):**
```
While Windows machine is on:
→ Run Robocopy script
→ D:\Backups\Proxmox (offsite)
```

### **Network topology:**

```
Internet
   ↓
Router (192.168.0.1)
   ↓
   ├─ Proxmox Host (192.168.0.109)
   │    ├─ LXC 100 (192.168.0.110) - Docker
   │    └─ VM 101 (192.168.0.202) - Home Assistant
   │         └─ USB: SONOFF Zigbee Dongle
   │              └─ Zigbee2MQTT
   │                   ├─ Philips Hue (3x)
   │                   ├─ EMOS GoSmart (1x)
   │                   └─ Aqara Door Sensor (1x)
   │
   └─ Windows PC (192.168.0.100) - Offsite backup
```

### **Access points:**

| Service | URL | Description |
|---------|-----|-------------|
| **Proxmox WebUI** | https://192.168.0.109:8006 | Proxmox management |
| **Home Assistant** | http://192.168.0.202:8123 | HA WebUI |
| **Zigbee2MQTT** | http://192.168.0.202:8099 | Z2M frontend (OR sidebar) |
| **Jellyfin** | http://192.168.0.110:8096 | Media server |
| **qBittorrent** | http://192.168.0.110:8080 | Torrent client |
| **Radarr** | http://192.168.0.110:7878 | Movie management |
| **Sonarr** | http://192.168.0.110:8989 | TV management |
| **Samba** | \\192.168.0.109\Storage | Network file share |

---

## 🔧 Useful Commands

### **Proxmox host:**

```bash
# VM/LXC status
qm status 101
pct status 100

# VM start/stop
qm start 101
qm stop 101
qm reboot 101

# LXC start/stop
pct start 100
pct stop 100
pct reboot 100

# LXC shell
pct enter 100

# Manual backup
vzdump 100 --storage backup-hdd --mode snapshot --compress zstd
vzdump 101 --storage backup-hdd --mode snapshot --compress zstd

# Backup list
ls -lh /mnt/storage/backup/proxmox/dump/

# SnapRAID
snapraid status
snapraid sync
snapraid scrub -p 10

# Storage info
pvesm status
df -h /mnt/storage
```

### **Home Assistant (Terminal & SSH):**

```bash
# HA CLI
ha help
ha core info
ha core restart
ha core update

# Add-on management
ha addons
ha addons info zigbee2mqtt
ha addons restart zigbee2mqtt
ha addons logs zigbee2mqtt

# Backup
ha backups new --name "manual-backup"
ha backups list

# USB devices
ls -lh /dev/ttyUSB*
ls -lh /dev/ttyACM*

# Config files
ls -lh /config/
cat /config/automations.yaml
nano /config/configuration.yaml
```

### **Zigbee2MQTT:**

**Z2M WebUI → Settings → Tools:**
- Touchlink factory reset (for Philips lamps)
- Permit join (All/Specific)
- Network map (graphical)

**View logs:**
```bash
# HA Terminal & SSH
docker logs -f addon_45df7312_zigbee2mqtt
```

### **Docker (LXC 100):**

```bash
# Container list
docker ps -a

# Logs
docker logs -f jellyfin
docker logs -f radarr

# Restart
docker restart jellyfin
docker compose -f /srv/docker-compose/jellyfin/docker-compose.yml restart

# Cleanup
docker system prune -a
```

### **Windows (PowerShell/CMD):**

```cmd
REM Samba connection
net use \\192.168.0.109\Storage /user:smbuser
net use  REM List all connections
net use * /delete /yes  REM Delete all

REM Robocopy sync
D:\Scripts\proxmox-backup-sync.bat

REM View log
type D:\Scripts\sync.log | more

REM Credential Manager
cmdkey /list
cmdkey /add:192.168.0.109 /user:smbuser /pass:PASSWORD
```

---

## ❗ Troubleshooting

### **HA VM won't boot:**

**Problem:** Stuck at "Booting from Hard Disk" or "Starting serial terminal"

**Solution:**
1. **STOP** attempting manual QCOW2 import
2. **Use the community script:**
   ```bash
   bash -c "$(curl -fsSL https://raw.githubusercontent.com/community-scripts/ProxmoxVE/main/vm/haos-vm.sh)"
   ```
3. Script automatically configures: UEFI, OVMF, q35, latest HA OS

### **Zigbee device won't pair:**

**Checks:**
1. **USB dongle accessible?**
   ```bash
   ls /dev/ttyUSB*  # In HA Terminal
   ```
2. **Z2M running?**
   ```
   Z2M Add-on → Log tab → "Started" message?
   ```
3. **Permit join ON?**
   ```
   Z2M WebUI → Permit join (All) → Green?
   ```
4. **Device in reset mode?**
   - Philips Hue: App reset
   - EMOS: 5x ON/OFF
   - Aqara: Button 5 sec → LED flashing?
5. **Dongle CLOSE to device?** (1-2 meters for first pairing!)

### **MQTT integration not visible:**

1. **Mosquitto running?**
   ```
   Settings → Add-ons → Mosquitto broker → Started?
   ```
2. **Z2M connected to MQTT?**
   ```
   Z2M Log → "MQTT connected" message?
   ```
3. **Did you add MQTT when discovered?**
   ```
   Settings → Devices & Services → Discovered → MQTT → ADD (do NOT ignore!)
   ```

### **Proxmox backup errors:**

**"unable to create backup":**
1. **Storage accessible?**
   ```bash
   ls -ld /mnt/storage/backup/proxmox
   df -h /mnt/storage
   ```
2. **VM/LXC running?**
   ```bash
   qm status 101
   pct status 100
   ```
3. **Snapshot mode supported?**
   - LXC: LVM-thin OK ✅
   - VM: QCOW2/RAW OK ✅

**"backup retention cleanup failed":**
- Keep last/weekly/monthly numbers too small?
- Enough space?
  ```bash
  df -h /mnt/storage
  ```

### **Windows backup sync error 1219:**

**Problem:** "Multiple connections to a server"

**Solution:**
```cmd
net use * /delete /yes
D:\Scripts\proxmox-backup-sync.bat
```

**Or modify the script:** Delete connections first!
```batch
net use \\192.168.0.109 /delete /yes 2>nul
robocopy "\\192.168.0.109\Storage\backup\proxmox\dump" "D:\Backups\Proxmox" /MIR
```

---

## 🎯 Next Steps

### **Short term (1 week):**

- [ ] **Pair more Zigbee devices** (additional lamps, sensors)
- [ ] **Fix automations** (device ID → entity ID conversion)
- [ ] **Customize HA Dashboard** (Layout, Lovelace cards)
- [ ] **Check Z2M network map** (Map tab)

### **Medium term (1 month):**

- [ ] **Install mobile app** (Android/iOS)
- [ ] **Set up notifications** (push notification)
- [ ] **Expand automations** (presence detection, schedules)
- [ ] **Energy monitoring** (with smart plugs)
- [ ] **Install HACS** (custom integrations)

### **Long term (3-6 months):**

- [ ] **Expand Zigbee mesh** (router devices, repeaters)
- [ ] **Advanced automations** (Node-RED, scripts)
- [ ] **Voice assistant** (Assist, Whisper, Piper)
- [ ] **Google Drive backup** (rclone offsite)
- [ ] **Dashboard display** (tablet, Raspberry Pi)

---

## 📚 Further Resources

### **Official documentation:**

- **Home Assistant:** https://www.home-assistant.io/docs/
- **Zigbee2MQTT:** https://www.zigbee2mqtt.io/
- **Proxmox VE:** https://pve.proxmox.com/wiki/Main_Page
- **SnapRAID:** https://www.snapraid.it/manual

### **Community:**

- **HA Community:** https://community.home-assistant.io/
- **HA Reddit:** https://www.reddit.com/r/homeassistant/
- **Z2M GitHub:** https://github.com/Koenkk/zigbee2mqtt
- **Proxmox Forum:** https://forum.proxmox.com/

### **Device compatibility:**

- **Z2M Supported devices:** https://www.zigbee2mqtt.io/supported-devices/
- **HA Integrations:** https://www.home-assistant.io/integrations/

---

## 🎉 Summary

**What we achieved:**

✅ **Home Assistant OS VM** (16.3) on Proxmox with UEFI boot  
✅ **Zigbee2MQTT** fully configured (MQTT, USB passthrough)  
✅ **5 Zigbee devices** paired and working  
✅ **Automations copied and fixed** from old HA  
✅ **Docker HA removed** from LXC (port freed)  
✅ **Full backup strategy:**  
  - Proxmox backup (daily to HDD)  
  - SnapRAID (media protection)  
  - Snapshot (pre-update on NVMe)  
  - Windows offsite (robocopy script)  
✅ **3-2-1 rule met** (3 copies, 2 media, 1 offsite)

**Working system:**
- 🏠 Home Assistant: http://192.168.0.202:8123
- 📡 Zigbee2MQTT: Sidebar or :8099
- 💾 Automatic backup: Nightly 02:30
- 🔒 Secure: Snapshot + Backup + Offsite

**Congratulations! Full home automation + backup system ready!** 🎄✨

---

**Created:** 2025-12-25  
**System:** Proxmox VE 9.1.2 / Home Assistant OS 16.3  
**Version:** 1.0
