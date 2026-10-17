# Nobara SSH Timeout - DSCP Marking Confirmed

**Date:** 2026-08-27
**Hostname:** nex-pc (Nobara desktop), pve, docker-host (LXC 100), adguard (LXC 102), caddy (LXC 110), claude-mgmt (LXC 109)
**IP address:** 192.168.0.100, 192.168.0.109, 192.168.0.110, 192.168.0.111, 192.168.0.208, 192.168.0.204

## Status: resolved

Every SSH connection from the Nobara desktop to every host on the LAN failed with `Connection timed out`, while `ping` and raw TCP to the same host and port succeeded. The cause was the DSCP marking OpenSSH puts on its packets. This confirms, for the connection-setup path, the hypothesis that [32](./32_Nobara_SSH_Freeze_Investigation.md) had tested and excluded on 2026-08-07.

The report that started it was "Proxmox is not reachable over SSH from Nobara, audit Tailscale". Tailscale turned out to be healthy in every respect and was not involved in either of the two faults found.

A second case, on the server side, followed on 2026-10-16: a Debian 13 sshd marks its own banner DSCP EF, and those packets never reach the pve host's physical NIC. See [53](./53_Autodarts_Thin_Client_For_A_Friend.md).

A third case followed on 2026-10-17: the fix below lived in nex's `~/.ssh/config`, so ssh started by root (the systemd SSHFS service) still marked its packets. See [Third case: the SSHFS service runs as root](#third-case-the-sshfs-service-runs-as-root-2026-10-17).

## The measurement that isolates it

The whole diagnosis rests on one asymmetry. Same host, same port, same source, back to back:

```bash
# raw TCP connect, bash builtin, no DSCP marking
cat < /dev/null > /dev/tcp/192.168.0.109/22   # OPEN, 4 out of 4

# OpenSSH, default IPQoS (af21 pre-auth)
ssh root@192.168.0.109                        # Connection timed out, 4 out of 4

# OpenSSH, marking disabled
ssh -o IPQoS=none root@192.168.0.109          # connects, reaches authentication
```

`ping` answered in 1.3 ms throughout and `sshd` on the far side logged the raw-TCP probes arriving:

```
sshd-session[1207589]: Connection closed by 192.168.0.100 port 54508
```

**If raw TCP connects and SSH does not, on the same host and port, it is neither the network nor sshd.** Nothing else in that pair differs except the DSCP bits, so nothing else needs testing.

## Scope

Not destination-specific. With default `IPQoS`, from Nobara:

| Target | Result |
|---|---|
| 192.168.0.109 (pve) | timeout |
| 192.168.0.110 (docker-host) | timeout |
| 192.168.0.111 (adguard) | timeout |
| 192.168.0.208 (caddy) | timeout |
| 192.168.0.204 (claude-mgmt) | **works** |

LXC 109 was the exception only because `~/.ssh/config` already carried a per-host override left over from the [32](./32_Nobara_SSH_Freeze_Investigation.md) investigation:

```
Host 192.168.0.204 claude-mgmt
    IPQoS none
```

That block is itself the evidence that the fault is not new. It was written on 2026-08-07 as a workaround scoped to a single host, so the marking was already being dropped then; every other host simply went untested for three weeks.

## Why doc 32 excluded this and was not wrong

On 2026-08-07 all five markings (`none`, `af21`, `cs1`, `lowdelay`, `throughput`) connected successfully, verified on the wire with `tcpdump -v`. The hypothesis failed its direct test and was correctly recorded as excluded.

What doc 32 already named, and what now looks like the mechanism: Nobara's "Ethernet" does not run to a switch, it runs through a TP-Link RE605X extender over a wireless backhaul, and WMM sorts frames into hardware queues by DSCP. A wireless queue that drops or starves an access category is exactly the kind of fault that is intermittent on one day and total on another. **This is inference from the topology, not a measurement - the drop point was not located.** Locating it would mean `tcpdump` on both sides of the extender simultaneously.

The general lesson is worth more than the specific cause: a hypothesis excluded by measurement is excluded *for the conditions of that measurement*, not forever.

## Fix

One block appended to `~/.ssh/config` on Nobara, replacing the single-host workaround with a global one:

```
Host *
    IPQoS none
```

Backup at `~/.ssh/config.bak`. Verified afterwards, with no `-o` overrides on the command line:

```
docker  -> docker-host
claude  -> claude-mgmt
vps     -> homelab-vps
master  -> opt5060-i5
proxmox -> pve, pve-manager/9.2.4/5e5ae681198514d4
```

The tailnet hosts (`master`, `worker1`, `worker2`, `orange`) were never affected, because WireGuard encapsulates the marked packet and the outer header is unmarked. They keep working with the global setting.

## The second fault, which the first one was hiding

Over the Tailscale path, SSH to pve returned something different:

```
root@100.116.49.30: Permission denied (publickey,password)
```

That is an authentication failure, not a network one, and it had a separate cause: pve's `/root/.ssh/authorized_keys` held four keys - `root@pve`, `claude-mgmt`, `termux`, `nex-pc-windows` - and none of them was Nobara's Linux key.

The pve journal explains why this had never been noticed:

```
Aug 07 20:12:08 pve sshd-session[2326907]: Accepted publickey for root from 192.168.0.100 port 60964 ssh2: ED25519 SHA256:V8CH...
```

The source IP is Nobara's, but the fingerprint is the `nex-pc-windows` key. It is the same physical machine booted into Windows (see [winpc](../hosts/winpc.md)). Nobara's own key, generated 2026-02-06, had never been installed on pve at all. Every successful login from that address had come from the Windows side.

