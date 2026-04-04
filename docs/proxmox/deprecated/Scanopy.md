**Date:** 2026-01-04
**Status:** DEPRECATED - replaced by [Homelable](../23_Homelable_Setup.md)
**LXC ID:** 104 (decommissioned)

---

## Overview

Scanopy was a self-hosted network scanner and topology visualizer running on Debian LXC 104. It was used for local LAN discovery and Tailscale network mapping.

---

## Basic Information

- **Platform:** Debian 13 LXC (Unprivileged)
- **Installation:** Proxmox Community Scripts
- **Version:** 0.12.9
- **Port:** 60072

### Installation Command

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/community-scripts/ProxmoxVE/main/ct/scanopy.sh)"
```

### LXC Specifications

- **Container ID:** 104
- **Hostname:** scanopy
- **CPU:** 2 cores
- **RAM:** 3GB
- **Disk:** 6GB
- **Network:** vmbr0, DHCP (192.168.0.122)
- **Features:** nesting=1, keyctl=1

### Access

- **Local:** `http://192.168.0.122:60072`
- **Tailscale:** `http://YOUR_TAILSCALE_IP:60072`

---

## Tailscale Integration

The main challenge was making Scanopy visible on both the local network and the Tailscale network simultaneously.

### The Routing Problem

When Proxmox advertised `192.168.0.0/24` via Tailscale and Scanopy had `--accept-routes` enabled, the kernel routed local traffic through `tailscale0` instead of `eth0`, causing a loop and timeouts.

### Final Solution

**Proxmox host** - disable subnet advertise:
```bash
tailscale up --ssh --reset
```

**Scanopy LXC** - accept routes + allow local network through Tailscale firewall:
```bash
tailscale up --accept-routes
iptables -I ts-input 1 -i eth0 -j ACCEPT
```

Make the iptables rule persistent via systemd override:
```
/etc/systemd/system/tailscaled.service.d/override.conf
```
```ini
[Service]
ExecStartPost=/bin/sh -c 'sleep 5 && /usr/bin/tailscale up --accept-routes && /usr/sbin/iptables -I ts-input 1 -i eth0 -j ACCEPT'
```

### LXC Config (TUN/TAP support)

**File:** `/etc/pve/lxc/104.conf`
```
lxc.cgroup2.devices.allow: c 10:200 rwm
lxc.mount.entry: /dev/net dev/net none bind,create=dir
```

---

## Configured Networks

1. **192.168.0.0/24** - Local LAN (eth0)
2. **100.64.0.0/10** - Tailscale CGNAT range (all peers)

---

## Useful Commands

```bash
# Service management
systemctl status scanopy-server
systemctl status scanopy-daemon
systemctl restart scanopy-server
systemctl restart scanopy-daemon

# Logs
journalctl -u scanopy-server -f
journalctl -u scanopy-daemon -f

# Config
cat /opt/scanopy/.env
cat /root/.config/daemon/config.json
```

---

## Further Documentation

- [Scanopy GitHub](https://github.com/scanopy/scanopy)
