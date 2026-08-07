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
| Network | Ethernet (enp39s0) → TP-Link RE605X extender → wireless backhaul → TP-Link Archer C6 (main router, 192.168.0.1) |

## Software

| Property | Value |
|----------|-------|
| OS | Nobara Linux 44 (KDE Plasma Desktop Edition) |
| Kernel | 7.1.4-200.nobara.fc44.x86_64 |
| NVIDIA driver | 595.84 |
| Desktop | KDE Plasma / Wayland |

Not always on. GPU inference node for the homelab.

---

## Storage Layout

| Device | Size | FS | Mount | Notes |
|--------|------|----|-------|-------|
| nvme0n1p1 | 600 MB | vfat | /boot/efi | **The only ESP on the machine** - holds both GRUB and the Windows bootloader |
| nvme0n1p2 | 2 GB | ext4 | /boot | |
| nvme0n1p3 | 1.8 TB | btrfs | /home | Main OS drive |
| nvme0n1p4 | 8.8 GB | swap | [SWAP] | |
| nvme1n1p2 | 465 GB | ntfs | /mnt/nvme | Secondary NVMe - **also the Windows 11 system partition** |
| nvme1n1p3 | 642 MB | ntfs | - | Windows recovery (WinRE) |
| sda1 | 3.6 TB | ntfs | /mnt/hdd | External HDD, backup target |
| zram0 | 8 GB | swap | [SWAP] | Compressed RAM swap |

---

## Dual-boot with Windows 11

The Windows side has its own page: [Windows 11 (nex-pc dual-boot)](winpc.md) - SSH access, key distribution, DNS.

Windows lives on `nvme1n1`, Nobara on `nvme0n1`, but **both bootloaders share the single ESP on `nvme0n1p1`**. The Windows disk has no EFI System Partition of its own - only MSR (16 MB) + NTFS + WinRE. Anything that reformats `nvme0n1p1` takes out both operating systems at once.

### 2026-08-07 - Windows invisible to GRUB after the Nobara install

Windows originally lived on `nvme0n1`. When Nobara was installed there, the installer reformatted the ESP and deleted `\EFI\Microsoft`. The Windows install itself stayed intact (`Windows\System32\winload.efi`, registry hives, and the pristine `Windows\Boot\EFI\bootmgfw.efi` copy were all present), but with no bootloader and no BCD there was nothing for `os-prober` to find. Not a GRUB detection bug - the boot files were simply gone.

No BitLocker was in play (the NTFS partition mounted and read fine from Linux), so the fix was non-destructive.

**Repair, from a Windows 11 installer USB.** Boot it in UEFI mode and press `Shift+F10` at any setup screen for a command prompt. Do **not** use Startup Repair - only run `bcdboot`:

```
diskpart
list vol
```

Identify the volumes carefully before continuing. On this machine `C:` in WinPE is the 3.6 TB data HDD, *not* Windows:

| Volume | Ltr | Size | What it is |
|---|---|---|---|
| 1 | C | 3726 GB NTFS | data HDD (`sda1`) - do not touch |
| 2 | - | 600 MB FAT32 (Hidden) | the ESP |
| 3 | D | 465 GB NTFS | the Windows install |
| 4 | - | 642 MB NTFS (Hidden) | WinRE |

```
sel vol 2
assign letter=S
exit
bcdboot D:\Windows /s S: /f UEFI
```

Expected output: `Boot files successfully created.` This writes `\EFI\Microsoft\Boot\bootmgfw.efi` + BCD, copying the boot files from the *target* install - so a Windows 10 PE can repair a Windows 11 install just as well. It does not touch `\EFI\fedora`.

**Then in Nobara.** `GRUB_DISABLE_OS_PROBER` was unset, which on Fedora/Nobara means *disabled*, so os-prober never ran:

```bash
echo 'GRUB_DISABLE_OS_PROBER=false' | sudo tee -a /etc/default/grub
sudo grub2-mkconfig -o /boot/grub2/grub.cfg
# Found Windows Boot Manager on /dev/nvme0n1p1@/EFI/Microsoft/Boot/bootmgfw.efi
```

`bcdboot` normally also puts Windows Boot Manager first in the firmware boot order; here it did not, and GRUB still came up first. If a Windows feature update ever steals the order back:

```bash
sudo efibootmgr              # note the entry numbers
sudo efibootmgr -o <Nobara>,<Windows>
```

---

## Running Services

