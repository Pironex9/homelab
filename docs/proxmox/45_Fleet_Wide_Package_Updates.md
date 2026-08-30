**Date:** 2026-08-30
**Hosts:** pve (192.168.0.109) and all nine LXCs - six Debian, three Alpine

---

# Updating the Whole Fleet in One Sitting

There was no procedure for "update everything". Every update until now was one container
at a time, ad hoc, whenever something forced it. The backlog was measured on 2026-08-18
and then postponed, and twelve days later it had grown rather than shrunk:

| | 2026-08-18 | 2026-08-30 |
|---|---|---|
| Security packages, six Debian LXCs | 192 | **196** |
| Security packages, pve host | not counted separately | **35** |
| Alpine LXCs | 3.23, three of them | 3.24 available, two still on 3.23 |

This is what was actually run, in order, with the measurements that decided each step and
the two things that broke.

---

## Preconditions, measured before anything ran

Three numbers had to be checked first. All of them came back green, and if any had not,
the right move was to stop rather than to proceed carefully.

```bash
# A backup from today for every guest
pvesh get /nodes/pve/tasks --limit 200 --output-format json | grep vzdump   # 02:00 OK
pvesm list backup-hdd --content backup | grep 2026_08_30                    # 9 LXC + 1 VM

# Thin pool headroom - an upgrade writes, and pve/data has hit 92% before
lvs --noheadings -o vg_name,lv_name,data_percent,metadata_percent --select 'lv_attr =~ ^t'
#   pve data 62.88 3.42       (threshold: stop above 80%)

# Is a kernel in the list, i.e. does this end in a host reboot?
apt-get -s upgrade | grep '^Inst' | awk '{print $2}' | grep -cE '^(proxmox-kernel|linux-image)'
#   0
```

The backup check is the one that matters, because the rollback path for a distribution
release upgrade is not `apk downgrade` - there is no such thing. It is
`pct restore <id> <vzdump> --force`, which discards the container's current disk. That is
worth knowing **before** starting, not after.

---

## The order, and why

Debian containers first, `apt upgrade` rather than `full-upgrade`, no container restarts:

**113 -> 107 -> 106 -> 100 -> 102 -> 109**, then the pve host.

The ordering rule is "least load-bearing first, and the thing you are standing on last".
LXC 102 is the LAN's DNS, so it goes near the end; LXC 109 runs the session doing the
updating, so it goes last of the containers. The pve host is a separate decision after all
nine guests are known good.

`apt upgrade` and not `full-upgrade` because the latter is allowed to remove packages to
resolve dependencies. On a fleet where every container was hand-assembled, a silent
removal is a worse outcome than a package left at an old version.

Every run used the same invocation:

```bash
DEBIAN_FRONTEND=noninteractive apt-get -y -o Dpkg::Options::=--force-confold upgrade
```

`--force-confold` keeps the existing config file when a package ships a new one. On a
homelab where nearly every config in `/etc` has been edited by hand, the default
interactive prompt is not an option in a scripted run, and `--force-confnew` would
silently discard those edits.

---

## The pve host runs detached from the SSH session

```bash
ssh root@192.168.0.109 "setsid bash -c 'DEBIAN_FRONTEND=noninteractive \
    apt-get -y -o Dpkg::Options::=--force-confold upgrade > /root/pve-upgrade.log 2>&1; \
    echo \"EXIT=\$?\" >> /root/pve-upgrade.log' < /dev/null > /dev/null 2>&1 &"
```

Then poll for the `EXIT=` line rather than holding the connection open.

The reason is specific: the pve upgrade includes `samba` and `openssh-server`, both of
which restart their daemons in the middle of the dpkg run. If the SSH connection dies at
that moment, dpkg is left half-applied, and a half-applied dpkg on the hypervisor is a far
worse position than an update that never started. The `EXIT=` sentinel makes the polling
loop unambiguous - a partial log tail cannot be mistaken for a finished run.

It took ~90 seconds and ended `EXIT=0`.

---

## What broke: immich_postgres, exit 137

The `containerd.io` 2.2.2 -> 2.3.4 upgrade on LXC 100 restarts the Docker daemon, and with
it all 34 containers. Thirty-three came back. `immich_postgres` did not:

