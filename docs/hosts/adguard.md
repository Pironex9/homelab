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

**Bootstrap DNS:** `9.9.9.9`, `149.112.112.112`, `2620:fe::fe` - all Quad9. These resolve the upstream *hostnames* over plain DNS so the DoH/DoT connections can be opened at startup. Cloudflare was removed from this list on 2026-08-12; no resolver outside Quad9 is contacted any more, including the OS resolver of the container itself.

### Cache

| Setting | Value |
|---------|-------|
| Cache enabled | yes |
| Cache size | 32 MB |
| Optimistic caching | enabled (30s TTL, 12h max age) |

### Rate limiting

| Setting | Value |
|---------|-------|
| `ratelimit` | `0` (disabled, since 2026-08-09) |
| `ratelimit_subnet_len_ipv4` | `24` (inert while the limit is 0) |

Disabled deliberately, see the lesson below. The setting exists to stop a *public* resolver
being abused as an amplifier, and this one is not reachable from the internet: a query to the
home public IP from the Hetzner VPS returns `connection refused`, so the router forwards no
port 53. Re-enable it if that ever stops being true, but then set
`ratelimit_subnet_len_ipv4: 32` at the same time.

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
- **Fleet-wide DNS baseline after the 2026-08-08 audit:** every LXC now carries `nameserver: 192.168.0.111 1.1.1.1` in its Proxmox config *and* in its running `/etc/resolv.conf`, because `pct set` alone only takes effect at next start. Two hosts needed more than that: **pve** had `accept-dns=true`, so tailscaled owned `/etc/resolv.conf` and pushed MagicDNS into every guest that had no explicit nameserver - fixed with `tailscale set --accept-dns=false` followed by `pvesh set /nodes/pve/dns --search homelab.local --dns1 192.168.0.111 --dns2 1.1.1.1` (use `pvesh`, not a hand-edited file - the node DNS object is what the GUI and the container-start path read). **LXC 100** was the same plus a `pct` nameserver pointing at the router; its 22 Docker stacks were never affected because `/etc/docker/daemon.json` already pins `"dns": ["192.168.0.111", "1.1.1.1"]`. Deliberate exceptions: **LXC 102** cannot point at itself, since that is circular - AdGuard must resolve its own DoH/DoT upstream hostnames before it can start. It ran on `1.1.1.1` until 2026-08-12 and is now on `9.9.9.9`, which breaks the circularity just as well without involving Cloudflare. The VPS stays on Hetzner's resolvers, as a public node should. Verified after the change: all eleven LXCs plus pve return a blocked answer for `doubleclick.net` and resolve `jellyfin.lan` to 192.168.0.208. Side effect worth knowing: `.lan` names now resolve from LXC 109 too, which they did not while it was on `8.8.8.8`.
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
- **A fixed leak stays visible on the dashboard for a full statistics interval (2026-08-12):** three days after the PTR fix above, `1.1.1.1` was still sitting in "Top upstreams for the last 7 days" and looked like the fix had not taken. It had. The dashboard panel is driven by `stats.db`, whose window is `statistics.interval: 7d`, and the leak ran until 2026-08-09 15:38 UTC - so 4.5 of the 7 charted days still contained it. The query log settles the question in one command, because it is per-query rather than aggregated:

    ```console
    root@adguard:~# grep -c '"Upstream":"1.1.1.1:53"' /opt/AdGuardHome/data/querylog.json
    155047
    root@adguard:~# grep '"Upstream":"1.1.1.1:53"' /opt/AdGuardHome/data/querylog.json | tail -1
    ... "T":"2026-08-09T15:38:22.416629122Z" ... "QH":"100.0.168.192.in-addr.arpa","QT":"PTR" ...
    ```

    155,047 leaked queries between 2026-07-05 and the fix, every one of them a private PTR, and nothing since. Over the same 7-day window the breakdown was 54.2% `tls://dns.quad9.net`, 22.0% cache, 10.1% `1.1.1.1`, 9.3% + 4.4% the two DoH upstreams; over the last 36 h the Cloudflare share was 0%. **Do not judge a DNS change by the dashboard until a full `statistics.interval` has passed** - and note that the "Top upstreams by average processing time" panel is a separate ranking where a plain port-53 resolver will always look best, since it skips the TLS handshake.
