
**Date:** 2026-01-04  
**System:** Proxmox VE 9.1.2

---

## 📋 Overview

### Installed Services

| Service | LXC ID | IP Address | Tailscale IP | Port | Status |
|---------|--------|------------|--------------|------|--------|
| Vaultwarden | 102 | TBD | TBD | 8000 | ✅ Working |
| Scanopy | 104 | 192.168.0.YOUR_SCANOPY_IP | YOUR_TAILSCALE_IP | 60072 | ✅ Working |

---

## 🔐 Vaultwarden (Password Manager)

### Basic Information
- **Platform:** Alpine Linux LXC
- **Installation:** Proxmox Community Scripts
- **Version:** Latest stable

### Installation Command
```bash
bash -c "$(wget -qO - https://github.com/community-scripts/ProxmoxVE/raw/main/ct/alpine-vaultwarden.sh)"
```

### LXC Specifications
- **CPU:** 1 core
- **RAM:** 1GB
- **Disk:** 4GB
- **Network:** vmbr0, DHCP

### Configuration
- Config file: `/etc/vaultwarden/config.json` or `/opt/vaultwarden/.env`
- Web admin: `http://<IP>:8000/admin`

---

## 🗺️ Scanopy (Network Discovery & Mapping)

### Basic Information
- **Platform:** Debian 13 LXC (Unprivileged)
- **Installation:** Proxmox Community Scripts
- **Version:** 0.12.9

### Installation Command
```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/community-scripts/ProxmoxVE/main/ct/scanopy.sh)"
```

### LXC Specifications
- **Container ID:** 104
- **Hostname:** scanopy
- **CPU:** 2 cores
- **RAM:** 3GB (3072 MiB)
- **Disk:** 6GB
- **Network:** vmbr0, DHCP (192.168.0.YOUR_SCANOPY_IP)
- **Features:** nesting=1, keyctl=1

### Access
- **Local IP:** http://192.168.0.YOUR_SCANOPY_IP:60072
- **Tailscale IP:** http://YOUR_TAILSCALE_IP:60072

### Daemon Configuration
**Manual daemon setup:**
```bash
# The daemon is already configured and running
systemctl status scanopy-daemon
```

**Daemon details:**
- Name: local-daemon
- Mode: Push
- Version: 0.12.9
- Network: My Network (YOUR_NETWORK_UUID)

### Config Files
- **Server config:** `/opt/scanopy/.env`
- **Daemon config:** `/root/.config/daemon/config.json`
- **Server service:** `/etc/systemd/system/scanopy-server.service`
- **Daemon service:** `/etc/systemd/system/scanopy-daemon.service`

---

## 🔗 Tailscale Integration

### Network Architecture
- **Home network (Proxmox):** 192.168.0.0/24
- **Remote K3s cluster:** 192.168.2.0/24 (different location)
- **Tailscale peers:** Directly reachable devices (on 100.x.x.x IPs)

### LXC 104 (Scanopy) - Tailscale Setup

#### Installation
```bash
curl -fsSL https://tailscale.com/install.sh | sh
```

#### Proxmox LXC Config Modification
**File:** `/etc/pve/lxc/104.conf`

Added lines (TUN/TAP support):
```
lxc.cgroup2.devices.allow: c 10:200 rwm
lxc.mount.entry: /dev/net dev/net none bind,create=dir
```

#### Proxmox Host - Disable Subnet Advertise
**IMPORTANT:** The Proxmox host must NOT advertise the local subnet (192.168.0.0/24)

**In Proxmox shell:**
```bash
# Reset and allow SSH WITHOUT advertise
tailscale up --ssh --reset
```

**Why?**
- Avoids routing conflict in the Scanopy LXC
- Remote K3s devices are directly reachable as Tailscale peers (no advertise needed)

#### Scanopy LXC - Start Tailscale
```bash
# Accept routes ENABLED (in case there are advertised subnets later)
tailscale up --reset --accept-routes

# AND iptables rule for local network access
iptables -I ts-input 1 -i eth0 -j ACCEPT
```

**Why this configuration?**
- `--accept-routes`: Accepts any advertised subnets (e.g. if the K3s site advertises other subnets later)
- `iptables -I ts-input 1 -i eth0 -j ACCEPT`: Prevents the Tailscale firewall from blocking the local network (eth0 interface)

#### Persistent Configuration (systemd override)
**File:** `/etc/systemd/system/tailscaled.service.d/override.conf`
```ini
[Service]
ExecStartPost=/bin/sh -c 'sleep 5 && /usr/bin/tailscale up --accept-routes && /usr/sbin/iptables -I ts-input 1 -i eth0 -j ACCEPT'
```

**Activate:**
```bash
systemctl daemon-reload
```

### Tailscale Network Status
```bash
tailscale status
```

