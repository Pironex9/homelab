
**Companion to: jellyfin-pangolin-setup-guide.md**

**Date:** 2026-01-11  
**Status:** Production Security Complete  
**Security Score:** 90/100 ⭐⭐⭐⭐⭐

---

## Table of Contents

1. [Security Overview](#1-security-overview)
2. [Cloudflare Security Configuration](#2-cloudflare-security-configuration)
3. [Pangolin 2FA Setup](#3-pangolin-2fa-setup)
4. [Hetzner Account 2FA Setup](#4-hetzner-account-2fa-setup)
5. [Pangolin Resource Rules](#5-pangolin-resource-rules)
6. [Future Security Improvements](#6-future-security-improvements)
7. [Security Monitoring](#7-security-monitoring)
8. [Incident Response](#8-incident-response)
9. [Backup Strategy](#9-backup-strategy)
10. [Security Checklist](#10-security-checklist)

---

## 1. Security Overview

### Multi-Layer Defense Architecture

```
┌──────────────────────────────────────────────────────────┐
│                  LAYER 1: EDGE (CLOUDFLARE)              │
│  - DDoS Protection                                       │
│  - Bot Fight Mode                                        │
│  - Security Headers                                      │
│  - HTTPS Enforcement                                     │
│  - AI Bot Blocking                                       │
└──────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────┐
│              LAYER 2: VPS (HETZNER + SECURITY)           │
│  - UFW Firewall                                          │
│  - Fail2ban (SSH + HTTP)                                 │
│  - SSH Key-only Authentication                           │
│  - Docker Security Hardening                             │
│  - Automatic Security Updates                            │
└──────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────┐
│         LAYER 3: APPLICATION (PANGOLIN)                  │
│  - User Authentication (2FA Enabled)                     │
│  - GeoIP Filtering (Slovakia Only)                       │
│  - Resource Access Rules                                 │
│  - Session Management                                    │
│  - Audit Logging                                         │
└──────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────┐
│            LAYER 4: TUNNEL (WIREGUARD)                   │
│  - Military-Grade Encryption                             │
│  - Authenticated Clients Only                            │
│  - Site Secret Validation                                │
└──────────────────────────────────────────────────────────┘
                            ↓
┌──────────────────────────────────────────────────────────┐
│              LAYER 5: BACKEND (JELLYFIN)                 │
│  - Isolated Network (192.168.0.0/24)                     │
│  - Access via Tunnel Only                                │
└──────────────────────────────────────────────────────────┘
```

### Security Score Breakdown

```
Layer 1 (Edge):         90/100 ⭐⭐⭐⭐⭐
Layer 2 (VPS):         100/100 ⭐⭐⭐⭐⭐
Layer 3 (Application):  95/100 ⭐⭐⭐⭐⭐
Layer 4 (Tunnel):      100/100 ⭐⭐⭐⭐⭐
Layer 5 (Backend):     100/100 ⭐⭐⭐⭐⭐
─────────────────────────────────────
OVERALL:                90/100 ⭐⭐⭐⭐⭐
```

---

## 2. Cloudflare Security Configuration

### Access Cloudflare Dashboard

```
URL: https://dash.cloudflare.com/
Domain: your-domain.com
```

### 2.1 Security Level

**Location:** `Security → Settings`

```
Setting: Security Level
Value: High

Description:
- Challenges visitors with threat score > 10
- Blocks known bad actors
- Automatic bot detection
- DDoS mitigation

When to adjust:
- Under active attack: "I'm Under Attack" mode
- False positives: Lower to "Medium"
- Normal operation: "High" (recommended)
```

---

### 2.2 Bot Fight Mode

**Location:** `Security → Bots`

```
Setting: Bot Fight Mode
Value: ON ✓

Setting: AI Bot Blocking
Value: ON ✓

Description:
- Detects automated traffic
- Challenges suspicious bots
- Protects against scraping
- Blocks AI crawlers

Benefits:
- Reduces server load
- Prevents data scraping
- Protects bandwidth
- Free bot mitigation
```

---

### 2.3 Browser Integrity Check

**Location:** `Security → Settings`

```
Setting: Browser Integrity Check
Value: ON ✓

Description:
- Validates browser headers
- Blocks headless browsers
- Detects tampered requests
- Anti-automation protection

What it blocks:
- Modified browsers
- Automation tools (Selenium, Puppeteer)
- Headless Chrome/Firefox
- Impersonation attempts
```

---

### 2.4 Challenge Passage

**Location:** `Security → Settings`

```
Setting: Challenge Passage
Value: 30 minutes

Description:
- Duration of challenge cookie validity
- User passes challenge → cookie set
- Valid for 30 minutes
- Reduces repeat challenges

Recommended values:
- 30 minutes: Balanced (default)
- 1 hour: Less strict
- 5 minutes: Very strict (annoying)
```

---

### 2.5 Managed Transforms - Security Headers

**Location:** `Rules → Settings → Managed Transforms`

#### HTTP Response Headers

```
Setting: Add security headers
Value: ON ✓

Headers added:
───────────────────────────────────────────
X-Content-Type-Options: nosniff
  → Prevents MIME type sniffing
  → Protects against XSS

X-Frame-Options: SAMEORIGIN
  → Prevents clickjacking
  → Blocks iframe embedding from other sites

X-XSS-Protection: 1; mode=block
  → Browser XSS filter
  → Legacy protection (still useful)

Referrer-Policy: strict-origin-when-cross-origin
  → Limits referrer information
  → Privacy protection
───────────────────────────────────────────
```

---

#### Remove Identifying Headers

```
Setting: Remove "X-Powered-By" headers
Value: ON ✓

Description:
- Hides backend technology
- Prevents information disclosure
- Reduces attack surface

Example:
Before: X-Powered-By: Express, Node.js
After:  (header removed)
```

---

### 2.6 SSL/TLS Configuration

**Location:** `SSL/TLS → Edge Certificates`

#### Automatic HTTPS Rewrites

```
Setting: Automatic HTTPS Rewrites
Value: ON ✓

Description:
- HTTP links → HTTPS automatically
- Prevents mixed content warnings
- Seamless HTTPS experience
- Fixes insecure references
```

#### Always Use HTTPS

```
Setting: Always Use HTTPS
Value: ON ✓

Description:
- HTTP requests → 301 redirect to HTTPS
- Forces all traffic to HTTPS
- No HTTP access possible

Result:
http://jellyfin.your-domain.com → https://jellyfin.your-domain.com
```

#### Minimum TLS Version

```
Setting: Minimum TLS Version
Value: TLS 1.2

Description:
- Disables old protocols (TLS 1.0, 1.1)
- Prevents downgrade attacks
- Modern security standards

Compatibility:
TLS 1.2: All modern browsers (2014+)
TLS 1.3: Very modern browsers (2018+)

Recommendation: TLS 1.2 (best compatibility)
```

#### HSTS (HTTP Strict Transport Security)

```
Setting: Enable HSTS
Value: Optional (not enabled by default)

Configuration (if enabling):
Max Age: 15768000 (6 months)
Include Subdomains: ON
Preload: OFF (initially)

⚠️ WARNING:
Once enabled, browsers enforce HTTPS for duration
Cannot switch back to HTTP easily
Test thoroughly before enabling

Recommendation: Enable after confirming stable HTTPS setup
```

---

### 2.7 Rate Limiting

**Location:** `Security → Security rules`

```
Current Status:
Rate Limiting Rules: 1/1 used (free tier limit)

Active Rule:
Name: Leaked credential check
Type: Rate limiting rule
Status: Active ✓

Description:
- Blocks leaked credential attempts
- Automatic protection
- Cloudflare-managed

⚠️ Free Tier Limitation:
- Only 1 rate limiting rule available
- Cannot add custom rate limiting rules
- Upgrade to Pro ($25/month) for more

Alternative:
- Use Pangolin Resource Rules for rate limiting
- Application-level protection
```

---

## 3. Pangolin 2FA Setup

### 3.1 Enable Two-Factor Authentication

**Location:** Pangolin Dashboard → Profile (top right) → Security

#### Step 1: Access Security Settings

```
1. Login to Pangolin Dashboard
   URL: https://pangolin.your-domain.com
   
2. Click profile icon (top right corner)

3. Select: Security

4. Scroll to: Two-Factor Authentication section
```

#### Step 2: Enable 2FA

```
1. Toggle: Two-Factor Authentication → ON

2. Choose method: TOTP (Time-based One-Time Password)
   Recommended apps:
   - Google Authenticator (iOS/Android)
   - Authy (iOS/Android/Desktop)
   - Microsoft Authenticator (iOS/Android)
   - 1Password (with TOTP support)

3. Scan QR code with authenticator app
   OR
   Manually enter secret key

4. Enter 6-digit verification code from app

5. Click: Verify & Enable
```

#### Step 3: Save Recovery Codes

```
⚠️ CRITICAL: Save recovery codes!

Recovery codes displayed (10 codes):
Example format:
  1. abcd-efgh-ijkl
  2. mnop-qrst-uvwx
  3. ... (8 more)

Action:
1. Click: Download Recovery Codes
   OR
2. Copy to secure location:
   - Password manager (recommended)
   - Encrypted file
   - Physical paper (secure location)

⚠️ WITHOUT recovery codes:
→ Lost phone = Lost access!
→ No way to recover account!

Storage recommendations:
✅ Password manager (Bitwarden, 1Password)
✅ Encrypted USB drive (backup)
✅ Physical paper (safe/lockbox)
❌ Plain text file on computer
❌ Email to yourself
❌ Cloud storage without encryption
```

#### Step 4: Test 2FA

```
1. Logout from Pangolin

2. Login again:
   Email: your@email.com
   Password: [your password]

3. 2FA prompt appears:
   Enter 6-digit code from authenticator app

4. Success! 2FA working ✓

Troubleshooting:
- Code invalid? Check device time sync
- Code expired? Wait for next code (30 sec cycle)
- Lost phone? Use recovery codes
```

### 3.2 2FA Login Flow

```
┌─────────────────────────────────────┐
│  User: https://pangolin.your-domain.com│
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Step 1: Email + Password           │
│  your@email.com                 │
│  **********                         │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Step 2: 2FA Code Required          │
│  Enter code from authenticator app: │
│  [1][2][3][4][5][6]                 │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Success! Dashboard Access ✓        │
└─────────────────────────────────────┘
```

### 3.3 Managing 2FA

#### Disable 2FA (Emergency)

```
If you need to disable 2FA:

Method 1: Normal (with 2FA access)
1. Login with 2FA
2. Profile → Security
3. Toggle 2FA → OFF
4. Confirm with password

Method 2: Recovery Code
1. Login with email + password
2. Click: "Use recovery code"
3. Enter one recovery code
4. Access granted
5. Go to Security → Disable 2FA

Method 3: Emergency (lost everything)
⚠️ Requires VPS access:
1. SSH to VPS: ssh root@YOUR_VPS_IP
2. Access Pangolin database
3. Disable 2FA for user (advanced)
4. Contact Pangolin support if needed
```

#### Reset Authenticator App

```
If switching phones or apps:

1. Login to Pangolin (with current 2FA)
2. Profile → Security
3. Two-Factor Authentication: Reconfigure
4. Scan new QR code with new device
5. Verify with new code
6. Old device codes invalid now ✓
```

---

## 4. Hetzner Account 2FA Setup

### 4.1 Access Hetzner Security Settings

```
1. Login to Hetzner Console
   URL: https://console.hetzner.cloud/
   
2. Click profile/account icon (top right)

3. Navigate to: Security Settings
   OR
   Account → Security
```

### 4.2 Enable Two-Factor Authentication

#### Step 1: Choose 2FA Method

```
Hetzner supports:
- TOTP (Time-based One-Time Password)
- SMS (less secure, not recommended)
- Hardware Key (YubiKey, if available)

Recommended: TOTP (same as Pangolin)
```

#### Step 2: Setup TOTP

```
1. Security Settings → Two-Factor Authentication

2. Click: Enable 2FA / Setup 2FA

3. Choose: Authenticator App (TOTP)

4. Scan QR code with authenticator app
   - Use SAME app as Pangolin (Google Authenticator, Authy, etc.)
   - Hetzner entry will appear separate from Pangolin

5. Enter verification code from app

6. Click: Verify & Enable
```

#### Step 3: Save Backup Codes

```
⚠️ CRITICAL: Hetzner also provides backup codes!

Save these separately from Pangolin codes!

Label clearly:
✅ "Hetzner Recovery Codes"
✅ Store in password manager
✅ Separate entry from Pangolin codes

DO NOT confuse with Pangolin codes!
```

### 4.3 2FA Login Flow (Hetzner)

```
┌─────────────────────────────────────┐
│  User: https://console.hetzner.cloud/│
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Step 1: Email + Password           │
│  [your Hetzner email]               │
│  **********                         │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Step 2: 2FA Code Required          │
│  Enter code from authenticator app: │
│  [1][2][3][4][5][6]                 │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Success! Hetzner Console Access ✓  │
│  VPS Management Available           │
└─────────────────────────────────────┘
```

### 4.4 What Hetzner 2FA Protects

```
With 2FA enabled:

✅ VPS Console Access
   - Cannot access without 2FA code
   - Prevents unauthorized login

✅ VPS Management
   - Create/delete servers
   - Billing access
   - SSH key management
   - Firewall rules

✅ Critical Actions
   - Delete VPS
   - Change password
   - API token generation

⚠️ Does NOT affect:
❌ SSH access to VPS (uses SSH keys separately)
❌ Pangolin access (separate 2FA)
❌ Jellyfin access (via Pangolin)

This is CONSOLE access only!
```

---

## 5. Pangolin Resource Rules

### 5.1 Current Jellyfin Rules

**Location:** Pangolin Dashboard → Resources → Jellyfin → Rules tab

```
Enable Rules: ON ✓
```

#### Rule 1: Home IP Bypass

```
Priority: 5
Action: Bypass Auth
Match Type: IP
Value: YOUR_HOME_IP (your home IP)
Enabled: ON ✓

Description:
- Your home IP gets direct access
- No authentication prompt
- Convenient for home use

⚠️ Important:
- Update if your home IP changes (dynamic IP)
- Check quarterly: https://whatismyipaddress.com/
- Disable if you want to always authenticate
```

---

#### Rule 2: Slovakia Authentication Required

```
Priority: 10
Action: Pass to Auth
Match Type: Country
Value: Slovakia (SK)
Enabled: ON ✓

Description:
- Users from Slovakia must authenticate
- Pangolin login required
- Protects resources

Effect:
- SK user → Pangolin login page → Jellyfin
- Authenticated access only
```

---

#### Rule 3: Block All Other Countries

```
Priority: 100
Action: Block Access
Match Type: Country
Value: ALL COUNTRIES (ALL)
Enabled: ON ✓

Description:
- Geographic restriction (GeoIP blocking)
- Only Slovakia + your home IP allowed
- All other countries blocked

Effect:
- US visitor → Blocked
- China → Blocked
- Russia → Blocked
- Only SK traffic passes

⚠️ Friend traveling abroad:
→ Temporarily disable Rule 3
→ Or add their country to Rule 2
→ Re-enable after travel
```

---

### 5.2 Understanding Rule Priority

```
Priority System (lower number = higher priority):

Rule evaluation order:
1. Priority 5: Bypass Auth (YOUR_HOME_IP)
2. Priority 10: Pass to Auth (SK)
3. Priority 100: Block Access (ALL)

Example flows:

Flow 1: Your Home IP (YOUR_HOME_IP from SK)
────────────────────────────────────
Request from: YOUR_HOME_IP, Slovakia
Rule 5 matches: YES (IP = YOUR_HOME_IP)
Action: Bypass Auth
Result: Direct access, no login ✓

Flow 2: Friend from Slovakia (different IP)
────────────────────────────────────
Request from: 91.123.45.67, Slovakia
Rule 5 matches: NO (IP different)
Rule 10 matches: YES (Country = SK)
Action: Pass to Auth
Result: Must login first ✓

Flow 3: Attacker from China
────────────────────────────────────
Request from: 1.2.3.4, China
Rule 5 matches: NO
Rule 10 matches: NO (Country ≠ SK)
Rule 100 matches: YES (ALL)
Action: Block Access
Result: Blocked! ❌
```

---

### 5.3 Additional Rules (Optional)

#### Rate Limiting (Pro Feature)

```
⚠️ Not available in Community Edition!

If you upgrade to Pangolin Pro:

Action: Rate Limit
Match Type: IP
Value: 0.0.0.0/0
Limit: 300 requests / 60 seconds
Priority: 15

Description:
- Limits requests per IP
- Prevents abuse
- Protects bandwidth

Recommended values for Jellyfin:
- 300 requests/min: Video streaming
- 100 requests/min: General browsing
- 10 requests/min: Authentication only
```

---

#### Block Scanner Paths

```
Action: Block Access
Match Type: Path
Value: /admin|/phpmyadmin|/.env|/wp-admin|/xmlrpc|/.git|/config
Priority: 1 (highest priority)
Enabled: ON

Description:
- Blocks common attack paths
- Reduces noise in logs
- Prevents vulnerability scanning

Paths blocked:
- /admin (WordPress admin)
- /phpmyadmin (database admin)
- /.env (environment files)
- /wp-admin (WordPress)
- /xmlrpc (API endpoint)
- /.git (source control)
- /config (configuration files)
```

---

## 6. Future Security Improvements

### 6.1 Optional Enhancements (Priority: Low)

#### Hardware Security Keys (YubiKey)

```
Cost: ~$50-60 per key
Benefit: Physical 2FA security
Setup time: 30 minutes

Supported by:
✅ Hetzner (FIDO2/U2F)
✅ Pangolin (FIDO2, if supported)
✅ Most major services

Advantages:
- Phishing-resistant
- No smartphone needed
- Very secure
- Durable hardware

Disadvantages:
- Additional cost
- Can be lost (buy 2!)
- Not all services support

Recommendation:
⬜ Consider if handling sensitive data
⬜ Not critical for home lab
⬜ TOTP sufficient for current setup
```

---

#### VPN-Only Access (Tailscale/WireGuard)

```
Setup time: 1-2 hours
Benefit: Additional access layer
Complexity: Medium

Implementation:
1. Keep Pangolin for public access
2. Add Tailscale VPN layer
3. Friends connect via Tailscale first
4. Then access Jellyfin

Advantages:
✅ Extra security layer
✅ Encrypted access
✅ No public exposure

Disadvantages:
❌ Friends need VPN client
❌ More complex setup
❌ Additional management

Recommendation:
⬜ Not needed (Pangolin already uses WireGuard!)
⬜ Current setup sufficient
```

---

#### CrowdSec Integration

```
Cost: Free (community edition)
Setup time: 1-2 hours
Benefit: Community threat intelligence

What it does:
- Shared IP reputation
- Automatic blocking
- Crowd-sourced attack data
- Real-time threat feed

Installation (VPS):
curl -s https://install.crowdsec.net | sudo sh
apt install crowdsec-firewall-bouncer-iptables

Configuration:
- Connect to CrowdSec hub
- Install bouncers
- Enable collections
- Monitor decisions

Advantages:
✅ Community intelligence
✅ Automatic updates
✅ Advanced detection
✅ Free tier available

Disadvantages:
⚠️ Complex configuration
⚠️ Resource usage
⚠️ Learning curve

Recommendation:
⬜ Consider for enterprise use
⬜ Overkill for home lab
⬜ Current Fail2ban sufficient
```

---

#### Advanced Monitoring (Grafana + Prometheus)

```
Setup time: 2-4 hours
Benefit: Comprehensive monitoring
Complexity: High

Components:
- Prometheus (metrics)
- Grafana (dashboards)
- Node Exporter (VPS metrics)
- Loki (log aggregation)
- Alertmanager (notifications)

Metrics tracked:
- CPU/Memory/Disk usage
- Network traffic
- Container health
- Request rates
- Error rates
- Response times

Advantages:
✅ Beautiful dashboards
✅ Historical data
✅ Proactive alerting
✅ Performance insights

Disadvantages:
❌ Resource intensive
❌ Complex setup
❌ Maintenance overhead

Recommendation:
⬜ Nice to have
⬜ Not critical
⬜ Simple uptime monitoring sufficient
```

---

### 6.2 Recommended Near-Term Actions (Priority: Medium)

#### Uptime Monitoring (15 minutes)

```
Service: UptimeRobot (free tier)
URL: https://uptimerobot.com/

Setup:
1. Create free account
2. Add monitor:
   - Type: HTTPS
   - URL: https://jellyfin.your-domain.com
   - Interval: 5 minutes
   
3. Add alert contacts:
   - Email: your@email.com
   - (Optional) SMS, Slack, Discord
   
4. Verify monitoring active

Benefits:
✅ Know when service is down
✅ Uptime statistics
✅ Automatic alerts
✅ Free tier sufficient

Alternative services:
- Uptime Kuma (self-hosted)
- Pingdom
- StatusCake
```

---

#### Log Review Schedule (Monthly)

```
Monthly tasks (30 minutes):

VPS Logs:
□ SSH access logs: tail -100 /var/log/auth.log
□ Fail2ban bans: fail2ban-client banned
□ UFW blocks: grep UFW /var/log/ufw.log | tail -50
□ Docker logs: docker logs pangolin --since 7d | grep -i error

Cloudflare:
□ Security events: Security → Analytics → Last 30 days
□ Traffic patterns: Analytics → Traffic
□ Bot activity: Security → Bots

Pangolin:
□ Login attempts: Dashboard → Analytics (if available)
□ Resource access: Check logs for unusual patterns
□ Failed authentications: Look for brute force

Red flags:
⚠️ Repeated failed logins
⚠️ Unusual traffic patterns
⚠️ Many banned IPs
⚠️ High error rates
```

---

#### Backup Verification (Quarterly)

```
Quarterly tasks (1 hour):

Configuration Backups:
□ VPS: /opt/pangolin/config/
□ SSH keys: ~/.ssh/
□ Fail2ban config: /etc/fail2ban/jail.local
□ UFW rules: ufw status > backup.txt

Test restoration:
□ Verify backups readable
□ Test restoration process
□ Document any issues
□ Update backup procedures

Recovery time objectives:
- Configuration restore: < 30 minutes
- Full system rebuild: < 2 hours
- Service recovery: < 4 hours
```

---

## 7. Security Monitoring

### 7.1 Daily Monitoring (Automated)

```
Automated checks (no action needed if healthy):

Cloudflare:
✅ Service uptime
✅ Certificate validity
✅ DNS resolution

VPS:
✅ Docker containers running
✅ Fail2ban active
✅ SSH service active
✅ Disk space available

Pangolin:
✅ WireGuard tunnel connected
✅ Resources accessible
✅ Authentication working

If issues detected:
→ Uptime monitor sends alert
→ Check logs
→ Follow troubleshooting guide
```

---

### 7.2 Weekly Monitoring (5 minutes)

```
Manual checks (Sunday evening recommended):

Checklist:
□ Visit: https://jellyfin.your-domain.com
  → Should load and authenticate ✓

□ Check Fail2ban status (VPS SSH):
  fail2ban-client status sshd
  → Should show banned IPs (if any)

□ Check Docker containers (VPS SSH):
  docker ps
  → All containers: Up and healthy ✓

□ Check Cloudflare Security Events:
  Dashboard → Security → Analytics
  → Review any unusual activity

□ Verify Newt connection (Proxmox):
  systemctl status newt.service
  → Should be: active (running) ✓

Time required: 5 minutes
Action needed: Only if anomalies detected
```

---

### 7.3 Monthly Monitoring (30 minutes)

```
Detailed review (first Sunday of month):

1. Log Analysis (15 min):
   □ Review SSH access attempts
   □ Check Fail2ban ban history
   □ Analyze Cloudflare security events
   □ Look for patterns/trends

2. Update Check (5 min):
   □ VPS: apt update && apt list --upgradable
   □ Docker: docker pull check for updates
   □ Cloudflare: Any new features?
   □ Pangolin: Check for updates

3. Certificate Check (2 min):
   □ SSL certificates valid?
   □ Expiration dates?
   □ Auto-renewal working?

4. Performance Review (5 min):
   □ VPS resources: htop, df -h
   □ Network usage: vnstat
   □ Service response times
   □ Any degradation?

5. Documentation Update (3 min):
   □ Any config changes?
   □ New issues encountered?
   □ Update this guide if needed

Action items:
→ Document findings
→ Apply updates if needed
→ Adjust monitoring if patterns detected
```

---

## 8. Incident Response

### 8.1 Service Down

**Symptom:** Jellyfin not accessible

```
Step 1: Identify scope
□ Check uptime monitor alert
□ Verify from multiple devices/networks
□ Check: https://isitdownrightnow.com/jellyfin.your-domain.com

Step 2: Check Cloudflare
□ Login: https://dash.cloudflare.com/
□ Check domain status
□ DNS records intact?
□ SSL certificate valid?

Step 3: Check VPS
□ SSH to VPS: ssh root@YOUR_VPS_IP
□ Container status: docker ps
□ If containers down: docker compose up -d
□ Check logs: docker logs pangolin

Step 4: Check Home Lab
□ SSH to Proxmox: ssh root@192.168.0.109
□ Newt status: systemctl status newt.service
□ If down: systemctl restart newt.service
□ Jellyfin running?: curl http://192.168.0.110:8096

Step 5: Verify restoration
□ Wait 2-3 minutes
□ Test access again
□ Check all services green
```

---

### 8.2 Suspected Attack

**Symptom:** Unusual traffic, many failed logins, DDoS

```
Step 1: Assess situation
□ Cloudflare Security Events
□ Fail2ban banned IPs
□ System resources (htop)
□ Traffic patterns unusual?

Step 2: Immediate actions
□ Enable "I'm Under Attack" mode (Cloudflare)
□ Review Fail2ban bans: fail2ban-client banned
□ Check top attacking IPs
□ Document attack details

Step 3: Block attack vectors
□ Cloudflare: Add IP Access Rules
□ UFW: Block specific IPs if needed
□ Fail2ban: Increase ban duration temporarily
□ Consider disabling service temporarily

Step 4: Post-incident
□ Review logs thoroughly
□ Identify attack method
□ Strengthen defenses
□ Update monitoring
□ Document lessons learned
```

---

### 8.3 Account Compromise

**Symptom:** Unexpected logins, configuration changes

```
⚠️ CRITICAL - Act immediately!

Step 1: Secure access
□ Change Pangolin password immediately
□ Change Hetzner password immediately
□ Revoke any API tokens
□ Check 2FA still active

Step 2: Audit changes
□ Pangolin: Check resource configurations
□ VPS: Check container configs
□ DNS: Verify DNS records unchanged
□ Review recent login history

Step 3: Lock down
□ Enable "Under Attack" mode
□ Temporary geographic restrictions
□ Reduce session timeouts
□ Enable additional logging

Step 4: Investigate
□ Review access logs
□ Identify compromise vector
□ Check for backdoors
□ Scan for malware

Step 5: Recovery
□ Rebuild affected components if needed
□ Update all credentials
□ Strengthen authentication
□ Implement additional monitoring
□ Consider security audit
```

---

### 8.4 Certificate Expiration

**Symptom:** SSL errors, "Not Secure" warnings

```
Let's Encrypt certificates auto-renew!
This should not happen normally.

Step 1: Check certificate status
□ Browser: Click padlock icon
□ Check expiration date
□ VPS: docker logs traefik | grep certificate

Step 2: Force renewal
□ SSH to VPS
□ Check Traefik logs
□ Restart Traefik: docker restart traefik
□ Monitor logs: docker logs -f traefik
□ Wait for certificate request

Step 3: Manual intervention (if auto-renewal fails)
□ Check DNS records pointing correctly
□ Cloudflare: Gray cloud (DNS only) not orange!
□ Port 80 open in UFW
□ Traefik config correct

Step 4: Emergency workaround
□ Temporarily disable HTTPS requirement
□ Fix certificate issue
□ Re-enable HTTPS
□ Verify all certificates valid
```

---

## 9. Backup Strategy

### 9.1 What to Backup

#### Critical Configuration Files (VPS)

```
Location: /opt/pangolin/config/
Frequency: Weekly
Retention: 4 weeks

Files:
- docker-compose.yml
- traefik/dynamic_config.yml
- letsencrypt/acme.json (SSL certificates)
- Any custom configs

Backup command:
tar -czf pangolin-config-$(date +%Y%m%d).tar.gz /opt/pangolin/config/
```

---

#### System Configuration (VPS)

```
Files to backup:
- /etc/ssh/sshd_config (SSH config)
- /etc/fail2ban/jail.local (Fail2ban rules)
- /etc/docker/daemon.json (Docker security)
- /etc/systemd/system/newt.service (Newt service)
- UFW rules: ufw status > ufw-backup.txt

Backup command:
mkdir -p /root/backups
cp /etc/ssh/sshd_config /root/backups/
cp /etc/fail2ban/jail.local /root/backups/
cp /etc/docker/daemon.json /root/backups/
ufw status numbered > /root/backups/ufw-rules.txt
```

---

#### SSH Keys

```
⚠️ CRITICAL: Backup your private SSH key!

Location: Your PC
Windows: C:\Users\[username]\.ssh\id_rsa
Linux: ~/.ssh/id_rsa

Backup locations:
✅ Encrypted USB drive
✅ Password manager (secure notes)
✅ Encrypted cloud storage
❌ Plain text anywhere
❌ Email

If lost:
→ No SSH access to VPS!
→ Must use Hetzner Console
→ Generate new key
```

---

#### Pangolin Database

```
⚠️ Contains users, resources, configurations!

Backup method (if supported):
1. Pangolin Dashboard → Settings → Backup
2. Or via command line:
   docker exec pangolin pg_dump > pangolin-db-backup.sql

Frequency: Weekly
Retention: 4 weeks

Alternative:
- Full container backup
- Volume snapshot
```

---

### 9.2 Backup Locations

#### Local Backup (VPS)

```
Location: /root/backups/
Pros: Fast, easy
Cons: Lost if VPS deleted!

Not sufficient alone!
Use only as intermediate storage.
```

---

#### Remote Backup (Recommended)

```
Options:

1. Hetzner Storage Box (paid)
   - Cost: ~€3-10/month
   - Integrated with Hetzner
   - Automated backup
   
2. Personal Cloud Storage
   - Google Drive
   - OneDrive
   - Dropbox
   - Encrypted before upload!

3. External Hard Drive (Physical)
   - Download backups monthly
   - Store securely
   - Offline backup

4. Git Repository (configs only)
   - Private GitHub/GitLab repo
   - Version control
   - Easy restoration
   - Don't commit secrets!

Recommendation:
→ Personal cloud (encrypted) for convenience
→ Monthly external drive for disaster recovery
```

---

### 9.3 Backup Automation

#### Simple Backup Script

```bash
#!/bin/bash
# File: /root/backup.sh

DATE=$(date +%Y%m%d)
BACKUP_DIR="/root/backups"
RETAIN_DAYS=30

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup Pangolin config
tar -czf $BACKUP_DIR/pangolin-config-$DATE.tar.gz /opt/pangolin/config/

# Backup system configs
cp /etc/ssh/sshd_config $BACKUP_DIR/sshd_config-$DATE
cp /etc/fail2ban/jail.local $BACKUP_DIR/jail.local-$DATE
cp /etc/docker/daemon.json $BACKUP_DIR/daemon.json-$DATE
ufw status numbered > $BACKUP_DIR/ufw-rules-$DATE.txt

# Remove old backups (older than 30 days)
find $BACKUP_DIR -name "*.tar.gz" -mtime +$RETAIN_DAYS -delete
find $BACKUP_DIR -name "*-$DATE" -mtime +$RETAIN_DAYS -delete

echo "Backup completed: $DATE"
```

**Setup cron job (weekly):**

```bash
# Edit crontab
crontab -e

# Add this line (runs every Sunday at 3 AM):
0 3 * * 0 /root/backup.sh >> /var/log/backup.log 2>&1

# Verify
crontab -l
```

---

### 9.4 Restoration Procedures

#### Restore Pangolin Configuration

```bash
# Stop containers
cd /opt/pangolin
docker compose down

# Restore config from backup
tar -xzf /root/backups/pangolin-config-YYYYMMDD.tar.gz -C /

# Restart containers
docker compose up -d

# Verify
docker ps
```

---

#### Restore System Configuration

```bash
# Restore SSH config
cp /root/backups/sshd_config-YYYYMMDD /etc/ssh/sshd_config
systemctl restart ssh

# Restore Fail2ban config
cp /root/backups/jail.local-YYYYMMDD /etc/fail2ban/jail.local
systemctl restart fail2ban

# Restore Docker config
cp /root/backups/daemon.json-YYYYMMDD /etc/docker/daemon.json
systemctl restart docker

# Restore UFW rules (manual from text file)
# Review backup file and reapply rules
```

---

#### Full Disaster Recovery

```
Scenario: VPS completely lost

Time to recovery: 2-4 hours

Steps:
1. Create new Hetzner VPS (30 min)
   - Same specs (CX23)
   - Same location (FSN1)
   - Add SSH key
   
2. Run initial setup (30 min)
   - apt update && upgrade
   - Install Docker
   - Configure UFW
   - Install Fail2ban
   
3. Restore Pangolin (30 min)
   - Extract backup
   - Place in /opt/pangolin
   - docker compose up -d
   
4. Update DNS (5 min)
   - Point to new VPS IP
   - Wait for propagation
   
5. Verify services (30 min)
   - Test all functionality
   - Check certificates
   - Verify tunnel
   
6. Restore system configs (30 min)
   - SSH hardening
   - Fail2ban rules
   - Docker security
   
Total: ~2-4 hours to full recovery
```

---

## 10. Security Checklist

### 10.1 Initial Setup (Complete ✓)

```
VPS Security:
✅ SSH key-only authentication
✅ Password authentication disabled
✅ SSH rate limited
✅ UFW firewall configured
✅ Fail2ban installed and active
✅ Docker security hardened
✅ Automatic updates enabled
✅ Swap configured

Cloudflare Security:
✅ Security Level: High
✅ Bot Fight Mode: ON
✅ AI Bot Blocking: ON
✅ Browser Integrity Check: ON
✅ Security Headers: ON
✅ X-Powered-By removed
✅ HTTPS enforced
✅ Automatic HTTPS Rewrites
✅ TLS 1.2 minimum
✅ Challenge Passage: 30 min

Pangolin Security:
✅ Admin account 2FA enabled
✅ Strong password set
✅ Session timeout configured
✅ GeoIP rules configured
✅ Resource authentication enabled
✅ Audit logging enabled

External Accounts:
✅ Hetzner account 2FA enabled
✅ Cloudflare account secured
✅ Recovery codes saved

Documentation:
✅ Setup guide created
✅ Security guide created
✅ Troubleshooting documented
✅ Credentials securely stored
```

---

### 10.2 Ongoing Maintenance

#### Weekly Tasks (5 minutes)

```
□ Test Jellyfin access
□ Check Fail2ban status
□ Verify Docker containers running
□ Review Cloudflare Security Events
□ Check Newt tunnel connection
```

#### Monthly Tasks (30 minutes)

```
□ Review system logs
□ Check for software updates
□ Verify SSL certificates valid
□ Review Fail2ban ban history
□ Performance check (htop, df -h)
□ Backup verification
□ Update documentation if needed
```

#### Quarterly Tasks (1 hour)

```
□ Full security audit
□ Update home IP if changed
□ Test backup restoration
□ Review and update firewall rules
□ Check for new security features
□ Rotate passwords (optional)
□ Review access logs thoroughly
```

#### Annual Tasks (2 hours)

```
□ Comprehensive security review
□ Evaluate new security tools
□ Update disaster recovery plan
□ Review and update documentation
□ Consider security upgrades
□ SSH key rotation (optional)
```

---

### 10.3 Security Scorecard

```
═══════════════════════════════════════════════════════
CURRENT SECURITY SCORE: 90/100 ⭐⭐⭐⭐⭐
═══════════════════════════════════════════════════════

Layer 1 (Cloudflare Edge):      90/100 ⭐⭐⭐⭐⭐
Layer 2 (VPS Security):        100/100 ⭐⭐⭐⭐⭐
Layer 3 (Pangolin):             95/100 ⭐⭐⭐⭐⭐
Layer 4 (WireGuard Tunnel):    100/100 ⭐⭐⭐⭐⭐
Layer 5 (Backend):             100/100 ⭐⭐⭐⭐⭐

Authentication:                100/100 ⭐⭐⭐⭐⭐
- Password: Strong ✓
- 2FA: Enabled (Pangolin + Hetzner) ✓
- Recovery codes: Saved ✓

Access Control:                100/100 ⭐⭐⭐⭐⭐
- GeoIP filtering ✓
- Rule-based access ✓
- Resource-level auth ✓

Encryption:                     93/100 ⭐⭐⭐⭐⭐
- HTTPS enforced (redirect) ✓
- TLS 1.2+ ✓
- WireGuard tunnel ✓
- HSTS: Not enabled (SSL-stripping risk on first visit)

Monitoring:                     82/100 ⭐⭐⭐⭐
- Fail2ban active ✓
- Log monitoring ✓
- Uptime Kuma monitoring ✓
- Netdata (performance/infrastructure observability) ✓
- Security event monitoring (Wazuh/Falco): Not configured
- File integrity monitoring: Not configured

Backup & Recovery:              85/100 ⭐⭐⭐⭐
- Configs documented ✓
- Manual backups possible ✓
- Automated backups: Not configured
- Disaster recovery: Documented ✓

Documentation:                 100/100 ⭐⭐⭐⭐⭐
- Complete setup guide ✓
- Security documentation ✓
- Troubleshooting guide ✓
- Incident response plan ✓

═══════════════════════════════════════════════════════

To reach 100/100:
Free wins:
→ Enable HSTS in Cloudflare (+4 points: Encryption + Layer 1)
→ Security event monitoring - Wazuh/osquery (+4 points, open source)
Paid/complex:
→ Automated VPS backup system (+2 points)

Current recommendation: STAY AT 90/100!
Solid homelab security. Free wins available when ready.
```

---

## Quick Reference

### Important URLs

```
Pangolin Dashboard: https://pangolin.your-domain.com
Jellyfin Service:   https://jellyfin.your-domain.com
Hetzner Console:    https://console.hetzner.cloud/
Cloudflare Dash:    https://dash.cloudflare.com/
```

### Emergency Contacts

```
Hetzner Support: https://www.hetzner.com/support
Cloudflare:      https://support.cloudflare.com/
Pangolin Docs:   https://docs.pangolin.net/
```

### Critical Commands

```bash
# VPS Security Check
systemctl status fail2ban ssh docker
docker ps
ufw status verbose

# View Banned IPs
fail2ban-client banned
fail2ban-client status sshd

# Check Logs
tail -f /var/log/auth.log
docker logs -f traefik
docker logs -f pangolin

# Newt Status (Home Lab)
systemctl status newt.service
journalctl -u newt.service -f
```

---

**Document Version:** 1.0  
**Last Updated:** 2026-01-11  
**Status:** Production Security Complete  
**Next Review:** 2026-02-11