| Service | Description |
|---------|-------------|
| ollama.service | Local LLM inference (GPU) |
| docker.service | Immich remote ML container |
| periphery.service | Komodo Periphery agent (outbound to Komodo Core) |
| sshd.service | SSH server |
| mnt-claudemgmt.service | SSHFS mount from LXC 109 |
| mnt-storage/disk1-4 automount | NFS from Proxmox host |
| firewalld.service | Firewall |
| smartd.service | SMART disk monitoring |

---

## Docker Containers

| Container | Image | Port | Description |
|-----------|-------|------|-------------|
| `immich_machine_learning_remote` | `ghcr.io/immich-app/immich-machine-learning:v2.7.4-cuda` | 3003 | Immich remote ML (face recognition, smart search) - GPU accelerated |

---

## Ollama

Service: `ollama.service` (active, GPU)

| Model | Size | Used by |
|-------|------|---------|
| qwen3:8b | ~5.2 GB | Karakeep AI tagging, Suggestarr LLM |
| nomic-embed-text:latest | 274 MB | Karakeep embedding |

Ollama API: `http://192.168.0.100:11434/`

Services using this instance: Karakeep (`INFERENCE_TEXT_MODEL`), Suggestarr (`OPENAI_BASE_URL`).

**Note:** Nobara is not 24/7. When offline, Karakeep AI tagging, Suggestarr LLM, and Immich ML (smart search, face recognition) are unavailable.

---

## TCP Keepalive Configuration

Applied 2026-04-09 to speed up dead connection detection (relevant for NFS, SSHFS, Ollama, Docker):

File: `/etc/sysctl.d/99-tcp-keepalive.conf`

```
net.ipv4.tcp_keepalive_time=60
net.ipv4.tcp_keepalive_intvl=10
net.ipv4.tcp_keepalive_probes=3
```

Apply without reboot:
```bash
sudo sysctl -p /etc/sysctl.d/99-tcp-keepalive.conf
```

**What it does:** System-wide TCP keepalive settings. After 60 seconds of idle, sends keepalive probes every 10 seconds, 3 times. If no response, the connection is declared dead. Default Linux values are 7200s/75s/9 - meaning a dead connection can hang for ~2.5 hours before being detected.

**Scope:** All TCP connections on the system (NFS, SSHFS, Ollama, Docker, Steam, browser, etc.). No functional impact - connections just fail faster when the remote end is unreachable instead of hanging indefinitely.

---

## Dual-homed LAN + Tailscale port (2026-08-07)

This machine sits on 192.168.0.0/24 twice - Ethernet `enp39s0` 192.168.0.100 (metric 100) and WiFi `wlp41s0` 192.168.0.90 (metric 600), both with a default route. Two fixes were applied after SSH sessions to it started stalling for long stretches:

```bash
# WiFi power save off (Intel AC 3168 / iwlwifi, on by default)
sudo nmcli connection modify Secret 802-11-wireless.powersave 2
sudo nmcli connection up Secret

# /etc/sysctl.d/99-arp-flux.conf - stop answering ARP for the other interface's IP
net.ipv4.conf.all.arp_ignore=1
net.ipv4.conf.all.arp_announce=2
```

Without `arp_ignore`/`arp_announce`, Linux answers an ARP request for 192.168.0.100 on the WiFi interface as well, so a peer can end up sending Ethernet-addressed traffic over the power-saving WiFi link. The neighbour table showed exactly that - the same LAN hosts cached on both interfaces at once.

Tailscale port: this node is the fifth Tailscale node behind the Archer C6 and was still on the default UDP 41641, colliding with pve. Changed to 41645 in `/etc/default/tailscaled`, see [31 - Tailscale Port Collision + DNS Audit](../proxmox/31_Tailscale_Port_Collision_DNS_Audit.md).

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

## Known Issues

### SSH sessions to LXC 109 freeze for long stretches (open, 2026-08-07)

An interactive SSH session to LXC 109 running Claude Code freezes completely - no output, no echo - then recovers on its own. **Unresolved.** Eight hypotheses have been excluded by measurement, two unrelated real failures were captured, and two watchers are running on LXC 109 to catch the next occurrence: `/var/log/nobara-freeze.log` and `/var/log/nobara-stall.log`.

Read [32 - Nobara SSH Freeze](../proxmox/32_Nobara_SSH_Freeze_Investigation.md) before touching this again - it lists what was already ruled out and how, so the next attempt does not repeat the same tests.

`IPQoS none` is now set on both ends (`/etc/ssh/sshd_config.d/99-ipqos.conf` and `~/.ssh/config`) because SSH was the only traffic on this LAN marking its packets with DSCP, which matters on a wireless backhaul. It did not fix the freeze.

### Black screen on first boot (Plymouth → SDDM race condition)

