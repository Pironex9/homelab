
## Proxmox Unprivileged LXC + Docker + Intel QuickSync

**System:** HP EliteDesk 800 G4 SFF  
**CPU:** Intel i5-8400 (UHD Graphics 630)  
**Proxmox:** 8.2+  
**LXC:** Debian 12 (Bookworm) - Unprivileged  
**Jellyfin:** Official Docker image  

---

> **Note:** The Intel UHD 630 is shared between Jellyfin (hardware transcoding) and Immich (ML/face detection). Both services can use it simultaneously without conflict.

## 1. Proxmox Host - GPU Permissions

### Driver installation

```bash
# On the Proxmox host
apt update
apt install intel-media-va-driver i965-va-driver vainfo intel-gpu-tools -y
```

### Check render group

```bash
getent group render
# Output: render:x:993:
```

**Important:** Note the GID number (993) - this is what you need to use!

### Set permissions

```bash
chown root:render /dev/dri/card0
chown root:render /dev/dri/renderD128
chmod 660 /dev/dri/card0 /dev/dri/renderD128
```

### Persistent permissions (udev rules)

```bash
nano /etc/udev/rules.d/99-gpu.rules
```

Contents:
```
SUBSYSTEM=="drm", KERNEL=="card*", GROUP="render", MODE="0660"
SUBSYSTEM=="drm", KERNEL=="renderD*", GROUP="render", MODE="0660"
```

Activate:
```bash
udevadm control --reload-rules
udevadm trigger
```

### Test on Proxmox host

```bash
vainfo
# Successful output:
# vainfo: VA-API version: 1.22
# vainfo: Driver version: Intel iHD driver...
# VAProfileH264Main, VAProfileHEVCMain, etc.
```

---

## 2. LXC Device Passthrough

### Proxmox GUI method (recommended - Proxmox 8.2+)

1. Select the LXC
2. **Resources** → **Add** → **Device Passthrough**
3. Add device:
   - **Path:** `/dev/dri/card0`
   - **GID:** `993` (render group GID)
   - **Advanced** → OK
4. Second device:
   - **Path:** `/dev/dri/renderD128`
   - **GID:** `993`
5. Restart LXC

### LXC Config (auto-generated)

`/etc/pve/lxc/100.conf`:

```bash
arch: amd64
cores: 4
dev0: /dev/dri/card0,gid=993
dev1: /dev/dri/renderD128,gid=993
features: nesting=1
hostname: docker-host
memory: 8192
mp0: /mnt/storage,mp=/mnt/storage
nameserver: 192.168.0.1
net0: name=eth0,bridge=vmbr0,firewall=1,gw=192.168.0.1,hwaddr=YOUR_LXC_MAC_ADDRESS,ip=192.168.0.110/24,type=veth
onboot: 1
ostype: debian
rootfs: local-lvm:vm-100-disk-1,size=48G
swap: 0
unprivileged: 1
```

**Important:**
- Do **NOT** use the old `lxc.cgroup2.devices.allow` and `lxc.mount.entry` lines!
- The new `dev0` and `dev1` parameters replace them.

---

## 3. LXC Container - Driver installation

### Enter the LXC

```bash
pct enter 100
```

### Install drivers

```bash
apt update
apt install intel-media-va-driver i965-va-driver vainfo intel-gpu-tools libva-drm2 -y
```

### Verify inside the LXC

```bash
ls -l /dev/dri
# Output:
# crw-rw---- 1 root render 226,   0 ... card0
# crw-rw---- 1 root render 226, 128 ... renderD128
```

---

## 4. Docker Compose - Jellyfin

### Docker Compose file

`/path/to/jellyfin/docker-compose.yml`:

```yaml
services:
  jellyfin:
    image: jellyfin/jellyfin  # IMPORTANT: Official image, NOT linuxserver/jellyfin!
    container_name: jellyfin
    environment:
      - PUID=${PUID}
      - PGID=${PGID}
      - TZ=${TZ}
      - UMASK=${UMASK}
      - JELLYFIN_PublishedServerUrl=http://${HOMEPAGE_HOST}:8096
    network_mode: host
    volumes:
      - /srv/docker-data/jellyfin:/config
      - /srv/docker-data/jellyfin/cache:/cache
      - type: bind
        source: /mnt/storage/media/movies
        target: /media
      - type: bind
        source: /mnt/storage/media/tv
        target: /media2
        read_only: true
    devices:
      - /dev/dri:/dev/dri  # GPU passthrough
    group_add:
      - "993"  # Render group GID (from the Proxmox host!)
    restart: unless-stopped
    extra_hosts:
      - host.docker.internal:host-gateway

networks:
  arr_stack:
    external: true
```

### Start container

```bash
docker compose down
docker compose up -d
```

### Test inside Docker container

```bash
docker exec jellyfin /usr/lib/jellyfin-ffmpeg/vainfo
# Successful output:
# vainfo: VA-API version: 1.22 (libva 2.22.0)
# vainfo: Driver version: Intel iHD driver for Intel(R) Gen Graphics - 25.4.4
# VAProfileH264Main, VAProfileHEVCMain, VAProfileVP9Profile0, etc.
```

---

## 5. Jellyfin Settings

### Dashboard → Playback → Transcoding

**Hardware acceleration:**
- `Intel QuickSync (QSV)`

**Enable hardware decoding for:**
- ✅ H264
- ✅ HEVC
- ✅ MPEG2
- ✅ VC1
- ✅ VP8
- ✅ VP9
- ✅ HEVC 10bit
- ✅ VP9 10bit
- ✅ Prefer OS native DXVA or VA-API hardware decoders

