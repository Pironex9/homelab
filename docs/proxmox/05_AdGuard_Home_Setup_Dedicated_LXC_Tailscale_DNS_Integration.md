
**Date:** 2025-12-26  
**System:** Proxmox VE 9.1.2  
**Goal:** AdGuard Home DNS server installation with Quad9 DoH/DoT upstream and Tailscale MagicDNS integration

---

## 📋 Table of Contents

1. [System overview](#system-overview)
2. [Why a dedicated LXC?](#why-a-dedicated-lxc)
3. [Avoiding port conflicts](#why-a-dedicated-lxc)
4. [Creating the LXC](#creating-the-lxc)
5. [Installing AdGuard Home](#installing-adguard-home)
6. [AdGuard configuration](#adguard-configuration)
7. [Quad9 DoH/DoT setup](#quad9-dohdot-setup)
8. [Setting DNS on network devices](#setting-dns-on-network-devices)
9. [Tailscale DNS integration](#tailscale-dns-integration)
10. [Testing and verification](#testing-and-verification)
11. [Troubleshooting](#troubleshooting)

---

## 🖥️ System Overview

### **Current infrastructure:**

| ID | Type | Name | IP | Services |
|----|------|------|----|----------|
| **100** | LXC | docker-host | 192.168.0.110 | Nginx Proxy Manager, Jellyfin, *arr stack, qBittorrent |
| **101** | VM | homeassistant | 192.168.0.202 | Home Assistant OS, Zigbee2MQTT, Mosquitto |
| **102** | LXC | **adguard-home** | **192.168.0.111** | **AdGuard Home DNS** |

### **Network:**

```
Router: 192.168.0.1
Proxmox Host: 192.168.0.109
AdGuard DNS: 192.168.0.111 ← NEW!
```

---

## 🎯 Why a Dedicated LXC?

### **Problem identification:**

**Port conflicts in Docker (LXC 100):**

| Service | Ports | Conflict |
|---------|-------|----------|
| **AdGuard Home** | 53 (DNS), 80 (WebUI), 443 (DoH/DoT) | ⚠️ |
| **Nginx Proxy Manager** | 80 (HTTP), 443 (HTTPS), 81 (WebUI) | ⚠️ |
| **Conflict:** | **80, 443** | ❌❌ |

**If AdGuard were in Docker:**
- ❌ Nginx could not listen on port 80/443
- ❌ Reverse proxy would NOT work
- ❌ SSL termination would NOT work

---

### **SOLUTION: Dedicated LXC!**

**Advantages:**

✅ **Port isolation** - No conflict with Nginx  
✅ **Static IP** - Easy DHCP configuration (192.168.0.111)  
✅ **Network accessibility** - All devices (physical machines, Docker, VM) can use it  
✅ **Independent** - LXC stops/restarts → does not affect Docker or HA  
✅ **Easy backup** - Proxmox vzdump  
✅ **Lightweight** - LXC has no VM overhead (512MB RAM is enough!)  
✅ **Boot order** - Starts first (other services can use DNS)  

---

## 🏗️ Architecture

### **Full DNS chain:**

```
┌─────────────────────────────────────────────────────┐
│ Router (192.168.0.1)                                 │
│ DHCP DNS server: 192.168.0.111 (AdGuard)            │
└─────────────────────────────────────────────────────┘
                        ↓
        ┌───────────────┼───────────────┐
        ↓               ↓               ↓
┌───────────────┐ ┌───────────────┐ ┌───────────────┐
│ LXC 102       │ │ LXC 100       │ │ VM 101        │
│ AdGuard Home  │ │ Docker Stack  │ │ Home Assistant│
│ 192.168.0.111 │ │ 192.168.0.110 │ │ 192.168.0.202 │
│               │ │               │ │               │
│ Port 53 (DNS) │ │ Nginx (80/443)│ │ HA + Z2M      │
│ Port 80 (UI)  │ │ Jellyfin, *arr│ │               │
│               │ │ DNS→111 ✅    │ │ DNS→111 ✅    │
└───────────────┘ └───────────────┘ └───────────────┘
        ↓
    Upstream DNS
        ↓
┌───────────────┐
│ Quad9 DoH/DoT │
│ dns.quad9.net │
│ 🔒 Encrypted  │
│ 🛡️ Malware    │
└───────────────┘
```

---

## 📦 Creating the LXC

### **Proxmox WebUI:**

**Create CT:**

```
General:
  CT ID: 102
  Hostname: adguard-home
  Password: [secure password]

Template:
  Storage: local
  Template: Debian 12

Disks:
  Storage: local-lvm
  Disk size: 8GB
  
  After usage:
    OS + AdGuard: ~1.5-2GB
    Free: ~6GB ✅
    Thin provisioning: Only ~2GB physical

CPU:
  Cores: 1
  
  Sufficient because:
    DNS queries are fast
    AdGuard is lightweight
    No heavy processing

Memory:
  Memory: 512MB
  Swap: 512MB
  
  Sufficient because:
    AdGuard ~100-200MB RAM
    Query cache is minimal
    No heavy load

Network:
  Bridge: vmbr0
  Static IP: 192.168.0.111/24
  Gateway: 192.168.0.1
  DNS: 1.1.1.1 (temporary, later will use itself)

DNS:
  DNS servers: 1.1.1.1

Options:
  Start at boot: ✅ ON
  Start order: 1 (starts first!)
  Start delay: 10 sec (so DNS is ready before other LXC/VMs start)
```

**Confirm → Create**

---

## 📥 Installing AdGuard Home

### **Open LXC Console:**

**Proxmox WebUI:**
1. **102 (adguard-home)** → **Console**
2. **Start** LXC
3. **Login:** `root` + password

---

### **Installation:**

```bash
# System update
apt update && apt upgrade -y

# Install curl
apt install curl wget htop nano -y

# AdGuard Home official install script
curl -s -S -L https://raw.githubusercontent.com/AdguardTeam/AdGuardHome/master/scripts/install.sh | sh -s -- -v

# Check service
systemctl status AdGuardHome
# ● AdGuardHome.service - AdGuard Home
#    Active: active (running) ✅

# Port check
ss -tulpn | grep -E '53|3000'
# tcp LISTEN 0.0.0.0:53    ✅ DNS
# tcp LISTEN 0.0.0.0:3000  ✅ WebUI

# IP address
ip addr show eth0 | grep inet
# inet 192.168.0.111/24 ✅
```

---

## 🌐 AdGuard Configuration

### **Initial Setup Wizard:**

**WebUI:** `http://192.168.0.111:3000`

**Steps:**

1. **Welcome** → Next

2. **Admin Web Interface:**
   - **All interfaces** ✅
   - **Port:** `80` (change from 3000!)
     - WHY? Port 80 is more convenient
     - NO conflict! Nginx is in LXC 100!
   - Next

3. **DNS Server:**
   - **All interfaces** ✅
   - **Port:** `53` ✅
   - Next

4. **Authentication:**
   - **Username:** `admin`
   - **Password:** [secure password]
   - Next

5. **Complete** → Open Dashboard

**NEW URL:** `http://192.168.0.111` (no more :3000!)

---

## 🔐 Quad9 DoH/DoT Setup

### **Why Quad9?**

**Advantages:**

✅ **Privacy-focused** - Does not log IP addresses  
✅ **Security** - Blocks malware/phishing domains (20+ threat intel)  
✅ **GDPR compliant** - Headquartered in Switzerland  
✅ **Non-profit** - No ads/tracking  
✅ **DoH/DoT support** - Encrypted DNS  

**Quad9 vs Cloudflare vs Google:**

| Provider | Latency | Privacy | Security | Headquarters |
|----------|---------|---------|----------|--------------|
| **Quad9** | ~15-20ms | ✅✅✅ | ✅✅✅ Malware | 🇨🇭 Switzerland |
| **Cloudflare** | ~10-15ms | ✅✅ | ✅ | 🇺🇸 USA |
| **Google** | ~10-15ms | ⚠️ Logs | ✅ | 🇺🇸 USA |

---

### **Setting upstream DNS:**

**AdGuard WebUI → Settings → DNS settings:**

**Upstream DNS servers:**

```
https://dns.quad9.net/dns-query
https://dns11.quad9.net/dns-query
tls://dns.quad9.net
```

**Explanation:**
- **DoH (DNS over HTTPS):** Port 443, full encryption
- **DoT (DNS over TLS):** Port 853, fast encryption
- **dns11:** ECS support (geo-location hint, faster CDN)

**Bootstrap DNS servers:**

```
9.9.9.9
149.112.112.112
1.1.1.1
2620:fe::fe
```

**WHY DO WE NEED BOOTSTRAP?**

Bootstrap DNS resolves the `dns.quad9.net` domain name via plain DNS so the DoH/DoT connection can be established!

**Process:**
```
1. AdGuard starts → needs DoH → what's the IP of dns.quad9.net?
2. Bootstrap DNS (9.9.9.9) → dns.quad9.net = 9.9.9.9 ✅
3. DoH connection: https://dns.quad9.net/dns-query ✅
```

---

**Private reverse DNS servers:**

```
192.168.0.0/16
```

(Local network reverse DNS)

---

**DNS server configuration:**

✅ **Enable DNSSEC** (DNS security)  
✅ **Enable EDO** (Extended DNS Optimizations)  
✅ **Enable parallel requests** (faster)  
⚠️ **Disable IPv6** (if no IPv6 network)  

**Apply**

---

**Test upstreams:**

**Click "Test upstreams" button**

**Result:**
```
✅ https://dns.quad9.net/dns-query - OK (15 ms)
✅ https://dns11.quad9.net/dns-query - OK (18 ms)
✅ tls://dns.quad9.net - OK (12 ms)
```

**All green? ✅ WORKING!**

---

### **Adding blocklists:**

**Filters → DNS blocklists:**

**Default:**
- ✅ AdGuard DNS filter (~450k rules)

**To add:**

**OISD Basic:**
```
Name: OISD Basic
URL: https://small.oisd.nl/
```

**Dan Pollock's List:**
```
Name: Dan Pollock
URL: https://someonewhocares.org/hosts/zero/hosts
```

**AdAway:**
```
Name: AdAway
URL: https://adaway.org/hosts.txt
```

**Apply → Update filters now**

**Total:** ~500,000-600,000 rules ✅

---

### **Extra settings:**

**Settings → General settings:**

**Filtering:**
- ✅ Enable Safe Browsing
- ⚠️ Enable Parental Control (if you have children)

**Query logs:**
- **Retention:** 7 days
- ⚠️ Anonymize client IP (if maximum privacy is needed)

**Statistics:**
- **Retention:** 90 days

**Apply**

---

## 🌐 Setting DNS on Network Devices

### **1. Router DHCP DNS (MOST IMPORTANT!):**

**Router admin panel (192.168.0.1):**

**DHCP Server / LAN settings:**

**BEFORE:**
```
Primary DNS: YOUR_ISP_DNS1 (ISP - E-MAX)
Secondary DNS: YOUR_ISP_DNS2 (ISP - E-MAX)
```

**AFTER:**
```
Primary DNS: 192.168.0.111 (AdGuard) ✅
Secondary DNS: 1.1.1.1 (Cloudflare fallback)
```

**Save → DHCP Server Restart**

**Result:**
- All new DHCP clients → AdGuard DNS
- Existing machines → DHCP renew required!

---

### **2. Docker containers (LXC 100):**

```bash
# Enter LXC 100
pct enter 100

# Docker daemon config
nano /etc/docker/daemon.json
```

**File contents:**
```json
{
  "dns": ["192.168.0.111", "1.1.1.1"],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

**Docker restart:**
```bash
systemctl restart docker

# Verify
docker run --rm alpine nslookup google.com
# Server: 192.168.0.111 ✅
```

---

### **3. Home Assistant (VM 101):**

**Automatic (DHCP):**
- HA OS automatically uses the network DNS
- Router DHCP → 192.168.0.111 ✅

**Manual (if static IP):**

**HA Terminal & SSH:**
```bash
ha network update eth0 --ipv4-nameserver 192.168.0.111 --ipv4-nameserver 1.1.1.1
```

**OR WebUI:**
- Settings → System → Network
- DNS servers: `192.168.0.111`, `1.1.1.1`

---

### **4. Windows machines:**

**Automatic (DHCP):**
```cmd
ipconfig /release
ipconfig /renew
```

**Manual (static IP):**
1. Network Adapter Properties
2. IPv4 Properties
3. **Preferred DNS:** `192.168.0.111`
4. **Alternate DNS:** `1.1.1.1`
5. OK

---

### **5. LXC boot order (CRITICAL!):**

**PROBLEM:** Proxmox boots → AdGuard not yet up → DNS fails!

**SOLUTION:** Boot order + delay

```bash
# Proxmox host
pct set 102 -onboot 1 -startup order=1,up=10
pct set 100 -startup order=2,up=5
pct set 101 -startup order=3,up=5
```

**Result:**
```
1. Proxmox boot
2. LXC 102 (AdGuard) START → 10 sec wait
3. AdGuard DNS ready ✅
4. LXC 100 (Docker) START → uses AdGuard ✅
5. VM 101 (HA) START → uses AdGuard ✅
```

---

## 🔗 Tailscale DNS Integration

### **Problem identification:**

**Proxmox host DNS:**

```bash
cat /etc/resolv.conf

# resolv.conf(5) file generated by tailscale
# DO NOT EDIT THIS FILE BY HAND
nameserver 100.100.100.100  ← Tailscale MagicDNS
search YOUR_TAILSCALE_NET.ts.net homelab.local
```

**Tailscale automatically overrides DNS!**

**100.100.100.100** = Tailscale MagicDNS (split DNS, hostname resolution)

---

### **SOLUTION: Tailscale Global Nameservers!**

**Tailscale Admin Console:**

```
https://login.tailscale.com/admin/dns
```

**Configuration:**

**Global nameservers:**
1. **Add nameserver:** `192.168.0.111` (AdGuard)
2. **Add nameserver:** `1.1.1.1` (fallback)
3. **Save**

**Result:**
```
Proxmox → Tailscale MagicDNS (100.100.100.100)
         → Upstream: AdGuard (192.168.0.111) ✅
                    → Upstream: Quad9 DoH ✅
```

**BEST OF BOTH WORLDS:**
- ✅ Tailscale hostnames work (`*.YOUR_TAILSCALE_NET.ts.net`)
- ✅ AdGuard blocking works
- ✅ Quad9 encryption works

---

### **Do NOT modify resolv.conf!**

**⚠️ IMPORTANT:**

```bash
# DO NOT EDIT THIS:
/etc/resolv.conf

# Tailscale auto-generates it!
# If you modify it → it will be overwritten!
```

**LEAVE IT AS:**
```
nameserver 100.100.100.100
```

**Set upstream in:** Tailscale Admin Console! ✅

---

## 🧪 Testing and Verification

### **1. Does DNS work?**

**Windows/Linux:**
```bash
nslookup google.com

# Expected result:
Server:  adguard-home
Address: 192.168.0.111  ✅

Name:    google.com
Address: 142.250.185.46
```

---

### **2. Does it block?**

**Test ad domain:**
```bash
nslookup doubleclick.net

# Expected result:
Server:  adguard-home
Address: 192.168.0.111

Name:    doubleclick.net
Address: 0.0.0.0  ← BLOCKED! ✅
```

**In browser:**
```
https://ads-blocker.com/testing/
```

**Result:** Ads blocked! ✅

---

### **3. AdGuard Dashboard:**

**http://192.168.0.111**

**Query Log:**
- DNS requests visible
- Blocked: red ⛔
- Allowed: green ✅

**Dashboard stats:**
- **Queries (24h):** increasing
- **Blocked by filters:** ~20-40% (normal)
- **Top clients:** list of devices

**Top clients check:**
```
192.168.0.109 (Proxmox host) ✅
192.168.0.110 (Docker LXC) ✅
192.168.0.202 (HA OS VM) ✅
192.168.0.XXX (Windows/Phone) ✅
```

---

### **4. DNS Leak Test:**

**In browser:**
```
https://www.dnsleaktest.com/
```

**Extended test**

**CORRECT result:**
```
✅ Quad9 DNS - 9.9.9.9 - Switzerland 🇨🇭
✅ Quad9 DNS - 149.112.112.112 - Switzerland 🇨🇭
```

**INCORRECT result (ISP visible):**
- ⚠️ AdGuard upstream not set to Quad9
- ⚠️ Browser using its own DoH (Chrome/Firefox setting)
- ⚠️ Router DHCP DNS not yet updated

---

### **5. Does DoH/DoT work?**

**LXC Console:**
```bash
pct enter 102

# Port 53 (plain DNS) → NOT in use!
tcpdump -i eth0 port 53 -n
# (No traffic, because DoH/DoT uses 443/853!)

# Port 443 (DoH) → HAS traffic!
tcpdump -i eth0 port 443 -n
# (HTTPS traffic to Quad9 is visible!)
```

✅ **Encrypted DNS working!** 🔒

---

## ❗ Troubleshooting

### **Problem 1: DNS not working**

**Symptom:** `nslookup google.com` → timeout

**Check:**
```bash
# Is AdGuard running?
pct enter 102
systemctl status AdGuardHome
# Active (running)? ✅

# Is port 53 listening?
ss -tulpn | grep :53
# 0.0.0.0:53 LISTEN ✅

# Firewall?
iptables -L -n | grep DROP
# No DROP rule? ✅
```

**Solution:**
```bash
systemctl restart AdGuardHome
```

---

### **Problem 2: Upstream DNS fail**

**Symptom:** AdGuard → Settings → Test upstreams → red X

**Check:**
```bash
# DNS test from LXC
dig @9.9.9.9 google.com
# Working? ✅

# Resolve Quad9 hostname
dig dns.quad9.net
# IP: 9.9.9.9 ✅

# HTTPS test
curl -I https://dns.quad9.net/dns-query
# HTTP/2 200 ✅
```

**Solution:**
- Check bootstrap DNS (is 9.9.9.9 configured?)
- Does internet connection work?
- Is firewall port 443/853 open?

---

### **Problem 3: Browser bypasses AdGuard**

**Symptom:** DNS leak test → Cloudflare visible, NOT Quad9

**CAUSE:** Browser built-in DoH!

**Chrome/Edge:**
- Settings → Privacy → Security
- **Use secure DNS** → **OFF** ✅

**Firefox:**
- Settings → Privacy & Security
- **DNS over HTTPS** → **OFF** ✅

---

### **Problem 4: AdGuard LXC stops during boot**

**Symptom:** DNS not working after Proxmox boot

**CAUSE:** Wrong boot order or no delay

**Solution:**
```bash
pct set 102 -onboot 1 -startup order=1,up=10
pct set 100 -startup order=2,up=5
pct set 101 -startup order=3,up=5
```

**AND fallback DNS everywhere:**
```
DNS: 192.168.0.111, 1.1.1.1
```

---

### **Problem 5: Tailscale overrides DNS**

**Symptom:** `cat /etc/resolv.conf` → 100.100.100.100, cannot be modified

**CAUSE:** Tailscale auto-generates it

**SOLUTION: Do NOT modify resolv.conf!**

**Instead:**
- Tailscale Admin Console → DNS → Global nameservers
- Add: 192.168.0.111

---

## 📊 Final Configuration Summary

### **LXC 102 - AdGuard Home:**

```
IP: 192.168.0.111
Port 53: DNS server
Port 80: WebUI
Upstream DNS: Quad9 DoH/DoT
Bootstrap DNS: 9.9.9.9, 149.112.112.112, 1.1.1.1
Blocklists: ~500,000 rules
```

---

### **Proxmox Host:**

```
/etc/resolv.conf: 100.100.100.100 (Tailscale MagicDNS)
  → Upstream: 192.168.0.111 (AdGuard - Tailscale Admin Console)
    → Upstream: Quad9 DoH
```

---

### **LXC 100 - Docker:**

```
/etc/docker/daemon.json:
{
  "dns": ["192.168.0.111", "1.1.1.1"]
}

Docker containers → AdGuard → Quad9 DoH ✅
```

---

### **VM 101 - HA OS:**

```
DHCP DNS: 192.168.0.111 (automatic)
OR
Manual DNS: 192.168.0.111, 1.1.1.1

HA → AdGuard → Quad9 DoH ✅
```

---

### **Router DHCP:**

```
Primary DNS: 192.168.0.111
Secondary DNS: 1.1.1.1

Physical machines → AdGuard → Quad9 DoH ✅
```

---

### **Tailscale:**

```
Admin Console → DNS → Global nameservers:
  - 192.168.0.111 (AdGuard)
  - 1.1.1.1 (Cloudflare fallback)

MagicDNS: 100.100.100.100
Search domains: YOUR_TAILSCALE_NET.ts.net, homelab.local
```

---

## 🛡️ Protection Layers

**Full DNS Security Stack:**

```
1. 🔒 Quad9 DoH/DoT
   - Encrypted DNS (ISP cannot see)
   - Malware/phishing blocking (20+ threat intel)
   - Privacy (no logs, Switzerland)

2. 🚫 AdGuard Home
   - Ad blocking (~500k rules)
   - Local DNS cache (faster)
   - Query logging (troubleshooting)
   - Custom blocklists/allowlists

3. 📊 Tailscale MagicDNS
   - Private hostname resolution
   - Split DNS (Tailscale network + public)
   - Secure mesh networking

4. 🏠 Local network
   - Single DNS server (192.168.0.111)
   - Fallback DNS (1.1.1.1)
   - Centralized management
```

---

## 📈 Performance

**Expected metrics:**

```
DNS query latency:
  - Local cache hit: ~1-2ms ⚡
  - AdGuard cache miss: ~15-20ms (Quad9)
  - Blocked domain: <1ms (instant) ⚡

Blocking effectiveness:
  - Ads: ~30-40%
  - Malware/phishing: automatic
  - Privacy tracking: ~20-30%

Resource usage (LXC 102):
  - CPU: <5% (idle), ~10-20% (active)
  - RAM: ~150-250MB / 512MB
  - Disk: ~2GB / 8GB
```

---

## 🔧 Useful Commands

### **AdGuard management:**

```bash
# Service control
systemctl status AdGuardHome
systemctl restart AdGuardHome
systemctl stop AdGuardHome

# Config file
nano /opt/AdGuardHome/AdGuardHome.yaml

# Logs
journalctl -u AdGuardHome -f
```

---

### **DNS testing:**

```bash
# Basic query
nslookup google.com
dig google.com

# Specific DNS server
nslookup google.com 192.168.0.111
dig @192.168.0.111 google.com

# DNS trace
dig +trace google.com

# Reverse DNS
nslookup 192.168.0.111
```

---

### **Network debugging:**

```bash
# Port check
ss -tulpn | grep -E '53|80|443'

# DNS traffic capture
tcpdump -i eth0 port 53 -vv
tcpdump -i eth0 port 443 -vv

# Connection test
telnet 192.168.0.111 53
curl -I http://192.168.0.111
```

---

### **LXC management:**

```bash
# Start/Stop
pct start 102
pct stop 102
pct reboot 102

# Console
pct enter 102

# Status
pct status 102

# Resource usage
pct exec 102 -- htop
```

---

## 🎯 Best Practices

### **1. Always have a fallback DNS!**

```
On EVERY device:
Primary DNS: 192.168.0.111 (AdGuard)
Secondary DNS: 1.1.1.1 (Cloudflare fallback)

Why?
- AdGuard stops → fallback takes over ✅
- During boot AdGuard not yet up → fallback works ✅
- Emergency → no DNS blackout ✅
```

---

### **2. Correct boot order configuration:**

```bash
LXC 102 (AdGuard): order=1, up=10
LXC 100 (Docker): order=2, up=5
VM 101 (HA): order=3, up=5

Proxmox boot:
1. AdGuard starts FIRST → 10 sec delay
2. DNS ready ✅
3. Docker/HA start → DNS works ✅
```

---

### **3. Regular maintenance:**

```
Weekly:
- AdGuard Dashboard stats review
- Blocklist update (auto, verify)
- Query Log review (suspicious activity?)

Monthly:
- AdGuard update check
- LXC backup (Proxmox vzdump)
- Disk usage check (df -h)

Semi-annually:
- Blocklist cleanup (redundant lists?)
- Custom rules review
- Performance tuning
```

---

### **4. Monitoring:**

**Watch AdGuard Dashboard:**
```
http://192.168.0.111

Metrics:
- Queries/day: increasing?
- Blocked %: ~30-40% is normal
- Top blocked domains: ad trackers?
- Top clients: all devices visible?
```

**Proxmox monitoring:**
```
Proxmox WebUI → LXC 102:
- CPU usage: <20%
- RAM usage: <50% (256MB / 512MB)
- Disk usage: <30% (2GB / 8GB)
```

---

### **5. Backup strategy:**

**Proxmox backup (LXC):**
```bash
# Manual backup
vzdump 102 --storage backup-hdd --mode snapshot --compress zstd

# Automatic (Datacenter → Backup)
Schedule: daily 02:00
Storage: backup-hdd
Retention: Keep last 7
```

**AdGuard config export:**
```
AdGuard WebUI → Settings → General settings
→ Export settings
→ Download AdGuardHome.yaml
```

---

## 🎉 Summary

**What we achieved:**

✅ **Dedicated AdGuard Home LXC** (192.168.0.111)  
✅ **Port conflicts resolved** (Nginx + AdGuard working together)  
✅ **Quad9 DoH/DoT upstream** (encrypted DNS)  
✅ **~500k blocklist rules** (ad + malware blocking)  
✅ **Tailscale DNS integration** (MagicDNS + AdGuard)  
✅ **Fallback DNS on every device** (1.1.1.1)  
✅ **Boot order optimized** (AdGuard starts first)  
✅ **Full network protection** (all devices use it)  

**Protection levels:**

1. 🔒 **Privacy:** Quad9 DoH (ISP cannot see DNS)
2. 🛡️ **Security:** Quad9 malware blocking + AdGuard filtering
3. 🚫 **Ad-blocking:** ~500k rules, ~30-40% blocked
4. 📊 **Visibility:** Query logs, statistics, dashboard
5. ⚡ **Performance:** Local cache, <20ms latency

**FULL DNS SECURITY STACK WORKING!** 🏆✨

---

**Created:** 2025-12-26  
**System:** Proxmox VE 9.1.2 / AdGuard Home v0.107+ / Tailscale  
**Version:** 1.0
