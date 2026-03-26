
**Date:** 2026-02-09
**Updated:** 2026-03-26
**System:** Proxmox VE 9.1
**Affected devices:** ADATA HD710 PRO 1.8TB (disk4, USB 3.0), disk3 (USB)

---

## Problem Description

The `/mnt/disk4` mountpoint was randomly unmounting, causing the following issues:
- Jellyfin media server was unable to play files
- MergerFS pool became partially inaccessible
- Netdata generated false alarm alerts

### Symptoms
```
[Thu Feb 5 08:45:43 2026] usb 2-9: USB disconnect, device number 3
[Thu Feb 5 08:45:43 2026] device offline error, dev sdd
[Thu Feb 5 08:45:43 2026] EXT4-fs (sdd1): shut down requested (2)
[Thu Feb 5 08:45:43 2026] EXT4-fs (sdd1): unmounting filesystem
```

---

## Root Cause Analysis

### Hardware Info
- **Device:** ADATA HD710 PRO
- **Connection:** USB 3.0 (Bus 002, Device variable)
- **Vendor ID:** 125f
- **Product ID:** a75a
- **Serial:** YOUR_USB_SERIAL
- **Capacity:** 1.8TB (1,950,615,552 sectors)

### Root Cause
The USB device **automatically entered suspend mode** (Linux USB power management), which caused a disconnect event. The EXT4 filesystem performed an emergency shutdown as a protective measure.

---

## Implemented Solutions

### 1. Disable USB Autosuspend

**File:** `/etc/udev/rules.d/50-adata-no-suspend.rules`
```bash
# ADATA HD710 PRO - disable USB autosuspend
ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="125f", ATTR{idProduct}=="a75a", TEST=="power/control", ATTR{power/control}="on"
ACTION=="add", SUBSYSTEM=="usb", ATTR{idVendor}=="125f", ATTR{idProduct}=="a75a", TEST=="power/autosuspend", ATTR{power/autosuspend}="-1"
```

**Apply:**
```bash
udevadm control --reload-rules
echo on > /sys/bus/usb/devices/2-9/power/control
echo -1 > /sys/bus/usb/devices/2-9/power/autosuspend
```

### 2. Automatic Remount Watchdog + NFS Restart

USB disconnect causes systemd to stop nfs-server (dependency chain: disk unmount -> nfs-server stops). The watchdog handles both remount and NFS restart.

**File:** `/usr/local/bin/disk4-watchdog.sh`
```bash
#!/bin/bash
while true; do
    if ! mountpoint -q /mnt/disk4; then
        logger "disk4-watchdog: /mnt/disk4 not mounted, attempting remount..."
        if mount /mnt/disk4; then
            logger "disk4-watchdog: Successfully remounted /mnt/disk4"
            if ! systemctl is-active --quiet nfs-server; then
                logger "disk4-watchdog: Restarting nfs-server..."
                systemctl start nfs-server && logger "disk4-watchdog: nfs-server restarted"
            fi
        fi
    fi
    sleep 60
done
```

**File:** `/usr/local/bin/disk3-watchdog.sh` (disk3 is also USB)
```bash
#!/bin/bash
while true; do
    if ! mountpoint -q /mnt/disk3; then
        logger "disk3-watchdog: /mnt/disk3 not mounted, attempting remount..."
        if mount /mnt/disk3; then
            logger "disk3-watchdog: Successfully remounted /mnt/disk3"
            if ! systemctl is-active --quiet nfs-server; then
                logger "disk3-watchdog: Restarting nfs-server..."
                systemctl start nfs-server && logger "disk3-watchdog: nfs-server restarted"
            fi
        fi
    fi
    sleep 60
done
```

**Systemd Services:**

`/etc/systemd/system/disk4-watchdog.service`
```ini
[Unit]
Description=Disk4 Auto-remount Watchdog
After=local-fs.target

[Service]
Type=simple
ExecStart=/usr/local/bin/disk4-watchdog.sh
Restart=always

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/disk3-watchdog.service`
```ini
[Unit]
Description=Disk3 Auto-remount Watchdog
After=local-fs.target

[Service]
Type=simple
ExecStart=/usr/local/bin/disk3-watchdog.sh
Restart=always

[Install]
WantedBy=multi-user.target
```

**Activate disk3 watchdog (disk4 was already active):**
```bash
chmod +x /usr/local/bin/disk3-watchdog.sh
systemctl daemon-reload
systemctl enable --now disk3-watchdog
```

---

## System Configuration

### /etc/fstab - Disk Mounts
```bash
# 2x 6TB HDD mounts
UUID=YOUR_DISK1_UUID  /mnt/disk1  ext4  defaults,noatime  0  2
UUID=YOUR_DISK2_UUID  /mnt/disk2  ext4  defaults,noatime  0  2

# USB HDDs
UUID=YOUR_DISK3_UUID  /mnt/disk3  ext4  defaults,noatime  0  2
UUID=YOUR_DISK4_UUID  /mnt/disk4  ext4  defaults,noatime  0  2

# MergerFS (disk2 is SnapRAID parity, not in pool!)
/mnt/disk1:/mnt/disk3:/mnt/disk4  /mnt/storage  fuse.mergerfs  defaults,allow_other,use_ino,cache.files=partial,dropcacheonclose=true,category.create=mfs  0  0
```

