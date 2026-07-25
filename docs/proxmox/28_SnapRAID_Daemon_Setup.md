# SnapRAID Daemon Setup

**Date:** 2026-07-25
**Hostname:** pve
**IP address:** 192.168.0.109

## Overview

The Proxmox host (`pve`) ran SnapRAID as a CLI-only tool (v12.3, manually built, `/usr/local/bin/snapraid`) with a weekly `snapraid sync` cron job. [SnapRAID Daemon](https://www.snapraid.it/ui) (`snapraidd`) wraps the same CLI engine with a scheduler, SMART monitoring, disk spindown, and a web dashboard, so this replaces the manual cron with a supervised, observable service.

Dashboard: **http://192.168.0.109:7627** (LAN and Tailscale only, see ACL below).

## Why the old install had to be replaced first

The old `/usr/local/bin/snapraid` binary was installed manually (compiled from source, copied into place) - never registered with `dpkg`. `apt-cache policy snapraid` showed `Installed: (none)` even though the binary worked fine. The daemon's `.deb` package declares a hard dependency on `snapraid (>= 14.1)` tracked via dpkg, so it failed to install even though a working SnapRAID binary was already present:

```
snapraid-daemon : Depends: snapraid (>= 14.1) but it is not going to be installed
```

Debian's own repo only ships `snapraid 12.4-1` (too old), so the fix was installing the upstream `snapraid` `.deb` (v14.9) directly from GitHub releases.

## Install

```bash
# 1. SnapRAID CLI v14.9 (dpkg-managed, satisfies the daemon's dependency)
cd /tmp
curl -fsSLO https://github.com/amadvance/snapraid/releases/download/v14.9/snapraid_14.9-1_amd64.deb
apt-get install -y ./snapraid_14.9-1_amd64.deb

# Compatibility check BEFORE touching anything - confirms the new binary parses
# the existing /etc/snapraid.conf and content files correctly (read-only)
/usr/bin/snapraid -c /etc/snapraid.conf status

# 2. SnapRAID Daemon v1.14
curl -fsSLO https://github.com/amadvance/snapraid-daemon/releases/download/v1.14/snapraid-daemon_1.14-1_amd64.deb
apt-get install -y ./snapraid-daemon_1.14-1_amd64.deb
```

The daemon `.deb` ships a working default `/etc/snapraidd.conf` (not just an example) and auto-enables `snapraidd.service` via a symlink - it does not touch `/etc/snapraid.conf`.

## Two SnapRAID binaries coexist - `sys_engine` must be explicit

After install there are two binaries:
- `/usr/local/bin/snapraid` - old, v12.3, manual, unregistered with dpkg
- `/usr/bin/snapraid` - new, v14.9, dpkg-managed

Debian's `PATH` puts `/usr/local/bin` **before** `/usr/bin`, so a bare `snapraid` command resolves to the *old* v12.3 binary. The daemon's own auto-detection (`sys_engine` unset) searches both `/usr/bin` and `/usr/local/bin` with an undocumented priority, so it was pinned explicitly in `/etc/snapraidd.conf`:

```
sys_engine = /usr/bin/snapraid
```

## Config changes applied (`/etc/snapraidd.conf`)

| Setting | Value | Why |
|---|---|---|
| `sys_engine` | `/usr/bin/snapraid` | Force the new v14.9 binary, avoid PATH ambiguity (above) |
| `net_port` | `0.0.0.0:7627` | Reach the dashboard from LAN/Tailscale, not just localhost |
| `net_acl` | `+100.0.0.0/8,+192.168.0.0/24,+127.0.0.1` | Restrict access to Tailscale CGNAT range + LAN + loopback |
| `maintenance_schedule` | `Sun 03:00` | Matches the old cron's timing; avoids the 02:00 nightly `vzdump` job |

### Doc/release drift found during setup (both required workarounds)

1. **No authentication in this release.** The GitHub `master` branch docs (manpage, `snapraidd.conf.example`) describe a `net_auth_credential` config option and a `snapraidd -g user:pass` flag to generate an Argon2id hash for HTTP Basic Auth. **Neither exists in the actual v1.14 release binary** - `snapraidd -H` doesn't list `-g`/`--gen-auth`, and `net_auth_credential` isn't a recognized key in the shipped config. This is an unreleased feature documented ahead of the release. Access control for now is `net_acl` (IP allowlist) only, no password. Caddy reverse-proxy Basic Auth is an option if password protection becomes necessary before the daemon catches up.
2. **Bare port number doesn't bind to all interfaces.** The docs say `net_port = 7627` (no IP) binds to all IPv4 interfaces (`0.0.0.0`). In practice it bound to `127.0.0.1`/`::1` only. Using the explicit form `net_port = 0.0.0.0:7627` worked as expected.

## Removed: old manual cron

The old weekly sync cron (`0 3 * * 0 /usr/local/bin/snapraid sync` in root's crontab) was removed - the daemon's `maintenance_schedule = Sun 03:00` now covers sync + scrub + report at the same time slot. Backup of the old crontab: `/tmp/crontab.bak` on `pve`.

## Old binary: quarantined, not yet deleted

`/usr/local/bin/snapraid` (v12.3) is not referenced anywhere else on the system - checked cron (all users), `/etc/cron.d`, `/etc/cron.daily`, `/etc/cron.weekly`, systemd units, and `/root/*.sh` scripts. Ran a reversible dry run - renamed (not deleted) to `/usr/local/bin/snapraid.disabled-test`, confirmed the bare `snapraid` command now resolves to `/usr/bin/snapraid` (v14.9), the daemon stayed active, and the dashboard/API kept responding. No breakage found.

**Currently left quarantined under the renamed path**, pending a full `pve` host reboot to catch any boot-order or PATH dependency that a runtime check can't see. Delete for real only after a clean reboot confirms nothing regresses.

## Verify

```bash
systemctl status snapraidd
ss -tlnp | grep 7627
curl -s -o /dev/null -w '%{http_code}\n' http://192.168.0.109:7627/
```
