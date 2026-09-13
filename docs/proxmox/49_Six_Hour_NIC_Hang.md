# Six Hours of "No Internet" That Was One Hypervisor NIC

**Date:** 2026-09-13
**Hostname:** pve (HP EliteDesk 800 G4), adguard (LXC 102), claude-mgmt (LXC 109), docker-host (LXC 100), nex-pc (Nobara desktop)
**IP address:** 192.168.0.109, 192.168.0.111, 192.168.0.204, 192.168.0.110, 192.168.0.100

## Status: root cause identified, workaround deliberately not applied

Overnight the TV could not reach Jellyfin, and the Nobara desktop reported no internet connection. Power-cycling the router restored everything. The router was never at fault. The Intel I219-LM on the Proxmox host wedged its transmit ring at 02:58:53 and stayed wedged for 6 hours 15 minutes; the router's power cycle happened to drop the link, and the link event was what freed it.

The first instinct was a rogue DHCP server on the RE605X extender, and its DHCP was switched off as a precaution. That was not the fault either, and the section below says how that was ruled out rather than assumed.

## The report, and what each symptom actually was

| Reported | Actual |
|---|---|
| TV cannot reach Jellyfin | Jellyfin is LXC 100 on pve. Its traffic leaves through the hung NIC. |
| Nobara says "no internet" | Nobara's resolver is AdGuard on LXC 102, also on pve. DNS was dead, so NetworkManager's connectivity check failed. Nobara's own network was fine. |
| Router reboot fixed it | The link down/up reset the NIC. Rebooting anything that drops that link would have worked. |

## Three clocks, one onset

The strength of the diagnosis is that three independent subsystems, logging on two different machines, agree on the minute without being told to.

```
pve kernel      02:58:53  e1000e 0000:00:1f.6 nic0: Detected Hardware Unit Hang
LXC 109 tailscaled  02:59:52  logtail upload: context deadline exceeded
LXC 109 tailscaled  03:00:15  netcheck: UDP is blocked, trying HTTPS
LXC 102 AdGuardHome 03:00     upstream errors go from 60/hour to 12,000/hour
```

AdGuard's error histogram, per hour, is the clearest shape of the outage:

```
Sep 12 22:00      42
Sep 12 23:00      48
Sep 13 00:00      60
Sep 13 03:00    9851      <- onset
Sep 13 04:00   12327
Sep 13 05:00   12596
Sep 13 06:00   12979
Sep 13 07:00   12533
Sep 13 08:00   13111
Sep 13 09:00    3328      <- ends at 09:14
```

### The timezone trap that nearly moved the onset by two hours

`pve` runs CEST. Every LXC on it runs UTC. Read straight off the screen, AdGuard's storm starts at `01:00` and the kernel hang at `02:58`, which looks like a two-hour gap and invites a story about what happened in between. There was no gap. `01:00 UTC` is `03:00 CEST`.

Check it before correlating anything across a container boundary here:

```bash
date                                    # 09:25 CEST on pve
ssh root@192.168.0.111 'date'           # 07:25 UTC in the LXC
```

## Why one NIC took the whole house down

```
# /etc/network/interfaces on pve
auto vmbr0
iface vmbr0 inet static
	address 192.168.0.109/24
	gateway 192.168.0.1
	bridge-ports nic0
```

`nic0` is the only bridge port of `vmbr0`. Every LXC and VM on the hypervisor - AdGuard, Jellyfin and the rest of the docker host, Home Assistant, Caddy, this management LXC - reaches the LAN through that single interface. Bridge-internal traffic between two LXCs never touches the NIC and kept working, which is why `ssh` between containers stayed up and made the fault look like a DNS problem rather than a link problem.

The hang is on the transmit side specifically. Inbound frames still arrived; replies never left.

## The driver never recovered on its own

```
Sep 13 02:58:53 pve kernel: e1000e 0000:00:1f.6 nic0: Detected Hardware Unit Hang:
                              TDH                  <8a>
                              TDT                  <4a>
                              next_to_use          <4a>
                              next_to_clean        <89>
                            buffer_info[next_to_clean]:
                              time_stamp           <1438647d9>
                              next_to_watch        <8a>
                              jiffies              <143864c00>
                              next_to_watch.status <0>
```

`TDH` (head) stuck at `0x8a` while `TDT` (tail) sits at `0x4a`: the hardware stopped consuming the descriptor ring and the driver kept queueing behind it.

11,246 of these were logged, a steady 1800 per hour - one every two seconds - for the whole window. In the same window:

```bash
journalctl -k --since "2026-09-13 02:00" --until "2026-09-13 09:20" \
  | grep -icE "reset adapter|NETDEV WATCHDOG|transmit queue.*timed out"
0
```

Zero. The usual e1000e story is hang, then `Reset adapter unexpectedly`, then a few seconds of outage. Here the detection fired 11,246 times and the reset path never did, which is what turned a transient into six hours. Without the link event it would presumably still be hung.