**Peers:**
- **pve** (YOUR_TAILSCALE_IP_PVE) - Proxmox host (home, 192.168.0.0/24)
- **nex-pc** (YOUR_TAILSCALE_IP_PC) - Windows desktop
- **orangepione** (YOUR_TAILSCALE_IP_ORANGEPI) - Orange Pi (K3s site, 192.168.2.0/24)
- **opt3050-i5** (YOUR_TAILSCALE_IP_OPT1) - K3s cluster node 1 (remote location)
- **opt3060-i3** (YOUR_TAILSCALE_IP_OPT2) - K3s cluster node 2 (remote location)
- **opt5060-i5** (YOUR_TAILSCALE_IP_OPT3) - K3s cluster node 3 (remote location)

**K3s Cluster Info:**
- Physical location: Remote (different location, not home)
- Local subnet: 192.168.2.0/24
- Tailscale access: Directly as peers (on 100.x.x.x IPs)
- Advertise: NOT needed (all important devices are direct Tailscale peers)

---

## 📡 Network Discovery

### Configured Networks (Subnets)

1. **192.168.0.0/24** (LAN - Local Network)
   - ✅ Fully mapped
   - Discovered devices: 14+
   - Type: Local (eth0 interface)

2. **MamaNet - 100.64.0.0/10** (Tailscale CGNAT Range)
   - Covers ALL Tailscale peers
   - Includes: K3s cluster (OptiPlexes), orangepione, pve, nex-pc etc.
   - Type: VPN (Tailscale)

3. **Internet** (0.0.0.0/0) - Public DNS, cloud services
   - Type: Internet

4. **Remote Network** (0.0.0.0/0) - Organizational container for remote hosts
   - Type: Remote

### Starting a Scan

#### From Web UI (Subnets menu):
1. **Subnets** menu
2. View the configured subnets
3. Click a subnet and start a scan

#### From Sessions menu:
1. **Sessions** menu → **Start Discovery**
2. **Select** which subnet to scan:
   - 192.168.0.0/24 - Local LAN
   - 100.64.0.0/10 - Tailscale network (K3s cluster + all peers)
   - Or both at once

### Scanning Tailscale Devices

**Scanopy automatically sees:**
- ✅ Tailscale interface (tailscale0)
- ✅ All peers (on 100.x.x.x IPs)
- ✅ K3s cluster nodes (opt3050-i5, opt3060-i3, opt5060-i5)
- ✅ orangepione

**Scanning:**
- The daemon automatically discovers Tailscale peers
- Port scanning and service discovery work through Tailscale
- Encryption: provided by Tailscale (WireGuard-based)

---

## 🔧 Troubleshooting

### Scanopy local IP not reachable

**Problem:** 192.168.0.YOUR_SCANOPY_IP:60072 not accessible from browser

**Checks:**
```bash
# Service status
systemctl status scanopy-server
systemctl status scanopy-daemon

# Port listening
ss -tulpn | grep 60072

# Check Tailscale iptables rule
iptables -L ts-input -n -v --line-numbers

# The first rule must be eth0 ACCEPT
# If missing:
iptables -I ts-input 1 -i eth0 -j ACCEPT
```

### Tailscale not working after restart

**Solution:**
```bash
# Check override file
cat /etc/systemd/system/tailscaled.service.d/override.conf

# If missing or wrong, recreate it:
mkdir -p /etc/systemd/system/tailscaled.service.d/
cat > /etc/systemd/system/tailscaled.service.d/override.conf << 'EOF'
[Service]
ExecStartPost=/bin/sh -c 'sleep 5 && /usr/bin/tailscale up --accept-routes && /usr/sbin/iptables -I ts-input 1 -i eth0 -j ACCEPT'
EOF

systemctl daemon-reload
systemctl restart tailscaled
```

### Proxmox host advertising subnet (conflict)

**Problem:** The Proxmox host is advertising 192.168.0.0/24 and this causes a conflict

**Check:**
```bash
# On Proxmox host
tailscale status | grep advertise

# In Scanopy LXC
ip route show table all | grep "192.168.0.0/24 dev tailscale0"
```

**Solution - on Proxmox host:**
```bash
# Disable advertise
tailscale up --ssh --reset
```

**Solution - in Scanopy LXC (if the above is not enough):**
```bash
# Delete the conflicting route
ip route del 192.168.0.0/24 dev tailscale0 table 52
```

### K3s cluster not reachable

**Problem:** OptiPlex nodes cannot be scanned

**Checks:**
```bash
# Tailscale peer status
tailscale status | grep opt

# Ping test to Tailscale IP
ping YOUR_TAILSCALE_IP_OPT1
ping YOUR_TAILSCALE_IP_OPT2
ping YOUR_TAILSCALE_IP_OPT3

# Tailscale routes
ip route show table 52 | grep "100\."
```

