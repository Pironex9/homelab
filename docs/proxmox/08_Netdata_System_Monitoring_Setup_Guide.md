
**Version:** 1.0  
**Date:** 2025-12-30  
**Platform:** Proxmox VE Host  
**Purpose:** Real-time system monitoring with local-only operation

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Installation](#installation)
3. [Local-Only Setup (NO Cloud)](#local-only-setup-no-cloud)
4. [WebUI Usage](#webui-usage)
5. [Dashboard Navigation](#dashboard-navigation)
6. [Alarms Configuration](#alarms-configuration)
7. [Integration with Scrutiny](#integration-with-scrutiny)
8. [Troubleshooting](#troubleshooting)
9. [Best Practices](#best-practices)

---

## 🏗️ Overview

### **What is Netdata?**

Netdata is a real-time performance monitoring tool that provides:

```
✅ Real-time metrics (1-second granularity)
✅ 6,000+ metrics auto-detected
✅ Beautiful, responsive WebUI
✅ Zero configuration required
✅ Per-second performance monitoring
✅ CPU, Memory, Disk I/O, Network
✅ Container & VM metrics (LXC, Docker, KVM)
✅ Built-in alarms
✅ Historical data (local storage)
✅ Lightweight (~100-200 MB RAM)
```

---

### **Netdata vs. Alternatives:**

| Feature | Netdata | Prometheus+Grafana | Glances |
|---------|---------|-------------------|---------|
| Setup time | 5 min ⚡ | 30-60 min | 5 min |
| Configuration | Zero config | Heavy config | Minimal |
| Real-time | 1 sec ✅ | 15-60 sec | 1 sec |
| WebUI | Built-in ✅ | Need Grafana | Basic |
| Learning curve | Easy | Steep | Easy |
| Resource usage | ~150 MB | ~500 MB+ | ~50 MB |
| Best for | Quick monitoring | Long-term trends | CLI lovers |

---

### **Why Netdata for Proxmox?**

```
✅ Instant visibility (no setup!)
✅ Real-time troubleshooting
✅ Per-container metrics (LXC/VM)
✅ Beautiful dashboards
✅ Perfect for home lab
✅ 100% free (open source)
✅ Local-only operation (NO cloud required)
```

---

## 🚀 Installation

### **Prerequisites:**

**Proxmox Host:**
```
✅ Proxmox VE 7.x or 8.x
✅ Internet connection (for install only)
✅ ~200 MB free disk space
✅ Port 19999 available
```

---

### **One-Liner Installation:**

**Proxmox host SSH:**

```bash
# Install Netdata (latest stable)
bash <(curl -Ss https://get.netdata.cloud/kickstart.sh)
```

**During installation:**

```
Installer will ask:
  "Would you like to connect to Netdata Cloud?"
  
Answer: n (NO!)
  
Or: Just press Enter to skip
```

**Installation takes ~2-3 minutes:**

```
Installing dependencies...
Downloading Netdata...
Installing Netdata Agent...
Configuring auto-updates...
Starting Netdata service...

✅ Installation complete!
```

---

### **Verify Installation:**

```bash
# Check service status
systemctl status netdata

# Expected:
# Active: active (running)
# Memory: ~126 MB

# Check WebUI accessible
curl -s http://localhost:19999/api/v1/info | grep -i version

# Expected: version info JSON
```

---

### **WebUI Access:**

**Browser:**
```
http://192.168.0.109:19999

(Replace 192.168.0.109 with your Proxmox IP)
```

**Expected:**
- Dashboard loads ✅
- Metrics visible ✅
- Graphs updating in real-time ✅

---

## 🔒 Local-Only Setup (NO Cloud)

### **Why Local-Only?**

```
Privacy:
  ✅ NO data sent to Netdata Cloud
  ✅ NO external connections
  ✅ 100% local storage
  ✅ Complete control

Performance:
  ✅ No cloud overhead
  ✅ Faster response
  ✅ Less network usage
```

---

### **Check Cloud Status:**

```bash
# Proxmox host

# Check if claimed to cloud
cat /var/lib/netdata/cloud.d/claimed_id

# If file doesn't exist or empty → NOT claimed ✅
# If UUID present → Claimed (need to disconnect)
```

---

### **Disconnect from Cloud (if needed):**

**If claimed_id exists:**

```bash
# Stop Netdata
systemctl stop netdata

# Remove cloud claim files
rm -rf /var/lib/netdata/cloud.d/*
rm -f /var/lib/netdata/claim.d/*

# Create cloud disable config
mkdir -p /etc/netdata/cloud.d

cat > /etc/netdata/cloud.d/cloud.conf << 'EOF'
[cloud]
    enabled = no
    cloud base url =
EOF

# Start Netdata
systemctl start netdata

# Wait for startup
sleep 5

# Verify cloud disabled
curl -s http://localhost:19999/api/v1/info | grep -E '"cloud-(enabled|available)"'
```

**Note:** Even if `cloud-enabled: true` and `cloud-available: true`, if `claimed_id` doesn't exist, NO data is sent to cloud. This is normal and safe.

---

### **Verify Local-Only Operation:**

```bash
# Check no external connections
ss -tunp | grep netdata

# Expected: Only local port 19999 listening
# NO connections to port 443 (HTTPS/cloud)
```

---

### **WebUI Cloud Prompt:**

**First time accessing WebUI:**

```
Pop-up: "Welcome to Netdata - Please connect your agent"

Actions:
  1. Click "Sign out" (top right)
  2. Choose "Use anonymously"
  3. Dashboard loads ✅

Or: Close the pop-up (X button)
```

**Result:**
- Local-only dashboard ✅
- NO cloud connection ✅
- All features work ✅

---

## 🌐 WebUI Usage

### **Main Dashboard Overview:**

**URL:** `http://192.168.0.109:19999`

**Top Section (Overview):**

```
┌──────────────────────────────────────────────┐
│ CURRENTLY COLLECTED METRICS: 6,371           │
│                                              │
│ [Total 1] [Running 0] [Sending 0] [Archived 0]
└──────────────────────────────────────────────┘

Gauges (big circles):
  - Total CPU Read: Disk read rate
  - Total Disk Writes: Disk write rate
  - Avg CPU per Node: CPU percentage
  - Avg Used RAM per Node: Memory percentage
  - Total Network Inbound: RX traffic
  - Total Network Outbound: TX traffic
```

---

### **Left Sidebar Navigation:**

**Main Sections:**

```
🏠 Home
   - Dashboard overview
   
🖥️ System
   ├─ Compute (CPU metrics)
   ├─ Memory (RAM, swap, cache)
   ├─ Storage (Disk I/O)
   └─ Network (Interface traffic)
   
🐳 Containers & VMs
   ├─ LXC containers (100, 102, etc.)
   └─ Virtual Machines (101, etc.)
   
📦 Applications
   ├─ Docker (if detected)
   ├─ Databases (Postgres, MySQL)
   └─ Web servers (Nginx, Apache)
```

---

### **Top Menu Bar:**

```
📊 Nodes: All monitored hosts (only "pve" in single setup)
📈 Metrics: Browse all 6,371 metrics
🔝 Top: Top processes by CPU/RAM
📝 Logs: System logs (systemd journal)
📋 Dashboard: Custom dashboard builder
🚨 Alerts: Active alarms (0/0 = no alerts)
🎬 Events: System events timeline
🤖 Anomalies: Local anomaly detection
⚙️ Settings: Netdata configuration
```

---

### **Time Window Selector:**

**Top right corner:**

```
Presets:
  - Last 5 minutes
  - Last 15 minutes
  - Last hour
  - Last 6 hours
  - Last 12 hours
  - Last 24 hours ✅ (common)
  
Custom:
  - Click dates to set custom range
```

---

## 📊 Dashboard Navigation

### **1. CPU Metrics:**

**Navigation:** System → Compute → CPU

**Metrics visible:**

```
Total CPU Usage:
  - Aggregate percentage
  - Per-core breakdown
  - Real-time graph

CPU by Core:
  - CPU0: X%
  - CPU1: X%
  - CPU2: X%
  - CPU3: X%
  
CPU Temperature:
  - If sensors available
  - Per-core temps
  
CPU Frequency:
  - Current vs. max frequency
  - Frequency scaling events
```

**Graphs:**
- Line charts (real-time)
- 1-second granularity
- Color-coded by CPU state (user, system, iowait, etc.)

---

### **2. Memory Metrics:**

**Navigation:** System → Memory

**Metrics visible:**

```
Memory Usage Breakdown:
  - Used: Active application memory
  - Cache: File cache (can be freed)
  - Buffers: Disk buffers
  - Available: Real free memory
  - Swap: Swap usage ⚠️
  
Memory by Type:
  - Committed: Total committed memory
  - Active: Recently used pages
  - Inactive: Least recently used
  - Slab: Kernel slab allocations
```

**Important:**
- Green = Good (available memory)
- Yellow = Warning (>80% used)
- Red = Critical (>95% used)

---

### **3. Storage (Disk I/O):**

**Navigation:** System → Storage → Disk

**Metrics per disk:**

```
/dev/nvme0n1: (System disk)
  - Read rate (MB/s)
  - Write rate (MB/s)
  - I/O operations (IOPS)
  - Busy percentage
  - Await time
  
/dev/sda, sdb, sdc, sdd: (Data disks)
  - Same metrics as above
  - Compare with Scrutiny SMART data
```

**Graphs:**
- Read/Write rates (real-time)
- I/O wait time
- Disk utilization %

---

### **4. Network Traffic:**

**Navigation:** System → Network

**Metrics per interface:**

```
Physical Interfaces:
  enp*: Main Ethernet
    - Received (RX): Inbound traffic
    - Sent (TX): Outbound traffic
    - Packets/sec
    - Errors/Drops
    
Bridge Interfaces:
  vmbr0: Proxmox bridge
    - VM/LXC traffic aggregated
    
Virtual Interfaces:
  veth*: Per-LXC network
    - Individual container traffic
```

**Graphs:**
- Bandwidth usage (Mbit/s)
- Packet rates
- Error counters

---

### **5. Containers & VMs:**

**Navigation:** Containers & VMs → Click container/VM

**Per-container metrics:**

```
LXC 100 (docker-host):
  CPU:
    - Usage percentage
    - CPU time
    - Throttling events
    
  Memory:
    - Used/Available
    - Cache/Buffers
    - Swap usage ⚠️
    
  Disk:
    - Reads/Writes
    - I/O operations
    
  Network:
    - RX/TX traffic
    - Per veth interface
```

**Click container name to drill down!**

---

### **6. Top Processes:**

**Top Menu → Top**

**Views:**

```
By CPU:
  - Highest CPU consumers
  - Real-time updates
  - PID, user, command
  
By Memory:
  - Highest RAM consumers
  - Resident Set Size (RSS)
  - Shared memory
  
By Disk I/O:
  - Highest I/O generators
  - Read/Write rates
```

**Use case:** "Why is system slow?" → Check Top!

---

## 🔍 Interactive Features

### **Graph Interactions:**

**Zoom:**
```
Mouse: Click and drag to select time range
Result: Graph zooms to selection
Reset: Click "Reset zoom" button
```

**Pan:**
```
Mouse: Click and drag left/right (outside selection)
Result: Time window shifts
```

**Hover:**
```
Mouse: Hover over graph
Result: Tooltip shows exact values at that time
```

**Export:**
```
Right-click graph → Save image
Or: Screenshot tool
```

---

### **Metric Correlations:**

**Hold Shift + Click multiple graphs:**

```
Result:
  - All selected graphs highlighted
  - Time cursor synchronized
  - Correlate events across metrics
  
Example:
  CPU spike + Disk I/O spike + Network spike
  → Correlated event (e.g., backup running)
```

---

## 🚨 Alarms Configuration

### **Built-in Alarms:**

**Netdata includes pre-configured alarms:**

```
System:
  ✅ CPU usage > 90% (10 min)
  ✅ RAM usage > 95%
  ✅ Load average > cores * 2
  ✅ Disk usage > 90%
  ✅ Swap usage > 90%
  
Disk:
  ✅ Disk I/O errors
  ✅ Disk backlog > 10 sec
  ✅ Read/Write errors
  
Network:
  ✅ Interface errors/drops
  ✅ Packet loss
  ✅ High retransmits
  
Containers:
  ✅ Container CPU throttling
  ✅ Container OOM events
```

---

### **View Active Alarms:**

**Top Menu → Alerts**

```
Status:
  - Critical (red): Immediate action needed
  - Warning (yellow): Potential issue
  - Clear (green): No issues ✅
  
Alarm details:
  - Which metric triggered
  - Current value
  - Threshold exceeded
  - Duration
  - Last status change
```

---

### **Configure Alarm Notifications:**

**Email Alerts:**

```bash
# Proxmox host
nano /etc/netdata/health_alarm_notify.conf
```

**Edit these sections:**

```bash
# Enable email
SEND_EMAIL="YES"

# Recipient email
DEFAULT_RECIPIENT_EMAIL="your-email@gmail.com"

# Sender
EMAIL_SENDER="netdata@proxmox.local"

# SMTP settings (if custom)
SMTP_SERVER="smtp.gmail.com"
SMTP_PORT="587"
SMTP_USERNAME="your-email@gmail.com"
SMTP_PASSWORD="your-app-password"
```

**Restart Netdata:**

```bash
systemctl restart netdata
```

---

**Slack/Discord Webhooks:**

```bash
# In same file: /etc/netdata/health_alarm_notify.conf

# Slack
SEND_SLACK="YES"
SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
DEFAULT_RECIPIENT_SLACK="alarms"

# Discord
SEND_DISCORD="YES"
DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/YOUR_WEBHOOK_URL"
DEFAULT_RECIPIENT_DISCORD="alarms"
```

---

### **Custom Alarms:**

**Create custom alarm:**

```bash
# Create alarm file
nano /etc/netdata/health.d/custom.conf
```

**Example: Alert on high LXC 100 swap:**

```yaml
# LXC 100 Swap Usage Alarm
alarm: lxc100_high_swap
on: cgroup_docker-host.swap
lookup: average -5m unaligned of used
units: MB
every: 1m
warn: $this > 1500
crit: $this > 1800
info: LXC 100 swap usage is high
to: sysadmin
```

**Reload alarms:**

```bash
killall -USR2 netdata
```

---

## 🔗 Integration with Scrutiny

### **Complementary Monitoring:**

```
Netdata (System Monitoring):
  ✅ Real-time CPU, RAM, Network
  ✅ Disk I/O performance
  ✅ Container metrics
  ✅ 1-second granularity
  
Scrutiny (Disk Health):
  ✅ SMART attributes
  ✅ Disk temperature
  ✅ Failure prediction
  ✅ Hourly SMART scans
```

---

### **Combined Workflow:**

**Scenario 1: Disk Performance Issue**

```
1. Netdata → Storage → Disk
   - See high I/O wait
   - Identify which disk (/dev/sda)
   
2. Scrutiny → http://192.168.0.110:8082
   - Check /dev/sda SMART data
   - Reallocated sectors?
   - Pending sectors?
   - Temperature OK?
   
Result: Disk health vs. performance correlation
```

---

**Scenario 2: System Slowdown**

```
1. Netdata → Dashboard
   - CPU OK (~10%)
   - RAM OK (~40%)
   - Disk I/O → SPIKE! ⚠️
   
2. Netdata → Storage → Disk
   - /dev/sdc high utilization
   
3. Scrutiny → Dashboard
   - /dev/sdc temperature: 55°C (high!)
   
Result: Thermal throttling causing slowdown
```

---

### **Homepage Integration (Optional):**

**Add Netdata widget to Homepage dashboard:**

```yaml
# LXC 100: /srv/docker-data/homepage/services.yaml

- Monitoring:
    - Netdata:
        icon: netdata.png
        href: http://192.168.0.109:19999
        description: Real-time system monitoring
        widget:
          type: iframe
          url: http://192.168.0.109:19999
    
    - Scrutiny:
        icon: scrutiny.png
        href: http://192.168.0.110:8082
        description: Disk health monitoring
        widget:
          type: scrutiny
          url: http://192.168.0.110:8082
```

---

## 🔧 Troubleshooting

### **Problem: WebUI not accessible**

**Check service:**

```bash
# Proxmox host
systemctl status netdata

# If inactive:
systemctl start netdata

# If failed:
journalctl -u netdata -n 50
```

---

**Check port:**

```bash
# Is port 19999 listening?
ss -tulpn | grep 19999

# Expected:
# tcp LISTEN 0.0.0.0:19999

# If not, check firewall:
iptables -L | grep 19999
```

---

**Test locally:**

```bash
# Proxmox host
curl http://localhost:19999

# Should return HTML
```

---

### **Problem: No metrics showing**

**Check plugins:**

```bash
# List running plugins
ps aux | grep netdata | grep plugin

# Expected: Many plugin processes
```

---

**Check logs:**

```bash
journalctl -u netdata -f

# Look for errors like:
# "plugin disabled"
# "permission denied"
```

---

**Restart Netdata:**

```bash
systemctl restart netdata

# Wait 10 seconds
sleep 10

# Check WebUI
```

---

### **Problem: High memory usage**

**Check retention:**

```bash
# Proxmox host
nano /etc/netdata/netdata.conf
```

**Adjust retention:**

```ini
[db]
    # Reduce retention to lower memory
    # Default: 3600 seconds (1 hour)
    retention = 3600
    
    # Or more aggressive:
    retention = 1800  # 30 minutes
```

**Restart:**

```bash
systemctl restart netdata
```

---

### **Problem: Cloud connection warnings**

**Even after disabling cloud:**

**Check:**

```bash
cat /var/lib/netdata/cloud.d/claimed_id

# If file doesn't exist → Good! ✅
# If UUID present → Follow "Local-Only Setup" section
```

---

**Verify no external connections:**

```bash
ss -tunp | grep netdata

# Should show ONLY:
# - Local port 19999 listening
# - NO connections to port 443
```

---

## 📋 Best Practices

### **Daily Usage:**

```
Morning check (~30 seconds):
  1. Open http://192.168.0.109:19999
  2. Glance at top gauges
     - CPU < 80%? ✅
     - RAM < 80%? ✅
     - Network traffic normal? ✅
  3. Check Alerts (top bar)
     - 0/0? ✅ All good!
  4. Close tab
```

---

### **Troubleshooting Workflow:**

```
Issue: "System is slow"

Steps:
  1. Netdata → Dashboard
     - Which metric is high?
     
  2. CPU high?
     → Top → By CPU
     → Identify process
     
  3. RAM high?
     → System → Memory
     → Check swap usage
     → Containers & VMs → Which container?
     
  4. Disk I/O high?
     → Storage → Disk
     → Which disk?
     → Scrutiny → Check SMART
     
  5. Network high?
     → Network → Interfaces
     → Which container generating traffic?
```

---

### **Performance Tuning:**

**Reduce resource usage:**

```bash
# /etc/netdata/netdata.conf

[global]
    # Update every 2 seconds instead of 1
    update every = 2
    
[db]
    # Reduce retention to 30 minutes
    retention = 1800
    
[plugins]
    # Disable unused plugins
    python.d = no  # If not using Python plugins
```

**Restart:**

```bash
systemctl restart netdata
```

---

### **Security:**

**Restrict access (optional):**

```bash
# /etc/netdata/netdata.conf

[web]
    # Bind only to localhost (access via SSH tunnel)
    bind to = localhost
    
    # Or specific IP
    bind to = 192.168.0.109
    
    # Allow only specific IPs
    allow connections from = localhost 192.168.0.*
```

---

**Enable HTTPS (optional):**

```bash
# Generate self-signed cert
openssl req -newkey rsa:2048 -nodes -keyout /etc/netdata/ssl/key.pem -x509 -days 365 -out /etc/netdata/ssl/cert.pem

# /etc/netdata/netdata.conf
[web]
    ssl key = /etc/netdata/ssl/key.pem
    ssl certificate = /etc/netdata/ssl/cert.pem
```

**Restart:**

```bash
systemctl restart netdata

# Access via HTTPS
https://192.168.0.109:19999
```

---

### **Backup Configuration:**

```bash
# Backup Netdata config
tar -czf netdata-config-backup.tar.gz /etc/netdata/

# Backup to safe location
mv netdata-config-backup.tar.gz /mnt/storage/backups/
```

---

### **Updates:**

**Netdata auto-updates by default!**

```
Auto-update:
  - Enabled during installation
  - Checks daily via cron
  - Updates to latest stable
  
Verify:
  ls -la /etc/cron.daily/netdata-updater
  
Disable (not recommended):
  rm /etc/cron.daily/netdata-updater
```

**Manual update:**

```bash
/usr/libexec/netdata/netdata-updater.sh
```

---

## 📊 Monitoring Checklist

### **System Health (Daily):**

```
☑ CPU usage < 80% average
☑ RAM usage < 80%
☑ Swap usage < 10% ⚠️
☑ Disk usage < 90%
☑ No active alarms (0/0)
☑ All metrics updating (real-time)
☑ Network traffic expected
```

---

### **Container Health (Daily):**

```
☑ LXC 100 (docker-host):
   - CPU < 50%
   - RAM < 80%
   - Swap < 10% ⚠️ (currently 95%!)
   
☑ LXC 102 (adguard):
   - Normal operation
   
☑ VM 101 (homeassistant):
   - Normal operation
```

---

### **Disk Performance (Weekly):**

```
☑ Netdata → Storage → Disk
   - No sustained high I/O wait
   - No error counters increasing
   
☑ Scrutiny → http://192.168.0.110:8082
   - All disks: Passed status
   - Temperatures < 50°C
   - No reallocated sectors
```

---

## 🎯 Quick Reference

### **Important URLs:**

```
Netdata WebUI:
  http://192.168.0.109:19999

Scrutiny WebUI:
  http://192.168.0.110:8082

Netdata API:
  http://192.168.0.109:19999/api/v1/info
```

---

### **Important Files:**

```
Main config:
  /etc/netdata/netdata.conf

Alarms:
  /etc/netdata/health.d/*.conf

Alarm notifications:
  /etc/netdata/health_alarm_notify.conf

Plugins:
  /usr/libexec/netdata/plugins.d/

Data storage:
  /var/cache/netdata/

Logs:
  journalctl -u netdata
```

---

### **Common Commands:**

```bash
# Service control
systemctl status netdata
systemctl start netdata
systemctl stop netdata
systemctl restart netdata

# Check version
netdata -V

# Test config
netdata -W unittest

# Update manually
/usr/libexec/netdata/netdata-updater.sh

# View logs
journalctl -u netdata -f

# Check ports
ss -tulpn | grep 19999

# Memory usage
ps aux | grep netdata | grep -v grep
```

---

## ✅ Success Indicators

**Your Netdata setup is working correctly when:**

```
✅ WebUI accessible: http://192.168.0.109:19999
✅ Dashboard shows real-time metrics
✅ All gauges updating (1 sec refresh)
✅ Containers & VMs visible
✅ No active alarms (or expected alarms only)
✅ Graphs respond to zoom/pan
✅ claimed_id file doesn't exist (local-only)
✅ No external connections (ss shows only local port)
✅ Memory usage reasonable (~150-200 MB)
✅ Service auto-starts on boot
```

---

## 🏆 Complete Monitoring Stack

```
┌─────────────────────────────────────────────┐
│ Proxmox Host (192.168.0.109)                │
│                                             │
│ ✅ Netdata (System Monitoring)             │
│    http://192.168.0.109:19999              │
│    - Real-time metrics (1 sec)             │
│    - CPU, RAM, Network, Disk I/O           │
│    - Container/VM metrics                  │
│    - 6,371 metrics                         │
│    - Local only (NO cloud!)                │
│                                             │
│ ✅ Scrutiny Collector (Disk Health)        │
│    - SMART data collection                 │
│    - 5 disks monitored                     │
│    - Hourly updates                        │
└─────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────┐
│ LXC 100 (192.168.0.110)                     │
│                                             │
│ ✅ Scrutiny Server (Disk Dashboard)        │
│    http://192.168.0.110:8082               │
│    - SMART attributes                      │
│    - Temperature trends                    │
│    - Health predictions                    │
└─────────────────────────────────────────────┘

COMPLETE MONITORING! 🎉
  - System performance: Netdata ⚡
  - Disk health: Scrutiny 💾
  - 100% local, 100% privacy 🔒
```

---

**Prepared:** 2025-12-30  
**Version:** 1.0  
**Tested:** Proxmox VE 8.x  
**Netdata Version:** 2.8.0-161-nightly

**ENJOY REAL-TIME MONITORING WITH NETDATA!** 📊✨
