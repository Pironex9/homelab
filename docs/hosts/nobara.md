# Nobara PC

**Date:** 2026-04-09
**SSH access from LXC 109:** `ssh nex@192.168.0.100` (key: claude-mgmt)
**Hostname:** nex-pc
**IP address:** 192.168.0.100 (Ethernet, enp39s0)
**Tailscale IP:** 100.109.197.79
**User:** nex

---

## Hardware

| Component | Detail |
|-----------|--------|
| CPU | AMD Ryzen 7 3700X (8-core, 16 threads) |
| RAM | 32 GB |
| GPU | NVIDIA GeForce RTX 2060 SUPER, 8 GB VRAM |
| Storage | 1.8 TB NVMe (OS/home) + 465 GB NVMe (NTFS, /mnt/nvme) + 3.6 TB HDD (NTFS, /mnt/hdd) |
| Network | Ethernet via TP-Link RE605X wireless backhaul to main router |

## Software

| Property | Value |
|----------|-------|
| OS | Nobara Linux 43 (KDE Plasma Desktop Edition) |
| Kernel | 6.19.11-201.nobara.fc43.x86_64 |
| NVIDIA driver | 595.58.03 |
| Desktop | KDE Plasma / Wayland |

Not always on. GPU inference node for the homelab.

---

## Storage Layout

| Device | Size | FS | Mount | Notes |
|--------|------|----|-------|-------|
| nvme0n1p3 | 1.8 TB | btrfs | /home | Main OS drive |
| nvme1n1p2 | 465 GB | ntfs | /mnt/nvme | Secondary NVMe |
| sda1 | 3.6 TB | ntfs | /mnt/hdd | External HDD, backup target |
| zram0 | 8 GB | swap | [SWAP] | Compressed RAM swap |

---

## Running Services

| Service | Description |
|---------|-------------|
| ollama.service | Local LLM inference (GPU) |
| docker.service | AnythingLLM + Open WebUI containers |
| periphery.service | Komodo Periphery agent (outbound to Komodo Core) |
| sshd.service | SSH server |
| mnt-claudemgmt.service | SSHFS mount from LXC 109 |
| mnt-storage/disk1-4 automount | NFS from Proxmox host |
| firewalld.service | Firewall |
| smartd.service | SMART disk monitoring |

---

## Docker Containers

| Container | Image | Status |
|-----------|-------|--------|
| open-webui | ghcr.io/open-webui/open-webui:main | running |
| anythingllm | mintplexlabs/anythingllm:latest | running |

---

## Ollama

Service: `ollama.service` (active, GPU)

| Model | Size |
|-------|------|
| qwen2.5:7b | 4.7 GB |
| nomic-embed-text:latest | 274 MB |

Karakeep AI tagging uses Ollama via `http://192.168.0.100:11434/`.

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

| Mount | Source | State |
|-------|--------|-------|
| /mnt/storage | 192.168.0.109:/mnt/storage | automount |
| /mnt/disk1 | 192.168.0.109:/mnt/disk1 | automount |
| /mnt/disk2 | 192.168.0.109:/mnt/disk2 | automount |
| /mnt/disk3 | 192.168.0.109:/mnt/disk3 | automount |
| /mnt/disk4 | 192.168.0.109:/mnt/disk4 | automount |

### LXC 109 claude-mgmt (SSHFS service)

```
/mnt/claudemgmt  ←  root@192.168.0.204:/root
```

Managed by `mnt-claudemgmt.service` (not automount). See [NFS Setup Documentation](../proxmox/14_NFS-Setup_Documentation.md).

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
