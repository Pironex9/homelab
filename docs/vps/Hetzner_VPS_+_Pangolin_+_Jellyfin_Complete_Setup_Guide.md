
**Date:** 2026-01-11  
**Purpose:** Remote Jellyfin streaming via Pangolin reverse proxy  
**Home Lab:** Proxmox (192.168.0.109), Jellyfin LXC (192.168.0.110:8096)  
**VPS:** Hetzner CX23, Ubuntu 24.04 LTS  
**Domain:** your-domain.com (Cloudflare DNS)

---

## Table of Contents

1. [VPS Provisioning](#1-vps-provisioning)
2. [Initial VPS Setup](#2-initial-vps-setup)
3. [Docker Installation](#3-docker-installation)
4. [Cloudflare DNS Configuration](#4-cloudflare-dns-configuration)
5. [Pangolin Installation](#5-pangolin-installation)
6. [Home Lab Newt Client Setup](#6-home-lab-newt-client-setup)
7. [Jellyfin Resource Configuration](#7-jellyfin-resource-configuration)
8. [VPS Security Hardening](#8-vps-security-hardening)
9. [Remaining Security Steps](#9-remaining-security-steps)
10. [Architecture Overview](#10-architecture-overview)
11. [Costs](#11-costs)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. VPS Provisioning

### Hetzner Cloud Console

**VPS Specifications:**
- **Provider:** Hetzner Cloud
- **Plan:** CX23 (2 vCPU, 4GB RAM, 40GB SSD)
- **Location:** Falkenstein/Nuremberg (FSN1)
- **Image:** Ubuntu 24.04 LTS
- **IP Address:** YOUR_VPS_IP
- **Hostname:** homelab-proxy

**Setup:**
1. Login to Hetzner Cloud Console
2. Create new project (or use existing)
3. Add Server → CX23
4. Location: Falkenstein (FSN1)
5. Image: Ubuntu 24.04
6. SSH Key: Add your public SSH key
7. Hostname: homelab-proxy
8. Create & Start

**SSH Access:**
```bash
ssh root@YOUR_VPS_IP
```

---

## 2. Initial VPS Setup

### System Update

```bash
# Update package list and upgrade
apt update && apt upgrade -y

# Reboot if kernel updated
reboot
```

### Firewall Configuration (UFW)

```bash
# Enable UFW
ufw --force enable

# Allow required ports
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
ufw allow 51820/udp comment 'WireGuard'
ufw allow 21820/udp comment 'Gerbil clients'

# Verify rules
ufw status verbose
```

**Expected Output:**
```
To                         Action      From
--                         ------      ----
22/tcp                     ALLOW IN    Anywhere                   # SSH
80/tcp                     ALLOW IN    Anywhere                   # HTTP
443/tcp                    ALLOW IN    Anywhere                   # HTTPS
51820/udp                  ALLOW IN    Anywhere                   # WireGuard
21820/udp                  ALLOW IN    Anywhere                   # Gerbil clients
```

### Swap Configuration

```bash
# Create 2GB swap file
fallocate -l 2G /swapfile
chmod 600 /swapfile
mkswap /swapfile
swapon /swapfile

# Make permanent
echo '/swapfile none swap sw 0 0' >> /etc/fstab

# Verify
free -h
```

### Automatic Security Updates

```bash
# Install unattended-upgrades
apt install unattended-upgrades -y

# Configure
dpkg-reconfigure -plow unattended-upgrades

# Enable service
systemctl enable unattended-upgrades
systemctl start unattended-upgrades

# Verify
systemctl status unattended-upgrades
```

---

## 3. Docker Installation

### Install Docker

```bash
# Install Docker using official script
curl -fsSL https://get.docker.com | sh

# Enable and start Docker
systemctl enable docker
systemctl start docker

# Verify installation
docker --version
docker compose version
```

**Expected Versions:**
- Docker: 29.1.4+
- Docker Compose: v5.0.1+

---

## 4. Cloudflare DNS Configuration

### DNS Records Setup

**Login to Cloudflare Dashboard:**
```
https://dash.cloudflare.com/
```

**Add DNS Records:**

#### Record 1: Pangolin Dashboard
```
Type: A
Name: pangolin
IPv4 address: YOUR_VPS_IP
Proxy status: DNS only (Gray cloud) ← CRITICAL!
TTL: Auto
```

#### Record 2: Jellyfin Service
```
Type: A
Name: jellyfin
IPv4 address: YOUR_VPS_IP
Proxy status: DNS only (Gray cloud) ← CRITICAL!
TTL: Auto
```

**⚠️ IMPORTANT: Proxy Status MUST be "DNS only" (gray cloud)**
- Orange cloud (Proxied) will break Let's Encrypt SSL
- Orange cloud violates Cloudflare ToS for video streaming

### Verify DNS Propagation

**VPS:**
```bash
nslookup pangolin.your-domain.com
nslookup jellyfin.your-domain.com
```

**Expected:**
```
Address: YOUR_VPS_IP
```

**If DNS not propagating to local network:**
- Flush local DNS cache (router/PC/AdGuard Home)
- Wait 2-5 minutes for propagation

---

## 5. Pangolin Installation

### Official Installer

**Download and Run Installer:**

```bash
# Create directory
mkdir -p /opt/pangolin
cd /opt/pangolin

# Download installer
curl -fsSL https://static.pangolin.net/get-installer.sh | bash

# Run installer
./installer
```

### Installation Prompts

**Answer the following prompts:**

```
Base Domain: your-domain.com
Dashboard Domain: pangolin.your-domain.com (default)
Email Address: your@email.com
Tunneling Support (Gerbil): yes
SMTP Configuration: no
IPv6 Support: yes
GeoLite2 Database: yes
CrowdSec Integration: no
```

**Installation will:**
- Deploy 3 Docker containers: `pangolin`, `gerbil`, `traefik`
- Generate configuration in `/opt/pangolin/config/`
- Request Let's Encrypt SSL certificates
- Start all services

### Verify Installation

```bash
# Check running containers
docker ps

# Expected output:
# - fosrl/pangolin:latest (ports 3000-3002)
# - fosrl/gerbil:latest (UDP 51820, 21820, TCP 80, 443)
# - traefik:v3.6 (reverse proxy)

# Check Traefik logs
docker logs traefik

# Wait for SSL certificate
# Expected: "Certificate obtained for pangolin.your-domain.com"
```

### Access Pangolin Dashboard

**Wait 2-5 minutes for DNS + SSL, then:**

```
URL: https://pangolin.your-domain.com
```

**Initial Setup:**
1. Navigate to: https://pangolin.your-domain.com/auth/initial-setup
2. Setup Token: (displayed in installer output, expires after use)
3. Admin Email: your@email.com
4. Admin Password: [set secure password]
5. Complete setup

### Create Organization

**Pangolin Dashboard:**
```
Organizations → Create Organization
Name: Homelab
→ Save
```

### Create Site (WireGuard Tunnel)

**Pangolin Dashboard:**
```
Sites → Create Site

Site Type: Newt Site (Recommended)
Site Name: Home Network
Site Address: 100.90.128.0/24 (auto-generated)
Accept Client Connections: Enabled

→ Create Site
```

**Note the following for Newt client:**
- Site ID: `YOUR_PANGOLIN_SITE_ID`
- Site Secret: `YOUR_PANGOLIN_SITE_SECRET`
- Endpoint: `https://pangolin.your-domain.com`
- Identifier: `lasting-forficula-smymensis`

---

## 6. Home Lab Newt Client Setup

### Installation (Proxmox Host)

**SSH to Proxmox:**
```bash
ssh root@192.168.0.109
```

**Install Newt Client:**
```bash
# Download and install
curl -fsSL https://static.pangolin.net/get-newt.sh | bash

# Verify installation
which newt
newt --version
```

### Test Connection (Foreground)

```bash
newt --id YOUR_PANGOLIN_SITE_ID \
     --secret YOUR_PANGOLIN_SITE_SECRET \
     --endpoint https://pangolin.your-domain.com
```

**Expected Output:**
```
Newt version 1.8.1
Websocket connected
Tunnel connection established successfully!
Ready to accept connections from clients!
```

**Press Ctrl+C to stop**

### Create Systemd Service

**Service File:**
```bash
nano /etc/systemd/system/newt.service
```

**Contents:**
```ini
[Unit]
Description=Newt Client - Pangolin Tunnel
After=network-online.target

[Service]
Type=simple
User=root
ExecStart=/usr/local/bin/newt --id YOUR_PANGOLIN_SITE_ID --secret YOUR_PANGOLIN_SITE_SECRET --endpoint https://pangolin.your-domain.com
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

**Enable and Start Service:**
```bash
# Reload systemd
systemctl daemon-reload

# Enable on boot
systemctl enable newt.service

# Start service
systemctl start newt.service

# Check status
systemctl status newt.service
```

**Expected Status:**
```
Active: active (running)
```

### Verify Tunnel Status

**Pangolin Dashboard:**
```
Sites → Home Network
Status: ● Online (green)
```

---

## 7. Jellyfin Resource Configuration

### Create Resource

**Pangolin Dashboard:**
```
Resources → Create Resource
```

**Resource Information:**
```
Type: HTTPS Resource
Name: Jellyfin
```

**HTTPS Settings:**
```
Subdomain: jellyfin
Base Domain: your-domain.com (auto-selected)

Full URL: https://jellyfin.your-domain.com
```

**Targets Configuration:**
```
Click: "+ Add Target"

Target Settings:
  Site: Home Network
  Target Type: HTTP
  Target Address: 192.168.0.110:8096
  Health Check: Enabled (optional)
  
→ Add Target
```

**Health Check Configuration (Optional):**
```
Enable Health Checks: ON
Method: HTTP
IP/Host: 192.168.0.110
Port: 8096
Path: /
HTTP Method: GET
Healthy Interval: 5 seconds
Unhealthy Interval: 30 seconds
Timeout: 5 seconds
```

**Additional Proxy Settings:**
```
Enable SSL: ON (auto-enabled)
TLS Server Name: (leave empty)
Enable Sticky Sessions: OFF
Custom Host Header: (leave empty)
Custom Headers: (leave empty)
```

**General Settings:**
```
Enable Resource: ON
Visibility: Enabled
```

**Authentication:**
```
Use Platform SSO: ON
(User management via Pangolin)
```

**Save:**
```
→ Create Resource / Save All Settings
```

### Verify SSL Certificate

**Wait 30-60 seconds for Traefik to request Let's Encrypt certificate**

**Check Traefik logs:**
```bash
# VPS
docker logs -f traefik
```

**Expected:**
```
Certificate obtained for domain(s) jellyfin.your-domain.com
```

### Test Access

**Browser:**
```
https://jellyfin.your-domain.com
```

**Expected:**
- Valid SSL certificate (green padlock)
- Pangolin login page (if Authentication: Protected)
- Jellyfin interface loads after authentication

---

## 8. VPS Security Hardening

### Fail2ban Installation

```bash
# Install Fail2ban
apt update
apt install fail2ban -y

# Enable and start
systemctl enable fail2ban
systemctl start fail2ban

# Check status
systemctl status fail2ban
fail2ban-client status
```

### Fail2ban Configuration

**Create Custom Config:**
```bash
nano /etc/fail2ban/jail.local
```

**Contents:**
```ini
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3
destemail = your@email.com
sendername = Fail2Ban

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 3600

[traefik-auth]
enabled = true
port = http,https
filter = traefik-auth
logpath = /opt/pangolin/config/traefik/logs/access.log
maxretry = 5
bantime = 1800
```

**Restart Fail2ban:**
```bash
systemctl restart fail2ban

# Verify jails
fail2ban-client status

# Check SSH jail
fail2ban-client status sshd
```

### SSH Hardening

**Backup Original Config:**
```bash
cp /etc/ssh/sshd_config /etc/ssh/sshd_config.backup
```

**Automatic Configuration:**
```bash
# Disable password authentication (key-only)
sed -i 's/^#PasswordAuthentication yes/PasswordAuthentication no/' /etc/ssh/sshd_config
sed -i 's/^#PermitRootLogin prohibit-password/PermitRootLogin prohibit-password/' /etc/ssh/sshd_config
sed -i 's/^#PubkeyAuthentication yes/PubkeyAuthentication yes/' /etc/ssh/sshd_config
sed -i 's/^#MaxAuthTries 6/MaxAuthTries 3/' /etc/ssh/sshd_config
sed -i 's/^X11Forwarding yes/X11Forwarding no/' /etc/ssh/sshd_config

# Add hardening options
cat >> /etc/ssh/sshd_config << 'EOF'

# SSH Security Hardening
Protocol 2
PermitEmptyPasswords no
ClientAliveInterval 300
ClientAliveCountMax 2
AllowTcpForwarding no
EOF
```

**Verify Configuration:**
```bash
# Test config syntax
sshd -t

# View changes
grep -E "PasswordAuthentication|PermitRootLogin|PubkeyAuthentication|MaxAuthTries|X11Forwarding|PermitEmptyPasswords|AllowTcpForwarding" /etc/ssh/sshd_config | grep -v "^#"
```

**Expected Output:**
```
PasswordAuthentication no
PermitRootLogin prohibit-password
PubkeyAuthentication yes
MaxAuthTries 3
X11Forwarding no
PermitEmptyPasswords no
AllowTcpForwarding no
```

**Restart SSH:**
```bash
systemctl restart ssh
systemctl status ssh
```

**⚠️ CRITICAL: Test new SSH connection before closing current session!**

### Docker Security

**Create Security Config:**
```bash
nano /etc/docker/daemon.json
```

**Contents:**
```json
{
  "live-restore": true,
  "userland-proxy": false,
  "no-new-privileges": true,
  "icc": false,
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
```

**Restart Docker:**
```bash
systemctl restart docker

# Wait for containers to restart
sleep 10

# Verify containers running
docker ps
```

### UFW Rate Limiting

```bash
# Add rate limiting for SSH
ufw limit 22/tcp

# Reload firewall
ufw reload

# Verify
ufw status verbose
```

**Expected:**
```
22/tcp                     LIMIT IN    Anywhere
```

**Rate Limiting = Max 6 connections per 30 seconds per IP**

---

## 9. Remaining Security Steps

### Cloudflare Security ✅ (completed - see Doc 12: Security Configuration Guide)

**Dashboard → your-domain.com → Security:**

#### 1. Security Level
```
Security → Settings
Security Level: High
Challenge Passage: 30 minutes
→ Save
```

#### 2. Bot Fight Mode
```
Security → Bots
Bot Fight Mode: ON
Super Bot Fight Mode: ON (if available)
→ Save
```

#### 3. WAF Custom Rules
```
Security → WAF → Custom rules

Rule 1 - Block High Threats:
Name: block-high-threats
Expression: (cf.threat_score gt 14)
Action: Block
→ Deploy

Rule 2 - Challenge Suspicious:
Name: challenge-suspicious
Expression: (cf.threat_score gt 5 and cf.threat_score lt 15)
Action: Managed Challenge
→ Deploy

Rule 3 - Rate Limit Authentication:
Name: rate-limit-auth
Expression: (http.request.uri.path contains "/auth")
Action: Managed Challenge
When rate exceeds: 10 requests per 60 seconds
→ Deploy
```

#### 4. Rate Limiting
```
Security → Rate Limiting Rules

Name: general-protection
If incoming requests match: jellyfin.your-domain.com
Rate: 100 requests per 1 minute
Action: Block for 10 minutes
→ Deploy
```

### Pangolin Security Settings ✅ (completed - see Doc 12: Security Configuration Guide)

**Dashboard → Settings (ORGANIZATION section):**

#### Session Settings
```
Session Timeout: 24 hours
Require re-authentication for sensitive actions: ON
```

#### Login Protection
```
Max failed login attempts: 5
Lockout duration: 15 minutes
Enable rate limiting: ON
```

#### Audit Logging
```
Log all access attempts: ON
Log configuration changes: ON
```

### Jellyfin Resource Rules ✅ (completed - see Doc 12: Security Configuration Guide)

**Resources → Jellyfin → Rules tab:**

```
Enable Rules: ON

Rule 1 - Rate Limit:
Action: Rate Limit
Match Type: IP
Value: 0.0.0.0/0
Limit: 100 requests per 60 seconds
Enabled: ON

Rule 2 - Block Scanner Paths:
Action: Block
Match Type: Path
Value: /admin|/phpmyadmin|/.env|/wp-admin|/xmlrpc|/.git
Enabled: ON

→ Save All Settings
```

---

## 10. Architecture Overview

### System Flow

```
Internet (Client Browser)
    ↓
    ↓ HTTPS
    ↓
jellyfin.your-domain.com (YOUR_VPS_IP)
    ↓
    ↓ Cloudflare DNS (Gray cloud)
    ↓
Hetzner VPS (YOUR_VPS_IP)
├─ Traefik (Reverse Proxy)
│  ├─ SSL Termination (Let's Encrypt)
│  └─ Routing (jellyfin.your-domain.com)
├─ Gerbil (WireGuard Server)
│  ├─ UDP 51820 (WireGuard)
│  ├─ UDP 21820 (Gerbil clients)
│  └─ Network: 100.90.128.0/24
└─ Pangolin (Dashboard/API)
   ├─ Ports 3000-3002
   └─ Authentication & Management
    ↓
    ↓ WireGuard Tunnel (Encrypted)
    ↓
Home Network (192.168.0.0/24)
├─ Proxmox Host (192.168.0.109)
│  └─ Newt Client (systemd service)
│     └─ WireGuard IP: 100.90.128.2
└─ Jellyfin LXC (192.168.0.110:8096)
   └─ Media Server
```

### Network Topology

**Public Network:**
- VPS IP: YOUR_VPS_IP
- Domain: your-domain.com
- Subdomains: pangolin.your-domain.com, jellyfin.your-domain.com

**WireGuard Tunnel Network:**
- Subnet: 100.90.128.0/24
- Gerbil (VPS): 100.90.128.1
- Newt Client (Home Lab): 100.90.128.2

**Home Network:**
- Subnet: 192.168.0.0/24
- Proxmox Host: 192.168.0.109
- Jellyfin LXC: 192.168.0.110

### Port Mapping

**VPS (YOUR_VPS_IP):**
| Port | Protocol | Service | Purpose |
|------|----------|---------|---------|
| 22 | TCP | SSH | Server management |
| 80 | TCP | Gerbil/Traefik | HTTP (redirect to HTTPS) |
| 443 | TCP | Gerbil/Traefik | HTTPS traffic |
| 51820 | UDP | Gerbil | WireGuard tunnel |
| 21820 | UDP | Gerbil | Gerbil client connections |

**Pangolin Containers:**
| Container | Ports | Purpose |
|-----------|-------|---------|
| pangolin | 3000-3002 | Dashboard/API (internal) |
| gerbil | 80, 443, 51820, 21820 | WireGuard + HTTP/HTTPS |
| traefik | - | Reverse proxy (internal) |

---

## 11. Costs

**Monthly Costs:**
```
Hetzner CX23 VPS: €3.49/month
Domain (your-domain.com): ~€9/year (€0.75/month)
───────────────────────────────────
TOTAL: €4.24/month (~€51/year)
```

**Annual Costs:**
```
Hetzner VPS: €41.88/year
Domain: €9/year
───────────────────────────────────
TOTAL: €50.88/year (~17,000 HUF/year)
```

**Initial Investment:**
- €20 PayPal verification = ~5.7 months prepaid
- Approximately €21 remaining credit

---

## 12. Troubleshooting

### DNS Issues

**Problem:** `jellyfin.your-domain.com` returns NXDOMAIN

**Solutions:**
1. **Check Cloudflare DNS:**
   ```
   Cloudflare Dashboard → DNS → Records
   Verify A record exists and points to YOUR_VPS_IP
   ```

2. **Flush Local DNS Cache:**
   ```bash
   # Windows
   ipconfig /flushdns
   
   # Linux
   sudo systemd-resolve --flush-caches
   
   # AdGuard Home
   Settings → DNS Settings → Clear DNS cache
   ```

3. **Test DNS Resolution:**
   ```bash
   # VPS
   nslookup jellyfin.your-domain.com
   
   # Expected: YOUR_VPS_IP
   ```

4. **Wait for Propagation:**
   - DNS changes can take 2-5 minutes
   - Negative caching can persist longer

### SSL Certificate Issues

**Problem:** Let's Encrypt certificate fails to obtain

**Solutions:**
1. **Verify DNS Points to VPS:**
   ```bash
   nslookup pangolin.your-domain.com
   # Must return: YOUR_VPS_IP
   ```

2. **Check Cloudflare Proxy Status:**
   ```
   Must be: DNS only (Gray cloud)
   Orange cloud will block Let's Encrypt!
   ```

3. **Check Port 80 Open:**
   ```bash
   # VPS
   ufw status | grep 80
   # Should show: 80/tcp ALLOW IN
   ```

4. **Clear ACME Cache:**
   ```bash
   # VPS
   rm /opt/pangolin/config/letsencrypt/acme.json
   docker restart traefik
   
   # Wait 60 seconds, check logs
   docker logs -f traefik
   ```

### WireGuard Tunnel Not Connecting

**Problem:** Newt client can't connect to Pangolin

**Solutions:**
1. **Check Newt Service:**
   ```bash
   # Proxmox host
   systemctl status newt.service
   
   # View logs
   journalctl -u newt.service -f
   ```

2. **Verify Site Credentials:**
   ```bash
   # Check Site ID and Secret match Pangolin dashboard
   cat /etc/systemd/system/newt.service
   ```

3. **Test Manual Connection:**
   ```bash
   # Stop service
   systemctl stop newt.service
   
   # Run foreground
   newt --id [SITE_ID] --secret [SECRET] --endpoint https://pangolin.your-domain.com
   
   # Should see: "Tunnel connection established successfully!"
   ```

4. **Check Firewall:**
   ```bash
   # VPS - verify WireGuard ports open
   ufw status | grep -E "51820|21820"
   ```

5. **Pangolin Dashboard:**
   ```
   Sites → Home Network
   Status should be: ● Online (green)
   ```

### Jellyfin Not Accessible

**Problem:** `https://jellyfin.your-domain.com` not loading

**Solutions:**
1. **Check Resource Status:**
   ```
   Pangolin Dashboard → Resources → Jellyfin
   Status: Should show resource details without errors
   ```

2. **Check Target Health:**
   ```
   Jellyfin → Proxy tab
   Target health: ⚙️ Healthy (green)
   ```

3. **Verify Jellyfin Running:**
   ```bash
   # Home Lab - check Jellyfin LXC
   curl http://192.168.0.110:8096
   # Should return Jellyfin HTML
   ```

4. **Check Traefik Routing:**
   ```bash
   # VPS
   docker logs traefik | grep jellyfin
   ```

5. **Verify Visibility:**
   ```
   Jellyfin Resource → General tab
   Visibility: Must be "Enabled"
   ```

### Fail2ban Not Banning

**Problem:** Brute force attacks not getting banned

**Solutions:**
1. **Check Fail2ban Status:**
   ```bash
   systemctl status fail2ban
   fail2ban-client status sshd
   ```

2. **Test Ban Manually:**
   ```bash
   # Ban test IP
   fail2ban-client set sshd banip 1.2.3.4
   
   # Check banned list
   fail2ban-client get sshd banned
   
   # Unban
   fail2ban-client set sshd unbanip 1.2.3.4
   ```

3. **Check Logs:**
   ```bash
   tail -f /var/log/fail2ban.log
   tail -f /var/log/auth.log
   ```

4. **Restart Fail2ban:**
   ```bash
   systemctl restart fail2ban
   ```

### Docker Containers Not Starting

**Problem:** Pangolin containers fail to start

**Solutions:**
1. **Check Docker Status:**
   ```bash
   systemctl status docker
   ```

2. **View Container Logs:**
   ```bash
   docker logs pangolin
   docker logs gerbil
   docker logs traefik
   ```

3. **Check Port Conflicts:**
   ```bash
   # See what's using ports
   ss -tlnp | grep -E ":80|:443|:51820"
   ```

4. **Restart All Containers:**
   ```bash
   cd /opt/pangolin
   docker compose down
   docker compose up -d
   ```

5. **Check Disk Space:**
   ```bash
   df -h
   # Root partition should have >1GB free
   ```

---

## Quick Reference

### Important URLs
```
Pangolin Dashboard: https://pangolin.your-domain.com
Jellyfin (Public): https://jellyfin.your-domain.com
Jellyfin (Local): http://192.168.0.110:8096
Hetzner Console: https://console.hetzner.cloud/
Cloudflare Dashboard: https://dash.cloudflare.com/
```

### Important Paths (VPS)
```
Pangolin Config: /opt/pangolin/config/
Traefik Config: /opt/pangolin/config/traefik/
SSL Certificates: /opt/pangolin/config/letsencrypt/
Docker Compose: /opt/pangolin/docker-compose.yml
SSH Config: /etc/ssh/sshd_config
Fail2ban Config: /etc/fail2ban/jail.local
UFW Rules: /etc/ufw/
```

### Important Paths (Home Lab)
```
Newt Binary: /usr/local/bin/newt
Newt Service: /etc/systemd/system/newt.service
Newt Config: /root/.config/newt-client/config.json
```

### Key Credentials
```
VPS IP: YOUR_VPS_IP
VPS User: root (SSH key auth only)
Pangolin Admin: your@email.com
Site ID: YOUR_PANGOLIN_SITE_ID
Site Secret: YOUR_PANGOLIN_SITE_SECRET
```

### Common Commands

**VPS Management:**
```bash
# Check all services
systemctl status ssh fail2ban docker

# View firewall rules
ufw status verbose

# Check banned IPs
fail2ban-client banned

# Docker containers status
docker ps
docker stats --no-stream

# View logs
docker logs -f traefik
docker logs -f pangolin
journalctl -u fail2ban -f
tail -f /var/log/auth.log
```

**Home Lab Management:**
```bash
# Proxmox host
systemctl status newt.service
journalctl -u newt.service -f

# Test Jellyfin locally
curl http://192.168.0.110:8096
```

---

**Document Version:** 1.0  
**Last Updated:** 2026-01-11  
**Status:** Complete - full security configuration documented in Doc 12
