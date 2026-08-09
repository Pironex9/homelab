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
| 80 | TCP | AdGuard Home web UI (HTTP) |
| 443 | TCP | AdGuard Home web UI (HTTPS) |
| 853 | TCP | DNS-over-TLS (DoT) client endpoint |

## AdGuard Home

**Version:** v0.107.72
**Install path:** `/opt/AdGuardHome/`
**Config file:** `/opt/AdGuardHome/AdGuardHome.yaml`
**Local domain:** `lan`

### Upstream DNS

Quad9 - privacy-focused, malware-blocking resolver, using all three protocols with load balancing:

| Upstream | Protocol |
|----------|----------|
| `https://dns.quad9.net/dns-query` | DNS-over-HTTPS |
| `https://dns11.quad9.net/dns-query` | DNS-over-HTTPS (ECS) |
| `tls://dns.quad9.net` | DNS-over-TLS |

**Mode:** load balance
**DNSSEC:** enabled (AdGuard validates, in addition to Quad9 upstream validation)
**Upstream timeout:** 10s

### Cache

| Setting | Value |
|---------|-------|
| Cache enabled | yes |
| Cache size | 32 MB |
| Optimistic caching | enabled (30s TTL, 12h max age) |

### Statistics & Query Log

| Setting | Value |
|---------|-------|
| Statistics interval | 7 days |
| Query log interval | 90 days |

### Local DNS Rewrites

All service domains resolve to `192.168.0.208` (Caddy reverse proxy). Direct host records for SSH and management access:

**Service domains (via Caddy):**

| Hostname | IP |
|----------|----|
| `proxmox.lan` | `192.168.0.208` |
| `adguard.lan` | `192.168.0.208` |
| `komodo.lan` | `192.168.0.208` |
| `karakeep.lan` | `192.168.0.208` |
| `n8n.lan` | `192.168.0.208` |
| `ollama.lan` | `192.168.0.208` |
| `jellyfin.lan` | `192.168.0.208` |
| `homepage.lan` | `192.168.0.208` |
| `portfolio.lan` | `192.168.0.208` |
| `topology.lan` | `192.168.0.208` |
| `immich.lan` | `192.168.0.208` |
| `bentopdf.lan` | `192.168.0.208` |
| `docuseal.lan` | `192.168.0.208` |
| `qbit.lan` | `192.168.0.208` |
| `sonarr.lan` | `192.168.0.208` |
| `form.lan` | `192.168.0.208` |
| `uptime-kuma.lan` | `192.168.0.208` |
| `syncthing.lan` | `192.168.0.208` |
| `suggestarr.lan` | `192.168.0.208` |
| `notifiarr.lan` | `192.168.0.208` |
| `calibre.lan` | `192.168.0.208` |
| `seerr.lan` | `192.168.0.208` |
| `radarr.lan` | `192.168.0.208` |
| `scrutiny.lan` | `192.168.0.208` |
| `prowlarr.lan` | `192.168.0.208` |
| `freshrss.lan` | `192.168.0.208` |
| `netdata.lan` | `192.168.0.208` |
| `haos.lan` | `192.168.0.208` |
| `vaultwarden.lan` | `192.168.0.208` |
| `syncthing-nex.lan` | `192.168.0.208` |
| `nobara.lan` | `192.168.0.208` |
| `homelable.lan` | `192.168.0.208` |

**Direct host records (management):**

| Hostname | IP |
|----------|----|
| `docker.lan` | `192.168.0.208` |
| `claude.lan` | `192.168.0.208` |

**PTR records** (reverse DNS):

| PTR | Resolves to |
|-----|-------------|
| `109.0.168.192.in-addr.arpa` | `proxmox.lan` |
| `110.0.168.192.in-addr.arpa` | `docker.lan` |
| `111.0.168.192.in-addr.arpa` | `adguard.lan` |
| `105.0.168.192.in-addr.arpa` | `komodo.lan` |
| `128.0.168.192.in-addr.arpa` | `karakeep.lan` |
| `112.0.168.192.in-addr.arpa` | `n8n.lan` |
| `204.0.168.192.in-addr.arpa` | `claude.lan` |
| `231.0.168.192.in-addr.arpa` | `ollama.lan` |
| `100.0.168.192.in-addr.arpa` | `nobara.lan` |