**Solution:**
```bash
# If the OptiPlexes are offline in Tailscale:
# SSH to the OptiPlexes and restart Tailscale
systemctl restart tailscaled

# Or on orangepione (if that is reachable)
```

### Daemon not visible in Web UI

**Solution:**
```bash
# Restart daemon
systemctl restart scanopy-daemon

# Check logs
journalctl -u scanopy-daemon -f

# Check server connection
curl http://127.0.0.1:60072
```

---

## 📝 Useful Commands

### Scanopy
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

### Tailscale
```bash
# Status
tailscale status

# Ping peer
tailscale ping <hostname-or-ip>

# Routes
ip route show table 52

# Restart with correct flags
tailscale down
tailscale up --accept-routes=false --netfilter-mode=off
```

### Network Debugging
```bash
# Port check
ss -tulpn | grep 60072

# Ping test
ping 192.168.0.YOUR_SCANOPY_IP

# HTTP test
curl -I http://192.168.0.YOUR_SCANOPY_IP:60072

# Packet capture
tcpdump -i eth0 -n host 192.168.0.YOUR_SCANOPY_IP

# Routing
ip route show
ip route show table all
ip rule show
```

---

## ⚠️ Important Notes

### Tailscale Routing Solution
**Final configuration:**
1. **Proxmox host:** Must NOT advertise the local subnet (192.168.0.0/24)
   - `tailscale up --ssh --reset`
2. **Scanopy LXC:** Accept routes + iptables fix
   - `tailscale up --accept-routes`
   - `iptables -I ts-input 1 -i eth0 -j ACCEPT`

**Why this solution works:**
- ✅ Avoids routing conflict (192.168.0.0/24 is not in the Tailscale routing table)
- ✅ Scanopy can see the local network (eth0 interface)
- ✅ Scanopy can see ALL Tailscale peers
- ✅ If an advertised subnet is added later (e.g. 192.168.2.0/24), it will be visible too

### K3s Cluster Access
- **Physical location:** Remote site (not home)
- **Local subnet:** 192.168.2.0/24
- **Tailscale access:** Directly as peers (no advertise needed)
- **Devices:** 3x OptiPlex + 1x orangepione

**Advertise is NOT needed because:**
- All important devices are direct Tailscale peers
- There are no other devices on 192.168.2.0/24 that need to be scanned

### Firewall & iptables
- Tailscale was blocking the local network by default (ts-input chain)
- **Solution:** `iptables -I ts-input 1 -i eth0 -j ACCEPT`
- This rule is permanent (systemd override)
- The LXC is reachable from all interfaces (local + Tailscale)

### rp_filter Setting
- No longer needed (resolved along with the routing conflict)
- Default setting: `rp_filter=2` (strict mode) - kept as-is

---

## 🚀 Next Steps

### Ready to use immediately:

1. **Network Scanning**
   - ✅ Local LAN (192.168.0.0/24) scanning
   - ✅ Tailscale network (100.64.0.0/10) scanning
   - ✅ K3s cluster discovery (OptiPlex nodes)

2. **Scheduled Scans**
   - Configurable from the Scanopy UI
   - Recommended: Daily scan on local LAN, weekly on Tailscale network

### Optional configurations:

