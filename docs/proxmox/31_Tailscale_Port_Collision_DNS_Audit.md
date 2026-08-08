# Tailscale Audit - UDP Port Collision, Tailnet DNS Design, Socket-Activated sshd

**Date:** 2026-08-03
**Hostname:** claude-mgmt (LXC 109), pve, docker-host (LXC 100), alpine-komodo (LXC 105)
**IP address:** 192.168.0.204, 192.168.0.109, 192.168.0.110, 192.168.0.105

## Summary

Remote sessions to LXC 109 over Tailscale kept freezing and dropping, and after turning Tailscale off on the phone, mobile internet stayed dead for a while with a "DNS unavailable" warning from the Tailscale app. A full routing and DNS audit found two independent causes plus one silent bug uncovered along the way:

1. Four Tailscale nodes behind one router were all bound to the same UDP port, so only one of them could hold the router's UPnP port mapping. LXC 109 lost that race and kept flapping between a direct path and a DERP relay.
2. The tailnet's **global** nameserver was a LAN-only address (AdGuard on 192.168.0.111). Every DNS query from a remote device had to traverse the tunnel, so when cause 1 flapped, all name resolution died, not just homelab names.
3. On LXC 109 both `ssh.service` and `ssh.socket` were enabled, which made a `systemctl reload ssh` kill the standalone daemon. This was invisible because socket activation kept serving new logins.

## Symptoms

- SSH and code-server sessions to LXC 109 hanging for seconds, sometimes disconnecting outright
- Every other host on the same LAN reachable over Tailscale without issue
- Tailscale on Android: "DNS unavailable - Tailscale cannot reach configured DNS servers"
- Phone without working internet for a while immediately after disabling Tailscale

## Cause 1 - UDP port collision behind a single NAT

The home router (TP-Link Archer C6) advertises UPnP with `method=single`, visible in the tailscaled log:

```
portmapper: saw UPnP type WANIPConnection1 at http://192.168.0.1:1900/igd.xml;
Archer C6 AC1200 MU-MIMO Wi-Fi Router (TP-Link), method=single
```

It can map external UDP 41641 to exactly one internal host. All four Tailscale nodes behind it defaulted to 41641:

```bash
# on each node
ss -ulnp | grep tailscaled
```

pve won the mapping and held a stable direct path; LXC 109 did not. Confirmed live - the same peer answered over three different paths within one test:

```bash
tailscale ping -c 6 100.80.129.47
# pong ... via DERP(fra) in 74ms
# pong ... via DERP(fra) in 85ms
# pong ... via DERP(fra) in 53ms
# pong ... via 46.34.238.153:22575 in 40ms
```

Every switch between DERP and direct is a few seconds of blackholed packets, which an interactive SSH or WebSocket session experiences as a freeze.

The endpoint churn in the logs shows the same thing from the other side:

```bash
journalctl -u tailscaled --since "24 hours ago" | grep -oE 'now using [^ ]+' | sort | uniq -c | sort -rn
#   6 now using 10.16.7.79:21550
#   2 now using 10.16.7.79:20064
#   1 now using 10.16.7.79:6813
#   1 now using 10.16.7.79:53990
#   1 now using 10.16.7.79:46713
```

