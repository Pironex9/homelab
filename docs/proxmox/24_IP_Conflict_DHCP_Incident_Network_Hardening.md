# IP Conflict and DHCP Incident - Full Network Hardening

**Date:** 2026-07-06
**Hostname:** pve (+ all LXCs/VMs)
**IP address:** 192.168.0.109

## Summary

A day of intermittent, seemingly random service outages (public 503 flapping, internal timeouts, "connection error" from LAN clients) turned out to be a stack of independent problems rooted in two design weaknesses:

1. Two devices on the LAN were claiming infrastructure IP addresses via ARP (a rogue phone on 192.168.0.110, a family phone with a stale router binding on 192.168.0.105).
2. Most LXCs and the HAOS VM were silently running on DHCP. They had held their "well-known" addresses for months only because the router kept renewing the same lease. When the DHCP pool was changed, they all started migrating to new addresses.

By the end of the day every infrastructure host was converted to a true static IP and both rogue devices were removed.

## Symptoms

- Uptime Kuma (Discord): Jellyfin/Form/DocuSeal/HA public monitors flapping down/up with 503 every few minutes, internal monitors timing out with 7-19 s pings
- Newt logs on pve: `health check failed: ... context deadline exceeded` on all LXC 100 backends
- Jellyfin "connection error" from LAN clients, homepage.lan flashing API errors
- Komodo UI unreachable while all Komodo containers were healthy

## Root causes and fixes (in discovery order)

### 1. Rogue phone claiming 192.168.0.110 (LXC 100 docker-host)

`tcpdump` showed two ARP replies for every who-has 192.168.0.110: the real LXC (`bc:24:11:be:de:2e`) and a rogue `8e:ae:aa:8f:54:9a` (locally administered, randomized MAC). Every client that cached the rogue reply lost ~50% of its SYNs to LXC 100 (the classic 1.03 s curl time = one SYN retransmit).

The device was an unknown "Redmi-10C" phone, not owned by the household. It most likely obtained the .110 lease from router DHCP while the whole homelab was powered off during electrical work, then defended the address after the servers came back. It was blocked on the router. Diagnostic used:

```bash
# duplicate address detection - more than 1 reply per probe = conflict
arping -D -c 4 -I vmbr0 192.168.0.110
# identify the claimants
tcpdump -i vmbr0 -nn -e arp host 192.168.0.110
```

Security follow-up: an unknown device on the WiFi means the password is compromised. MAC blocking is weak against MAC randomization - change the WiFi password and disable WPS.

### 2. Family phone claiming 192.168.0.105 (Komodo)

A second claimant (`64:11:a4:3e:56:ce`) was answering ARP for 192.168.0.105 with gratuitous ARP storms, breaking the Komodo periphery websocket (60-80% packet loss between LXC 100 and 105). It survived an RE605X power cycle, which ruled out the extender. It turned out to be a family phone that had an old IP/MAC binding to .105 in the Archer C6. Removing the binding and restarting the router stopped the claims.

### 3. Interim defense: static ARP entries

While the rogues were active, permanent ARP entries were set on the critical path so Newt (public health checks), Caddy (.lan) and the Komodo path kept working:

```bash
# pve, LXC 100, LXC 102, LXC 109 (Debian):
ip neigh replace 192.168.0.110 lladdr bc:24:11:be:de:2e dev vmbr0 nud permanent
ip neigh replace 192.168.0.105 lladdr bc:24:11:f0:bd:71 dev vmbr0 nud permanent
# LXC 110 (Alpine/busybox):
arp -s 192.168.0.110 bc:24:11:be:de:2e
```

These entries are not reboot-persistent and are harmless to leave in place.

### 4. The DHCP time bombs: infra hosts without static IPs

The DHCP pool was narrowed to 192.168.0.20-99 to keep client devices out of the server range. This immediately exposed that many "static looking" hosts were actually DHCP clients:

| Host | Was | Now (static) |
|---|---|---|
| LXC 110 Caddy | DHCP, held .208 for months, moved to .78 | 192.168.0.208 |
| LXC 105 Komodo | DHCP, moved to .95 | 192.168.0.105 |
| LXC 103 Vaultwarden | DHCP (lease .219 not yet expired) | 192.168.0.219 |
| LXC 106 Karakeep | DHCP | 192.168.0.128 |
| LXC 107 n8n | DHCP | 192.168.0.112 |
| LXC 108 Ollama | DHCP | 192.168.0.231 |
| VM 101 HAOS | DHCP, moved to .92 | 192.168.0.202 |

