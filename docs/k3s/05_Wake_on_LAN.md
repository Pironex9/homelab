**Date:** 2026-08-28
**Cluster:** 3x Dell OptiPlex, 192.168.1.0/24 (separate location, Tailscale access only)

---

# Wake-on-LAN

Powering the remote nodes on over the network, and why the obvious setup silently does not survive a shutdown.

Split out of the [K3s Cluster host page](../hosts/k3s-cluster.md) on 2026-08-28,
which had grown to 1983 lines and six unrelated projects. The host page keeps the
machine reference - hardware, addressing, live state, access - and this page keeps
the work. Nothing below was rewritten in the move.

---

## Wake-on-LAN

The cluster is powered off when not in use. An Orange Pi One (Armbian) on the same network handles WoL.

### Orange Pi One

| Property | Value |
|----------|-------|
| OS | Armbian 25.8.1 Noble |
| Role | WoL server + Tailscale exit node |
| Interface | end0 (MAC `02:81:85:dc:83:d9`, locally administered) |
| Local IP | 192.168.1.100 (DHCP reservation on the remote router, 2026-08-29) |
| Tailscale IP | 100.120.73.44 |
| Tailscale hostname | orangepione |
| User | nex |

**The LAN address drifted for months before anyone noticed.** It had no DHCP
reservation, and the two places that recorded it disagreed with each other and with
reality: this page said `192.168.1.52`, the host page said `192.168.1.51`, and on
2026-08-29 it answered on `192.168.1.100`. Nothing broke, because every caller
reaches it by the Tailscale name `orangepione` - which is exactly why the drift
stayed invisible. A reservation for `192.168.1.100` was added on the remote router
the same day, so the two now agree. The interface still reports the address as
`dynamic`; a reservation is a pinned lease, not a static address, and `ip addr`
cannot tell the two apart.

**It offers an exit node, not the subnet route.** Measured from a peer on
2026-08-29, its approved `AllowedIPs` are `0.0.0.0/0` and `::/0` only. It also
advertises `192.168.1.0/24`, but that prefix is not approved on this machine and
`PrimaryRoutes` is empty - `opt3060-i3` carries the subnet route. Advertising a
prefix and serving it are two different states, and `tailscale status` on the
board itself shows the advertisement either way.

### WoL script

**File:** `/usr/local/bin/wakeonlan.sh` on the Orange Pi, root-owned.

**It has three callers, all pointing at this one file** - that matters, because on
2026-08-27 a fix landed in a second copy under `/home/nex/` and the web UI kept running
the old broken one for an hour:

| Caller | How |
|---|---|
| `nex` crontab | `@reboot sleep 60 && /usr/local/bin/wakeonlan.sh` |
| Web UI on port 5000 | `/usr/local/bin/wol-web.py` -> `GET /wake` -> `subprocess.run` |
| By hand | `ssh nex@orangepione "sudo /usr/local/bin/wakeonlan.sh"` |

Editing it needs the `nex` sudo password: the passwordless sudo on that box covers only
`/usr/sbin/etherwake` and the script itself, and there is no root SSH key. That is
annoying but it is the right trade - the alternative, a user-owned copy elsewhere, is
exactly what produced the two-copies bug above.

```bash
#!/bin/bash
# K3s Cluster wake up script
#
# Two packet formats per MAC, over several rounds. Both decisions come from
# measurement - see "Why the master never woke" below.
#
# The first round runs in the foreground, the rest in the background. Otherwise the
# web UI blocks for 104 s (measured), because wol-web.py calls it with
# capture_output=True. The background block redirects to /dev/null on purpose: if it
# inherited the pipe, subprocess.run would still wait for it to finish.

MAC1="54:bf:64:68:a0:30"  # opt5060-i5  (Intel I219 - ONLY the UDP form wakes it)
MAC2="54:bf:64:a2:ff:77"  # opt3060-i3  (Realtek RTL8168h)
MAC3="d8:9e:f3:13:4d:97"  # opt3050-i5  (Realtek RTL8168h)
INTERFACE="end0"
BCAST="192.168.1.255"
ROUNDS=6      # 6 rounds x 20 s = ~100 s of coverage
GAP=20

send_udp() {
    python3 -c '
import socket, sys
mac, bcast = sys.argv[1], sys.argv[2]
pkt = b"\xff" * 6 + bytes.fromhex(mac.replace(":", "")) * 16
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
for port in (7, 9):
    s.sendto(pkt, (bcast, port))
' "$1" "$BCAST"
}

send_round() {
    for MAC in $MAC1 $MAC2 $MAC3; do
        sudo etherwake -i $INTERFACE $MAC
        send_udp "$MAC"
    done
}

echo "Waking up nodes ($ROUNDS rounds over $((ROUNDS * GAP))s, etherwake + UDP magic packet)..."
send_round
echo "  round 1/$ROUNDS sent, rounds 2-$ROUNDS continue in the background"

(
    for r in $(seq 2 $ROUNDS); do
        sleep $GAP
        send_round
    done
) >/dev/null 2>&1 &

echo "Wake packets sent to all nodes"
```