```
Sep 13 09:13:43 pve kernel: e1000e ... nic0: Detected Hardware Unit Hang   <- last one
Sep 13 09:13:44 pve kernel: e1000e ... nic0: NIC Link is Down              <- router unplugged
Sep 13 09:14:11 pve kernel: e1000e ... nic0: NIC Link is Up 10 Mbps Half Duplex
Sep 13 09:14:11 pve kernel: e1000e ... nic0: NIC Link is Down
Sep 13 09:14:15 pve kernel: e1000e ... nic0: NIC Link is Up 1000 Mbps Full Duplex
```

## The hardware

```
$ lspci -nnk -s 00:1f.6
00:1f.6 Ethernet controller [0200]: Intel Corporation Ethernet Connection (7) I219-LM [8086:15bb] (rev 10)
	DeviceName: Onboard Lan
	Kernel driver in use: e1000e

$ ethtool -i nic0
driver: e1000e
version: 7.0.14-3-pve
firmware-version: 0.5-4

$ ethtool -k nic0 | grep -E "segmentation"
tcp-segmentation-offload: on
generic-segmentation-offload: on
```

The I219 family has a long-standing transmit-path defect that Intel has acknowledged as a hardware bug and never fixed in silicon. Disabling TSO is the documented workaround; there is no driver-side cure.

This is the first occurrence on this host. The retained journal reaches back to 2025-12-19 and contains no `Hardware Unit Hang` line before today.

## Two things that look like evidence and are not

**The NFS timeouts immediately before the hang.** The kernel log has `nfs: server 192.168.0.100 not responding, timed out` starting at 02:58:04, 49 seconds before the first hang, which reads like a trigger. It is not. The same message appears about 600 times an hour going back to 2026-09-11, and it was still appearing at 09:14:55 after the NIC had recovered. It is a separate, pre-existing fault on the Nobara backup export, tracked below. Whether its constant TCP retransmits contributed to wedging the ring is unproven and this investigation does not claim it.

**A successful `dig @9.9.9.9` proving upstream DNS is fine.** It proves nothing on this LAN. The Archer C6 intercepts every outbound port 53, so a plain UDP query is answered by the router regardless of whether Quad9 is reachable - the measurement is in the [AdGuard Home setup](./05_AdGuard_Home_Setup_Dedicated_LXC_Tailscale_DNS_Integration.md). AdGuard's real upstreams are DoT on 853 and DoH on 443, and those are the ones that were timing out. Test those ports, not 53:

```bash
for p in 853 443; do timeout 5 bash -c "</dev/tcp/9.9.9.9/$p" && echo "$p OK" || echo "$p FAIL"; done
```

## Ruling out the extender

A rogue DHCP server on the RE605X would show up as a lease event, a changed gateway or a changed resolver on some host. The overnight journals of both the AdGuard and docker-host LXCs contain zero DHCP, lease, or renew lines:

```bash
ssh root@192.168.0.111 'journalctl --since "2026-09-12 20:00" \
  | grep -icE "dhcp|lease|carrier|renew"'
0
```

Nothing was handed a bad lease, and the fault is fully explained on the hypervisor. Leaving the extender's DHCP off is harmless and one less thing that can serve a lease, so it stays off.

## The workaround, and why it is not applied

```
iface nic0 inet manual
	post-up /sbin/ethtool -K nic0 tso off gso off
```

Applied live, without a reboot, and reversible with `tso on gso on`:

```bash
ethtool -K nic0 tso off gso off
```

The cost is host CPU: with TSO off, segmentation of large outbound frames moves from the NIC to the kernel. On a box that mostly serves media over the LAN that is measurable under sustained transfer.

**Not applied, by decision.** One occurrence in nine months of retained logs does not justify permanently giving up an offload on the hypervisor's only uplink. The trade is worth revisiting on the second occurrence, and the monitor below is what will make a second occurrence visible on the day it happens rather than in the morning.

## What this exposed

**Nothing alerted for six hours.** There are Uptime Kuma push monitors on the cron jobs, but nothing watches whether pve itself can reach the internet, and nothing reads the kernel ring buffer. Both gaps are cheap to close: a push monitor driven by an outbound check from pve, and a journal match on `Hardware Unit Hang`. The existing push-monitor pattern is in [35 - Cron Job Monitoring](./35_Cron_Job_Monitoring_Uptime_Kuma.md).

**The Nobara NFS export is intermittently dead.** `192.168.0.100:/mnt/hdd/Backup` on `/mnt/pve/nobara-backup` times out for hours at a stretch - continuously from 2026-09-11 23:00 to 2026-09-12 08:00, then again from 2026-09-13 00:24 until the desktop was rebooted this morning, after which it mounts and lists normally. The mount is `soft,timeo=30,retrans=3`, so it fails rather than blocks, but a Proxmox backup target that is absent for nine-hour stretches is not a backup target. This is plausibly the same underlying condition as [32 - Nobara SSH Freeze](./32_Nobara_SSH_Freeze_Investigation.md), which is still open.