**Hardware encoding options:**
- ✅ Enable hardware encoding
- ❌ Enable Intel Low-Power H.264 hardware encoder (leave disabled)
- ❌ Enable Intel Low-Power HEVC hardware encoder (leave disabled)

**Encoding format options:**
- ✅ Allow encoding in HEVC format
- ❌ Allow encoding in AV1 format (UHD 630 does not support it)
- ✅ Enable VPP Tone mapping (HDR → SDR conversion)

**Other settings:**
- **Encoding preset:** `medium`
- **Transcoding thread count:** `Auto`
- **H.265 encoding CRF:** `28`
- **H.264 encoding CRF:** `23`

---

## 6. User Bandwidth Limits (8 Mbps upload)

### Remote user settings

**Dashboard → Users → [User] → Playback:**

- **Max streaming bitrate:** `5000-6000 kbps` (5-6 Mbps)
- **Allow video playback that requires transcoding:** ✅
- **Allow audio playback that requires transcoding:** ✅

### LAN users

- **Max streaming bitrate:** `120000 kbps` or `Auto`
- Enable Direct Play for all formats

---

## 7. Testing

### Vainfo test hierarchy

```bash
# 1. Proxmox host
vainfo
# Successful? → Continue

# 2. LXC container
pct enter 100
vainfo
# Successful? → Continue (if "failed to initialize display", that is OK - the driver files are present)

# 3. Docker container
docker exec jellyfin /usr/lib/jellyfin-ffmpeg/vainfo
# THIS MUST WORK! Lists all codecs.
```

### Live transcoding test

1. **Play a video** from a browser or phone
2. **Change the quality** to force transcoding (e.g. 720p 4 Mbps)
3. **On the Proxmox host, run:**

```bash
intel_gpu_top
```

**Successful output:**
```
ENGINES           BUSY
Render/3D       92.88% |████████████████████████████  |
Video           98.31% |██████████████████████████████|
VideoEnhance     0.00% |                               |

PID     NAME      Video
395094  ffmpeg    |██████████████████████████████    |
```

If the **Video** bar is moving → **WORKING!** ✅

### Jellyfin Dashboard

**Dashboard → Playback Activity:**

- Badge next to stream: **"Transcoding"**
- **"HW"** icon visible
- CPU usage: **2-10%** (not 80-100%!)

---

## 8. Troubleshooting

### "failed to initialize display" error

**OK if:**
- The driver files exist (`ls -l /usr/lib/x86_64-linux-gnu/dri/`)
- Jellyfin ffmpeg vainfo works

**NOT OK if:**
- There are no drivers even inside the LXC → reinstall them
- No driver inside the Docker container → `apt install` into the container

### LXC won't start

```bash
# Check config
cat /etc/pve/lxc/100.conf

# Only dev0/dev1 should be present - the old lxc.cgroup2 and lxc.mount.entry lines must be removed!
```

### GPU not visible in Docker

```bash
# Check
docker exec jellyfin ls -l /dev/dri

# If empty:
# 1. Check in the LXC: ls -l /dev/dri
# 2. Check the devices: section in docker-compose.yml
# 3. Check the group_add: value (993?)
```

### Transcoding not using the GPU

1. **Jellyfin Dashboard → Playback:** Is Intel QuickSync enabled?
2. **Enable hardware decoding:** Every codec checked?
3. **Enable hardware encoding:** Is it enabled?
4. **Restart Jellyfin container:** `docker compose restart`

---

## 9. Performance Metrics

### Hardware transcoding (Intel UHD 630):

| Content | Transcoding | CPU | GPU Video | Streams |
|---------|-------------|-----|-----------|---------|
| 1080p H.264 → 1080p H.264 6Mbps | Real-time | 2-5% | 50-70% | 3-4 |
| 1080p HEVC → 1080p H.264 6Mbps | Real-time | 2-5% | 70-90% | 2-3 |
| 4K HEVC → 1080p H.264 6Mbps | Real-time | 5-10% | 90-98% | 1-2 |

### Software transcoding (comparison):

| Content | Transcoding | CPU | Streams |
|---------|-------------|-----|---------|
| 1080p HEVC → 1080p H.264 6Mbps | 0.8-1.2x | 80-100% | 1 |

**Conclusion:** Hardware transcoding is 10-20x more efficient! 🚀

---

## 10. Notes

- **Official Jellyfin image:** The `jellyfin/jellyfin` image **works better** in an LXC environment than `linuxserver/jellyfin`
- **Unprivileged LXC:** More secure than privileged, but device passthrough requires proper GID mapping
- **GID 993:** This is the render group ID on your Proxmox host. If yours is different, update it everywhere!
- **8 Mbps upload:** Maximum 1-2 remote streams @ 5-6 Mbps recommended
- **Privileged mode NOT needed:** The `privileged: true` Docker flag is not required with the new setup

---

## Created by

**Date:** January 14, 2026  
**Setup by:** Nex  
**Hardware:** HP EliteDesk 800 G4 SFF (i5-8400, UHD 630)  
**Working configuration - tested and verified!** ✅

---

## Useful links

- [Jellyfin Hardware Acceleration Docs](https://jellyfin.org/docs/general/administration/hardware-acceleration/)
- [Proxmox LXC Device Passthrough](https://pve.proxmox.com/pve-docs/pve-admin-guide.html#chapter_pct)
- [Intel QuickSync Support Matrix](https://en.wikipedia.org/wiki/Intel_Quick_Sync_Video)