### Disk Layout

| Disk   | Size   | Type        | Mount Point   | Role               |
|--------|--------|-------------|---------------|--------------------|
| sda1   | 5.5TB  | SATA        | /mnt/disk1    | Data + MergerFS    |
| sdb1   | 5.5TB  | SATA        | /mnt/disk2    | SnapRAID Parity    |
| sdc1   | 931GB  | SATA        | /mnt/disk3    | Data + MergerFS    |
| sdd1   | 1.8TB  | USB 3.0     | /mnt/disk4    | Data + MergerFS    |

**Total MergerFS pool:** ~8.1TB

---

## Verification Commands

### Watchdog Status
```bash
systemctl status disk4-watchdog disk3-watchdog
journalctl -u disk4-watchdog -f
journalctl -u disk3-watchdog -f
```

### USB Power Settings
```bash
cat /sys/bus/usb/devices/2-9/power/control      # Output: on
cat /sys/bus/usb/devices/2-9/power/autosuspend  # Output: -1
```

### Disk Mount Status
```bash
lsblk | grep sdd
mount | grep disk4
df -h | grep disk4
```

### MergerFS Status
```bash
mount | grep storage
df -h | grep storage
ls /mnt/storage/media  # Test whether it is accessible
```

### USB Disconnect Monitoring (real-time)
```bash
dmesg -w | grep -i "usb\|sdd"
```

---

## Troubleshooting

### If disk4 unmounts AGAIN:

1. **Check watchdog operation:**
```bash
   systemctl status disk4-watchdog
   journalctl -u disk4-watchdog --since "10 minutes ago"
```

2. **Check kernel logs:**
```bash
   dmesg -T | grep -i "sdd\|usb" | tail -50
```

3. **Manual remount:**
```bash
   mount /mnt/disk4
```

4. **If the watchdog does NOT remount automatically:**
```bash
   systemctl restart disk4-watchdog
```

### If problems persist:

**Hardware solutions:**
1. Try a **different USB port** (rear port > front port)
2. Use a **shorter or better quality USB 3.0 cable**
3. Use an **externally powered USB hub** if available
4. Check that **too many devices are not sharing** the same USB controller

**Additional software settings:**
```bash
# Increase Linux kernel USB timeout (optional, if disconnects still occur)
echo 0 > /sys/module/usbcore/parameters/autosuspend
```

---

## SMART Monitoring

Regular health checks for the disk:
```bash
# Quick health check
smartctl -H /dev/sdd

# Detailed info
smartctl -a /dev/sdd

# Run extended test (offline, ~2-3 hours)
smartctl -t long /dev/sdd
```

**SMART Status (last check):** PASSED ✅

---

## Next Steps

1. ✅ USB autosuspend disabled
2. ✅ Watchdog service running and enabled
3. ⏳ **Monitor for 1-2 weeks** to see if the problem recurs
4. 🔜 If stable → close documentation
5. 🔜 If not → hardware replacement (cable/hub/port)

---

## Related Services

### Jellyfin Docker
If Jellyfin stops working after a disk unmount:
```bash
cd /srv/docker-data/jellyfin
docker-compose restart
docker logs jellyfin --tail 50
```

### MergerFS Reload
If the MergerFS pool does not refresh:
```bash
umount /mnt/storage
mount /mnt/storage
```

---

## Notes

- **disk2 is NOT part of the MergerFS pool** because it is the SnapRAID parity disk
- The watchdog checks the mount **every 60 seconds**
- The USB device is on **port 2-9**, which may change on reconnect
- The **udev rules apply automatically** after every boot

---

---

## Incident: 2026-03-24 03:02 - NFS server stopped

**What happened:** disk4 USB disconnect at 03:02 (during SnapRAID sync) triggered an NFS server shutdown. The disk reconnected within 5 seconds and the watchdog remounted it, but the watchdog did not restart nfs-server. NFS remained down for 2 days until manually started.

**Root cause chain:**
1. disk4 USB disconnect (likely I/O load from SnapRAID sync)
2. EXT4 emergency shutdown on sdd1
3. systemd unmounted `/mnt/disk4`
4. systemd stopped nfs-server (dependency on mounted export paths)
5. disk4 reconnected, watchdog remounted it
6. nfs-server not restarted - remained inactive for 2 days

**Fix applied 2026-03-26:**
- disk4 watchdog updated to restart nfs-server after successful remount
- disk3 watchdog created with same logic (disk3 is also USB)

---

**Last updated:** 2026-03-26
**Status:** Resolved
**Author:** Nex @ Proxmox homelab
