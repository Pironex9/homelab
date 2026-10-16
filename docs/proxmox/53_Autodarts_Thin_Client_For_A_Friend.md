# Autodarts Thin Client for a Friend

**Date:** 2026-10-16
**Hostname:** 3darterde (Dell Wyse 5070 thin client)
**IP address:** 192.168.0.32 (home LAN, during setup only, DHCP), 100.72.153.27 (tailnet)

## Status: set up, on-site checks pending

A used Dell Wyse 5070 was prepared as the Autodarts computer for a friend's Autodarts Vantage. The people who will use it do not work with computers, so the target was a box that sits behind the board and runs Autodarts on power-on, with no input needed. They play from a tablet. The hard parts were not Autodarts itself. They were an SSH server that accepted every connection and never answered, a desktop that put the machine to sleep after 15 minutes, and an Autodarts self-update that broke its own autostart.

Three things can only be checked at the friend's place: the WiFi connection, AC power recovery after pulling the plug, and the Autodarts first-run wizard with the cameras attached. See [Still to verify on site](#still-to-verify-on-site).

## Why a thin client and not the tablet

The Vantage's three cameras connect over a single 3-in-1 USB cable, and detection runs in Autodarts Desktop. That app ships for Windows, macOS and Linux only. An Android tablet can be the display, but not the detection computer. The Autodarts docs list thin clients in the J4105 class among the tested setups, so a Wyse 5070 (Celeron J4105, 4 cores, 8 GB RAM) was bought used for 80 EUR. The same model sells preconfigured for Autodarts for 110-120 EUR. This unit arrived with a seller's image already on it: Debian 13 trixie, KDE Plasma on Wayland, SDDM autologin as user `autodarts`, hostname `3DarterDE`.

The Wyse has 4 USB 3.0 ports on the back. The Vantage cable goes into one of those. Running three cameras off one port is exactly where old laptops fail on power and bandwidth.

## Finding it on the LAN

The first ping sweep and ARP table showed no Dell MAC at all, because the box turned out to be switched off. Once it booted, a passive capture filtered on its wired MAC found it within seconds. A booting KDE machine announces itself over mDNS:

```
192.168.0.32.5353 > 224.0.0.251.5353: ... (Cache flush) A 192.168.0.32, (Cache flush) PTR 3DarterDE.local.
```

**A passive `tcpdump` on the MAC beats any scan.** It does not depend on the target answering ICMP, and the hostname arrives for free.

A port sweep then showed nothing listening except KDE Connect on 1716. There was no SSH and no Autodarts. KDE Connect answering on TCP ruled out a blanket firewall: the services were simply not running.

## The SSH server that never said hello

`openssh-server` was installed from the console (after an `apt update`, as the package index on the image was empty). The port opened, but every client failed:

```
Connection timed out during banner exchange
```

Two guesses were tested first and were wrong:

1. **Socket activation.** `ssh.socket` was disabled and `ssh.service` was enabled instead. The service ran (`active (running)`, listening on `0.0.0.0:22`), and nothing changed.
2. **NIC offload.** The Wyse uses the `r8169` driver (RTL8168h), which has a history of offload bugs. Running `ethtool -K enp1s0 tso off gso off tx off` changed nothing either.

`ssh autodarts@localhost` on the box itself got a password prompt immediately, so sshd was fine and the fault was on the network path. The sshd log agreed: it saw every one of our connections arrive and gave up on each with `Timeout before authentication`.

Once a shell was available over Tailscale (next section), a capture on both ends of the same connection showed where the data went. On the Wyse (`enp1s0`), sshd sent its banner and the key exchange, then retransmitted them:

```
192.168.0.32.22 > 192.168.0.204: Flags [P.], seq 1:42,     length 41: SSH: SSH-2.0-OpenSSH_10.0p2 Debian-7+deb13u4
192.168.0.32.22 > 192.168.0.204: Flags [P.], seq 42:1082,  length 1040
192.168.0.32.22 > 192.168.0.204: Flags [P.], seq 1:1082,   length 1081   # retransmit, x5
```

On claude-mgmt (LXC 109), and on the pve host's physical NIC `nic0`, only the SYN-ACK and the pure ACKs ever arrived. Not one data segment. The verbose capture showed the only difference:

```
IP (tos 0x0,  ...) 192.168.0.32.22 > 192.168.0.204: Flags [S.]     # arrives
IP (tos 0x0,  ...) 192.168.0.32.22 > 192.168.0.204: Flags [.]      # arrives
IP (tos 0xb8, ...) 192.168.0.32.22 > 192.168.0.204: Flags [P.] ... # never arrives
```

