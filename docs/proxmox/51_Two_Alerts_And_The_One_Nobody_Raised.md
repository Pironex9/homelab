**Date:** 2026-09-27
**Hosts:** pve (192.168.0.109), LXC 100 docker-host (192.168.0.110), LXC 103 vaultwarden (192.168.0.219)
**Triggered by:** a Netdata cgroup memory alarm and the morning `homelab-digest.sh` run

---

# Two Alerts, and the One Nobody Raised

Two things arrived within the hour. Netdata: `cgroup docker-host memory utilization
87.81%`. The morning digest: the LVM thin pool had jumped 64.67% -> 68.33% overnight,
the oldest SnapRAID scrub block was 42 days old against a 30-day threshold, and LXC 103
had been showing an Alpine patch release behind for ten days.

Measuring those three before touching any of them turned up a fourth that neither the
alarm nor the digest had said a word about, and it was the closest to hurting:

```
$ df -h /
/dev/mapper/pve-vm--100--disk--0   51G   46G  3.3G  94% /
```

3.3 GB left on the container that runs 26 Compose stacks. Nothing was monitoring the
guest filesystem - the thin pool watch sees the pool, and the Netdata alarm watched
memory.

---

## The 94% nobody raised

The breakdown said this was not a leak, it was inventory:

```
$ du -xh --max-depth=1 /var /srv | sort -hr | head -3
33G  /var/lib          <- Docker images
8.9G /srv/docker-data  <- bind mounts
354M /var/log

$ docker system df
Images  40  39 active  33.09GB  2.018GB reclaimable (6%)
```

One image out of forty was unreferenced, and the journal had grown to 352 MB. Both go
without asking anybody:

```bash
docker image prune -f          # reclaimed 2.018 GB
journalctl --vacuum-size=100M  # freed 288.8 MB of archived journals
```

The journal was capped so it cannot walk back up, since nothing else stops it:

```
# /etc/systemd/journald.conf
SystemMaxUse=200M
```

Result: **94% -> 89%, 3.3 GB -> 5.5 GB free.** That is a reprieve, not a fix. 33 GB of
Docker images on a 51 GB root is the actual shape of the problem, and the answer to it is
the second NVMe that `docs/proxmox` has been deferring, not another prune.

### Closing the gap it exposed

`scripts/homelab-digest.sh` now reads every running container's root filesystem and warns
past 85%, because the reason this went unnoticed was not that the number was hard to get.
The loop runs on the host in a single ssh call, since a `pct exec` per container from LXC
109 is a round trip each:

```bash
for id in $(pct list | awk "NR>1 && \$2==\"running\"{print \$1}"); do
    u=$(pct exec $id -- df -P / 2>/dev/null | awk "NR==2{print \$5}")
    [ -n "$u" ] && echo "$id ${u%\%}"
done
```

**`df -P` is load-bearing, not tidiness.** busybox wraps a long device name onto its own
line, so with a plain `df /` row 2 has no fifth field and the two Alpine containers vanish
from the output without an error:

```
$ pct exec 103 -- df /
Filesystem           1K-blocks      Used Available Use% Mounted on
/dev/mapper/pve-vm--103--disk--0
                        996780    233980    693988  25% /
```

A monitor that silently reports on 7 of 9 containers is worse than none, because it reports
OK for machines it never read. `-P` forces one line per filesystem and both containers come
back. An empty result from the whole loop is treated as a failure rather than a clean pass,
the same rule `lxc-fstrim` already follows.

First run flagged the container this page is about:

```
⚠️ LXC rootfs 85% felett: 100(89%)
```

It will keep flagging it every morning, correctly, until the images move off that 51 GB
root. VMs are outside this check - there is no `pct exec` for them, and 101 is Home
Assistant OS.

## Two numbers that look like the same number

The filesystem being 89% full and the thin volume being 92.76% allocated are different
facts with different fixes, and conflating them wastes an evening.

* **Filesystem usage** is what `df` reports inside the guest. Only deleting files moves it.
* **Thin-pool allocation** is what `lvs` reports on the host. It only drops when the guest's
  freed blocks are discarded back to the pool.

So the prune did nothing for the pool, and the trim did nothing for `df`:

```bash
# inside LXC 100 - does not work, and the error is the point
$ fstrim -v /
fstrim: /: FITRIM ioctl failed: Operation not permitted

# from pve, which owns the block device
$ pct fstrim 100
/var/lib/lxc/100/rootfs/: 7.2 GiB (7721709568 bytes) trimmed
```

An unprivileged container is not allowed to issue discards to its own root device; that is
why `/usr/local/bin/lxc-fstrim` runs on the host at 01:30 and not in the guest.

**The trim is a treadmill, not a repair.** That same cron had already trimmed 6.5 GiB out
of LXC 100 at 01:30 the same morning, and 7.2 GiB had accumulated again by 18:45. The
container churns roughly 7 GB of freed blocks a day through Docker layer writes, logs and
OCR temp files. Reading a large trim as "we found the leak" gets it backwards: a large
trim is the normal daily figure here.

