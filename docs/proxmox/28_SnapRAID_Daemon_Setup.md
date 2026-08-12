# SnapRAID Daemon Setup

**Date:** 2026-07-25
**Updated:** 2026-08-12
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

### Tuning pass 2026-08-12: the weekly job had been failing silently for ten days

The daemon was up with two weeks of uptime and the dashboard looked healthy, but `snapraid status` told a different story: the whole array sat at exactly ten days since the last scrub or sync, and only one scrub had run in four weekly slots. Three separate problems, each of which hid the next.

| Setting | Was | Now | Why |
|---|---|---|---|
| `scrub_older_than` | `10` | `6` | With a weekly schedule, a ten-day floor means blocks touched last Sunday are only seven days old and are not eligible, so the scrub selects nothing and skips itself every other week |
| `scrub_percentage` | `0.7` | `5` | 0.7% a week is a full pass every 143 weeks, roughly 2.7 years. At 5% it is about 20 weeks |
| `sync_threshold_deletes` | `50` | `1000` | The guard is there to stop a sync after a disk fails to mount. But the `vzdump` backups on d1 rotate weekly and the downloads directory is cleaned regularly, so ordinary housekeeping crossed 50 routinely |

**The delete threshold was the one actually breaking things.** The 2026-08-09 sync aborted with `Too many files were removed (324, limit is 50). Sync aborted.`, and because the daemon runs maintenance as a chain (`up → sync → scrub → report`), the scrub never got a turn either. Three days later the pending count was 996, so the next Sunday would have aborted the same way. Parity had been ten days stale while nothing on the dashboard said so.

Before raising the threshold, confirm the deletions are real rather than a missing mount - the failure mode the guard exists for. Read them, do not just count them:

```console
root@pve:~# grep "^scan:remove" /var/log/snapraid/20260812-131059-diff.log | head
scan:remove:d1:backup/proxmox/dump/vzdump-lxc-109-2026_07_28-02_09_47.tar.zst
scan:remove:d1:media/downloads/Kindergarten Cop (1990) [1080p]/WWW.YIFY-TORRENTS.COM.jpg
...
```

Rotating backups and cleaned-up downloads, all on a disk that is mounted. A missing mount looks different: every path on one disk disappears at once, and the count is in the tens of thousands.

### The `exit:warning` trap: one soft error costs the whole week's scrub

Any non-zero `error_soft` makes sync exit `warning`, and the maintenance chain stops there. It does not matter that parity was written correctly; the scrub simply never runs. Two things produced soft errors here:

1. **A live database inside the array.** Immich's `pgdata` sits on the MergerFS pool, and Postgres rewrites `pg_wal`, `pg_control` and `pg_xact` while SnapRAID is reading them, giving `Unexpected attribute change`. Fixed by widening `exclude /immich/pgdata/pg_stat_tmp/` to `exclude /immich/pgdata/` and dumping the database into the pool instead - see [15 - Backup System](./15_Proxmox_Backup_System_Documentation.md).
2. **Moving files while a sync is running.** 30205 `Open error. No such file or directory` in one run, all from a 14 GB directory that was relocated mid-sync. Harmless to the data, fatal to that week's scrub.

Changing an `exclude` costs one manual run: the already-indexed files become deletions on the next sync, 1694 of them here, which trips `sync_threshold_deletes` on purpose. Absorb it once through the API rather than by loosening the guard permanently:

```console
root@pve:~# curl -s -X POST http://127.0.0.1:7627/snapraid/v1/maintenance \
    -H 'Content-Type: application/json' -d '{"ignore_thresholds":true}'
{ "success": true }
```

`ignore_thresholds` is documented in `/usr/share/doc/snapraid-daemon/snapraidd.yaml` under `CommandRequest`. There is no CLI trigger - `snapraidd -H` lists only daemon lifecycle flags, so the REST API on port 7627 is the only way to start a run by hand. Watch it with `GET /snapraid/v1/activity`.

Result of the first clean chain since 2026-08-02:

```
sync:  added 1, removed 1694, error_soft 0, exit ok
scrub: "Scrub plan: auto. 5.0% of the array, older than 6 days"  ->  error_soft 0, exit ok
```

**The general lesson: a green service status says the daemon is running, not that its work is getting done.** `systemctl is-active` was `active` throughout. The two commands that actually answer the question are `snapraid status`, whose histogram shows the age spread of the scrubbed blocks, and `ls /var/log/snapraid/ | grep -vE 'probe|down_idle'`, where a week with a sync but no scrub is visible at a glance.

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

## Reboot test and final cleanup (2026-07-25)

Before permanently deleting the quarantined old binary, did a full `pve` host reboot to catch any boot-order dependency a runtime check can't see. Everything came back clean:

- All 10 LXCs and the HAOS VM back to `running`
- All 4 disks remounted (UUID-based `/etc/fstab`, unaffected by device letter reassignment - see below)
- MergerFS pool (`disk1+disk3+disk4`) back up
- `snapraidd` active, port `7627` listening, dashboard reachable
- `snapraid status` reported the same sync/scrub state as before the reboot - nothing regressed

No issues found, so the old binary and its leftover man page were deleted for good:

```bash
rm /usr/local/bin/snapraid.disabled-test
rm /usr/local/share/man/man1/snapraid.1
```

`man snapraid` now correctly resolves to the dpkg-managed v14.9 page. `/usr/local/bin` and `/usr/local/share/man/man1` no longer contain any SnapRAID remnants.

### Gotcha: `/dev/sdX` letters are not stable across reboots

After the reboot, `d1` (serial `AR11051EJA18VH`) enumerated as `/dev/sdb` instead of `/dev/sda` - the two internal SATA HGST drives (`d1`, `parity`) and the two USB drives (`d3`, `d4`) got assigned different `/dev/sdX` letters than before the reboot. This is normal Linux behavior with multiple SATA/USB disks and is exactly why `/etc/fstab` here uses UUIDs, not device paths - the `disk1`-`disk4` mountpoints resolved to the correct physical disks regardless.

**Practical implication:** never assume a `/dev/sdX` mapping from a previous session still holds. Before running `smartctl`/`hdparm` against a specific physical disk, re-check with `lsblk -o NAME,MODEL,SERIAL,TRAN` and match on serial number, not on the device letter.

## Related: disk failure-risk re-assessment after the v12.3 -> v14.9 upgrade

Upgrading the SnapRAID engine as part of this install changed the `snapraid smart` failure-probability numbers dramatically for the same physical array - worth knowing if compared against older readings:

| | v12.3 (old) | v14.9 (new) |
|---|---|---|
| Array-wide (at least one disk fails within 1 year) | 96% | 15% |
| `d1` individually | 84% | 4% |

Neither number was treated as ground truth - cross-checked against raw `smartctl -a` output instead (see `private/todo.md` #8 for the full writeup). Verdict: `d1` has no active errors (0 reallocated/pending sectors, PASSED self-test) but does show genuine accumulated mechanical wear (`Load_Cycle_Count`/`Power-Off_Retract_Count` at their normalized threshold, likely inherited from its life before being acquired refurbished) - real, but not an emergency. Planned (not urgent) replacement.