`tos 0xb8` is DSCP EF. OpenSSH 10.0 on Debian 13 defaults to `IPQoS ef cs1` (`sshd -T` printed `ipqos ef cs1`), so the server marks the banner itself. This is the same fault as [43](./43_Nobara_DSCP_SSH_Timeout.md), but from the server side. There, the Nobara client's af21 marking was dropped. Here it is the server's EF. Both times, raw TCP to the same port worked and SSH did not.

The fix is one line on the server:

```bash
echo "IPQoS none" | sudo tee /etc/ssh/sshd_config.d/10-ipqos-none.conf
sudo sshd -t && sudo systemctl restart ssh
sudo sshd -T | grep ipqos    # ipqos none none
```

What this adds to doc 43: the marked packets do not reach the pve host's physical NIC. They are lost before pve, on the switch or the Archer C6 path. Where exactly is still not measured. Traffic from the Wyse to the router and the internet (`apt`, an HTTP GET to 192.168.0.1) worked throughout, because those connections are unmarked. **Any new Debian 13 sshd on this LAN will hit this.** HTTP servers do not mark their packets, so Autodarts was never affected.

## Tailscale as the way in

While LAN SSH was still broken, Tailscale was installed from the console. It goes over UDP, which the Wyse delivered fine (its 1514-byte mDNS frames arrived too). That gave a shell to capture from. It stays on the box permanently anyway, for remote support.

```bash
curl -fsSL https://tailscale.com/install.sh -o ts.sh   # no pipe: German keyboard, see below
sudo sh ts.sh
sudo tailscale up                                      # deliberately WITHOUT --accept-routes
```

`--accept-routes` stays off. pve advertises `192.168.0.0/24`, and on Linux an accepted subnet route would pull the box's own LAN traffic into the tunnel. That is the same class of symptom as the one being debugged. `tailscale up` confirmed it: `Some peers are advertising routes but --accept-routes is false`.

The console work was done over photos of the screen. The box has a German QWERTZ layout, where `|` is AltGr + `<`, `@` is AltGr + Q, and Y and Z are swapped. Every command given to the person at the keyboard was written without pipes for that reason.

## Autodarts: an autostart that a self-update broke

The image had `autodarts-desktop` 1.6.0 installed as a deb, but it was not in autostart, so nothing listened on 3180. Copying `/usr/share/applications/autodarts-desktop.desktop` into `~/.config/autostart/` fixed that.

The app then updated itself to 2.0.2. `/var/log/dpkg.log` shows the deb going to 1.7.0 and then being removed at 19:38:54, replaced by an AppImage at `~/.local/bin/autodarts-desktop.AppImage`. The autostart file still said `Exec=autodarts-desktop`. That binary no longer existed, so the next login would have started nothing, without any error. The autostart entry was replaced with the AppImage's own `.desktop` file:

```
Exec=/home/autodarts/.local/bin/autodarts-desktop.AppImage %u
```

After a reboot the app was running and listening on `0.0.0.0:3180` within a minute, with no monitor attached.

**Autodarts 2.0 removed the Board Manager.** Port 3180 still answers, but only with "Board Manager is no longer supported ... Please manage your board through the Autodarts Desktop App or the Terminal App instead." Board setup, cameras and calibration are now a five-step wizard in the Desktop window (sign-in, board name, cameras, calibration, test throw). Two consequences:

- The tablet no longer needs LAN access to the box. Play goes through `play.autodarts.io` and the cloud. Because of that, a DHCP reservation at the friend's place is no longer required.
- Recalibration needs the GUI. SSH and Tailscale do not reach it. The headless docs mention terminal commands (`autodarts`, `autodarts remote`), which have not been tried here.

## The box that disappeared

About fifteen minutes after the last command, the box dropped off both the LAN and the tailnet (`offline, last seen 14m ago`). A 40-second capture saw no frame from either of its MACs, yet its power LED was on. A power-button restart brought it back. There was no persistent journal (`no persistent journal was found`), so the previous boot left no record.

The likely cause is Plasma's power management. Since 2023, PowerDevil's default AC profile suspends after 15 minutes of inactivity, and SSH sessions do not count as activity. There was no `~/.config/powerdevilrc`, so the defaults applied. **This is inferred, not proven.** No log of that boot survived. At the friend's place, the same default would have stopped Autodarts 15 minutes after every boot.

A setting in the desktop can be changed back by anyone, so the fix is system-wide, and the journal is now kept:

```bash
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target suspend-then-hibernate.target
sudo mkdir -p /var/log/journal && sudo systemd-tmpfiles --create --prefix /var/log/journal && sudo systemctl restart systemd-journald
sudo journalctl --flush
```

If it disappears again, `journalctl -b -1` will show why.

## Hardening before it leaves the house

The box will sit in someone else's home on the owner's tailnet. As it arrived, it had the password `123456` (also on a sticker on the case), password SSH, and passwordless `sudo`. It was also tailnet-owned by the owner's user, which meant it could reach every node.

**SSH key-only.** The LXC 109 key was installed and key-only login verified first. Only then was `/etc/ssh/sshd_config.d/20-no-password.conf` added:

```
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
```

Both directions were checked: a password attempt now gets `Permission denied (publickey).`, and key login works over the LAN and the tailnet.

**Password.** A generated 16-character password replaced `123456` (stored in Vaultwarden, not here). The character set leaves out `y`/`z` (swapped on QWERTZ) and `0`/`O`/`1`/`l`/`I`, with no symbols. `su` with the old password now fails. KDE Wallet was checked before the change, so Chrome would not start prompting for a wallet password. `pam_kwallet5` is only in `/etc/pam.d/sddm` and not in the autologin stack, yet the wallet had opened at boot without a prompt. So the wallet is not tied to the login password, and changing it does not affect the wallet.

**Passwordless sudo stays, deliberately.** With password SSH gone, it is only reachable by whoever holds the key. Removing it would make every remote fix need the password.

**Tailnet isolation with `tag:darts`.** The existing policy needed one line, not a new rule. The box was owned by the owner's user, so it was inside `autogroup:owner`, and the first grant (`src: autogroup:owner`, `dst: *`) gave it the whole tailnet. A tagged device leaves `autogroup:owner`. `tag:darts` appears in no grant's `src`, so the box can reach nothing. Owner devices still reach it through `dst: *`. Only `tagOwners` changed:

```json
"tagOwners": {
    // ...existing tags...
    "tag:darts": ["autogroup:owner"],
},
```

The tag was then applied in the admin console. The operator's OAuth client here only has `devices:core auth_keys` (`GET /acl` returns 404), so it could neither read the policy nor be used to apply the tag. Measured before and after tagging, from the box:

| Target | Before | After |
|---|---|---|
| pve `100.116.49.30:22` | REACHABLE | blocked |
| docker-host `100.97.95.101:22` | REACHABLE | blocked |
| claude-mgmt `100.98.146.14:22` | REACHABLE | blocked |

SSH from claude-mgmt to the box over the tailnet kept working. Tagged devices get no node key expiry (`keyExpiry: none`), so the box will not drop off the tailnet after 180 days. Key expiry had already been disabled in the console before tagging.

## Updates

The image had 303 pending updates, 115 of them security. A `full-upgrade` ran as a transient unit, so a dropped SSH session could not kill it. It installed 325 packages with `EXIT=0` and no errors, including a new kernel (`6.12.113+deb13-amd64`):

```bash
sudo systemd-run --unit=darts-upgrade --collect bash -c "export DEBIAN_FRONTEND=noninteractive; apt-get update && apt-get -y -o Dpkg::Options::=--force-confdef -o Dpkg::Options::=--force-confold full-upgrade > /var/log/darts-upgrade.log 2>&1; echo EXIT=\$? >> /var/log/darts-upgrade.log"
```

`unattended-upgrades` was already installed but switched off (`APT::Periodic::Unattended-Upgrade "0"`). It is now `"1"`, using the Debian, Debian-Security and `-security` origins. A `--dry-run` completed cleanly.

## WiFi for the friend's place

The box will use WiFi there. The card is an Intel Gemini Lake CNVi (`8086:31dc`, `iwlwifi`), dual-band, and with the antennas fitted it saw 2.4 and 5 GHz networks at home at 80-100% signal. Two system-wide NetworkManager profiles were created:

| Profile | SSID | Priority | Notes |
|---|---|---|---|
| `darts-wifi` | `<extender_5ghz_ssid>` | 10 | range extender, 3 m away, no wall |
| `darts-wifi-fallback` | `<main_router_ssid>` | 5 | main router, 2-3 walls away |

```bash
sudo nmcli con add type wifi ifname wlp0s12f0 con-name darts-wifi ssid "<extender_5ghz_ssid>" \
  wifi-sec.key-mgmt wpa-psk wifi-sec.psk "your_wifi_psk_here" wifi-sec.psk-flags 0 \
  connection.permissions "" connection.autoconnect yes connection.autoconnect-priority 10 \
  wifi.powersave 2 wifi.cloned-mac-address permanent ipv4.route-metric 600
```