Pool after: **68.86% -> 66.89%**, and the LXC 100 volume **92.76% -> 86.49%**. The digest's
overnight jump was the previous day's Paperless install - four new images, not a runaway
guest.

## The memory alarm was true, and it was not urgent

87.81% of a 10 GB cgroup limit sounds like the container is about to start killing
processes. It was not:

```
              total   used   free  shared  buff/cache  available
Mem:           10Gi  7.8Gi  463Mi    1.0Gi       2.8Gi       2.2Gi
Swap:            0B
```

2.8 GB of that utilization is page cache, which is reclaimable on demand, and 2.2 GB was
genuinely available. The cgroup memory metric counts the cache, so the number a phone
alert shows is always higher than the number that decides whether anything dies.

Still worth acting on: swap is 0, so there is no slack under a spike, and the day before
had added Paperless (933 MB) on top of Dawarich's three `bundle` workers (~1 GB) and
qBittorrent (1.06 GB RSS). The host has room - 31 GB total, 13 GB available - so the cap
went up live, with no container restart:

```bash
pct set 100 -memory 12288
```

`available` went 2.2 GB -> 4.2 GB, and the same utilization now reads about 73%.

Guest memory across the host sums to 42 GB on a 31 GB machine. That overcommit is
deliberate and normal for LXC, where a limit is a ceiling and not a reservation; it is
also the reason raising one container's ceiling is cheap and raising all of them is not.

## The scrub that could never catch up

The digest had been counting up for weeks: 34 days on 09-15, 42 days on 09-27. A one-off
`scrub -p 20 -o 40` on 09-14 had pulled the oldest block from 43 days down to 34, so the
mechanism worked - it just decayed again at about two-thirds of a day per day.

The arithmetic explains it without any further measurement:

```
$ snapraid status
   Files Fragmented Excess  Wasted  Used    Free  Use Name
   73858     404     4922     0.0    4711    4150  53%
```

4711 GB of data, `scrub_percentage = 1`, so 47 GB a night, so **100 nights for one full
pass** - against a threshold that wants nothing older than 30 days. No one-off catch-up
can fix a rate problem; it only resets the clock and lets it drift again.

Sizing it from the threshold instead: a 30-day guarantee needs 100 / 30 = 3.34% a night,
so 4% with margin. That is 188 GB a night, roughly 15-25 minutes at the 130-350 MB/s this
array actually scrubs at, in a window that starts after a 15-22 minute sync at 03:00.

```
# /etc/snapraidd.conf
scrub_percentage = 4
scrub_older_than = 6
```

The daemon takes this without a restart, and says so rather than leaving you to assume it:

```
$ systemctl reload snapraidd
snapraidd[1985]: reload requested
snapraidd[1985]: config loaded successfully from /etc/snapraidd.conf
```

At 4% the 42-day tail still needs a full pass to clear, so a bounded catch-up ran the same
evening - and it is bounded on purpose, because a scrub that is still holding
`/var/snapraid.content.lock` at 03:00 collides with the daemon's own maintenance:

```bash
systemd-run --unit=snapraid-catchup-scrub --collect \
    --property=RuntimeMaxSec=22800 \
    --property=StandardOutput=append:/var/log/snapraid/manual-20260927-scrub.log \
    --property=StandardError=append:/var/log/snapraid/manual-20260927-scrub.log \
    /usr/bin/snapraid --conf /etc/snapraid.conf scrub -p 25 -o 30
```

`RuntimeMaxSec` expires at 01:00, before the 01:30 fstrim and well before the 03:00
window. Killing a scrub is safe: it only reads, and `autosave 500` has already written
progress into the content file.

One consequence worth knowing before it looks like a fault: while that unit runs, any
other `snapraid` command on the host fails with `The lock file
'/var/snapraid.content.lock' is already in use!`. That includes `snapraid status`, so the
usual way of checking on things is unavailable exactly while the long job is running. Read
the unit's log instead.

That catch-up finished in 1 hour 42 minutes, 914 GB read, `Everything OK`, and moved the
oldest block **42 days -> 29**, with the unscrubbed share 39% -> 33%. Its wait-time
breakdown names the slow tail: d1 58%, d3 30%, d4 4% - the drag is on the disk already
flagged by SMART, where throughput fell from 240 MB/s to 13 MB/s over the last two percent.

29 days is one day under the threshold, so the catch-up alone proves nothing about the
rate. Whether 4% holds is a measurement for the following mornings: the oldest-block age in
the digest has to keep falling without another manual run.

## Vaultwarden

