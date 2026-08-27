# Nobara SSH Freeze - Open Investigation

**Date:** 2026-08-07
**Hostname:** nex-pc (Nobara desktop), claude-mgmt (LXC 109), pve, docker-host (LXC 100)
**IP address:** 192.168.0.100, 192.168.0.204, 192.168.0.109, 192.168.0.110

## Status: unresolved

This documents an investigation that did **not** find its root cause. It is written down anyway, because the value is in what has already been excluded and in the measurement setup that is now running. Without this, the next attempt would start by re-testing the same five wrong hypotheses.

## Symptom

An interactive SSH session from the Nobara desktop to LXC 109, running Claude Code, freezes completely for long stretches. Nothing renders, typed input does not echo, and the "thinking" animation stops mid-frame. It recovers on its own. Reported the same day as a Nobara update to kernel `7.1.4-200.nobara.fc44` and NVIDIA `595.84`, and alongside a report that a phone on the house WiFi could not reach the internal network either.

## Ruled out, with the measurement that ruled it out

| Hypothesis | Why it is not the cause |
|---|---|
| Tailscale | During a freeze, `tailscale ping` answers in 2-4 ms and SSH over the tailnet IP connects instantly, while the LAN path is dead |
| Tailscale UDP port collision | Real and fixed (see [31](./31_Tailscale_Port_Collision_DNS_Audit.md)), but the freezes continued afterwards |
| NVIDIA / kernel hang | All five reboots that day ended with a clean `systemd-shutdown`; no hung task, no Xid, no NIC error in the journal |
| Memory pressure on LXC 109 | 8.1 GB of 10 GB available, no swap configured, memory PSI ~0 |
| IO stall on LXC 109 | The high figures in `/proc/pressure/io` are the **host's** - an unprivileged LXC is not PSI-namespaced and shows pve's numbers verbatim. pve's thin pool was at 77.8%, not critical |
| MTU / path blackhole | A 4000-byte transfer over the same LAN path on port 2222 completes instantly, including a small-write-then-wait pattern that mimics sshd |
| sshd broken on Nobara | SSH from Nobara to its **own** LAN IP completes the full handshake instantly while every remote client times out |
| DSCP marking (`IPQoS`) | All five markings (`none`, `af21`, `cs1`, `lowdelay`, `throughput`) connect successfully, and `tcpdump` confirms the option really changes the wire (`af21` produces `tos 0x48`, `none` produces `tos 0x0`) |

> **Superseded in part, 2026-08-27.** The DSCP row above records what was measured on this date and stays as written. Three weeks later the same marking blackholed every SSH connection from Nobara to every LAN host, and `IPQoS none` fixed it - see [43 - Nobara DSCP SSH Timeout](./43_Nobara_DSCP_SSH_Timeout.md). A hypothesis excluded by measurement is excluded for the conditions of that measurement. It says nothing about the session freezes documented here, which remain unexplained.

The DSCP hypothesis was the most promising one and is worth spelling out, because it looked airtight for a while: OpenSSH is the only traffic on this LAN that marks its packets, Nobara's "Ethernet" actually runs through a TP-Link RE605X extender over a wireless backhaul, and WMM sorts frames into hardware queues by DSCP. It still failed the direct test.

## Two failures that were measured, and are real

### 1. Port 22 blackholed in one direction

For roughly ten minutes, every SSH connection **to** Nobara stalled in the banner exchange, from three different clients (LXC 109, LXC 100, pve). At the same time, on the same LAN path to the same IP: ping was lossless, closed ports refused correctly, Ollama on :11434 and Syncthing on :8384 both answered HTTP 200 in single-digit milliseconds, and a purpose-built listener on :2222 transferred 4000 bytes instantly.

The sender-side socket showed what was happening:

```bash
ss -tinm '( sport = :22 )'
# ESTAB 192.168.0.100:22 -> 192.168.0.204:35600
#   bytes_received:41            <- the client's version string arrived
#   bytes_sent:2206  bytes_retrans:1136  unacked:2  lost:2
#   mss:64 / mss:128             <- collapsed from 1448 by black-hole probing
```

So the client-to-server direction was perfect and the server-to-client **data** packets were being dropped, with the kernel retransmitting at ever smaller MSS. Pure ACKs and SYN/ACKs passed throughout, which is why the TCP handshake always succeeded and only the payload vanished.

`sshd` itself was healthy the whole time - proven by SSH from Nobara to its own LAN address completing normally.

### 2. Root-only connect timeout for 17 minutes