Previous version kept as `/usr/local/bin/wakeonlan.sh.bak-2026-08-27` (the original
412-byte `etherwake`-only script).

### Web UI (port 5000)

`/usr/local/bin/wol-web.py`, a Flask app run as root by `wol-web.service`, listening on
`0.0.0.0:5000` - reachable over Tailscale at `http://100.120.73.44:5000/`. `GET /wake`
shells out to `wakeonlan.sh` and returns its stdout.

Because it uses `subprocess.run(..., capture_output=True)`, **anything the script leaves
holding stdout keeps the HTTP request open**. That is why the retry rounds background
themselves with `>/dev/null 2>&1` rather than just `&`. Measured before and after:
104.65 s -> 0.82 s, with the background rounds confirmed still running afterwards.

**Auto-start on boot** (`nex` user crontab):
```
@reboot sleep 60 && /usr/local/bin/wakeonlan.sh
```

Passwordless sudo configured for both `etherwake` and the script:
```
/etc/sudoers.d/etherwake:  nex ALL=(ALL) NOPASSWD: /usr/sbin/etherwake
/etc/sudoers.d/wakeonlan:  nex ALL=(ALL) NOPASSWD: /usr/local/bin/wakeonlan.sh
```

**Remote trigger from any Tailscale node:**
```bash
ssh nex@orangepione "sudo /usr/local/bin/wakeonlan.sh"
```

### WoL reliability notes

WoL is unreliable after extended offline periods (hours/days). Known causes:

- **Packet format** - the biggest one, and the one that cost years of "WoL is flaky here": `etherwake`'s raw `0x0842` frame never woke the master. See the section below; the script now sends a UDP magic packet as well.
- **GS305 Green Ethernet (IEEE 802.3az)** - the switch puts ports into low-power idle when a device disconnects. Unmanaged - cannot be disabled. Suspected for a long time, never actually confirmed as a cause.
- **NIC WoL state** - `ethtool wol g` is re-applied on each boot via `wol.service`. If the machine was power-cut before booting, the state may be lost.

**Workaround:** If WoL fails, power-cycle the node physically or via a smart PDU. BIOS should be set to `AC Power Recovery = Power On` so the node boots automatically on power restore.

### Why the master never woke, and the two workers always did (2026-08-27)

**The packet format, not the BIOS and not the switch.** `etherwake` sends a raw
Ethernet frame with EtherType `0x0842`. The master's Intel I219 does not wake on that
frame in any form; it wakes on the identical payload wrapped in a UDP broadcast. Both
Realtek workers accept either. Proven with three controlled shutdown-and-wake cycles
on the live master:

| Sent from the Orange Pi | Result |
|---|---|
| `etherwake` unicast, 3x (the original script) | nothing in 180 s |
| `etherwake -b` broadcast frame, 5x | nothing in 75 s |
| **UDP magic packet to `192.168.1.255:9`** | **awake in 24 s** |

Timing on the first successful wake, from the machine's own side: `uptime -s` said
16:45:23 CEST and `systemd-analyze` reported 14.274 s firmware + 2.924 s loader, which
puts the power-on at ~14:45:06 UTC - two seconds after the UDP packet, and five minutes
after the `etherwake` batch that did nothing.

**And a second, independent cause: timing.** A magic packet sent ~40 seconds after
`systemctl poweroff` was simply lost - the deployed script fired that early on the
fourth test cycle and the master stayed dark for 75 seconds. The identical packet sent
2 to 5 minutes after shutdown woke it every time. The NIC does not arm its WoL filter
the instant the OS stops; there is a window at the start of S5 where magic packets go
nowhere. The exact threshold is somewhere between 40 s and 2.5 minutes and was not
narrowed further - four power cycles on a remote machine was enough.