The Alpine patch upgrade on LXC 103 is written up where the rest of that container's
procedure lives, in
[09 - Vaultwarden](09_Vaultwarden.md#2026-09-27-a-patch-level-upgrade-and-a-cheaper-rollback-point),
including why the rollback point was a snapshot rather than a fresh `vzdump`.

---

## What each fix was worth

| Item | Before | After | Mechanism |
|---|---|---|---|
| LXC 100 rootfs | 94%, 3.3 GB free | 89%, 5.5 GB free | image prune + journal vacuum |
| pve thin pool | 68.86% | 66.89% | `pct fstrim 100` |
| vm-100-disk-0 allocation | 92.76% | 86.49% | same trim |
| LXC 100 memory | 10 GB cap, 2.2 GB available | 12 GB cap, 4.2 GB available | live `pct set` |
| SnapRAID scrub pass | 100 nights | 25 nights | `scrub_percentage` 1 -> 4 |
| SnapRAID oldest block | 42 days | 29 days | bounded catch-up scrub |
| LXC 103 | Alpine 3.24.1, 47 packages behind | Alpine 3.24.2, 0 behind | `apk upgrade` |

The one that mattered most had no alert attached to it. The two that did fire were both
true and neither was an emergency.

---

## Two days later: 96%, and the prune was never the fix

The new digest check earned itself on its second morning. 2026-09-28 it flagged LXC 100 at
94%, 2026-09-29 at 96% - 2.4 GB free, up seven points from the 89% the prune had left. The
first instinct, that something had started writing, was wrong. No runaway file exists:

```
$ du -xh --max-depth=1 /var/lib | sort -hr | head -3
34G  /var/lib
33G  /var/lib/containerd     <- Docker's image store, not /var/lib/docker
517M /var/lib/docker

$ docker system df
Images  42  39 active  34.28GB  3.271GB reclaimable (9%)
```

Forty images two days ago, forty-two now, and the reclaimable share up from 2.018 GB to
3.271 GB. The image timestamps name the mechanism:

```
$ docker images --format '{{.CreatedSince}}\t{{.Repository}}'
16 hours ago  ghcr.io/hotio/qbittorrent
24 hours ago  ghcr.io/immich-app/immich-server
29 hours ago  docuseal/docuseal
41 hours ago  ghcr.io/seerr-team/seerr
```

Komodo deploys `:latest` tags, so three to four pulls land every day and each one leaves the
image it replaced dangling. Measured: **~1.6 GB a day**, which is why 5.5 GB of headroom
lasted exactly two days and why a weekly cleanup could never work - seven days of churn is
11 GB against 5.4 GB of free space.

### Only dangling images, and one day of them kept

```bash
# /etc/cron.d/docker-image-prune on LXC 100
0 23 * * * root /usr/bin/docker image prune -f --filter "until=24h" >> /var/log/docker-prune.log 2>&1
```

Three decisions in that one line:

**No `-a`.** Comparing `docker image ls` against `docker ps --format '{{.Image}}'` produces a
tempting list of "unused but tagged" images - `caddy:alpine`, `jellyfin/jellyfin:latest` and
others that are demonstrably in use. The two commands render an image reference differently,
so the difference between them is not an unused set, and `prune -a` acting on that reasoning
would delete images running containers depend on. Plain `prune` removes only dangling images
and never one a container still references.

**`until=24h`.** Without it, the previous image version is gone the same night, and the
easiest rollback from a bad `:latest` update - restart onto the local previous image - goes
with it. Keeping one day costs about 1.6 GB of the 5.4 GB reclaimed and buys back a day of
rollback.

**23:00 UTC, not 01:00.** This container runs `Etc/UTC` while pve runs CEST, which
`/etc/cron.d/immich-pgdump` already warns about in its header. 23:00 UTC is 01:00 CEST, half
an hour ahead of the pve `lxc-fstrim` at 01:30 CEST, so the blocks the prune frees are
discarded back to the thin pool the same night instead of waiting a day.

Verified rather than assumed, given three cron jobs in this homelab have died silently
before. `env -i` first, to prove the command does not depend on an interactive environment:

```console
root@docker-host:~# env -i /usr/bin/docker image prune -f --filter "until=24h"
Total reclaimed space: 0B
```

Then the same line installed as a temporary every-minute job, waited out, and removed once
`/var/log/docker-prune.log` had a real entry written by cron itself. A parse error in
`/etc/cron.d` is silent, and `systemctl restart cron` reports success either way.

### What this does not fix

33 GB of images and 8.9 GB of live data in `/srv/docker-data` on a 51 GB root leaves the
container permanently in the 85-90% band - right at the digest threshold, with every new
stack pushing closer. The cron stops the churn accumulating; it does not create headroom.
The two real exits, neither taken yet:

* **Grow the rootfs by ~15 GB.** Takes the thin pool from 67% to about 76%, under the 80%
  digest threshold but not by much, and postpones rather than solves.
* **The second NVMe**, open since the thin pool's first capacity crisis. Moving Docker's data
  root there removes the pool's largest writer outright.

Moving the containerd store onto the mergerfs pool is not a third option: USB HDDs under
overlay snapshots would be both slow and fragile.

---

## Further Documentation

- [28 - SnapRAID Daemon Setup](28_SnapRAID_Daemon_Setup.md) - the daemon config, the delete threshold, and the earlier scrub tuning passes
- [09 - Vaultwarden](09_Vaultwarden.md) - the upgrade procedure for LXC 103
- [50 - Paperless and the HP Smart Tank](50_Paperless_And_The_HP_Smart_Tank.md) - the install that accounts for the overnight thin-pool jump
- [35 - Cron Job Monitoring with Uptime Kuma](35_Cron_Job_Monitoring_Uptime_Kuma.md) - the push monitors, including the fstrim job
