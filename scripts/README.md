# Scripts

`k3s-backup.sh` is the one backup script here, and it exists because the K3s
cluster had no backup at all. Everything else that runs lives on pve, not in this
repo - see the table below.

An earlier `backup.sh` used to sit in this directory,
describing one restic repository per Docker service under `$BACKUP_DEST_NFS`,
and it was never deployed anywhere - docker-host has no restic installed. It was
deleted on 2026-08-12 because it read as a working backup layer and misled a
reader who went looking for where Immich was covered. What actually runs:

| Layer | Where | When |
|---|---|---|
| vzdump of every guest (LXC 100's rootfs carries all of `/srv/docker-data`) | `/mnt/storage/backup/proxmox` | daily 02:00 |
| restic of the pve host root | `/mnt/disk1/backup/proxmox-host` | Sunday 04:00 |
| rsync of both to the Nobara NFS share | `/mnt/pve/nobara-backup` | Sunday 11:00 and 19:00 |
| `pg_dumpall` of Immich into the SnapRAID-protected pool | `/mnt/storage/immich/pgdump` | daily 02:30 CEST, on LXC 100 |
| `k3s-backup.sh` - K3s control plane, gpg-encrypted | `/mnt/storage/backup/k3s` | daily 01:30, from LXC 109 |
| Longhorn volume backups to Garage S3 (`RecurringJob`, not a script here) | `longhorn` bucket on LXC 100 | daily 01:00 UTC |

Configuration for the script below lives in `scripts/.env` (gitignored). See
`.env.example` for every key and for the values that match the live pve setup.

## snapraid-notify.sh

Not a backup script and not scheduled: this is the `notify_result` handler the
SnapRAID daemon on pve calls when a maintenance run reports at warning level or
worse. It is deployed to `/usr/local/bin/snapraid-notify.sh` on pve, not run from
this repo.

The daemon pipes the full task report into stdin and passes the subject line as
`$1`. The script reads stdin exactly once - if nothing consumes that pipe the
writing side can block - then fans out to two places:

| Destination | Carries | Why |
|---|---|---|
| Uptime Kuma push (`cron: snapraid maintenance (pve)`) | subject line, `status=down` | Kuma's Discord notifier is the channel that demonstrably reaches a phone |
| ntfy on the agentos LXC, topic `snapraid` | the whole report | The detail to read afterwards |

The Kuma push URL, token included, is read from `/etc/snapraid-notify.env` (mode
600, not in this repo). The script exits 0 on every path, because a dead
notification target must not make the daemon treat the maintenance task itself as
failed.

The other half of the pair is not a script at all: `notify_heartbeat` in
`/etc/snapraidd.conf` is a plain `curl` that pushes `status=up` after a successful
chain, which is what makes the same monitor a dead man's switch. Full reasoning,
the `notify_result_level = warning` correction, and the `curl -G` trap are in
[28 - SnapRAID Daemon Setup](../docs/proxmox/28_SnapRAID_Daemon_Setup.md).

## restore-test.sh

Proves the backups are actually restorable. Discovers every restic repository
under `$BACKUP_DEST_NFS` (no service list of its own), and per repository:

1. reports the age of the newest snapshot, fails past `RESTORE_TEST_MAX_AGE_DAYS`
2. runs `restic check --read-data-subset=1%`
3. restores `RESTORE_TEST_FILES` files from a randomly picked snapshot into a
   temp dir, compares size against the snapshot tree and sha256 against
   `restic dump`, then deletes the temp dir

Every repository is tested even if an earlier one failed. One summary goes to
ntfy (`$NTFY_BASE_URL/$NTFY_TOPIC`, topic `homelab-digest`) and the exit code is
non-zero if anything failed, so cron surfaces it.

```bash
./restore-test.sh                    # every discovered repository
./restore-test.sh immich immich-db   # only these
./restore-test.sh --no-ntfy          # no summary, for running by hand
```

### Scheduling

`restic check` takes an exclusive lock, so run it well after the backup window.
On pve the backup itself runs Sunday 04:00, so the test goes after it:

```bash
# Restore test every Sunday at 6 AM, two hours after the backup
0 6 * * 0 /root/restore-test/restore-test.sh >> /var/log/homelab/restore-test-cron.log 2>&1
```

Deployed on pve as `/root/restore-test/restore-test.sh` with its `.env` beside
it (the script sources `.env` from its own directory).

Logs to `/var/log/homelab/restore-test.log`.

## k3s-backup.sh

The K3s cluster at the second location had **no backup of any kind** until
2026-08-24 - not the cluster state, not the three machines. Its entire state is a
single sqlite file on the master, so a dead system disk meant reinstalling rather
than restoring.

Runs on LXC 109, because only that host has SSH keys to both the K3s nodes and
pve. pve can reach the nodes over Tailscale but was deliberately not given an
authorized_key of its own. The tar streams straight through to pve, so nothing
lands on 109's small disk.

### Why `VACUUM INTO` and not `cp`

It takes a consistent copy of a live database (a read transaction; in WAL mode
writers are not blocked), so k3s keeps running. It also compacts: on 2026-08-24 a
3.4 GB `state.db` produced a 623 MB copy, because 82% of the file was free pages.
Two seconds.

### Why it is encrypted

The archive carries the cluster CA private keys and the node join token, and
`/mnt/storage` is **both** a Samba share and an NFS export to the whole
`192.168.0.0/24` with `rw,no_root_squash`. Under `no_root_squash` file permissions
are not a control - root on any LAN machine is root on the server. So the content
goes out encrypted with gpg AES256.

The passphrase is `/root/.secrets/k3s-backup-passphrase` on LXC 109. **Lose it and
the backups are unreadable.** LXC 109 is covered by the daily vzdump, but that copy
lives inside the homelab too, so a whole-site loss would take the backups and their
key together. Since 2026-08-24 the passphrase is therefore also in the password
manager, which is what the file-less restore form below is for.

Do not delete the file thinking the password manager copy replaces it. The two have
different jobs: the file is the script's input and the nightly run needs it, while the
password manager copy is the human one for the day LXC 109 is gone. Without the file
the job stops at its own guard - `HIBA: a jelszófájl hiányzik vagy üres` - and no
backup is written from that night on.

Note that MergerFS ignores the umask on create (it makes files 666) and only
honours a later `chmod`, so the script chmods explicitly after writing. That
protects integrity, not confidentiality - the content is already encrypted.

### What it captures

| Item | Why it is needed |
|---|---|
| `state.db` (VACUUM INTO copy) | the entire cluster state |
| `tls/`, `cred/`, `token`, `node-token` | without these you cannot connect to a restored DB and nodes cannot rejoin. Since 2026-08-28 `cred/` also holds `encryption-config.json`, the **only** copy of the key that makes the Secrets in `state.db` readable - see the secrets-encryption section in `docs/k3s/04_Hardening_and_Recovery.md` |
| `manifests/` | the k3s packaged addon manifests |
| systemd unit + env files, master and both workers | where `--node-ip` and `K3S_URL` actually live |
| `kubectl` YAML export (separate file) | human-readable fallback, and the view you need to *rebuild* rather than restore |

### Verification

Step 4 does not check that a file was created - it pipes the archive back through
`gpg --decrypt` and reads the tar to confirm `state.db` is inside. An encrypted
backup that cannot be decrypted is worse than none, because you believe you are
covered. The decryption runs on 109, where the passphrase is; pve never sees it.

A failed run deletes its own partial files from the destination. Without that, an
interrupted transfer left a 70-byte "archive" that counted toward retention and
would have pushed out the last good backup after a few bad days.

```bash
./k3s-backup.sh              # backup plus ntfy notification
./k3s-backup.sh --no-ntfy    # no notification, for running by hand
```

### Retention

`KEEP` defaults to **30** (`K3S_BACKUP_KEEP` overrides it). It counts **archives, not
days** - that distinction has bitten once already. On 2026-08-24 seven manual runs
during a single afternoon of Argo CD work filled the whole window, and the oldest
restore point available the next morning was from that same afternoon:

```
$ ls -1 /mnt/storage/backup/k3s/ | sed -E "s/.*-(2026-[0-9-]+)_.*/\1/" | sort -u
2026-08-24
```

Raised 7 -> 30 on 2026-08-28, before the k3s upgrade, precisely because that day was
going to involve several manual runs again. Thirty archives are roughly 64 MB - the
cost of the fix is nothing, the cost of not having it is having no yesterday.

### Restoring

Deliberately not automated. Proven end to end on 2026-08-28 by
`k3s-restore-test.sh` (below), which is where the two constraints in this section
come from.

```bash
gpg --decrypt --passphrase-file /root/.secrets/k3s-backup-passphrase \
    k3s-control-plane-<TS>.tar.gz.gpg | tar xzf - -C /somewhere
# then on the master: systemctl stop k3s
#   put state.db, tls/ and cred/ back in place
#   systemctl start k3s
# then on the workers: systemctl restart k3s-agent
```

**The archive only works at the default path and the default port.** The six
kubeconfigs in `cred/` hard-code both, so `/somewhere` above is a staging
directory, not a place k3s can be pointed at:

- every one of them names `/var/lib/rancher/k3s/server/tls/...` as an absolute
  path, so a k3s started with a different `--data-dir` dies at once with
  `unable to read client-cert /var/lib/rancher/k3s/server/tls/client-supervisor.crt`
- every one of them names `https://127.0.0.1:6444`, which is `--https-listen-port`
  plus one. Restore on any other listen port and the scheduler and the
  controller-manager keep calling 6444 while the apiserver listens elsewhere:
  `unable to load configmap based request-header-client-ca-file ... dial tcp
  127.0.0.1:6444: connect: connection refused`, and k3s shuts itself down

Either could be worked around by rewriting the six files, but on a real restore
there is no reason to: the files go back exactly where they came from.

That form needs `/root/.secrets/k3s-backup-passphrase`, which is exactly the file that
will be missing in a real disaster - LXC 109 is where it lives. The passphrase is also
in Vaultwarden under **K3s control-plane backup - gpg passphrase**. To restore with the
passphrase typed rather than read from a file:

```bash
gpg --pinentry-mode loopback --decrypt k3s-control-plane-<TS>.tar.gz.gpg \
    | tar xzf - -C /somewhere
```

`--pinentry-mode loopback` makes gpg prompt on the terminal instead of trying to open a
pinentry dialog, which is what fails over SSH. Verified on 2026-08-24 against the
16:12 archive: it decrypts and `state.db` is in the listing.

The decrypted archive contains the cluster CA **private keys** and the join token.
Unpack it somewhere local, and delete it when you are done - do not leave it on
`/mnt/storage`, which is NFS-exported to the whole LAN with `no_root_squash`.

### Scheduling

```
30 1 * * * /root/homelab/scripts/k3s-backup.sh >> /var/log/homelab/k3s-backup.log 2>&1 && curl -fsS -m 10 -o /dev/null http://100.118.239.117:3001/api/push/<token>?status=up
```

The Kuma push was added on 2026-08-27, after this job failed silently for two nights.
While the master was down the script died on
`ssh: connect to host opt5060-i5 port 22: Connection timed out` and only the log knew.
It exits non-zero on failure, so the `&&` is the whole dead man's switch: a failed run
does not push, the heartbeat times out, and the monitor `cron: k3s-backup (LXC 109)`
goes red 25 hours later. The token lives in the crontab line and in
`/root/.secrets/kuma-k3s-backup-token`, never in this repository.

01:30 keeps it clear of the 02:00 vzdump window on the same backup disk. That window is
15 to 17 minutes wide, measured from the pve task UPIDs on three consecutive nights
(2026-08-24 to 08-26): 02:00 to 02:17 CEST. Since LXC 109 moved to `Europe/Budapest` on
2026-08-26 this line fires 30 minutes before the window opens; while the host was on
UTC it fired at 03:30 CEST, over an hour after the window closed. Clear of it either
way, but only now does the line mean on LXC 109 what it says on pve. The script
sets its own `PATH` because `kubectl` lives in `/usr/local/bin`, which cron does not
see - a trap that has silently killed three jobs in this homelab. Test with
`env -i PATH=/usr/bin:/bin HOME=/root ./k3s-backup.sh`.

Measured on 2026-08-24: 29 seconds end to end, 68 MB archive plus a 1.2 MB export.

## k3s-restore-test.sh

Restores the newest control-plane archive into a throwaway k3s and reads the
result back. On-demand, like `longhorn-restore-test.sh`.

`k3s-backup.sh` already proves the archive **decrypts** and that `state.db` is in
the tar listing. That is not the same claim. Between 2026-08-24 and 2026-08-28 the
answer to "does a cluster actually come back from this" was unknown, and two of
the three problems found on the first run would have surfaced during an outage.

It runs on LXC 109, because that is where the passphrase is. The live cluster is
only read, for comparison.

### How it works

1. picks the newest `k3s-control-plane-*.tar.gz.gpg` on pve (or takes a filename
   as `$1`), streams it back, decrypts and unpacks it into a mode-700 directory
2. re-runs `PRAGMA integrity_check` on the transferred copy. The backup ran one
   too, but on the file as it was on the master - this copy has since been through
   gpg, tar and two SSH hops
3. reads the k3s version out of `state.db` (`strings` for `v1.x.y+k3sN`, highest
   wins) and downloads that exact binary, cached under `/root/.cache/k3s-restore-test`
4. puts `state.db`, `tls/`, `cred/` and the three tokens in place and starts
   `k3s server --disable-agent` on `127.0.0.1:6443`, adding `--secrets-encryption`
   if the archive contains `cred/encryption-config.json` - the decision comes from
   the backup, not from a setting here
5. compares against the live cluster and checks the Secret contents
6. kills the server and deletes everything, including on failure (`trap`)

### Why `--disable-agent`

Without it the restored control plane also becomes a node, the kubelet starts, and
it begins scheduling the pods it found in the restored database - Longhorn, Argo
CD, all of it. Argo CD would immediately pull the real GitHub repository and
Longhorn would talk to the real Garage S3 bucket. With no agent not a single pod
starts, and none is needed: the question is whether the **data** came back, not
whether it runs.

### How the verdict is reached

There is no hard-coded list of expected objects. The first version looked for the
six Argo CD Applications by name and failed on the 06:49 archive, correctly
restored, because `monitoring` was only installed at 07:25. The rule instead is:
**every live object whose `creationTimestamp` is older than the backup must be
present in the restored cluster.** Anything newer is drift and is listed
separately, with a reminder to take a fresh backup.

The cutoff comes from the filename, which `k3s-backup.sh` writes in LXC 109's
**local** time while `creationTimestamp` is UTC - so it is parsed as local and
converted, never with `date -u -d`, which would read a naive timestamp as UTC and
put the cutoff two hours late, in the direction that invents failures. As a
cross-check the script also takes the newest `creationTimestamp` in the restored
data; if that is later than the filename cutoff, the data wins. That guard exists
because LXC 109 only moved to `Europe/Budapest` on 2026-08-26, so older archives
carry UTC in their names.

The last check is the one that matters most: Secret **contents**, not counts. If
kine rows had been truncated the object count would still be right. An empty value
is not a failure by itself - Kubernetes allows it and this cluster has three - so
a key only counts as lost when the live side has content and the restored side
does not.

### Proven on 2026-08-28

Against the 11:42 archive (7.0 MB encrypted, 25 MB `state.db`, 3061 kine rows), the
API answered `/readyz` **6 seconds** after start, and nothing was missing:

| | nodes | ns | crd | secret | cm | pvc | pv | deploy | sts | ds | Applications | LH volumes | LH replicas |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| expected | 3 | 10 | 84 | 39 | 57 | 3 | 3 | 22 | 7 | 5 | 6 | 3 | 9 |
| missing | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

116 Secret keys decoded, 3 of them empty on both sides.

### What it touches

Nothing on the live cluster, and nothing on pve beyond reading one file. On LXC 109
it creates and then deletes `/var/lib/rancher/k3s`, `/etc/rancher/k3s`,
`/etc/rancher/node` and `/tmp/k3s-restore-test`. The 79 MB cached binary is
deliberately kept; on a host at 91% that is worth knowing about.

It refuses to start if a `k3s.service` or `k3s-agent.service` unit exists, because
its own cleanup deletes `/var/lib/rancher/k3s` - on a real node that is the cluster.
It also refuses if port 6443 is already in use.

```bash
./k3s-restore-test.sh                                            # newest archive
./k3s-restore-test.sh k3s-control-plane-2026-08-27_01-30-01.tar.gz.gpg
KEEP=1 ./k3s-restore-test.sh                                     # leave it up to poke at
```

The full k3s log of the last run survives cleanup at
`/root/.cache/k3s-restore-test/last-run.log`.

### Four traps it walked into first

Worth keeping, because a real restore at 3am walks into the same ones.

1. **The `cred/` kubeconfigs pin the data-dir path and the apiserver port.** See
   the Restoring section above. Both are silent: the error text names a missing
   certificate or a refused connection, not a wrong path or port.
2. **k3s rewrites its own argv.** After startup `/proc` shows only
   `<path>/k3s server` - every flag is gone. A `pkill -f 'k3s server --disable-agent'`
   in the cleanup therefore never matched, two orphaned control planes kept running
   on their own already-deleted data directories, and the next run failed on a busy
   6443. The wait loop had the same bug and made a healthy k3s look dead. Both now
   track the PID.
3. **`kubectl -o go-template` prints `<no value>` for a missing namespace.** That
   string contains a space, so a field-count filter silently dropped every
   cluster-scoped object: the table read 0 CRDs where there are 84. `jsonpath`
   prints an empty string instead.
4. **An encrypted cluster restored without `--secrets-encryption` looks like it
   worked.** Added on 2026-08-28 when secrets encryption went on. Nodes, CRDs and
   Deployments all read back; only Secrets fail, with `identity transformer tried
   to read encrypted data`, and the server never reaches ready -
   `/readyz` returns `[-]informer-sync failed` forever because the Secret informer
   cannot sync. 474 of 962 log lines were that one error. The script therefore
   takes the decision from the archive, not from a flag someone has to remember.

## longhorn-backup-check.sh

A dead man's switch for the Longhorn volume backups, not a backup script itself.
The backups are taken by a Longhorn `RecurringJob` inside the cluster
(`k8s/manifests/longhorn/`); this checks that they actually happened.

Runs on LXC 109 - the only host with both `kubectl` for the cluster and an SSH key
to LXC 100, where the Garage S3 server lives.

### Why not a plain HTTP monitor on Garage

That would prove Garage answers. Garage answers just as cheerfully when Longhorn
cannot write to it (wrong key, revoked permission, full pool) and when the
`RecurringJob` never ran at all. "Is it up" and "did it happen" are different
questions, and only the second one is worth a page at 3am.

### What it checks

| # | Check | Fails when |
|---|---|---|
| 1 | `BackupTarget/default` | URL empty, or `Unavailable != False` |
| 2 | Garage bucket readable | `garage bucket info` returns nothing |
| 3 | Every volume's newest `Completed` backup | older than `LONGHORN_BACKUP_MAX_AGE_HOURS` (default 26) |
| 4 | `Backup` objects in `Error` state | any exist |
| 5 | Every `nodes.longhorn.io` node and disk | any `Ready` condition is not `True` |

Checks 1 and 5 are the ones that earn their keep today: the cluster has **zero**
volumes, so checks 3 and 4 have nothing to look at, but a broken key, a dead Garage or
an unmounted disk still turns the monitor red.

**Check 5 was added on 2026-08-27 and is there because of a specific miss.** That
morning the USB disk on `opt3050-i5` re-enumerated, systemd unmounted it and did not
mount it back, and Longhorn took the disk out of service with
`DiskFilesystemChanged`. The Kubernetes node stayed `Ready`, so nothing in
`kubectl get nodes` looked wrong - and this script pushed `up - no-volumes`, because
with no PVCs on the cluster checks 3 and 4 pass by definition. Disk health does not
depend on whether there is anything to back up today, so it needs its own gate. The
failure message carries the offending `node/path`; a healthy run reports the fleet:
`3 node, minden lemez Ready, 2288 GiB szabad`.

Two pieces of gating that took a fix each. **Zero volumes is not a failure** - the
cluster genuinely has no PVCs - but it reports a distinct `no-volumes` message, so
the heartbeat history cannot confuse "nothing to do" with "everything backed up".
And a **volume younger than the threshold is not stale**: the job runs at 01:00 UTC,
so a PVC created at noon has no backup yet and legitimately cannot have one. Without
that grace window every new PVC would fire an alert on creation, and a monitor that
cries wolf stops being read. Those volumes are counted separately in the message
(`0/1 kotet mentve, 1 uj (meg nincs mentes)`) rather than being reported as fine.

```bash
./longhorn-backup-check.sh                                    # prints, no ping
KUMA_PUSH_URL="http://.../api/push/<token>" ./longhorn-backup-check.sh
LONGHORN_BACKUP_MAX_AGE_HOURS=48 ./longhorn-backup-check.sh   # looser window
```

Exit code is non-zero on failure, so cron surfaces it even without Kuma.

### Scheduling

```
0 4 * * * KUMA_PUSH_URL=http://100.118.239.117:3001/api/push/<token> /root/homelab/scripts/longhorn-backup-check.sh >> /var/log/homelab/longhorn-backup-check.log 2>&1
```

**LXC 109 runs on Europe/Budapest since 2026-08-26** (it was on UTC before that, and
this line read `0 2` then). 04:00 local is 02:00 UTC, so the check still lands one hour
after the Longhorn `RecurringJob`. The `RecurringJob` fires at 01:00 **UTC** inside the
cluster and does not follow the host timezone, so the two clocks have to be reconciled
by hand every time one of them moves. The gap to `k3s-backup.sh` grew from 30 minutes
to 2h30m in the same move, which matters to nothing: neither takes a lock, and they
have no write target in common - `k3s-backup.sh` writes to `/mnt/storage/backup/k3s`
while this one only reads (`kubectl`, and `garage bucket info` over SSH to LXC 100).

That hour is not cosmetic. Left at `0 2` after the timezone move the check would have
run at 00:00 UTC, an hour *before* the day's backup, and the `MAX_AGE_HOURS=26` grace
would have been spent on a 23-hour-old backup instead of a 1-hour-old one. The monitor
would still be green on a normal day, but a single missed `RecurringJob` run would put
the age at 47 hours and alert, instead of being absorbed at 25 - the check would have
quietly become one missed run stricter than designed.

The push token lives in the crontab line, not in the script - this repository is
public. Like `k3s-backup.sh`, the script sets its own `PATH` because `kubectl` is in
`/usr/local/bin`, which cron does not see.

Both paths verified on 2026-08-25: a healthy run pushed `up` with
`no-volumes, bucket 589B`, and a deliberately unreachable Garage pushed `down` with
the reason, which reached the Discord notification.

## longhorn-restore-test.sh

Restores a Longhorn backup and asks whether the result is *usable*, not whether it
exists. Manual, on demand - there is no cron for it yet.

`longhorn-backup-check.sh` answers "did a backup happen". This one answers "can it be
read back, and does the application accept what comes out". A backup that uploaded
successfully but is corrupt or half-written passes the first check and fails this one.

### Why it does not compare checksums

The snapshot is taken from the **running** application, so it is crash-consistent -
exactly the state a node failure would leave. Measured on the Forgejo volume on
2026-08-28, that meant the SQLite WAL was larger than the database itself:

```
gitea.db        1 257 472 bytes
gitea.db-wal    4 128 272 bytes
```

`gitea.db` on its own is stale without the WAL. Hashing it against the live copy would
fail, and hashing it against a pre-snapshot copy would "pass" while hiding 4 MB of
unmerged WAL. So the verdict is instead: mount the restored volume in a pod running the
**application's own image**, run the application's own command against it, and look for
an expected string in the output. For Forgejo that is
`forgejo -c <app.ini> admin user list` matching the admin username.

### What it touches

The live PVC is only **read** - a snapshot is taken, the application is not stopped or
restarted. Everything it creates is named `restore-test-…` and labelled
`restore-test=true`, and it is all removed at the end. The `RecurringJob`'s own backups
are never touched.

| Variable | Default | Meaning |
|---|---|---|
| `NS` | `apps` | namespace of the PVC and deployment |
| `PVC` | `forgejo-data` | the volume to test |
| `DEPLOY` | `forgejo` | deployment whose image is reused for verification |
| `MOUNT` | `/var/lib/gitea` | where to mount the restored volume |
| `VERIFY_CMD` | `forgejo -c …/app.ini admin user list` | command run inside the verify pod |
| `VERIFY_MATCH` | `Pironex9` | string that must appear in its output |
| `KEEP_BACKUP` | `0` | `1` keeps the test snapshot and backup instead of deleting them |

Exit code is 0 only if `VERIFY_MATCH` appears in the verify pod's log.

### `status.size` is not what a backup costs

The script prints both numbers because the difference is large enough to mislead
capacity planning. On 2026-08-28, for a volume holding 5.4 MB of data:

```
size                283 115 520   <- the snapshot's logical extent
newlyUploadDataSize     554 286   <- what actually went to Garage, lz4-compressed
```

The Garage bucket independently reported 570.4 kB across 35 objects for its entire
contents. Plan `RecurringJob` retention against `newlyUploadDataSize`.

### If it fails

Everything it creates is disposable, so a partial run leaves no damage - but it may
leave objects behind. Clean up with:

```bash
kubectl -n apps delete pod restore-test-verify --ignore-not-found
kubectl -n apps delete pvc restore-test-data --ignore-not-found
kubectl delete sc longhorn-restore-test --ignore-not-found
kubectl -n longhorn-system delete backup,snapshot -l restore-test=true
```

## install-lan-ca-windows.ps1

Makes `https://<service>.lan` trusted on a Windows machine. The `.lan` certs are
signed by the mkcert CA on the Caddy LXC (110), and Windows carries two
independent trust stores: the system one, and Firefox's own NSS store, which
`mkcert -install` cannot write to on Windows at all. The script feeds both,
then checks DNS and proves the result with a real HTTPS request.

```powershell
# elevated PowerShell, Firefox closed
.\install-lan-ca-windows.ps1 -Fetch                       # pull rootCA.pem over SSH first
.\install-lan-ca-windows.ps1 -CertPath C:\path\rootCA.pem # use a local copy
.\install-lan-ca-windows.ps1 -SkipFirefox                 # Windows store only
```

Idempotent; an existing Firefox `policies.json` is merged, not replaced, and
backed up to `policies.json.bak`. Firefox reads the policy at startup only.

## seelen-webview-guard.ps1

**Retired 2026-08-19.** Seelen UI was removed from the Windows machine the same
day it was written; the script is kept because the technique transfers to any
long-running app whose WebView2 runtime can be swapped underneath it, and
because the reasoning is documented. It is not deployed anywhere.

Keeps [Seelen UI](../docs/hosts/winpc.md#seelen-ui) alive on the Windows side of
the dual boot. Every Seelen widget is a separate WebView2 instance, so when Edge
Update installs a new Evergreen runtime the already-running shell is left talking
to a runtime directory that no longer exists. Widgets that need a new webview
then fail with `HRESULT(0x80010108)` and the user sees "The widget 'X' stopped
responding too many times". The process never recovers by itself.

The script compares the registered runtime version against the path of Seelen's
own `msedgewebview2.exe` child and restarts Seelen only when they differ. No log
parsing, no heuristics, and a 10-minute cooldown stamp so a mismatch that refuses
to clear cannot become a restart loop.

`seelen-webview-guard.vbs` goes with it. The scheduled task runs the `.vbs`, not
PowerShell directly, because `powershell.exe -WindowStyle Hidden` still flashes a
console window - the host window is created before PowerShell reads the flag, so
a 5-minute task blinks on the desktop twelve times an hour and can steal focus.

```powershell
# deploy both
scp scripts/seelen-webview-guard.ps1 winpc:'C:/Users/<user>/seelen-webview-guard.ps1'
scp scripts/seelen-webview-guard.vbs winpc:'C:/Users/<user>/seelen-webview-guard.vbs'

# schedule (see docs/hosts/winpc.md for the full Register-ScheduledTask call)
$me = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name   # NOT $env:USERDOMAIN
```

Two things the task cannot get wrong: the principal must come from
`WindowsIdentity` because `$env:USERDOMAIN` is `WORKGROUP` on a machine that is
not domain-joined and `Register-ScheduledTask` rejects it, and the logon type
must be `Interactive` because relaunching an MSIX app needs a desktop session -
a SYSTEM task would kill Seelen and never bring it back.

The `.vbs` hardcodes the path to the `.ps1`; change both if the deploy location
moves. And note that `wscript.exe` exits 0 whether or not the script it launched
did anything, so a task result of `0` is not evidence that the guard ran.

Why it was retired: the guard caught the WebView2-update failure exactly as
designed, but four hours later a different widget died from a different WebView2
error (`0x8007139F`, with the runtime versions matching) that no process-level
check can see. Guarding a web-shell one symptom at a time is not a fight worth
picking - the full argument is in
[docs/hosts/winpc.md](../docs/hosts/winpc.md#why-it-was-removed).

## Related Documentation

- [Backup Strategy](../docs/proxmox/15_Proxmox_Backup_System_Documentation.md)
- [HTTPS for .lan on Windows](../docs/hosts/winpc.md#https-for-lan-services)
- [Seelen UI on the Windows dual boot](../docs/hosts/winpc.md#seelen-ui)

---

## lvm-thin-textfile.sh

Exports the `pve/data` thin pool fill levels for the Prometheus node_exporter. Runs on
**pve**, not on this LXC, from a systemd timer every five minutes.

```
lvm_thin_pool_data_percent{vg="pve",lv="data"} 62.55
lvm_thin_pool_metadata_percent{vg="pve",lv="data"} 3.41
lvm_thin_pool_size_bytes{vg="pve",lv="data"} 177100292096
```

node_exporter has no LVM collector, and a thin pool is not a filesystem, so
`node_filesystem_*` cannot see it - while it is the thing every LXC and VM disk is carved
out of, and the thing that has been at 92% before.

### Install

```bash
scp scripts/lvm-thin-textfile.sh root@192.168.0.109:/usr/local/bin/
ssh root@192.168.0.109 'chmod 755 /usr/local/bin/lvm-thin-textfile.sh'
# then lvm-thin-textfile.service (Type=oneshot) and .timer
#      (OnBootSec=2min, OnUnitActiveSec=5min) in /etc/systemd/system/
ssh root@192.168.0.109 'systemctl enable --now lvm-thin-textfile.timer'
```

The full unit files and the reasoning are in
[44 - Host Metrics Into The K3s Prometheus](../docs/proxmox/44_Host_Metrics_Into_The_K3s_Prometheus.md).

### Two things in it that look optional and are not

**`--select 'lv_attr =~ ^t'`** keeps the output to thin *pools*. Without it every thin
volume carved out of the pool reports its own `data_percent`, and each guest disk shows
up looking like a pool of its own.

**The write is atomic** - temp file, then `mv`. The textfile collector reads whole files
on every scrape, so writing in place produces a parse error whenever a scrape lands
mid-write. Rare, and therefore the kind of bug that surfaces once a month looking like
something else entirely.

### It has a dead man's switch

If the timer stops, node_exporter keeps serving the last values it read, for ever, with
no error anywhere - and the thin-pool alerts would be watching a frozen number while
reporting healthy. `HomelabThinPoolMetricsStale` in
`k8s/manifests/homelab-hosts/prometheusrule.yaml` fires after six missed runs.