Fixed with `ssh-copy-id -f -i <key> root@192.168.0.109`, backup at `/root/.ssh/authorized_keys.bak`.

**Two independent faults on one path produce one confusing symptom.** The timeout looked like a network problem and masked an authentication problem that would have surfaced immediately on its own. Neither is a regression from a recent change; both had been latent for weeks.

## Open, not chased

Nobara is dual-homed on the same subnet: `enp39s0` at 192.168.0.100 and `wlp41s0` at 192.168.0.90, each with its own default route (metric 100 and 600). `arping -c3 -I enp39s0 192.168.0.109` returns 6 replies to 3 probes, all from the same MAC. The `arp_ignore`/`arp_announce` sysctls from [32](./32_Nobara_SSH_Freeze_Investigation.md) are meant to contain this, and it is not what caused the timeout - `-b 192.168.0.90` and `-b 192.168.0.100` behaved identically in both directions of the `IPQoS` test. It stays on the list for the still-open freeze investigation.

## Third case: the SSHFS service runs as root (2026-10-17)

**Symptom:** Dolphin stopped opening on Nobara right after a pve reboot. Every launch added another hung process; seven were stuck at once, all in `request_wait_answer` (a FUSE wait). The NFS shares were not involved: `showmount -e 192.168.0.109` listed all five exports and `ls /mnt/storage` answered.

**Cause:** the hang was on `/mnt/claudemgmt`, the SSHFS mount from LXC 109, which rebooted with pve at 13:00:44. `mnt-claudemgmt.service` has no `User=`, so its ssh runs as root, and the `Host * / IPQoS none` block from the fix above only applies to nex. Every reconnect attempt failed:

```
sshfs[46453]: ssh: connect to host 192.168.0.204 port 22: Connection timed out
sshfs[8378]: read: Connection reset by peer
```

Measured at the same moment, from the same machine:

| Probe | Result |
|---|---|
| raw TCP to 192.168.0.204:22 (as nex) | open |
| `ssh root@192.168.0.204` (as nex, `IPQoS none` from `~/.ssh/config`) | connects instantly |
| sshfs reconnect ssh (as root) | `SYN-SENT` for 2 min 15 s, `tcpdump` on LXC 109 sees no SYN from .100 at all |

The same raw-TCP-vs-SSH asymmetry as in the first case, now split by user instead of by host. Unlike 2026-08-27, the SYN itself never arrived. Unverified on the wire, but the likely reason is that `openssh-clients-10.2p1` (installed 2026-10-11) sets the DSCP marking before `connect()`, so the SYN carries it too.

**Fix, part 1 - system-wide `IPQoS none`:**

```bash
echo 'IPQoS none' | sudo tee /etc/ssh/ssh_config.d/10-ipqos-none.conf
```

The file is in `ssh_config.d`, so it applies to every user, root and systemd services included. A package update does not overwrite it. That the file was the cause was proven by timing: sshfs reconnected on its own the moment the file existed, before the service was restarted, and the seven queued Dolphin windows opened at once.

**Fix, part 2 - fail fast during a real outage.** With reconnect working, one problem remained: while LXC 109 or pve is actually down, every access to the mount waits for the TCP connect timeout. Measured with throwaway mounts and an `iptables -j DROP` for Nobara's ssh traffic on pve (removed automatically after 300 s):

| Mount options | 1st `ls` during outage | 2nd `ls` | Recovery after the outage |
|---|---|---|---|
| current (`reconnect`, `ServerAliveInterval=5`) | 133 s | 135 s | automatic, 0 s |
| plus `ConnectTimeout=5` | 5 s | 5 s | automatic, 0 s |

Applied as a drop-in, `/etc/systemd/system/mnt-claudemgmt.service.d/20-connecttimeout.conf`:

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/sshfs root@192.168.0.204:/root /mnt/claudemgmt -f -o allow_other -o IdentityFile=/home/nex/.ssh/id_ed25519 -o reconnect -o ServerAliveInterval=5 -o ServerAliveCountMax=2 -o ConnectTimeout=5
```

The empty `ExecStart=` clears the original line; without it systemd rejects a second `ExecStart` on a `Type=simple` unit. Now, when LXC 109 is down, `/mnt/claudemgmt` returns an error after 5 seconds and the rest of Dolphin stays usable.

**Trap when verifying:** `systemctl restart` returns before sshfs has mounted, so an `ls` right after it lists the empty local directory underneath (which holds a stray `homelab` folder) and looks like a broken mount. Check with `findmnt /mnt/claudemgmt` instead.

**Lesson:** a fix in `~/.ssh/config` covers one user. Anything that runs ssh as another user (systemd services, root cron jobs, sshfs mounts) needs the setting in `/etc/ssh/ssh_config.d/`.

## Diagnostic reference

| Question | Command |
|---|---|
| Is it the network, sshd, or the SSH client? | `cat < /dev/null > /dev/tcp/HOST/22` next to `ssh HOST` - if they disagree, it is the client's socket options |
| Is DSCP the difference? | `ssh -o IPQoS=none HOST` |
| Did the option reach the wire? | `tcpdump -v` and read the `tos` field |
| Which key actually authenticated, and from where? | `journalctl -u ssh \| grep Accepted` - it logs source IP and key fingerprint |
| Which keys does the target accept? | `ssh-keygen -lf /root/.ssh/authorized_keys` |

## Related

- [32 - Nobara SSH Freeze Investigation](./32_Nobara_SSH_Freeze_Investigation.md)
- [31 - Tailscale Port Collision + DNS Audit](./31_Tailscale_Port_Collision_DNS_Audit.md)
- [Nobara PC](../hosts/nobara.md)