- **Cloudflare removed from the last two places it survived (2026-08-12):** with the PTR path closed, `1.1.1.1` still appeared as the third `bootstrap_dns` entry and as the OS resolver of LXC 102 itself. Neither carried live traffic, but both are removable. Bootstrap is now Quad9-only; the container resolver moved to `9.9.9.9`, which breaks the same circularity `1.1.1.1` was chosen for. Both halves are needed, and in this order - change the container resolver first, or AdGuard has no way to resolve its upstream hostnames while it restarts:

    ```console
    root@pve:~# pct set 102 --nameserver 9.9.9.9
    root@adguard:~# sed -i 's/^nameserver 1.1.1.1$/nameserver 9.9.9.9/' /etc/resolv.conf
    root@adguard:~# systemctl stop AdGuardHome
    root@adguard:~# sed -i '/^    - 1\.1\.1\.1$/d' /opt/AdGuardHome/AdGuardHome.yaml
    root@adguard:~# systemctl start AdGuardHome
    ```

    **Stop the service before editing the YAML.** A running AdGuard Home rewrites the file from its in-memory config on shutdown and on any UI change, so an edit made while it is up can be silently reverted. Verified afterwards: `grep -n '1\.1\.1\.1' /opt/AdGuardHome/AdGuardHome.yaml /etc/resolv.conf` returns nothing, `doubleclick.net` still answers `::`, `jellyfin.lan` still answers 192.168.0.208, and the first 189 queries after the restart went to Quad9 only.
- **The rate limit applied to the whole LAN as one bucket, and dropped queries in silence (2026-08-09):** `ratelimit: 20` reads like 20 queries per second per client. It is not. `ratelimit_subnet_len_ipv4: 24` groups clients by /24 before the limit is applied, so all of `192.168.0.0/24` shared a single 20 qps allowance. Measured from a LAN host by firing unique names in one burst: 10 sent → 10 answered, 30 sent → 18 answered, 60 sent → **20 answered and 40 dropped**. The drops produce no SERVFAIL, no REFUSED and no query-log entry, so the client sees only a timeout and the dashboard shows nothing wrong. Real traffic was hitting it: 240 seconds in a 24 h window reached ≥20 logged qps with a peak of 37, and the log by definition counts only what got through. Fixed with `ratelimit: 0`. **The general rule: a silent-drop defence cannot be audited from the logs of the thing doing the dropping** - the only way to see it is to generate a burst and count the answers.
- **`tls://` upstream timeouts are a half-closed pooled connection, not a Quad9 problem (2026-08-09):** about 225 `write: connection timed out` errors per 6 h against `tls://dns.quad9.net:853`, in bursts, while resolution kept working. The chain, each step observed: Quad9 closes an idle DoT connection after roughly 10 s (a query at 5 s idle succeeds, at 15 s the peer has already sent FIN); dnsproxy keeps the socket in its pool without reading it, which shows up as several sockets in `CLOSE-WAIT` with `Recv-Q 25`, the unread TLS `close_notify`; a later write into that socket is then black-holed rather than reset, leaving `unacked:1 retrans:1/9 backoff:8` and no ACK for 300+ seconds; the kernel retransmits until ETIMEDOUT, which is why the error surfaces in clumps minutes after the fact and why `ss` shows a row of `LAST-ACK` sockets with 60-110 bytes stuck in Send-Q. **The same test against `1.1.1.1:853` behaves identically**, so it is not provider-specific - the common element is the NAT on the path dropping the entry for a half-closed connection and discarding the follow-up packets instead of answering RST. Impact is nil and the fix is to leave it alone: over 24 h the DoT upstream carried 83% of the traffic with 0.32% of queries over 1 s, a *better* rate than either DoH upstream (0.71% and 0.94%). Removing the DoT entry would move load onto the slower two. AdGuard Home exposes no pool idle-timeout knob, so the log noise stays.
- **Remote Tailscale devices all appear as `192.168.0.109` in the client list:** pve is the subnet router and runs with `NoSNAT: false`, so it masquerades subnet-routed traffic behind its own LAN address. The effect on the dashboard is a "Proxmox" client with 2000+ queries a day at a 78% block rate, whose top domains are `mobile.events.data.microsoft.com` and `mobile.pipe.aria.microsoft.com` - phone telemetry, not hypervisor traffic. Per-client statistics and per-client blocking are therefore impossible for anything connecting over Tailscale. `--snat-subnet-routes=false` would fix the attribution but needs the LAN devices to have a route back into the Tailscale CGNAT range, which they do not, so this is documented rather than fixed.
- **PTR via `in-addr.arpa` rewrites:** AdGuard Home does not have a dedicated PTR record UI. Reverse DNS is handled by adding entries like `109.0.168.192.in-addr.arpa → proxmox.lan` to the rewrites section. Requires `private_networks` to include the local subnet so AdGuard handles PTR queries locally instead of forwarding to upstream.
- **Config edits need Python over SSH:** Editing the YAML config directly via SSH heredoc is unreliable due to shell quoting issues. The correct approach is to write a Python script locally, `scp` it to the host, and execute it there.
- **`update` command not available:** This LXC was installed before the community script update function was added. Use the full binary path instead: `/opt/AdGuardHome/AdGuardHome --update`. Add to PATH permanently: `echo 'export PATH=$PATH:/opt/AdGuardHome' >> /root/.bashrc`