This is very likely a large part of the historical "WoL is unreliable here", and it is
why the script now sends **6 rounds 20 seconds apart** rather than one burst: with
~100 seconds of coverage the timing does not have to be guessed.

The fix is in `wakeonlan.sh` above: **both** formats, to every MAC, over several rounds.
`etherwake` stays because it demonstrably works on the workers and costs nothing.

!!! warning "The retrying version has not been proven against a powered-off machine"

    The format and the timing were each proven on a live master. The 6-round script
    that combines both was verified only to run cleanly end to end (no sudo prompt, all
    rounds sent) - it has not itself been tested on a machine that was actually off,
    because that would have needed a fifth power cycle after the `Auto On 17:30`
    backstop had already passed for the day.

Everything else was measured and ruled out first, rather than assumed:

| Checked | opt5060-i5 (master) | opt3060-i3 (worker) | Verdict |
|---|---|---|---|
| MAC in `wakeonlan.sh` vs `/sys/class/net/*/address` | `54:bf:64:68:a0:30` = matches | matches | not it |
| BIOS `WakeOnLan` | `LanWlan` | `LanWlan` | not it |
| BIOS `DeepSleepCtrl` | `Disabled` | `Disabled` | not it |
| OS `ethtool ... Wake-on` | `g` | `g` | not it |
| `wol.service` | enabled, active | enabled, active | not it |
| EEE (802.3az) on the link | was `enabled - active` | `disabled` | see below |
| NIC | Intel I219 (`e1000e`) | Realtek RTL8168h (`r8169`) | explains the format difference |

`DeepSleepCtrl` is the setting Dell's own troubleshooting guide names first, and it was
already `Disabled` here, so the usual answer never applied to this machine.

!!! note "EEE was disabled too, and it is **not** proven to have mattered"

    Energy Efficient Ethernet was `enabled - active` on the master and `disabled` on
    both workers, which looked like the answer before the packet formats were separated.
    It was turned off (`ethtool --set-eee eno1 eee off`, link stayed up at 1000Mb/s) and
    made persistent as a second `ExecStart` in `wol.service` **before** the wake tests
    ran, so every test above happened with EEE already off. That means the tests say
    nothing about EEE either way: plain `etherwake` failed with EEE off just as it had
    with EEE on.

    It is being kept because it costs nothing and matches the two working nodes, not
    because it was shown to fix anything. Unit backup:
    `/etc/systemd/system/wol.service.bak-2026-08-27`; to revert, drop the line and run
    `ethtool --set-eee eno1 eee on`.

**Independent of all this, the master now has a backstop:** BIOS `AC Power Recovery =
Power On` plus `Auto On = Everyday 17:30`. The two workers are on `Last State`, which is
why they returned after the 2026-08-25 outage and the master did not.

After three power cycles in twenty minutes the cluster came back clean every time: all
3 nodes `Ready`, all Argo CD apps `Synced/Healthy`, all Longhorn disks `Ready`, one
default StorageClass, and `journalctl -u k3s -b | grep -c corrupt` returning 0.

#### Reading Dell BIOS settings from Linux, without a reboot

The 5060 and 3060 expose their BIOS through the `dell-wmi-sysman` kernel driver, so the
settings above were read over SSH rather than from a BIOS screen at the remote site:

```bash
cd /sys/class/firmware-attributes/dell-wmi-sysman/attributes
sudo cat WakeOnLan/current_value      # LanWlan
sudo cat WakeOnLan/possible_values    # Disabled;LanOnly;WlanOnly;LanWlan;LanWithPxeBoot;
sudo cat DeepSleepCtrl/current_value  # Disabled
sudo cat AutoOn/current_value         # Everyday
```

`current_value` reads as empty without root - it is not missing, it is unreadable.
The older `opt3050-i5` has no `dell-wmi-sysman`, so its BIOS still needs a screen.

### WoL persistence on K3s nodes

WoL resets to disabled after reboot on Linux. Each node has a systemd service to re-enable it:

**`/etc/systemd/system/wol.service`** (opt5060-i5 uses `eno1`, workers use `enp1s0`):
```ini
[Unit]
Description=Enable Wake-on-LAN on eno1
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/sbin/ethtool -s eno1 wol g
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

Status: all 3 nodes have `wol.service` enabled and active.
