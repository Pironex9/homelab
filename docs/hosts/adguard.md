# adguard LXC

## Overview

| Property | Value |
|----------|-------|
| Hostname | adguard |
| IP Address | 192.168.0.111 |
| VMID | 102 |
| OS | Debian GNU/Linux 12 (bookworm) |
| Kernel | 6.17.4-1-pve |
| CPU | 1 core |
| RAM | 1 GB |
| Disk | 8 GB (local-lvm, 16% used) |
| Purpose | Network-level ad/tracker/malware blocking via DNS |

## Running Services

| Service | Description |
|---------|-------------|
| `AdGuardHome.service` | AdGuard Home DNS server and web UI |
| `ssh.service` | OpenSSH server |
| `cron.service` | Scheduled tasks |

## Open Ports

| Port | Protocol | Service |
|------|----------|---------|
| 22 | TCP | SSH |
| 53 | TCP/UDP | DNS |
| 80 | TCP | AdGuard Home web UI |

## AdGuard Home

**Version:** v0.107.71
**Install path:** `/opt/AdGuardHome/`
**Config file:** `/opt/AdGuardHome/AdGuardHome.yaml`
**Local domain:** `lan`

### Upstream DNS

Quad9 — privacy-focused, malware-blocking resolver, using all three protocols with load balancing:

| Upstream | Protocol |
|----------|----------|
| `https://dns.quad9.net/dns-query` | DNS-over-HTTPS |
| `https://dns11.quad9.net/dns-query` | DNS-over-HTTPS (ECS) |
| `tls://dns.quad9.net` | DNS-over-TLS |

**Mode:** load balance
**DNSSEC:** disabled
**Upstream timeout:** 10s

### Cache

| Setting | Value |
|---------|-------|
| Cache enabled | yes |
| Cache size | 32 MB |
| Optimistic caching | disabled |

### Statistics & Query Log

| Setting | Value |
|---------|-------|
| Statistics interval | 7 days |
| Query log interval | 90 days |

### Local DNS Rewrites

Forward (name → IP) and reverse PTR (IP → name) records for all homelab hosts:

| Hostname | IP |
|----------|----|
| `proxmox.lan` | `192.168.0.109` |
| `docker.lan` | `192.168.0.110` |
| `adguard.lan` | `192.168.0.111` |
| `komodo.lan` | `192.168.0.105` |
| `karakeep.lan` | `192.168.0.128` |
| `n8n.lan` | `192.168.0.112` |
| `ollama.lan` | `192.168.0.231` |
| `claude.lan` | `192.168.0.204` |
| `nobara.lan` | `192.168.0.100` |

PTR records use the `in-addr.arpa` format in the rewrites section (e.g. `109.0.168.192.in-addr.arpa` → `proxmox.lan`).
`private_networks` is set to `192.168.0.0/24` so AdGuard handles PTR queries for the local subnet locally.

### Blocklists

#### Ad & Tracker Blocking

| List | Description |
|------|-------------|
| AdGuard DNS filter | AdGuard's main DNS blocklist |
| AdAway Default Blocklist | Mobile-focused ad blocking |
| AdGuard DNS Popup Hosts filter | Popup and notification spam |
| AWAvenue Ads Rule | Chinese ad network rules |
| Dan Pollock's List | Classic hosts-based blocklist |
| HaGeZi's Pro Blocklist | Comprehensive multi-purpose blocklist |
| HaGeZi's Pro++ Blocklist | Extended Pro version |
| OISD Blocklist Big | Large community-maintained list |
| Peter Lowe's Blocklist | Ad and tracking servers |
| Steven Black's List | Unified hosts file |
| NoCoin Filter List | Cryptominer blocking |
| Dandelion Sprout's Anti Push Notifications | Browser push notification abuse |
| Dandelion Sprout's Game Console Adblock List | Console telemetry/ads |
| Perflyst and Dandelion Sprout's Smart-TV Blocklist | Smart TV tracking |
| HUN: Hufilter | Hungarian ad/tracker list |

#### Security & Malware

| List | Description |
|------|-------------|
| HaGeZi's Threat Intelligence Feeds | Threat intel-based blocking |
| Malicious URL Blocklist (URLHaus) | Known malware distribution URLs |
| Phishing URL Blocklist (PhishTank and OpenPhish) | Phishing domains |
| Phishing Army | Extended phishing list |
| Scam Blocklist by DurableNapkin | Scam sites |
| The Big List of Hacked Malware Web Sites | Compromised sites |
| ShadowWhisperer's Malware List | Malware domains |
| Stalkerware Indicators List | Stalkerware/spyware domains |
| uBlock₀ filters – Badware risks | Badware risk domains |
| HaGeZi's DynDNS Blocklist | Dynamic DNS abuse |
| HaGeZi's Badware Hoster Blocklist | Hosting providers used for malware |
| HaGeZi's The World's Most Abused TLDs | High-risk TLD blocking |
| Dandelion Sprout's Anti-Malware List | Malware domains |

#### Allowlists

| List | Description |
|------|-------------|
| HaGeZi's Allowlist Referral | Whitelist for referral links broken by blocklists |
| BadBlock Whitelist | Commonly false-positive domains |
| HaGeZi's URL Shorteners | Whitelist for legitimate URL shorteners |

## Lessons Learned

- **Quad9 over multiple protocols:** Using DoH and DoT simultaneously with load balancing provides both redundancy and privacy. If one protocol is blocked or slow, the others handle the load.
- **Allowlists are essential with aggressive blocking:** With 15+ blocklists active, false positives are inevitable. Pairing HaGeZi's Pro++ with its own allowlist (Allowlist Referral) and BadBlock's whitelist significantly reduces breakage.
- **Web UI runs on port 80:** The AdGuard Home UI is accessible at `http://192.168.0.111` (no HTTPS by default). Access should be restricted to the local network only.
- **Low resource usage:** 1 GB RAM and 1 core is sufficient. Actual memory usage stays around 415 MB even with the full blocklist set loaded.
- **PTR rewrites require `enabled: true`:** AdGuard Home v0.107.71 automatically adds `enabled: false` to rewrite entries when it serializes the config. New rewrites added directly to the YAML must explicitly include `enabled: true`, otherwise they are silently ignored.
- **PTR via `in-addr.arpa` rewrites:** AdGuard Home does not have a dedicated PTR record UI. Reverse DNS is handled by adding entries like `109.0.168.192.in-addr.arpa → proxmox.lan` to the rewrites section. Requires `private_networks` to include the local subnet so AdGuard handles PTR queries locally instead of forwarding to upstream.
- **Config edits need Python over SSH:** Editing the YAML config directly via SSH heredoc is unreliable due to shell quoting issues. The correct approach is to write a Python script locally, `scp` it to the host, and execute it there.