The choices that matter:

- **`psk-flags 0` + empty `connection.permissions`:** the secret lives in `/etc/NetworkManager/system-connections/*.nmconnection` (root, `0600`), not in a user's KDE Wallet. A profile created from the Plasma applet would keep it in the wallet by default, and the box should connect at boot whether or not anyone is logged in.
- **`wifi.powersave 2`:** power saving disabled. Intel cards are known for latency spikes and dropouts with it on.
- **`cloned-mac-address permanent`:** the router always sees the hardware MAC, not a random one.
- **`wpa-psk` on a WPA2/WPA3 transition network**, not SAE. WPA2 is the more forgiving mode with range extenders.
- **Wired stays primary:** ethernet keeps route metric 100 and WiFi gets 600. If a cable is ever plugged in, traffic moves to it.

**Known limitation:** NetworkManager chooses by priority only when it activates a connection. It does not switch back to a better SSID while a worse one is up. After a power cut, the box boots in about 30 seconds. If the extender is slower, the box can land on the 2-3-walls router and stay there. Autodarts traffic is small, so this should degrade the connection rather than break it. A timer that moves back to the extender when it is visible is a five-line addition, not built yet.

## BIOS

- **AC Recovery = Power On:** after a power cut, the box starts without anyone touching it.
- **Wake on LAN:** left on. It is harmless but unlikely to be used: AC Recovery covers the real case, a magic packet only works from the same LAN, and Tailscale is not running on a powered-off box.
- **Wake on 2nd NIC:** off. It is for the optional second RJ45/SFP module, and this unit has only `enp1s0` and the WiFi card.

## Verified after the final reboot

| Item | Measurement |
|---|---|
| Autologin + Plasma | `plasmashell` running, `autodarts` session active |
| Autodarts autostart | AppImage running, listening on `:3180` |
| SSH key-only | `passwordauthentication no`, password attempt refused |
| SSH over LAN (DSCP fix) | `ipqos none none`, key login works |
| SSH over tailnet | key login works |
| Sleep disabled | all 5 targets `masked` |
| Persistent journal | `--list-boots` shows 3 boots |
| Unattended upgrades | `"1"`, `apt-daily*` timers enabled, no pending reboot |
| WiFi profiles | both present, autoconnect, root-only files |
| Tailnet isolation | `tag:darts`, `keyExpiry: none`, pve and docker-host blocked |

The `ethtool` offload change reverted at boot, as expected. It made no difference, so it was not made permanent.

## Still to verify on site

1. **WiFi actually connects.** Neither SSID is in range at home. Success looks like `3darterde` showing online on the tailnet within a minute or two of power-on.
2. **AC Recovery.** Pull the plug while it runs, plug it back in: it must boot with no button press.
3. **Autodarts first-run wizard** with the Vantage connected to a rear USB 3.0 port: sign-in, board, cameras, calibration, test throw.

## Rollback

| Change | Undo |
|---|---|
| sshd DSCP | `sudo rm /etc/ssh/sshd_config.d/10-ipqos-none.conf && sudo systemctl restart ssh` |
| SSH key-only | `sudo rm /etc/ssh/sshd_config.d/20-no-password.conf && sudo systemctl restart ssh` (from the console) |
| Sleep masked | `sudo systemctl unmask sleep.target suspend.target hibernate.target hybrid-sleep.target suspend-then-hibernate.target` |
| Autostart | `rm ~/.config/autostart/autodarts-desktop.desktop` |
| WiFi profiles | `sudo nmcli con delete darts-wifi darts-wifi-fallback` |
| Unattended upgrades | set `APT::Periodic::Unattended-Upgrade "0"` in `/etc/apt/apt.conf.d/20auto-upgrades` |
| Tailnet tag | remove `tag:darts` in the admin console (the box then gets full owner access again) |

## Lessons

- **When raw TCP connects and SSH does not, look at the DSCP bits first.** On this LAN, that was true for the client in doc 43 and for the server here. A capture on both ends with `-v` shows the `tos` field directly, and it took one try once there was a second vantage point.
- **A self-updating app can break its own autostart without an error.** Check the `Exec=` line after any update that changes how the app is packaged.
- **A desktop distro on an appliance needs its sleep defaults removed at the system level,** not in a settings dialog.
- **Isolate a device by taking it out of the group, not by adding a deny rule.** Tailscale policies are allow-only, so a tagged device that appears in no `src` reaches nothing.