PTR records use the `in-addr.arpa` format in the rewrites section.
`private_networks` is set to `192.168.0.0/24` so AdGuard handles PTR queries for the local subnet locally,
and `use_private_ptr_resolvers: false` keeps the ones that have no rewrite from leaving the LAN at all.

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

## Tailscale Integration

AdGuard serves `.lan` DNS for all Tailscale nodes via split DNS configured in the Tailscale admin panel (tailscale.com → DNS):

| Setting | Value |
|---------|-------|
| Split DNS domain | `lan` |
| Nameserver | `192.168.0.111` |
| Global nameserver | `192.168.0.111` (Override DNS servers: on) |
| MagicDNS | enabled |

This makes `.lan` hostnames resolve correctly on all Tailscale-connected devices - both local (e.g. Proxmox, which uses `100.100.100.100` as its DNS via Tailscale) and remote (e.g. laptop, phone over Tailscale). AdGuard is reachable from remote Tailscale nodes via Proxmox's subnet router (`192.168.0.0/24` advertised).

All DNS queries from all devices go through AdGuard → Quad9 (DoH/DoT). No third-party resolver (e.g. Cloudflare) sees any queries - true for forward lookups since day one, and for reverse lookups only since 2026-08-09, see the gotcha below. If AdGuard or Proxmox goes down, remote Tailscale devices lose DNS - acceptable tradeoff for a homelab.

DNS query flow:
- `.lan` queries (any device) → AdGuard (192.168.0.111) → local rewrites
- Reverse lookups of `192.168.0.x` → AdGuard → answered locally or NXDOMAIN, never forwarded
- All other queries (Tailscale devices) → AdGuard (192.168.0.111) → Quad9 (DoH/DoT, encrypted)
- LAN devices without Tailscale → AdGuard (192.168.0.111) → Quad9 (DoH/DoT, encrypted)

### Auto-update

Tailscale auto-update is enabled on all nodes (`tailscale set --auto-update=true`):

| Node | Method |
|------|--------|
| pve (192.168.0.109) | `tailscale set --auto-update=true` |
| claude-mgmt (lxc109) | via `pct exec 109` |
| opt5060-i5, opt3060-i3, opt3050-i5 | via SSH (nex@, passwordless sudo) |
| orangepione | manual (no passwordless sudo) |
| nex-pc (Nobara) | manual |

Manual update command: `tailscale update --yes`

### Subnet Router Note

Any host running Tailscale as a subnet router on the same network it advertises (e.g. Proxmox advertising `192.168.0.0/24`) must have stateful filtering disabled, otherwise direct LAN connections to that host are dropped by Tailscale's nftables layer:

```bash
tailscale set --stateful-filtering=false
```

Applied on: Proxmox (`192.168.0.109`). Also needed on any other subnet router (e.g. Orange Pi at remote site advertising `192.168.2.0/24`).

## Lessons Learned