1. **HTTPS Setup (Nginx Proxy Manager)**
   - Subdomain: scanopy.yourdomain.com
   - Forward to: 192.168.0.YOUR_SCANOPY_IP:60072
   - SSL certificate (Let's Encrypt)

2. **Vaultwarden HTTPS**
   - Subdomain: vault.yourdomain.com
   - Forward to: Vaultwarden LXC IP:8000
   - SSL certificate required (Vaultwarden requires HTTPS for client apps)

3. **MikroTik Router Upgrade**
   - VLAN segmentation (IoT, Guest, Management)
   - Advanced routing
   - Traffic monitoring and QoS
   - Firewall rules optimization

4. **K3s Cluster Monitoring**
   - Prometheus + Grafana installation
   - Node exporter on every OptiPlex
   - Kubernetes metrics collection
   - Scanopy integration with cluster services

5. **Backup Strategy**
   - Scanopy database (PostgreSQL) backup
   - Vaultwarden data backup
   - Automated backup to remote location via Tailscale

6. **Tailscale Exit Node** (optional)
   - If you want an exit node on the network
   - VPN access for mobile devices

### K3s Cluster Scan Fine-tuning:

**When the OptiPlexes are online:**
- Scanopy automatically discovers them (YOUR_TAILSCALE_IP_OPT1, YOUR_TAILSCALE_IP_OPT2, YOUR_TAILSCALE_IP_OPT3)
- Port scan and service discovery
- Kubernetes API endpoint discovery
- Container network mapping (if accessible)

---

## 🔍 Routing Problem Resolution - Detailed Explanation

### Origin of the problem

**Initial configuration:**
- Proxmox host was advertising the `192.168.0.0/24` subnet via Tailscale
- Scanopy LXC was started with the `--accept-routes` flag
- Result: In the routing table, `192.168.0.0/24` pointed to the `tailscale0` interface

**Consequence:**
```bash
# ip route show table 52
192.168.0.0/24 dev tailscale0 table 52  # WRONG!
```

This caused:
- Scanopy LXC tried to reach a local IP (e.g. 192.168.0.YOUR_SCANOPY_IP)
- The kernel sent the packet out via the `tailscale0` interface based on the routing table
- Tailscale tried to forward it through the Proxmox host
- BUT it was the LXC's own IP address, creating a loop
- **Result:** Timeout, no response

### Attempted solutions

**Attempt 1 - netfilter-mode=off:**
```bash
tailscale up --accept-routes=false --netfilter-mode=off
```
- ✅ Local IP worked
- ❌ Tailscale network was not fully functional (firewall off)
- ❌ Would not have seen advertised subnets

**Attempt 2 - Manual route deletion:**
```bash
ip route del 192.168.0.0/24 dev tailscale0 table 52
sysctl -w net.ipv4.conf.all.rp_filter=0
```
- ✅ Worked temporarily
- ❌ Would have needed to be re-applied after every restart

**Attempt 3 - PERMANENT SOLUTION - Source fix:**

**A. Proxmox host:**
```bash
tailscale up --ssh --reset  # Do NOT advertise
```

**B. Scanopy LXC:**
```bash
tailscale up --accept-routes  # Accept any advertised subnets
iptables -I ts-input 1 -i eth0 -j ACCEPT  # Local network access
```

**Why it works:**
- ✅ No `192.168.0.0/24` in the Tailscale routing table
- ✅ Local network reachable via the `eth0` interface
- ✅ Tailscale peers reachable via the `tailscale0` interface
- ✅ If another subnet is advertised later (e.g. 192.168.2.0/24), it will be visible
- ✅ Firewall properly configured (ts-input chain)

### Routing Tables BEFORE and AFTER

**BEFORE (WRONG):**
```bash
# Main table
default via 192.168.0.YOUR_ROUTER_IP dev eth0
192.168.0.0/24 dev eth0 proto kernel scope link src 192.168.0.YOUR_SCANOPY_IP

# Table 52 (Tailscale)
192.168.0.0/24 dev tailscale0  # ← CONFLICT!
YOUR_TAILSCALE_IP_OPT1 dev tailscale0
YOUR_TAILSCALE_IP_PVE dev tailscale0
```

**AFTER (CORRECT):**
```bash
# Main table
default via 192.168.0.YOUR_ROUTER_IP dev eth0
192.168.0.0/24 dev eth0 proto kernel scope link src 192.168.0.YOUR_SCANOPY_IP

# Table 52 (Tailscale)
# NO 192.168.0.0/24 ← CORRECT!
YOUR_TAILSCALE_IP_OPT1 dev tailscale0
YOUR_TAILSCALE_IP_PVE dev tailscale0
YOUR_TAILSCALE_IP_OPT2 dev tailscale0
```

### Lessons Learned

1. **Subnet advertise only when truly necessary**
   - If all important devices are direct Tailscale peers, it is not needed

2. **Routing priority matters**
   - The kernel always uses the most specific route
   - If there is a conflict, policy routing or route metric is needed

3. **Debugging firewall rules**
   - `iptables -L -n -v --line-numbers` for every chain
   - `tcpdump` for following packet flow

4. **Understanding Tailscale flags**
   - `--accept-routes`: Accepts advertised subnets
   - `--advertise-routes`: Advertises a subnet
   - `--netfilter-mode=off`: Disables the Tailscale firewall (not recommended in production)

---

## 📚 Further Documentation

- [Scanopy GitHub](https://github.com/scanopy/scanopy)
- [Vaultwarden Wiki](https://github.com/dani-garcia/vaultwarden/wiki)
- [Tailscale Docs](https://tailscale.com/kb/)
- [Proxmox Helper Scripts](https://community-scripts.github.io/ProxmoxVE/)

---

**Version:** 2.0  
**Last updated:** 2026-01-04 (Final routing fix)  
**Author:** Nex (Home Lab Setup Session)  

**Changes in v2.0:**
- ✅ Routing problem resolved (Proxmox advertise disabled)
- ✅ Scanopy accept-routes + iptables fix
- ✅ K3s cluster remote location documented
- ✅ Subnet configuration (192.168.0.0/24 + 100.64.0.0/10)
- ✅ Detailed troubleshooting and routing explanation
