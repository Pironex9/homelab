# Cron Job Monitoring with Uptime Kuma Push Monitors

**Date:** 2026-08-14
**Hostname:** pve, docker-host (LXC 100), claude-mgmt (LXC 109), homelab-vps
**IP address:** 192.168.0.109, 192.168.0.110, 192.168.0.204, 100.118.239.117

---

## Overview

Three cron jobs on this host were found dead within 48 hours, each for a different reason and none of them noisy about it (see [15 - Backup System](./15_Proxmox_Backup_System_Documentation.md) section 7). The pattern across all three was the same: cron reported success, the log file existed, and nothing was actually running. The `arping` keepalive had been a no-op for roughly five weeks.

What they had in common is that **nothing was watching for absence**. Every monitoring layer in this homelab checks whether something is up; none checked whether something happened. A job that stops running produces no alert, no failed request, no red tile - it produces nothing, and nothing is exactly what an availability monitor is built to ignore.

The fix is a dead man's switch: the job reports its own success, and the absence of that report is the alert.

## Why not a cron manager UI

The obvious-looking answer was a web UI for cron jobs - [Cronmaster](https://github.com/fccview/cronmaster) is the popular one. It was rejected for reasons worth recording, because the mismatch is easy to miss:

| What it addresses | The situation here |
|---|---|
| Not wanting to write cron syntax | The syntax was never wrong |
| One host per instance | 35 jobs across 11 hosts, so 11 instances |
| `privileged: true`, root, `docker.sock`, `pid: host` | Full host access in exchange for a UI |
| Captures stdout/stderr/exit code | No alerting on failure |

None of the three failures would have been caught. The evidence was already in a log file that nobody opened; a nicer log viewer shows the same unread log. The `arping` case would have defeated it outright, because that script ended in a hard-coded `exit 0`.

[Cronicle](https://github.com/jhuckaby/Cronicle) is the serious multi-host option - primary/worker agents, real scheduling - but it has moved to maintenance mode while its author works on a successor, which is a poor foundation for something new. [Healthchecks](https://healthchecks.io/) is the standard dedicated answer for the dead man's switch, and would be the pick if Uptime Kuma were not already running.

## Why Uptime Kuma was already the answer

Uptime Kuma v2.5.0 runs on the Hetzner VPS with 38 HTTP monitors. It had **zero push monitors** - watching every service and not one scheduled job.

Its location is what makes it the right host for this. A self-hosted Healthchecks on the LAN would go down with the homelab it is supposed to report on; a monitor on a separate machine at a separate provider is the only one that can report the homelab being dead. That is the same reason Uptime Kuma was moved off LXC 100 in the first place.

A Push monitor inverts the usual direction: Kuma stops polling and waits to be pinged. Give it the interval you expect, and if the ping does not arrive it goes down and fires the existing Discord notification.

## The monitors

Eight of the 35 jobs got a monitor - the ones whose silent absence costs something. The rest (logrotate, certificate renewal, `qm reboot`) fail loudly on their own.

| Monitor | Host | Schedule | Interval |
|---|---|---|---|
| `cron: lxc-fstrim (pve)` | pve | daily 01:30 | 90000 s |
| `cron: restic backup (pve)` | pve | Sun 04:00 | 612000 s |
| `cron: restore-test (pve)` | pve | Sun 06:00 | 612000 s |
| `cron: sync-to-nobara (pve)` | pve | Sun 11:00, 19:00 | 612000 s |
| `cron: arping-keepalive (pve)` | pve | every 5 min | 900 s |
| `cron: immich-pgdump (LXC 100)` | LXC 100 | daily 00:30 UTC | 90000 s |
| `cron: homelab-digest (LXC 109)` | LXC 109 | daily 07:00 | 90000 s |
| `cron: ai-digest (LXC 109)` | LXC 109 | daily 07:30 | 90000 s |

Intervals are the job period plus deliberate slack - 90000 s is 25 hours for a daily job, 612000 s is 7 days plus 2 hours - so ordinary jitter does not alert. A monitor that cries wolf is worse than no monitor, which this homelab already learned from the vzdump extension bug in [30 - Backup Verification](./30_Backup_Verification_Restore_Test.md).

## Creating monitors without the UI

**Uptime Kuma has no write REST API.** The REST surface is read-only (badges, status pages, the push endpoint itself); every write goes through Socket.IO, which is [an open feature request](https://github.com/louislam/uptime-kuma/issues/7151). For eight monitors the practical path is a direct SQLite insert with the container stopped.

Stopping it first is not optional. Uptime Kuma runs SQLite in WAL mode, so a copy taken while it is running captures the main database without the write-ahead log:

```console
root@homelab-vps:~# ls -la /opt/uptime-kuma/kuma.db*
-rwxr-xr-x 1 root root 743346176 Aug 14 10:07 /opt/uptime-kuma/kuma.db
-rwxr-xr-x 1 root root     32768 Aug 14 10:07 /opt/uptime-kuma/kuma.db-shm
-rwxr-xr-x 1 root root   8981632 Aug 14 10:07 /opt/uptime-kuma/kuma.db-wal
```

That 8.9 MB `-wal` file is the recent history a naive `cp` would silently drop. A clean `docker stop` checkpoints it, after which the backup is a single consistent file.

```bash
docker stop uptime-kuma && sleep 2
cp /opt/uptime-kuma/kuma.db /opt/uptime-kuma/kuma.db.bak-$(date +%Y%m%d)
```

Then one pair of rows per monitor. The push token is generated rather than accepted from Kuma, which is what makes the whole thing scriptable - the token can be written into the job before the monitor exists:

```sql
INSERT INTO monitor (name,type,active,user_id,interval,push_token,maxretries,
                     retry_interval,resend_interval,description,weight,
                     accepted_statuscodes_json,conditions)
VALUES ('cron: lxc-fstrim (pve)','push',1,1,90000,'<32-char-token>',0,60,0,
        'pve, napi 01:30. LVM thin pool trim a 02:00-s vzdump elott.',
        2000,'["200-299"]','[]');
INSERT INTO monitor_notification (monitor_id,notification_id)
VALUES (last_insert_rowid(),1);
```

`maxretries=0` is deliberate: retries make sense when a poll might fail transiently, but a missing ping is already the failure. `notification_id=1` attaches the existing Discord notification.

Tokens come from `openssl rand -hex 12`. Start the container afterwards and Kuma loads the new monitors at boot; there is no reload path for rows inserted underneath a running instance.

## Wiring the ping into the jobs

The ping goes at the end, gated on success:

```bash
KUMA="http://100.118.239.117:3001/api/push/<token>"
...
[ "$rc" -eq 0 ] && curl -fsS -m 10 -o /dev/null "$KUMA?status=up&msg=OK"
```

`-f` so an HTTP error is an error, `-m 10` so a hung monitoring host cannot hang the job it is monitoring.

**Push tokens do not go in the repository.** `docs/` and `scripts/` are public. For the three jobs whose scripts are version-controlled (`restore-test.sh`, `homelab-digest.sh`, `ai-digest.py`) the ping lives in the crontab line instead of the script, which keeps the token on the host and leaves the repo scripts portable:

```bash
0 7 * * * /root/homelab/scripts/homelab-digest.sh && curl -fsS -m 10 -o /dev/null http://100.118.239.117:3001/api/push/<token>?status=up
```

Host-local scripts (`/usr/local/bin/lxc-fstrim`, `/root/backup-proxmox-restic.sh`, `/root/sync-to-nobara.sh`, `/root/immich-pgdump.sh`) carry the ping inline.

### Reachability

Every host reaches the VPS over Tailscale, not the public internet, so the push endpoint is never exposed:

```console
root@pve:~# curl -fsS -m 10 -o /dev/null -w "%{http_code} %{time_total}s\n" \
    http://100.118.239.117:3001/api/push/<token>
200 0.049352s
```

An unknown token returns 404 rather than an error, which is a convenient way to prove reachability before the monitor exists.

## Three traps in the gating logic

Getting `curl` onto the last line is the easy part. Deciding *when* it should run is where this goes wrong, and each of these was found by testing rather than by reading.

### A loop that iterates zero times is a success

The first version of the trim job was:

```bash
rc=0
for id in $(/usr/sbin/pct list | awk 'NR>1 && $2=="running"{print $1}'); do
  /usr/sbin/pct fstrim "$id" || rc=1
done
[ "$rc" -eq 0 ] && curl ...
```

If `pct` goes missing again - the exact bug being guarded against - the substitution is empty, the loop body never executes, `rc` stays 0, and the job reports success. The monitor would have stayed green through the failure it exists to catch.

```bash
ids=$(/usr/sbin/pct list | awk 'NR>1 && $2=="running"{print $1}') || rc=1
[ -z "$ids" ] && { echo "HIBA: nincs futo konteneer a listaban"; rc=1; }
```

**An empty work list is a failure, not a quiet success.** Any job that loops over discovered work needs this check.

### Exit code 0 is not always the success signal

`arping-keepalive.sh` sends a gratuitous ARP announcement. Nothing answers a gratuitous ARP - that is what makes it an announcement - so `arping` returns 1 on a perfectly healthy run:

```console
root@pve:~# /usr/sbin/arping -c 1 -U -I vmbr0 192.168.0.109
ARPING 192.168.0.109
Timeout
--- 192.168.0.109 statistics ---
1 packets transmitted, 0 packets received, 100% unanswered (0 extra)
exit=1
```

An `if arping; then curl; fi` would therefore never ping, and the monitor would report the job dead while it worked fine. The condition that actually matters here is whether the command ran at all, and the shell distinguishes that with 127:

```bash
/usr/sbin/arping -c 1 -U -I vmbr0 192.168.0.109 >/dev/null 2>>/var/log/homelab/arping-keepalive.err
rc=$?
[ "$rc" -ne 127 ] && curl -fsS -m 10 -o /dev/null "$KUMA?status=up&msg=arping-rc-$rc"
exit 0
```

Verified both ways - a real run pings with `arping-rc-1`, and the same script with the binary path deliberately broken produces no heartbeat at all.

### A legitimate skip must still ping

`sync-to-nobara.sh` only runs when the desktop is powered on. Without a ping on the skip path, every week the machine happens to be off would raise a false alarm, and the monitor would be trained into background noise within a month:

```bash
else
  # A kihagyas is jogos vegkimenetel: Nobara ki van kapcsolva.
  echo "$(date) - NFS not mounted, skipping" >> /var/log/nobara-sync.log
  curl -fsS -m 10 -o /dev/null "$KUMA?status=up&msg=nobara-offline-skipped"
fi
```

The distinct `msg` keeps the two outcomes tellable apart in Kuma's history. "The job ran and correctly decided there was nothing to do" is a success; only "the job did not run" is a failure.

### And one that was already there

`backup-proxmox-restic.sh` has no `set -e` and three sequential `restic` calls. Appending a ping to the end would have reported success whenever `backup` failed but `check` passed. Each call now records its own status and the ping requires all three:

```bash
restic -r $REPO backup / ... || rc=1
restic -r $REPO forget ... --prune || rc=1
restic -r $REPO check || rc=1
[ "$rc" -eq 0 ] && curl -fsS -m 10 -o /dev/null "$KUMA?status=up&msg=OK"
exit $rc
```

## Verification

Each job was run under a stripped environment, which is the only way to reproduce what cron does:

```bash
env -i PATH=/usr/bin:/bin HOME=/root /usr/local/bin/lxc-fstrim
```

`curl` itself was checked the same way on all three hosts, since a ping that cannot resolve `curl` reproduces the original bug one level down:

```bash
env -i PATH=/usr/bin:/bin bash -c 'command -v curl'
```

Resulting state, read from Kuma's own database rather than the dashboard:

```
name                            iv      allapot  utolso_ping
------------------------------  ------  -------  -------------------
cron: lxc-fstrim (pve)           90000  UP       2026-08-14 10:23:44
cron: restic backup (pve)       612000  UP       2026-08-14 10:22:24
cron: restore-test (pve)        612000  UP       2026-08-14 10:22:24
cron: arping-keepalive (pve)       900  UP       2026-08-14 10:25:02
cron: immich-pgdump (LXC 100)    90000  UP       2026-08-14 10:24:19
cron: homelab-digest (LXC 109)   90000  UP       2026-08-14 10:25:19
cron: ai-digest (LXC 109)        90000  UP       2026-08-14 10:25:29
```

The weekly monitors were seeded with a manual ping (`msg=initial-seed-2026-08-14`) so they start green; a push monitor that has never been pinged goes down when its first interval expires, which would have meant an alert before the job's first real run.

`ai-digest` was seeded rather than executed, because running it sends a Telegram message and spends Claude tokens. Its cron line is the same `&&` form as `homelab-digest`, which was executed in full.

## What this still does not cover

- **SnapRAID sync and scrub** are scheduled by `snapraidd`, not cron, so there is no line to append a ping to. The daemon's own state is reported in the daily digest instead. See [28 - SnapRAID Daemon Setup](./28_SnapRAID_Daemon_Setup.md).
- **Duration and content are not checked.** A push monitor proves the job ran and exited 0. A backup that completes in one second because its source directory vanished still pings green. That is the known ceiling of the dead man's switch pattern, and it is why the weekly restore test exists alongside it.
- **The 27 unmonitored jobs** were a deliberate cut, not an oversight. Adding all of them would turn the Kuma dashboard into something nobody reads, which is how the original problem started.

## Related Documentation

- [15 - Backup System](./15_Proxmox_Backup_System_Documentation.md) - the three silent cron failures that prompted this, in section 7
- [30 - Backup Verification](./30_Backup_Verification_Restore_Test.md) - the restore test, and why a false alarm is worse than no alarm
- [VPS](../hosts/vps.md) - where Uptime Kuma runs and why it is off-site