- **Quad9 over multiple protocols:** Using DoH and DoT simultaneously with load balancing provides both redundancy and privacy. If one protocol is blocked or slow, the others handle the load.
- **Allowlists are essential with aggressive blocking:** With 15+ blocklists active, false positives are inevitable. Pairing HaGeZi's Pro++ with its own allowlist (Allowlist Referral) and BadBlock's whitelist significantly reduces breakage.
- **Web UI runs on port 80 and 443:** HTTP at `http://192.168.0.111`, HTTPS at `https://192.168.0.111`. HTTPS uses a self-signed cert (10-year validity, SAN for `adguard.lan` and `192.168.0.111`, stored at `/opt/AdGuardHome/certs/`). Browsers will warn unless the cert is installed as trusted. `force_https` is off - both protocols work. Access should be restricted to the local network only.
- **Router DHCP must hand out only AdGuard as DNS:** If the router also hands out a secondary DNS, systemd-resolved on Linux clients picks the fastest responder and may bypass AdGuard entirely, breaking `.lan` resolution. Set only `192.168.0.111` as Primary DNS in the router DHCP settings and leave Secondary DNS empty. **This is necessary but not sufficient on the Archer C6** - it was configured exactly this way and the router still appended its own LAN IP. See the entry below for the measurement and the client-side workaround.
- **Five LXCs were bypassing AdGuard entirely, and the router hid it (2026-08-08):** LXC 103, 106, 107, 110 and 111 have no `nameserver:` line in their Proxmox config, so on the 2026-07-29 restart Proxmox copied the *host's* `/etc/resolv.conf` into them - and on pve that file is owned by tailscaled, so it reads `nameserver 100.100.100.100`. None of those five run tailscaled, so that address is unreachable from them. Every lookup still succeeded in about 10 ms, which is the tell: **the Archer C6 transparently intercepts all outbound port 53.** Proof in one command - `nslookup github.com 203.0.113.99` from inside the container answers correctly, and 203.0.113.99 is TEST-NET, an address that cannot exist. The interception does not honour the blocklists: `doubleclick.net` resolved to a real Google address on the default path and to `0.0.0.0` when 192.168.0.111 was queried directly. So the containers looked healthy while their filtering had been off for ten days. Fix applied to all five: `pct set <id> --nameserver '192.168.0.111 1.1.1.1'` plus the same two lines written into the running container's `/etc/resolv.conf` (`pct set` only takes effect at next start). Verify with the `doubleclick.net` query above - a blocked answer is `0.0.0.0` on Alpine and `::` on Debian. **Never conclude DNS is healthy from a successful lookup on this LAN**; only a comparison against 192.168.0.111 proves which resolver actually answered. The same misconfiguration broke LXC 105 outright - see `docs/hosts/komodo.md` - because there a local tailscaled with `accept-dns=false` swallowed the query before the router could intercept it.
- **Fleet-wide DNS baseline after the 2026-08-08 audit:** every LXC now carries `nameserver: 192.168.0.111 1.1.1.1` in its Proxmox config *and* in its running `/etc/resolv.conf`, because `pct set` alone only takes effect at next start. Two hosts needed more than that: **pve** had `accept-dns=true`, so tailscaled owned `/etc/resolv.conf` and pushed MagicDNS into every guest that had no explicit nameserver - fixed with `tailscale set --accept-dns=false` followed by `pvesh set /nodes/pve/dns --search homelab.local --dns1 192.168.0.111 --dns2 1.1.1.1` (use `pvesh`, not a hand-edited file - the node DNS object is what the GUI and the container-start path read). **LXC 100** was the same plus a `pct` nameserver pointing at the router; its 22 Docker stacks were never affected because `/etc/docker/daemon.json` already pins `"dns": ["192.168.0.111", "1.1.1.1"]`. Deliberate exceptions: **LXC 102** stays on `1.1.1.1` - pointing AdGuard's own OS resolver at itself is circular, since it must resolve its DoH/DoT upstream hostnames to start; and the VPS stays on Hetzner's resolvers, as a public node should. Verified after the change: all eleven LXCs plus pve return a blocked answer for `doubleclick.net` and resolve `jellyfin.lan` to 192.168.0.208. Side effect worth knowing: `.lan` names now resolve from LXC 109 too, which they did not while it was on `8.8.8.8`.
- **The Archer C6 hands out its own LAN IP as a second DNS server, and there is no setting that stops it:** on Nobara, `resolvectl status` showed `DNS Servers: 192.168.0.111 192.168.0.1` with `Current DNS Server: 192.168.0.1` - systemd-resolved had silently picked the router and lost the filtering. The router's DHCP page was already configured correctly: Primary DNS `192.168.0.111`, **Secondary DNS `0.0.0.0`**. The firmware appends the gateway to DHCP option 6 anyway. Proof, from the client rather than the router UI:

    ```console
    $ nmcli -g ipv4.dns con show "Wired connection 1"          # empty - nothing set by hand
    $ nmcli -g ipv4.ignore-auto-dns con show "Wired connection 1"
    no
    $ nmcli -f DHCP4 con show "Wired connection 1" | grep domain_name_servers
    DHCP4.OPTION[4]:  domain_name_servers = 192.168.0.111 192.168.0.1
    ```

    Check the DHCP *offer* (`nmcli -f DHCP4`), not the router's config page - the page said one thing and the wire said another. The WAN page is a separate matter and irrelevant here: it shows the ISP's own resolver (`192.168.4.248`) and the CGNAT WAN address `10.16.7.79`, neither of which reaches LAN clients.

    Two ways out. Per client, which is what Nobara got: `ipv4.ignore-auto-dns yes` plus `ipv4.dns 192.168.0.111`. Do **not** add a public resolver as a second entry on a systemd-resolved host - it selects by responsiveness rather than strict order, which is how the router won in the first place. That is the opposite of the LXC convention (`192.168.0.111 1.1.1.1`), where the glibc resolver does keep strict order and only falls back on timeout. The trade-off is that the host has no DNS at all while AdGuard is down. Fleet-wide, the only real fix is to disable the router's DHCP server and let AdGuard Home serve DHCP instead - not done, since it makes LXC 102 a single point of failure for addressing as well as for resolution.