The Caddy move is what killed every `*.lan` site: all AdGuard DNS rewrites point to 192.168.0.208, and Caddy silently left that address. The Komodo move is why the Komodo UI died while its containers were healthy. HAOS moving is why `ha.homelabor.net` and the HA public share went down.

LXC fix pattern (keep the original MAC so router reservations stay valid):

```bash
pct set 110 --net0 name=eth0,bridge=vmbr0,firewall=1,hwaddr=BC:24:11:06:DC:79,ip=192.168.0.208/24,gw=192.168.0.1
pct reboot 110   # drops the old DHCP address cleanly
```

HAOS fix (from pve, via guest agent):

```bash
qm guest exec 101 -- ha network update enp6s18 --ipv4-method static \
  --ipv4-address 192.168.0.202/24 --ipv4-gateway 192.168.0.1 --ipv4-nameserver 192.168.0.111
```

### 5. Ollama bound to localhost after reboot

After the LXC 108 reboot, Ollama listened only on 127.0.0.1:11434. Permanent fix:

```bash
# /etc/systemd/system/ollama.service.d/network.conf
[Service]
Environment=OLLAMA_HOST=0.0.0.0
```

### 6. Newt tunnel goes stale after every router reboot

Twice during the day, all public services returned 503 immediately after a router restart, even though every backend was healthy. The Newt UDP tunnel to the Pangolin VPS keeps using a NAT mapping that no longer exists after the router reboots, and it does not always recover on its own (log signature: `Periodic ping failed ... failed to read ICMP packet: i/o timeout`).

Fix, on pve:

```bash
systemctl restart newt
```

Remember this after any router reboot. A systemd watchdog automating this is a possible future improvement.

### 7. Unrelated same-day events (for the record)

- 11:57 - /dev/sdd (ADATA HD710 PRO USB enclosure, /mnt/disk4) disconnected at USB level, auto-recovered in about 1 minute with clean ext4 journal recovery. SMART is completely clean (0 reallocated, 0 pending, 0 CRC) - suspect cable or power, not the disk. See also doc 13 for this drive's history.
- 15:12 - the "everything down" event was simply the user rebooting the Proxmox host (kernel 7.0.0-3 -> 7.0.14-3).
- The RE605X extender intermittently reflects frames back to the LAN (`vmbr0: received packet on nic0 with own address as source address` in the pve kernel log). Known quirk, mostly harmless, worth remembering when reading logs.

## Lessons

- ARP conflicts look like everything except an ARP conflict: random 503s, half-lost connections, services "flapping" while their containers are perfectly healthy. `arping -D` and a 10-second `tcpdump ... arp` answer it definitively.
- A DHCP lease that has renewed to the same address for months is not a static IP. Every infrastructure host must have its address configured on the host itself (`pct set --net0 ip=...`, `ha network update`), not inherited from router behavior.
- Router IP/MAC bindings guarantee your device gets that IP - they do not prevent the router from handing the same IP to someone else while your device is offline. Keep the DHCP pool disjoint from the server range (pool is now 192.168.0.20-99).
- After any router reboot: `systemctl restart newt` on pve, or all public services stay 503.
- An unknown device on the WiFi is a security incident, not just a network nuisance.

## Follow-ups (same evening)

### 8. Caddy fell back to DHCP once more

All re-IP'd LXCs were rebooted so their internal DHCP client would stop - except LXC 110, which only got the static address hotplugged. The still-running DHCP client reclaimed .78 on the next lease renewal and every `*.lan` site died again (AdGuard rewrites point to .208). Lesson: `pct set --net0 ip=...` alone is not enough on a running container - always `pct reboot` afterwards so the guest network config is regenerated and the DHCP client goes away.

### 9. Homepage scroll lag on the Nobara PC (Flatpak/NVIDIA mismatch)

The homepage dashboard scrolled with heavy jank on the Nobara PC but was smooth on a phone - so the server was innocent. Root cause: Firefox runs as a Flatpak, and Flatpak apps use their own containerized NVIDIA userspace driver. The host driver had been updated to 595.71.05 while the newest installed Flatpak GL runtime was 595.58.03; on a version mismatch the Flatpak app silently falls back to software rendering. Fix:

```bash
flatpak install --user -y flathub \
  org.freedesktop.Platform.GL.nvidia-595-71-05 \
  org.freedesktop.Platform.GL32.nvidia-595-71-05
# then fully restart Firefox; verify in about:support -> Graphics -> Compositing = WebRender (not Software)
```

Lesson: after every NVIDIA driver update on Nobara, run `flatpak update` too, or all Flatpak apps lose GPU acceleration. (A dead BlueMap tile pointing at the stopped Minecraft LXC was also removed from homepage's services.yaml along the way - it was flooding the logs with EHOSTUNREACH.)