```
immich_postgres | Exited (137) About a minute ago
immich_server   | Restarting (1) Less than a second ago
```

Exit 137 is SIGKILL, and the first instinct - out of memory - was wrong:

```bash
docker inspect immich_postgres -f "OOMKilled={{.State.OOMKilled}} ExitCode={{.State.ExitCode}}"
#   OOMKilled=false ExitCode=137
```

The log gives the real sequence:

```
19:28:50  LOG:  received fast shutdown request
19:28:52  LOG:  shutting down
19:29:06  <SIGKILL>
```

Docker's default stop timeout is **10 seconds**. Postgres asked for that long and a bit
more to finish its shutdown checkpoint, and containerd killed it at the deadline. Every
container on the host inherits this default - `docker inspect -f '{{.Config.StopTimeout}}'`
returns `<nil>` on all of them.

The recovery was `docker start immich_postgres`, and the startup log settles what the
damage was:

```
LOG:  database system was shut down at 2026-08-30 19:29:00 UTC
```

`database system was shut down at` - not `database system was interrupted` - means the
shutdown checkpoint **completed at 19:29:00**, six seconds before the SIGKILL landed. No
crash recovery ran, because none was needed. Had the kill arrived a few seconds earlier
the same line would have read differently and the story would have been about WAL replay.

**The lesson, carried forward the same evening.** LXC 105 had the identical shape: a Mongo
container, `StopTimeout=<nil>`, and a pending `containerd` upgrade. Rather than repeat the
experiment, the stack was stopped by hand first with a timeout that is not a guess:

```bash
for c in komodo-core-1 komodo-periphery-1 komodo-mongo-1; do docker stop -t 60 "$c"; done
```

All three `Exited (0)`, `mongod shutdown complete` with `exitCode: 0` in 80 ms. The order
matters too - the application containers stop before the database they write to.

---

## What did not break, and had to be proven rather than assumed

**Tailscale.** This was the standing worry, because a daemon that comes back on a
different port or without its identity is a remote-access outage that only shows up later.
It was checked before the first package was touched:

```
pve       1.102.3  port 41641  Running  18 peers
LXC 100   1.102.3  port 41643  Running  18 peers
LXC 109   1.102.3  port 41642  Running  18 peers
LXC 105   1.102.3  port 41644  Running  18 peers
```

and the reason nothing happened is that `tailscale` was in **no** host's upgrade list. It
comes from its own repository and 1.102.3 was already current, so `apt upgrade` never
considered it. That is a fact worth measuring rather than assuming, because the answer
would have been different a week either side of this date.

**Three failed systemd units that predate the updates.** All three would look like fresh
damage to anyone reading `systemctl --failed` afterwards:

| Unit | Host | Why it is not new |
|---|---|---|
| `run-rpc_pipefs.mount` | LXC 107, LXC 109 | `ActiveEnterTimestamp=` is empty - it has never once succeeded. `permission denied` mounting rpc_pipefs in an unprivileged container |
| `nvmf-autoconnect.service` | LXC 100 | `InactiveEnterTimestamp` is 14:52 UTC, hours before the 19:28 upgrade |

`systemctl show <unit> -p ActiveEnterTimestamp -p InactiveEnterTimestamp` is the cheap way
to date a failure. An empty `ActiveEnterTimestamp` means the unit has never worked, which
rules out the update as the cause without needing any log archaeology.

**The running VM keeps the old QEMU.** `pve-qemu-kvm` went 11.0.2 -> 11.0.3-3, but VM 101
still runs on the old binary:

```bash
ps -o pid=,lstart= -p $(cat /var/run/qemu-server/101.pid)
#   1331363   Sun Aug 23 21:45:35 2026
```

The PID is unchanged from before the upgrade. A QEMU version only changes when the process
is replaced, which means `qm stop` + `qm start` - a reboot from inside the guest does not
do it. Anyone reading `pveversion` and assuming the running guests match it is wrong.

---

## The Alpine containers are a different operation

LXC 103 was already on 3.24 with nothing pending. LXC 105 (Komodo) and LXC 110 (Caddy)
were on 3.23, and their repositories point at `latest-stable`:

```
http://dl-cdn.alpinelinux.org/alpine/latest-stable/main
http://dl-cdn.alpinelinux.org/alpine/latest-stable/community
```

`latest-stable` is a moving symlink, and it now points at 3.24. So the 109 and 94
"upgradable packages" on those two containers were not patches - they were a **release
upgrade wearing the clothes of a routine update**:

```
alpine-base policy:
  3.23.3-r0:   lib/apk/db/installed
  3.24.1-r0:   http://dl-cdn.alpinelinux.org/alpine/latest-stable/main
```

This is why they were deliberately excluded from the Debian round and done separately
afterwards. `apk policy <pkg>` is the check that distinguishes the two cases, and a
`latest-stable` repository line means it has to be run before every Alpine update, not
once.

The [Alpine wiki procedure](https://wiki.alpinelinux.org/wiki/Upgrading_Alpine_Linux_to_a_new_release_branch)
for a release branch is `apk update` followed by `apk upgrade --available`. The
`--available` flag is not optional decoration: it forces packages to be replaced even when
the version number has not moved, which is what a rebuild against a new `musl` looks like.
This upgrade did move musl, 1.2.5-r21 -> 1.2.6-r2, on both containers.

### The version pin that looked like a landmine and was a seatbelt

LXC 105's `/etc/apk/world` contains an exact-version pin, left behind by an earlier
one-shot install of Tailscale from the edge repository:

```
tailscale=1.102.3-r0
tailscale-openrc=1.102.3-r0
```

Alpine 3.24 community only carries **1.98.5-r0**. The obvious reading is that
`apk upgrade --available` either fails on an unsatisfiable constraint or silently
downgrades Tailscale by four minor versions. Both readings are wrong, and simulating it
first is what settled the question rather than an argument about apk's resolver:

```bash
apk upgrade --available --simulate
#   130 actions, tailscale not mentioned, zero downgrades
```

The exact pin is satisfied by the installed package, so apk keeps it and never considers
the repository's older build. The pin protects the package instead of breaking the
upgrade. **`apk upgrade --available --simulate` before any release upgrade** is the
generalisable habit here - it is free, and it converts a guess about a resolver into a
list of 130 lines you can read.

### Validate the config against the new binary before restarting the service

Alpine's `apk upgrade` replaces binaries but does **not** restart services. That is
usually described as a hazard, and it is, but it is also a window: for the few minutes
between upgrading and restarting, the new binary is on disk while the old one still serves
traffic. On the Caddy container that window was used deliberately.

```bash
caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
#   Valid configuration
#   rc=0
```

Caddy went 2.11.2 -> 2.11.4 and proxies 35 hostnames for the whole LAN. Had the config
been incompatible, this reports it while the old process is still up and serving. Running
`rc-service caddy restart` first and finding out afterwards is the same information at a
much worse moment.

The verification was a before-and-after status code sweep of all 35 hostnames, diffed:

```bash
for h in adguard.lan homepage.lan jellyfin.lan ...; do
    curl -sk -o /dev/null -w '%{http_code}' -m 10 --resolve "$h:443:192.168.0.208" "https://$h/"
done
```

Identical before and after, with one exception that is worth recording precisely because
it looks like collateral damage: **`ollama.lan` returns 502**. The Caddyfile proxies it to
`192.168.0.231:11434`, and that address does not answer ICMP either - the backend host is
gone, which matches Karakeep's AI having moved to Gemini on 2026-08-13. A dead entry in
the Caddyfile, not a broken proxy. A status-code sweep with no baseline would have blamed
the upgrade for it.

### The `.apk-new` files are the trap that bites later

apk never overwrites a modified config. It writes the package's version alongside, with an
`.apk-new` suffix, and says nothing. Two of the ten that appeared were live ammunition:

```
/etc/conf.d/tailscale.apk-new     LXC 105
/etc/caddy/Caddyfile.apk-new      LXC 110
```

`/etc/conf.d/tailscale` carries `port=41644`, one of four hand-assigned WireGuard ports
that exist because all four Tailscale nodes sit behind a single router and the default
41641 collides. Copying the `.apk-new` over it restores the default port and reintroduces
a fault that took a full audit to find the first time. The Caddyfile is 35 reverse-proxy
entries built up over months.

Neither was copied. The check that proves it:

```bash
md5sum /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak-pre-3.24
#   0f735e29bbc5953b2aa347130a55eba5  (identical)
grep '^port=' /etc/conf.d/tailscale
#   port=41644
```

`find /etc -name '*.apk-new'` belongs in the checklist immediately after every
`apk upgrade`, before any service restart.

### Restart Tailscale on purpose, while someone is watching

The Tailscale package did not change on LXC 105, but `musl` underneath it did. A running
process keeps the old libc mapped, so nothing would have gone wrong today - the failure, if
there is one, waits for the next reboot, which will happen unattended at some worse hour.

So it was restarted deliberately:

```
rc-service tailscale restart
tailscale ip -4              ->  100.86.108.33   (unchanged)
netstat -lnup | grep tailscaled
    udp  0.0.0.0:41644  358127/tailscaled     (custom port held)
nslookup github.com          ->  140.82.121.4   (DNS survived)
Running, 18 peers, reachable from LXC 109 over the tailnet
```

Same identity, same port, DNS intact. The general form: after a libc upgrade, restart the
network daemons under supervision rather than discovering their state at the next boot.

---

## Reclaiming the space afterwards

The thin pool went 62.88% -> 65.55% across the updates, from downloaded packages and new
versions sitting beside old ones. `apt-get clean` in each container removes the archives,
but that alone does not return the blocks to the pool.

`fstrim -av` on the host is **not** the tool here. It trims `/` and the ESP, and reports a
satisfying 13.7 GiB, while the container root volumes inside `pve/data` are untouched - the
pool percentage does not move. The containers' volumes are trimmed from the host with:

```bash
for id in 100 102 103 105 106 107 109 110 113; do pct fstrim "$id"; done
```

That returned 26.6 GB from the nine containers and took the pool to **61.05%**, below where
it started. A second pass after the two Alpine upgrades gave back another 1.7 GB.

---

## End state

| | Before | After |
|---|---|---|
| Debian LXC security packages | 196 | 0 |
| pve host security packages | 35 | 0 |
| Alpine 105 / 110 | 3.23.3 | 3.24.1, 0 upgradable |
| pve-manager | 9.2.4 | 9.2.11 |
| Docker (LXC 100 / 109) | 29.6.2 | 29.7.2 |
| Docker (LXC 105) | 29.1.3 | 29.5.3 |
| Thin pool data | 62.88% | 61.70% |
| Reboot required | - | none, on any host |

All nine guests and the VM running, `systemctl --failed` clean on the host, the two
Prometheus scrape targets `up=1`, and `Watchdog` the only firing alert.

---

## The checklist, condensed

1. Prove a same-day backup exists for every guest, and know the `pct restore` command
   before starting
2. Check the thin pool is under 80%
3. Check whether a kernel is in the list - that decides whether this ends in a reboot
4. For each container, before it is touched: `systemctl --failed` and the running service
   list, so a pre-existing failure cannot be mistaken for new damage
5. Check whether `docker-ce`/`containerd.io` is in the list. If it is, every container on
   that host restarts - verify the restart policies are `unless-stopped`, and stop any
   database by hand with `docker stop -t 60` first
6. Debian: `apt-get -y -o Dpkg::Options::=--force-confold upgrade`, never `full-upgrade`
7. The hypervisor runs detached with an `EXIT=` sentinel, never inside a live SSH session
8. Alpine: `apk policy alpine-base` first - `latest-stable` may have moved you to a new
   release. If it has, `apk upgrade --available --simulate` and read all of it
9. Alpine: `find /etc -name '*.apk-new'` before restarting anything, and validate the
   service config against the new binary while the old one is still serving
10. Alpine: restart the network daemons deliberately, and confirm identity, port and DNS
11. `apt-get clean` in every container, then `pct fstrim` per container from the host -
    `fstrim -av` on the host does not touch the pool
12. Re-measure: pending count zero, no new failed units, targets up, no new alerts
