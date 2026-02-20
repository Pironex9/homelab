
**Version:** 1.0  
**Date:** 2024-12-30  
**Platform:** Proxmox VE + LXC 100 (Docker)  
**Purpose:** SMART disk monitoring with web dashboard

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Server Setup (LXC 100)](#server-setup-lxc-100)
5. [Collector Setup (Proxmox Host)](#collector-setup-proxmox-host)
6. [Verification](#verification)
7. [Maintenance](#maintenance)
8. [Troubleshooting](#troubleshooting)
9. [Alerts Configuration](#alerts-configuration)

---

## 🏗️ Overview

### **What is Scrutiny?**

Scrutiny is a WebUI for smartd S.M.A.R.T monitoring. It provides:

```
✅ Real-time disk health monitoring
✅ SMART attribute tracking
✅ Temperature monitoring
✅ Failure prediction
✅ Historical data with graphs
✅ Email/webhook alerts
✅ Multi-host support
```

---

### **Why Two Components?**

**Problem:** LXC containers cannot directly access Proxmox host's physical disks.

**Solution:** Client-server architecture:

```
Scrutiny Server (LXC 100):
  - WebUI dashboard
  - Metrics storage (InfluxDB)
  - API endpoint
  - Alert management

Scrutiny Collector (Proxmox Host):
  - Reads SMART data from physical disks
  - Sends metrics to Server API
  - Runs hourly via systemd timer
```

---

## 🏗️ Architecture

### **System Overview:**

```
┌─────────────────────────────────────────────────┐
│ Proxmox Host (pve - 192.168.0.YOUR_PROXMOX_IP)              │
│                                                  │
│ Physical Disks:                                 │
│   ├─ /dev/nvme0n1 (238.5GB NVMe - System)      │
│   ├─ /dev/sda (5.5TB HDD - HGST)               │
│   ├─ /dev/sdb (5.5TB HDD - HGST)               │
│   ├─ /dev/sdc (931.5GB HDD - Seagate)          │
│   └─ /dev/sdd (1.8TB HDD - Seagate)            │
│                                                  │
│ Scrutiny Collector:                             │
│   ├─ Binary: /usr/local/bin/scrutiny-collector │
│   ├─ Config: /etc/scrutiny/collector.yaml      │
│   ├─ Systemd service (oneshot)                 │
│   └─ Systemd timer (hourly)                    │
│                                                  │
│   └─ Sends SMART data → HTTP API               │
└─────────────────────────────────────────────────┘
         ↓ API: http://192.168.0.YOUR_DOCKER_IP:8082
┌─────────────────────────────────────────────────┐
│ LXC 100 - Docker Host (192.168.0.YOUR_DOCKER_IP)           │
│                                                  │
│ Scrutiny Server (Docker):                       │
│   ├─ Container: scrutiny                        │
│   ├─ Image: ghcr.io/analogj/scrutiny:latest    │
│   ├─ WebUI: http://192.168.0.YOUR_DOCKER_IP:8082          │
│   ├─ InfluxDB (embedded metrics storage)        │
│   └─ Dashboard (all disks, historical data)     │
└─────────────────────────────────────────────────┘
```

---

### **Data Flow:**

```
1. Systemd timer triggers (every hour)
2. Collector runs smartctl on all disks
3. Collector sends SMART JSON to Server API
4. Server stores metrics in InfluxDB
5. WebUI displays current + historical data
6. Alerts triggered if thresholds exceeded
```

---

## ✅ Prerequisites

### **Software Requirements:**

**Proxmox Host:**
```
✅ smartmontools (smartctl)
✅ curl or wget
✅ systemd
```

**LXC 100:**
```
✅ Docker + Docker Compose
✅ Port 8082 available
```

---

### **Install smartmontools (Proxmox Host):**

```bash
# Proxmox host
apt update
apt install smartmontools -y

# Verify installation
smartctl --version
smartctl --scan
```

**Expected output:**
```
smartctl 7.3 2022-02-28
...

/dev/nvme0 -d nvme # /dev/nvme0, NVMe device
/dev/sda -d scsi # /dev/sda, SCSI device
/dev/sdb -d scsi # /dev/sdb, SCSI device
...
```

---

## 🐳 Server Setup (LXC 100)

### **Step 1: Check Existing Setup**

**If Scrutiny already running in LXC 100:**

```bash
pct enter 100

# Check running container
docker ps | grep scrutiny

# Check compose file
cat /srv/docker-compose/scrutiny/docker-compose.yml
```

---

### **Step 2: Docker Compose Configuration**

**If NOT installed, create:**

```bash
# LXC 100
pct enter 100

# Directories
mkdir -p /srv/docker-compose/scrutiny
mkdir -p /srv/docker-data/scrutiny/config
mkdir -p /srv/docker-data/scrutiny/influxdb

# Compose file
nano /srv/docker-compose/scrutiny/docker-compose.yml
```

**Docker Compose YAML:**

```yaml
services:
  scrutiny:
    image: ghcr.io/analogj/scrutiny:latest
    container_name: scrutiny
    environment:
      - TZ=Europe/Bratislava  # Your timezone
      - PUID=1000
      - PGID=1000
    volumes:
      - /srv/docker-data/scrutiny/config:/opt/scrutiny/config
      - /srv/docker-data/scrutiny/influxdb:/opt/scrutiny/influxdb
    ports:
      - 8082:8080  # WebUI port
    restart: unless-stopped
    privileged: false  # Server doesn't need privileged
    networks:
      - utils

networks:
  utils:
    external: true
```

**Key points:**
- Server runs in LXC (NOT privileged needed)
- Port 8082 exposed for WebUI + API
- Config + InfluxDB data persisted in volumes

---

### **Step 3: Start Server**

```bash
cd /srv/docker-compose/scrutiny

# Pull image
docker compose pull

# Start container
docker compose up -d

# Check logs
docker compose logs -f
```

**Expected logs:**
```
Starting Scrutiny API server...
Starting InfluxDB...
Starting Web server on :8080...
Scrutiny is ready!
```

**Press Ctrl+C to exit logs**

---

### **Step 4: Verify Server**

```bash
# Container status
docker ps | grep scrutiny

# Expected:
# scrutiny  Up X hours  0.0.0.0:8082->8080/tcp

# Test API endpoint
curl http://localhost:8082/api/health

# Expected:
# {"success": true}
```

---

### **Step 5: WebUI Access (Initial)**

**Browser:**
```
http://192.168.0.YOUR_DOCKER_IP:8082
```

**Expected:**
- Dashboard loads ✅
- No disks shown yet (collector not installed)

---

## 🖥️ Collector Setup (Proxmox Host)

### **Step 1: Download Collector Binary**

**Proxmox host SSH:**

```bash
# Get latest version
SCRUTINY_VERSION=$(curl -s https://api.github.com/repos/AnalogJ/scrutiny/releases/latest | grep "tag_name" | cut -d '"' -f 4)

echo "Latest version: $SCRUTINY_VERSION"

# Download collector binary
wget https://github.com/AnalogJ/scrutiny/releases/download/${SCRUTINY_VERSION}/scrutiny-collector-metrics-linux-amd64 -O /usr/local/bin/scrutiny-collector-metrics

# Make executable
chmod +x /usr/local/bin/scrutiny-collector-metrics

# Verify installation
/usr/local/bin/scrutiny-collector-metrics --version
```

**Expected output:**
```
scrutiny-collector-metrics version 0.8.1
```

---

### **Step 2: Identify Your Disks**

```bash
# List all block devices
lsblk

# SMART-capable devices
smartctl --scan
```

**Example output:**
```
/dev/nvme0 -d nvme # /dev/nvme0, NVMe device
/dev/sda -d scsi # /dev/sda, SCSI device
/dev/sdb -d scsi # /dev/sdb, SCSI device
/dev/sdc -d sat # /dev/sdc [SAT], ATA device
/dev/sdd -d sat # /dev/sdd [SAT], ATA device
```

**⚠️ Important:** Note your exact device names for config file!

---

### **Step 3: Test SMART Access**

```bash
# Test each disk
smartctl -a /dev/nvme0n1
smartctl -a /dev/sda
smartctl -a /dev/sdb
# ... etc for all disks

# All should return SMART data ✅
```

---

### **Step 4: Create Collector Config**

```bash
# Create directories
mkdir -p /etc/scrutiny
mkdir -p /var/log/scrutiny

# Config file
nano /etc/scrutiny/collector.yaml
```

**Collector Config YAML:**

```yaml
version: 1

# Host identifier (appears in WebUI)
host:
  id: proxmox-pve  # Change if needed

# Scrutiny Server API endpoint (LXC 100)
api:
  endpoint: http://192.168.0.YOUR_DOCKER_IP:8082

# Logging
log:
  level: INFO
  file: /var/log/scrutiny/collector.log

# Devices to monitor
# ⚠️ UPDATE THIS LIST with YOUR actual disks from 'smartctl --scan'
devices:
  - /dev/nvme0n1  # NVMe SSD (if you have one)
  - /dev/sda      # HDD 1
  - /dev/sdb      # HDD 2
  - /dev/sdc      # HDD 3
  - /dev/sdd      # HDD 4
  # Add or remove based on your system!

# Optional: Collection schedule (handled by systemd timer instead)
# commands:
#   metrics_scan_schedule: "0 2 * * *"  # Daily at 02:00
```

**⚠️ CRITICAL:** Update the `devices:` list with YOUR exact disk names!

**Save:** `Ctrl+O`, `Enter`, `Ctrl+X`

---

### **Step 5: Create Systemd Service**

```bash
nano /etc/systemd/system/scrutiny-collector.service
```

**Service File:**

```ini
[Unit]
Description=Scrutiny Collector - SMART Disk Monitoring
After=network.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/scrutiny-collector-metrics run --config /etc/scrutiny/collector.yaml
Restart=no

# Security
User=root  # Required for SMART access
NoNewPrivileges=true
PrivateTmp=true

# Logging
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Key points:**
- `Type=oneshot` - Runs once when triggered
- `User=root` - Required for smartctl disk access
- Logs to systemd journal

**Save:** `Ctrl+O`, `Enter`, `Ctrl+X`

---

### **Step 6: Create Systemd Timer (Hourly)**

```bash
nano /etc/systemd/system/scrutiny-collector.timer
```

**Timer File:**

```ini
[Unit]
Description=Scrutiny Collector Timer - Hourly SMART Scan
Requires=scrutiny-collector.service

[Timer]
OnBootSec=5min  # First run 5 minutes after boot
OnUnitActiveSec=1h  # Then every hour
Unit=scrutiny-collector.service

[Install]
WantedBy=timers.target
```

**Schedule:**
- First run: 5 minutes after boot
- Subsequent runs: Every 1 hour

**Save:** `Ctrl+O`, `Enter`, `Ctrl+X`

---

### **Step 7: Enable and Start Timer**

```bash
# Reload systemd
systemctl daemon-reload

# Enable timer (auto-start on boot)
systemctl enable scrutiny-collector.timer

# Start timer now
systemctl start scrutiny-collector.timer

# Verify timer active
systemctl list-timers | grep scrutiny
```

**Expected output:**
```
NEXT                         LEFT    LAST    PASSED  UNIT                         ACTIVATES
Tue 2025-12-30 13:00:00 CET  5min    -       -       scrutiny-collector.timer     scrutiny-collector.service
```

---

### **Step 8: Trigger Manual Run (Test)**

```bash
# Manual run to populate data immediately
systemctl start scrutiny-collector.service

# Wait ~10 seconds, then check logs
journalctl -u scrutiny-collector.service -n 50 --no-pager
```

**Expected log output:**
```
Collecting smartctl results for nvme0...
Executing command: smartctl --xall --json --device nvme /dev/nvme0
Publishing smartctl results for <WWN>...
Collecting smartctl results for sda...
Publishing smartctl results for <WWN>...
...
Main: Completed
```

**Look for:**
- ✅ "Collecting smartctl results for..."
- ✅ "Publishing smartctl results for..."
- ✅ "Main: Completed"
- ❌ NO critical errors (warnings OK)

---

## ✅ Verification

### **1. Check Timer Status**

```bash
# Proxmox host
systemctl status scrutiny-collector.timer

# Expected:
# Active: active (waiting)
# Trigger: <next run time>
```

---

### **2. Check Service Logs**

```bash
# Last 100 lines
journalctl -u scrutiny-collector.service -n 100 --no-pager

# Follow live (for next run)
journalctl -u scrutiny-collector.service -f
```

---

### **3. WebUI Dashboard**

**Browser:**
```
http://192.168.0.YOUR_DOCKER_IP:8082
```

**Expected Dashboard:**
```
proxmox-pve (host)
  ├─ /dev/nvme0n1 - NVMe SSD
  │    Status: Passed/Failed
  │    Temp: XX°C
  │    Capacity: XXX GB
  │    Powered On: X days/years
  │
  ├─ /dev/sda - HDD
  │    Status: Passed/Failed
  │    ...
  │
  └─ ... (all configured disks)
```

**All disks should show:**
- ✅ Status indicator (Passed = green)
- ✅ Current temperature
- ✅ Capacity
- ✅ Power-on time
- ✅ Last updated timestamp

---

### **4. Disk Details**

**Click on any disk card:**

```
Disk Details Page:
  - SMART Attributes Table
    - Raw values
    - Normalized values
    - Thresholds
  
  - Temperature History Graph
  - Power-On Hours Trend
  - Reallocated Sectors
  - Pending Sectors
  - UDMA CRC Errors
  - ... (all SMART metrics)
```

---

### **5. Historical Data**

**Wait 2-3 hours, then check:**
- Temperature graphs should show trends
- Metrics updating hourly

---

## 🔧 Maintenance

### **Check Collector Status**

```bash
# Proxmox host

# Timer status
systemctl status scrutiny-collector.timer

# Service status (last run)
systemctl status scrutiny-collector.service

# Next scheduled run
systemctl list-timers | grep scrutiny
```

---

### **Manual Collector Run**

```bash
# Trigger immediate run (doesn't affect timer schedule)
systemctl start scrutiny-collector.service

# Watch logs
journalctl -u scrutiny-collector.service -f
```

---

### **View Collector Logs**

```bash
# Last 50 lines
journalctl -u scrutiny-collector.service -n 50

# Last hour
journalctl -u scrutiny-collector.service --since "1 hour ago"

# Today's runs
journalctl -u scrutiny-collector.service --since today

# Follow live
journalctl -u scrutiny-collector.service -f
```

---

### **Restart Scrutiny Server**

```bash
# LXC 100
pct enter 100
cd /srv/docker-compose/scrutiny

# Restart
docker compose restart

# Check logs
docker compose logs -f
```

---

### **Update Collector Binary**

```bash
# Proxmox host

# Get latest version
SCRUTINY_VERSION=$(curl -s https://api.github.com/repos/AnalogJ/scrutiny/releases/latest | grep "tag_name" | cut -d '"' -f 4)

# Download new version
wget https://github.com/AnalogJ/scrutiny/releases/download/${SCRUTINY_VERSION}/scrutiny-collector-metrics-linux-amd64 -O /usr/local/bin/scrutiny-collector-metrics.new

# Replace old binary
mv /usr/local/bin/scrutiny-collector-metrics /usr/local/bin/scrutiny-collector-metrics.old
mv /usr/local/bin/scrutiny-collector-metrics.new /usr/local/bin/scrutiny-collector-metrics
chmod +x /usr/local/bin/scrutiny-collector-metrics

# Verify
/usr/local/bin/scrutiny-collector-metrics --version
```

---

### **Add/Remove Disks**

**If you add/remove physical disks:**

```bash
# Proxmox host

# Update device list
nano /etc/scrutiny/collector.yaml

# Update the devices: section
devices:
  - /dev/nvme0n1
  - /dev/sda
  - /dev/sdb
  # Add new disks here
  # Remove old disks

# Save and trigger manual run
systemctl start scrutiny-collector.service

# Verify in WebUI (new disk should appear)
```

---

## 🔧 Troubleshooting

### **Problem: No disks showing in WebUI**

**Diagnosis:**

```bash
# Proxmox host

# Check collector ran successfully
journalctl -u scrutiny-collector.service -n 100

# Look for errors:
# - "Could not retrieve device information"
# - "Connection refused" (API unreachable)
# - "Permission denied" (SMART access)
```

**Solution 1: API unreachable**

```bash
# Test API from Proxmox host
curl http://192.168.0.YOUR_DOCKER_IP:8082/api/health

# Should return: {"success": true}

# If fails:
# - Check LXC 100 Scrutiny container running
# - Check port 8082 not blocked
# - Check LXC IP correct (192.168.0.YOUR_DOCKER_IP)
```

**Solution 2: SMART access denied**

```bash
# Test SMART access
smartctl -a /dev/sda

# If "Permission denied":
# - Collector must run as root
# - Check service file: User=root
```

**Solution 3: Wrong device names**

```bash
# Verify device names
smartctl --scan

# Update collector.yaml with correct names
nano /etc/scrutiny/collector.yaml
```

---

### **Problem: Collector service fails**

**Check logs:**

```bash
journalctl -u scrutiny-collector.service -n 100 --no-pager
```

**Common errors:**

**"Config file not found"**
```bash
# Verify config exists
ls -la /etc/scrutiny/collector.yaml

# Check syntax (valid YAML?)
cat /etc/scrutiny/collector.yaml
```

**"Could not execute smartctl"**
```bash
# Verify smartmontools installed
which smartctl
smartctl --version
```

**"Connection refused to API"**
```bash
# Check Scrutiny Server running
pct enter 100
docker ps | grep scrutiny

# Check API accessible
curl http://192.168.0.YOUR_DOCKER_IP:8082/api/health
```

---

### **Problem: Timer not triggering**

```bash
# Check timer status
systemctl status scrutiny-collector.timer

# Should be: Active: active (waiting)

# If inactive:
systemctl enable scrutiny-collector.timer
systemctl start scrutiny-collector.timer

# Verify
systemctl list-timers | grep scrutiny
```

---

### **Problem: SMART checksum errors**

**Logs show:**
```
level=error msg="smartctl detected a checksum error"
```

**This is usually OK:**
- Old SMART log entry
- Previous cable/firmware issue
- Data still collected successfully

**If persistent:**
```bash
# Test disk directly
smartctl -a /dev/sdX

# Check for:
# - Cable issues (UDMA CRC errors)
# - Controller problems
# - Disk firmware bugs
```

---

### **Problem: High memory usage**

**Scrutiny Server using too much RAM:**

```bash
# LXC 100
docker stats scrutiny

# If high memory:
# - Check InfluxDB retention settings
# - Reduce history retention
# - Increase LXC RAM allocation
```

---

## 🔔 Alerts Configuration

### **Email Alerts**

**Edit Scrutiny server config:**

```bash
# LXC 100
pct enter 100

# Create/edit config
nano /srv/docker-data/scrutiny/config/scrutiny.yaml
```

**Config with email alerts:**

```yaml
# Notification level (warn, error, critical)
notify:
  level: warn
  
  # Email notifications
  email:
    smtp_host: smtp.gmail.com
    smtp_port: 587
    smtp_username: your-email@gmail.com
    smtp_password: your-app-password  # Gmail: use App Password
    smtp_tls: true
    from: scrutiny@your-domain.com
    to:
      - your-email@gmail.com
      - admin@your-domain.com
```

**Restart Scrutiny:**

```bash
cd /srv/docker-compose/scrutiny
docker compose restart
```

---

### **Discord Webhook**

```yaml
notify:
  level: warn
  
  discord:
    webhook_url: https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN
```

---

### **Slack Webhook**

```yaml
notify:
  level: warn
  
  slack:
    webhook_url: https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

---

### **Multiple Notification Channels**

```yaml
notify:
  level: warn
  
  email:
    smtp_host: smtp.gmail.com
    # ... email config
  
  discord:
    webhook_url: https://discord.com/...
  
  slack:
    webhook_url: https://hooks.slack.com/...
```

**All channels receive alerts simultaneously!**

---

## 📊 WebUI Features

### **Dashboard View**

```
Features:
  - All monitored hosts
  - Disk cards with status
  - Temperature indicators
  - Power-on time
  - Last update timestamp
  - Export button (PDF/CSV/JSON)
  - Settings button
```

---

### **Disk Details**

**Click any disk card:**

```
Tabs:
  - Overview (current status)
  - SMART Attributes (detailed table)
  - Temperature History (graph)
  - Metrics (historical trends)
```

**SMART Attributes Table:**
```
ID | Attribute Name      | Value | Worst | Thresh | Raw Value
---+--------------------+-------+-------+--------+------------
  5 | Reallocated Sectors|  100  |  100  |   10   |     0
  9 | Power-On Hours     |   98  |   98  |    0   | 26,304
 12 | Power Cycle Count  |  100  |  100  |    0   |   156
...
```

---

### **Export Data**

**Dashboard → Export button:**

```
Options:
  - PDF Report (all disks summary)
  - CSV Data Export (metrics)
  - JSON Export (API data)
```

---

### **Settings**

**Dashboard → Settings:**

```
Options:
  - Metrics Retention (how long to keep history)
  - Temperature Units (Celsius/Fahrenheit)
  - Dashboard Refresh Interval
  - Notification Settings
  - Theme (dark/light mode)
```

---

## 📈 Best Practices

### **Monitoring Frequency**

```
✅ Hourly collection (default)
   - Good balance (data freshness vs disk wear)
   
⚠️ More frequent (15 min)
   - More data points
   - But: more smartctl runs = disk wear
   
❌ Daily only
   - Misses rapid failures
```

**Recommendation:** Keep hourly (1h) collection.

---

### **Alert Thresholds**

```
Recommended notify level: warn

Triggers alerts for:
  ✅ Reallocated sectors increasing
  ✅ Pending sectors detected
  ✅ Temperature exceeds safe range
  ✅ SMART test failures
  ✅ Power-on hours anomalies
```

---

### **Data Retention**

```
Default: 30 days historical data

Adjust based on:
  - Available storage (InfluxDB size)
  - Trend analysis needs
  - Long-term health tracking

Example:
  - Short-term monitoring: 7 days
  - Standard monitoring: 30 days
  - Long-term analysis: 90+ days
```

---

### **Regular Checks**

```
Weekly:
  - Review dashboard for warnings
  - Check temperature trends
  - Verify all disks reporting

Monthly:
  - Export health report (PDF)
  - Review SMART attribute trends
  - Check for reallocated sectors

Quarterly:
  - Review power-on hours
  - Plan disk replacements (if needed)
  - Test alert notifications
```

---

## 📋 Quick Reference

### **Common Commands**

**Proxmox Host:**

```bash
# Manual collector run
systemctl start scrutiny-collector.service

# Check last run logs
journalctl -u scrutiny-collector.service -n 50

# Timer status
systemctl list-timers | grep scrutiny

# Restart timer
systemctl restart scrutiny-collector.timer
```

---

**LXC 100:**

```bash
# Restart Scrutiny server
pct enter 100
cd /srv/docker-compose/scrutiny
docker compose restart

# View logs
docker compose logs -f

# Check container status
docker ps | grep scrutiny
```

---

### **Important Files**

**Proxmox Host:**
```
Binary: /usr/local/bin/scrutiny-collector-metrics
Config: /etc/scrutiny/collector.yaml
Logs: journalctl -u scrutiny-collector.service
Service: /etc/systemd/system/scrutiny-collector.service
Timer: /etc/systemd/system/scrutiny-collector.timer
```

**LXC 100:**
```
Compose: /srv/docker-compose/scrutiny/docker-compose.yml
Config: /srv/docker-data/scrutiny/config/scrutiny.yaml
InfluxDB: /srv/docker-data/scrutiny/influxdb/
```

---

### **Important URLs**

```
WebUI: http://192.168.0.YOUR_DOCKER_IP:8082
API Health: http://192.168.0.YOUR_DOCKER_IP:8082/api/health
GitHub: https://github.com/AnalogJ/scrutiny
Documentation: https://github.com/AnalogJ/scrutiny/blob/master/docs/
```

---

## ✅ Setup Checklist

```
Proxmox Host:
☑ smartmontools installed
☑ Collector binary downloaded
☑ Config file created (/etc/scrutiny/collector.yaml)
☑ Devices list correct
☑ Systemd service created
☑ Systemd timer created
☑ Timer enabled and started
☑ Manual run successful
☑ Logs show "Main: Completed"

LXC 100:
☑ Scrutiny Server container running
☑ Port 8082 accessible
☑ API health check OK
☑ Config file present (if using alerts)

Verification:
☑ WebUI accessible (http://192.168.0.YOUR_DOCKER_IP:8082)
☑ All disks visible in dashboard
☑ SMART data displayed
☑ Status indicators showing
☑ Temperature readings present
☑ No critical errors in logs
☑ Timer scheduled correctly
```

---

## 🎉 Success Indicators

**Your setup is working correctly when:**

```
✅ Dashboard shows all physical disks
✅ Each disk has "Passed" status (if healthy)
✅ Temperature readings updating
✅ Last update timestamp recent (<2 hours)
✅ Historical graphs showing data
✅ No errors in collector logs
✅ Timer shows next run scheduled
✅ API health check returns success
```

---

**Prepared:** 2024-12-30  
**Version:** 1.0  
**Tested:** Proxmox VE 8.x + LXC 100 (Docker)

**ENJOY COMPREHENSIVE DISK HEALTH MONITORING!** 💾✨