`10.16.7.79` is not a remote device - it is the Archer C6's own WAN address, in the ISP's CGNAT range (the link is double-NATed; STUN reports the carrier's public `85.248.36.200`). Confirmed with `traceroute -n 10.16.7.79`, which answers on hop 1, and with `ip route get`, which routes it via `192.168.0.1`.

So those five different ports are five different UPnP mappings on the router, not five carrier NAT rebinds. Each node that lost the 41641 race tore the mapping down and asked for a new one, and the external port changed every time. This is the port collision seen from the router's side.

### Fix - one port per node

There is no `tailscale set --port`. The listening port lives in the init config and needs a daemon restart.

Debian/systemd hosts (`/etc/default/tailscaled`):

```bash
sed -i 's/^PORT="41641"/PORT="41642"/' /etc/default/tailscaled
systemctl restart tailscaled
```

Alpine/OpenRC hosts (`/etc/conf.d/tailscale`, note the lowercase key and that it ships commented out):

```bash
sed -i 's/^#port=41641$/port=41644/' /etc/conf.d/tailscale
rc-service tailscale restart
```

Final allocation:

| Node | LAN IP | UDP port | Config file |
|---|---|---|---|
| pve | 192.168.0.109 | 41641 | `/etc/default/tailscaled` |
| claude-mgmt (LXC 109) | 192.168.0.204 | 41642 | `/etc/default/tailscaled` |
| docker-host (LXC 100) | 192.168.0.110 | 41643 | `/etc/default/tailscaled` |
| alpine-komodo (LXC 105) | 192.168.0.105 | 41644 | `/etc/conf.d/tailscale` |
| nex-pc (Nobara desktop) | 192.168.0.100 | 41645 | `/etc/default/tailscaled` |

Nobara was missed in the first pass and only found on 2026-08-07, still on 41641 and therefore still fighting pve for the mapping. Count the nodes behind the router, not the ones in the homelab inventory - the desktop is a tailnet node too.

**A package upgrade wants to undo this.** On 2026-08-08 `apk upgrade tailscale` on LXC 105 (1.90.9 -> 1.98.5) shipped a new `/etc/conf.d/tailscale` as `/etc/conf.d/tailscale.apk-new` rather than overwriting the edited one, and its diff is exactly the regression:

```diff
-port=41644
+#port=41641
```

The live file was left alone, so the port survived - but anyone who later moves the `.apk-new` into place restores the collision, and it will present as the same intermittent direct/DERP flapping rather than as an obvious DNS or config error. After any tailscale package upgrade, confirm the port on the running daemon, not in the config file: `ps -eo args | grep -o 'port=[0-9]*'` on Alpine, `ss -ulnp | grep tailscaled` elsewhere. Note also that `apk upgrade` replaces the binary without restarting the daemon - `tailscale version` reported 1.98.5 while the running server was still 1.90.9, with the client printing a version-mismatch warning. `rc-service tailscale restart` is required.

Verification:

```bash
tailscale ping 100.98.146.14
# pong from claude-mgmt (100.98.146.14) via 192.168.0.204:41642 in 1ms
```

Restarting tailscaled does not disturb Docker containers on the same host - the Komodo stack stayed up throughout.

## Cause 2 - a LAN-only IP as the tailnet global nameserver

`tailscale dns status` showed the broken state:

```
Resolvers (in preference order):
  - 192.168.0.111        <- sole resolver, no fallback

Split DNS Routes:
  - lan                            -> 192.168.0.111
```

192.168.0.111 (AdGuard) is only reachable through the pve subnet router, so on mobile data **every** DNS query - not just `.lan` - had to travel phone to tunnel to pve to AdGuard. Consequences:

- A single point of failure. When the path from cause 1 flapped, all name resolution stopped and the Tailscale app reported it could not reach the configured DNS servers.
- No fallback resolver was configured.
- Android does not restore the carrier resolver the instant the VPN is torn down, so disabling Tailscale looked like a total internet outage for a minute.

AdGuard itself was healthy the whole time (0 ms local query time, working upstream). The fault was architectural, not a service failure.

### Fix

In the Tailscale admin console, remove the **global** nameserver and keep only the split DNS route for the `lan` domain. Correct end state:

```
Resolvers (in preference order):
  (no resolvers configured, system default will be used)

Split DNS Routes:
  - lan                            -> 192.168.0.111
```

Homelab names still resolve through AdGuard over the tunnel; everything else uses the client's own resolver, which always works.

**Rule of thumb:** a private LAN address may be a split DNS resolver for a specific domain, never the tailnet-wide global nameserver.

## Cause 3 - socket-activated sshd on LXC 109

Debian 13 ships SSH with socket activation: `ssh.socket` holds `ListenStream=22` with `Accept=no` and hands the listening descriptor to `ssh.service` when a connection arrives. On LXC 109 **both units were enabled**, so at boot `ssh.service` also started standalone and bound port 22 itself.

That stayed invisible until a `systemctl reload ssh`. The reload sends SIGHUP, sshd re-execs, and on re-exec it tries to bind the port itself instead of reusing the inherited descriptor:

```
sshd[172]: Received SIGHUP; restarting.
sshd[172]: error: Bind to port 22 on 0.0.0.0 failed: Address already in use.
sshd[172]: fatal: Cannot bind any address.
ssh.service: Failed with result 'exit-code'.
```

`ssh.service` died, yet logins kept working, because `ssh.socket` was still listening and simply re-triggered the service on the next connection. A failed unit with a fully working service is exactly the kind of thing a status check misses.

Fix - stop the standalone boot-time start, keep socket activation:

```bash
systemctl disable ssh.service   # ssh.socket stays enabled and triggers it on demand
systemctl reset-failed ssh.service
```

Healthy end state - both units active, one sshd, descriptor shared with systemd:

```bash
ss -tlnp | grep ':22'
# LISTEN 0 4096 *:22 *:* users:(("sshd",pid=322135,fd=3),("systemd",pid=1,fd=59))
```

Two takeaways: under socket activation prefer `systemctl restart ssh.socket ssh.service` over `reload`, and verify with a real connection from another host rather than trusting unit state:

```bash
ssh nobara 'ssh -o BatchMode=yes root@192.168.0.204 hostname'
```

The `/etc/systemd/system/ssh.service.d/restart.conf` watchdog drop-in (`Restart=always`, `RestartSec=5`) is left in place; it is harmless now that the service is only ever started by the socket.

Note: `run-rpc_pipefs.mount` is permanently failed inside this LXC (NFS pseudo-filesystem cannot be mounted in an unprivileged container). Pre-existing and harmless.

## Hardening - SSH keepalive

LXC 109 had `ClientAliveInterval 0`, so a session stuck behind a blackholed path hung indefinitely. In `/etc/ssh/sshd_config`:

```
ClientAliveInterval 30
ClientAliveCountMax 6
```

The session now survives a roughly three-minute path outage and dead sessions get reaped instead of accumulating.

## Diagnostic reference

| Question | Command |
|---|---|
| Is a peer path direct or relayed, and does it flap? | `tailscale ping -c 6 <peer-ip>` |
| How often does the path change, and to which endpoints? | `journalctl -u tailscaled \| grep 'now using'` |
| What DNS config does the control plane push? | `tailscale dns status` |
| Does a subnet route conflict with a directly connected one? | `ip rule show` then `ip route show table 52` |
| NAT type, port mapping method, DERP latency | `tailscale netcheck` |
| Which UDP port is this node bound to? | `ss -ulnp \| grep tailscaled` |

The `ip rule` check matters because Tailscale's own routing table (52 here) is evaluated at priority 5270, ahead of `main` at 32766. If a node accepts a subnet route covering the subnet it already sits on, table 52 wins and LAN traffic gets misrouted into `tailscale0`. LXC 109 must therefore stay on `--accept-routes=false`.

## Related

- [05 - AdGuard Home + Tailscale DNS](./05_AdGuard_Home_Setup_Dedicated_LXC_Tailscale_DNS_Integration.md)
- [24 - IP Conflict and DHCP Incident](./24_IP_Conflict_DHCP_Incident_Network_Hardening.md)
- [26 - Interactive Network Topology Map](./26_Network_Topology_Map.md)
- [Claude Code Mgmt (LXC 109)](../hosts/claude-mgmt.md)