**Symptom:** After a cold boot, the system shows a black screen with only a mouse cursor - KDE/SDDM doesn't load. On second boot (reboot), the GUI loads normally.

**Root cause:** Race condition between Plymouth (boot splash) and SDDM startup on Fedora 43 / Nobara fc43. SDDM starts before the GPU driver (NVIDIA in this case) fully initializes. This is a [known Fedora 43 KDE issue](https://discussion.fedoraproject.org/t/fedora-43-kde-sometimes-boots-to-a-black-screen/171080) - not kernel-version specific, affects older kernels too.

**Workaround applied (2026-04-26):** Added a 3-second delay before SDDM starts:

```bash
sudo mkdir -p /etc/systemd/system/sddm.service.d/
sudo tee /etc/systemd/system/sddm.service.d/delay.conf << 'EOF'
[Service]
ExecStartPre=/bin/sleep 3
EOF
sudo systemctl daemon-reload
```

File: `/etc/systemd/system/sddm.service.d/delay.conf`

If 3 seconds is not enough, increase to 5. If still broken, disable Plymouth entirely:
```bash
sudo grubby --update-kernel=ALL --remove-args=rhgb
```

**Status:** Fix was included in kwin 6.5.2+ (system is on 6.6.4) but the race condition still appeared - the sleep delay is the active workaround.

---

## Virtualization (KVM/libvirt)

Installed 2026-07-23 to run a Windows 10 VM for Claude Desktop practice (interview prep).

| Property | Value |
|----------|-------|
| Packages | `@virtualization` group (libvirt, qemu-kvm, virt-manager, spice-vdagent) |
| libvirtd | enabled, `qemu:///system` |
| Network | libvirt `default` NAT network (virbr0, 192.168.122.0/24) |
| VM | `win10-claude`, 8 GB RAM, 2 vCPU, 64 GB qcow2 disk at `/var/lib/libvirt/images/` |
| NIC | `e1000e` (not `virtio` - Windows 10 has no built-in virtio-net driver) |
| CPU mode | `host-passthrough` (passes AMD SVM through for nested virtualization) |
| Install source | `/mnt/hdd/INSTALL/OSs/W1064HU2202V1.iso` |

Console: `virt-manager` locally (GUI, SPICE display), or `virsh --connect qemu:///system console win10-claude`.

### VM internet access - Docker/libvirt FORWARD chain conflict

Right after creating the VM, the guest got a DHCP lease from libvirt's dnsmasq (192.168.122.0/24) and could reach the host (192.168.122.1) but nothing beyond it - no internet. Cause: Docker's own `iptables`-managed `table ip filter` chain `FORWARD` runs at nftables priority `filter` (0), *before* firewalld's `table inet firewalld` chain `filter_FORWARD` (priority `filter+10`) which has the correct libvirt-forwarding accept rule. Since Docker's `FORWARD` chain policy is `drop` and only jumps to `DOCKER-USER`/`DOCKER-FORWARD`/`ts-forward` (none of which know about `virbr0`), guest traffic was silently dropped before firewalld's rule ever ran. This is a known Docker+libvirt+firewalld(nftables) interaction (RHBZ 1638342 talks about the older iptables-backend version of the same class of bug).

Fix - add explicit accepts to `DOCKER-USER` (the one chain Docker guarantees not to overwrite on restart/reload):

```bash
sudo iptables -I DOCKER-USER -i virbr0 -o enp39s0 -j ACCEPT
sudo iptables -I DOCKER-USER -i enp39s0 -o virbr0 -j ACCEPT
```

### Resizing the VM

Static memory/CPU changes require the VM to be off:

```bash
sudo virsh --connect qemu:///system shutdown win10-claude
# wait for "shut off" in: virsh --connect qemu:///system list --all
sudo virt-xml win10-claude --edit --memory memory=8192,currentMemory=8192
sudo virsh --connect qemu:///system start win10-claude
```

### Clipboard sharing (host <-> guest)

Needs a SPICE agent on both ends:

- Host: `sudo dnf install -y spice-vdagent` (was skipped initially by the Nobara repo GPG bug below, install cleanly once that's fixed), then `sudo systemctl enable --now spice-vdagentd`.
- Guest: install [SPICE guest tools](https://www.spice-space.org/download/windows/spice-guest-tools/spice-guest-tools-latest.exe) inside Windows, then reboot the VM.

Once both are running, copy/paste works transparently through the `virt-manager` SPICE console window - no extra steps.

### Claude Desktop Cowork - "Missing HCS services: HNS, vmcompute"

Cowork's sandbox needs Windows' own Hyper-V/Host Compute Service stack (`vmcompute`, `hns`, `vfpext`), which needs nested virtualization inside the guest. Both host prerequisites were already satisfied by default here: `cat /sys/module/kvm_amd/parameters/nested` returned `1`, and `virt-install` had already set `<cpu mode='host-passthrough'/>` on the VM (passes AMD SVM through to the guest). So the fix was entirely inside Windows - enable the optional features and do a real restart (not shutdown/power-on, which skips re-initializing virtualization services under Fast Startup):

```powershell
Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -All
Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All
Enable-WindowsOptionalFeature -Online -FeatureName Containers -All
Restart-Computer
```

Verify after reboot: `Get-Service vmcompute, hns` should both show `Running`.

## Incidents

### 2026-07-23 - Network outage during `@virtualization` install (firewalld state corruption)

**Symptom:** Mid-`dnf install -y @virtualization`, the transaction appeared to hang at a `systemd` `%triggerpostun` scriptlet. Shortly after, all network connectivity died completely - not even the gateway (192.168.0.1) responded to ping, DNS resolution failed, and the active SSH session from LXC 109 dropped.

**Root causes (two independent issues):**

1. **Stale repo GPG keys.** `/etc/yum.repos.d/nobara.repo`'s `[nobara]` section only listed `gpgkey=` paths up to `RPM-GPG-KEY-fedora-43-primary`, and `[nobara-updates]` pointed at a `nobara-baseos-pubkey-41` file that had already been removed by a `nobara-gpg-keys` package upgrade. Fedora/Nobara had moved to fc44-signed packages, so any package from those repos failed `Signature verification failed`, blocking the whole transaction (dnf transactions are all-or-nothing).

2. **Corrupted firewalld nftables state.** The `@virtualization` install pulled in/restarted `firewalld`, which raced with a `NetworkManager` restart triggered by the same transaction. This left a stray `table inet firewalld_policy_drop` in the live nftables ruleset - a table running at a *higher priority* (`filter+9`) than firewalld's own zone rules (`filter+10`), with `policy drop` on all three chains (`filter_input`, `filter_forward`, `filter_output`) and only `ct state established,related` allowed through. Every new connection (ping, DNS, SSH) was silently dropped before it ever reached the normal zone-based rules. `firewalld`'s own log showed the underlying corruption: `ERROR: UNKNOWN_INTERFACE: 'enp39s0' is not in any zone` and a Python traceback around the time of the NetworkManager restart.

**Fixes applied:**

```bash
# 1. GPG key config - add the missing key, replace the dead one
sudo sed -i '9a\       file:///etc/pki/rpm-gpg/RPM-GPG-KEY-fedora-44-primary' /etc/yum.repos.d/nobara.repo
sudo sed -i \
  -e 's#file:///etc/pki/rpm-gpg/RPM-GPG-KEY-nobara-baseos-pubkey-41#file:///etc/pki/rpm-gpg/RPM-GPG-KEY-nobara-baseos-pubkey-44#' \
  /etc/yum.repos.d/nobara.repo

# 2. Corrupted firewalld state - full restart regenerates nftables from clean config
sudo systemctl restart firewalld
```

The `firewalld` restart alone fixed connectivity (the stray drop-table is a runtime nftables artifact, not a config file, so it doesn't recur on a normal boot). Interfaces were then explicitly re-pinned to the `FedoraWorkstation` zone (was already the default before the incident) to rule out any lingering ambiguity:

```bash
sudo firewall-cmd --zone=FedoraWorkstation --change-interface=enp39s0 --permanent
sudo firewall-cmd --zone=FedoraWorkstation --change-interface=wlp41s0 --permanent
sudo firewall-cmd --reload
```

**Diagnosis path:** `top` (no hung process) -> `ping` sweep (gateway unreachable = local L3/L2 issue, not remote DNS server) -> `ip a`/`ip route` (interfaces up, routes correct - ruled out interface/routing config) -> `ip neigh` (ARP partially working - ruled out pure L2 failure) -> `systemctl status firewalld` (found the `UNKNOWN_INTERFACE` errors and traceback) -> `nft list ruleset` (found the `firewalld_policy_drop` table with `policy drop` running ahead of the real zone rules).

**Lesson:** a package transaction that touches `libvirt`/`firewalld` while `NetworkManager` also restarts mid-transaction can corrupt firewalld's live nftables state independent of its saved config. If a network outage follows a package install involving virtualization/firewall packages, check `sudo nft list ruleset` for stray tables before assuming a routing or DNS problem - `systemctl restart firewalld` resolved it without needing a reboot.

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
- Root cause of LXC 109 outage: Tailscale `accept-routes=true` on LXC 109 - see [claude-mgmt.md](../hosts/claude-mgmt.md)