- **Low resource usage:** 1 GB RAM and 1 core is sufficient. Actual memory usage stays around 415 MB even with the full blocklist set loaded.
- **PTR rewrites require `enabled: true`:** AdGuard Home v0.107.71 automatically adds `enabled: false` to rewrite entries when it serializes the config. New rewrites added directly to the YAML must explicitly include `enabled: true`, otherwise they are silently ignored.
- **17% of all queries were still reaching Cloudflare, and the upstream table did not show it (2026-08-09):** the yesterday's fleet-wide DNS work left LXC 102 itself on `nameserver 1.1.1.1`, deliberately, because AdGuard must resolve its own DoH/DoT upstream hostnames before it can start. The unnoticed consequence: `use_private_ptr_resolvers: true` with an empty `local_ptr_upstreams` means AdGuard sends reverse lookups for the private range **to the container's own OS resolver** - so 508 of the last 3000 queries, every one of them a `*.0.168.192.in-addr.arpa` PTR, went to Cloudflare in plaintext on port 53. Only the addresses without a rewrite entry leak, which is why the nine documented PTRs above hid the problem; 326 of the 508 were repeated lookups of `192.168.0.100`. Cloudflare answers all of them NXDOMAIN, so nothing was gained in exchange for handing a public resolver a map of the internal network. Fix: `use_private_ptr_resolvers: false`, which makes AdGuard answer private PTRs from its rewrites and client list only. **The Upstream column of the query log is the place to catch this** - the general statistics page shows only totals, and a config file whose `upstream_dns:` block lists nothing but Quad9 is not evidence that nothing else is being queried.
- **PTR via `in-addr.arpa` rewrites:** AdGuard Home does not have a dedicated PTR record UI. Reverse DNS is handled by adding entries like `109.0.168.192.in-addr.arpa → proxmox.lan` to the rewrites section. Requires `private_networks` to include the local subnet so AdGuard handles PTR queries locally instead of forwarding to upstream.
- **Config edits need Python over SSH:** Editing the YAML config directly via SSH heredoc is unreliable due to shell quoting issues. The correct approach is to write a Python script locally, `scp` it to the host, and execute it there.
- **`update` command not available:** This LXC was installed before the community script update function was added. Use the full binary path instead: `/opt/AdGuardHome/AdGuardHome --update`. Add to PATH permanently: `echo 'export PATH=$PATH:/opt/AdGuardHome' >> /root/.bashrc`
