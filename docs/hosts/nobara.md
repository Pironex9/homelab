# Nobara PC

**Date:** 2026-04-09
**Hostname:** nex-pc
**IP address:** 192.168.0.100
**User:** nex

---

## Overview

| Property | Value |
|----------|-------|
| OS | Nobara Linux (Fedora-based) |
| Kernel | 6.19.11-201.nobara.fc43.x86_64 |
| GPU | NVIDIA RTX 2060 (driver 595.58.03) |
| Desktop | KDE Plasma / Wayland |
| Network | Ethernet via TP-Link RE605X wireless backhaul |
| Role | Desktop PC, Ollama GPU node (not 24/7) |

Not always on. Hosts Open WebUI + AnythingLLM + Ollama (GPU inference).

---

## NVIDIA + Wayland Configuration

### nvidia_drm.fbdev=1 kernel parameter

Applied 2026-04-08 to fix kwin_wayland crash loop on boot:

```bash
sudo grubby --update-kernel=ALL --args="nvidia_drm.fbdev=1"
```

**What it does:** Enables the NVIDIA DRM framebuffer device. Required for Wayland - KDE's display manager uses it to hand off display control to the NVIDIA driver. Without it, the driver doesn't take control in time and kwin_wayland crashes repeatedly at login (11 crashes per boot were observed).

**Verification:**
```bash
journalctl -b 0 --no-pager | grep -c "drkonqi-coredump-launcher.*kwin_wayland"
```
Should return 0. Note: on the first boot after applying the fix, it may still show 11 (drkonqi processing old crash reports from the previous boot). From the second boot onward it will be 0.

### kscreen config reset

If kwin crashes persist after applying the kernel parameter, delete the saved monitor config:

```bash
rm -rf ~/.local/share/kscreen/
```

---

## NFS / SSHFS Mounts

### Proxmox storage (NFS automount)

5 shares from Proxmox host (192.168.0.109): storage, disk1-4.
Managed via systemd automount units. See [NFS Setup Documentation](../proxmox/14_NFS-Setup_Documentation.md).

| Mount | Source | Type |
|-------|--------|------|
| /mnt/storage | 192.168.0.109:/mnt/storage | NFS automount |
| /mnt/disk1-4 | 192.168.0.109:/mnt/disk1-4 | NFS automount |

### LXC 109 claude-mgmt (SSHFS service)

Mounts `/root` from LXC 109 via SSHFS as a systemd service (not automount).

```
/mnt/claudemgmt  ←  root@192.168.0.204:/root
```

Service: `/etc/systemd/system/mnt-claudemgmt.service`

```bash
sudo systemctl status mnt-claudemgmt.service
```

**Why service and not automount:** The automount approach caused KDE desktop freezes when LXC 109 was offline - every directory access blocked D-Bus via systemd-hostnamed for 15+ seconds. The service mounts once at boot and uses `reconnect` to re-establish automatically without blocking the desktop.

---

## Incidents

### 2026-04-08 - GUI freeze on boot + Dolphin hangs

**Symptoms:**
- Desktop completely frozen on boot, nothing worked
- Dolphin file browser hanging for 60+ seconds on any folder open
- Console occasionally freezing while typing

**Root causes (three separate issues):**

1. **LXC 109 offline + SSHFS automount** - LXC 109 was unreachable after a Proxmox update. The `mnt-claudemgmt.automount` unit kept triggering on every Dolphin access, blocking D-Bus via systemd-hostnamed for 45 seconds per attempt. This cascaded to all desktop applications.

2. **kwin_wayland crash loop** - NVIDIA 595 driver + Wayland: 11 kwin crashes per boot before stabilizing. Caused the "everything frozen at login" experience.

3. **Stale kscreen monitor config** - Saved monitor configuration was invalid, triggering `Applying output configuration failed!` which contributed to the kwin crashes.

**Fixes applied:**
- `sudo systemctl disable --now mnt-claudemgmt.automount` (immediate relief)
- `rm -rf ~/.local/share/kscreen/` (fixed kwin crash loop)
- `sudo grubby --update-kernel=ALL --args="nvidia_drm.fbdev=1"` (permanent NVIDIA fix)
- Replaced automount with systemd service for SSHFS (permanent fix for LXC 109 outages)
- Root cause of LXC 109 outage: Tailscale `accept-routes=true` on LXC 109 - see [claude-mgmt.md](claude-mgmt.md)