Separately, `mnt-claudemgmt.service` failed 34 consecutive times over 17 minutes. Its `ExecStartPre` probe timed out at exactly 3.015 s each attempt, matching `ConnectTimeout=3`, and a manual `ssh -v` as root confirmed `connect to address 192.168.0.204 port 22: Connection timed out`.

During that same window, `nex` on the same machine opened 17 genuine connections to the same address, verified in LXC 109's `sshd` log by source port, with no `ControlMaster` socket involved. Several landed in the same second as a service failure.

This is the part that makes no sense yet:

- `ip route get 192.168.0.204 uid 0` and `uid 1000` return identical results
- `nft list ruleset` contains no `skuid`, `cgroup` or owner match
- the DSCP difference between the two was tested and excluded
- it recovered by itself and root has worked since

A 17-minute outage correlated with UID, on a host with no UID-based mechanism. Recorded as an open contradiction rather than explained away.

## Changes applied along the way

None of these fixed the freeze. They were all real defects found while looking, and are worth keeping.

| Change | Where |
|---|---|
| Tailscale UDP port 41641 -> 41645 | `/etc/default/tailscaled` on Nobara, the fifth node behind the router |
| WiFi power save off | `nmcli connection modify Secret 802-11-wireless.powersave 2` |
| `arp_ignore=1`, `arp_announce=2` | `/etc/sysctl.d/99-arp-flux.conf` on Nobara, dual-homed on 192.168.0.0/24 |
| `IPQoS none` (server) | `/etc/ssh/sshd_config.d/99-ipqos.conf` on both Nobara and LXC 109 |
| `IPQoS none` (client) | `~/.ssh/config` on both hosts, scoped to the other host |
| Verbose `ExecStartPre` | `systemctl edit mnt-claudemgmt.service` on Nobara - the original swallowed the error with `2>/dev/null` |

## What is running now

Two watchers on LXC 109, because the failure never appeared while anything was looking at it. They cover different failure modes on purpose.

| Script | Catches | Log |
|---|---|---|
| `scripts/nobara-freeze-watch.sh` | **New** connections failing. Every 30 s it probes SSH, HTTP, Tailscale and ping side by side, so a port-22-only failure is immediately distinguishable from a dead path. On `ssh22` down while `http` up, it dumps the sender-side socket state | `/var/log/nobara-freeze.log` |
| `scripts/nobara-session-stall.sh` | An **established** session going silent, which is what the user actually experiences. Two 5 s heartbeats, one per direction, the reverse one tunnelled over Tailscale so the outer hop cannot be what stalls. Logs gaps over 6 s, dumps sockets over 8 s | `/var/log/nobara-stall.log` |

Neither has recorded a single failure during a reported freeze so far. That is itself a finding: during the user's freezes, new connections in both directions kept succeeding and an already-open session on LXC 109 never missed a heartbeat.

## Where to resume

1. Read both logs first. Do not form a hypothesis before reading them.
2. If `nobara-stall.log` shows a gap, the direction and the socket dump say whether packets were lost (retransmits, `unacked`) or whether the sender simply stopped writing.
3. If both logs are clean during a freeze, the network and both hosts were fine, and the remaining suspect is the local terminal on Nobara - Konsole, kwin/Wayland, or the NVIDIA driver. That path has not been investigated at all yet.
4. When `mnt-claudemgmt.service` next fails, the journal now contains the full `ssh -v` output. Note that its `ExecStartPre` authenticates as root with root's own key, while `ExecStart` passes `-o IdentityFile=/home/nex/.ssh/id_ed25519` - the two steps do not use the same credentials.

## Diagnostic reference

| Question | Command |
|---|---|
| Is the loss in the data direction, and how bad? | `ss -tinm '( sport = :22 )'` on the sender |
| Is it port 22 or the whole path? | probe :22, an HTTP port, and a scratch listener at once |
| Is sshd or the network at fault? | SSH from the host to its **own** LAN IP - it never leaves the machine |
| Does an option really change the wire? | `tcpdump -v` and read the `tos` field, do not trust the config |
| Is the container or the host under IO pressure? | `/proc/pressure/io` inside an LXC shows the **host's** values |

## Related

- [31 - Tailscale Port Collision + DNS Audit](./31_Tailscale_Port_Collision_DNS_Audit.md)
- [24 - IP Conflict and DHCP Incident](./24_IP_Conflict_DHCP_Incident_Network_Hardening.md)
- [Nobara PC](../hosts/nobara.md)
- [Claude Code Mgmt (LXC 109)](../hosts/claude-mgmt.md)
