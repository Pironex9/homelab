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
| `tls/`, `cred/`, `token`, `node-token` | without these you cannot connect to a restored DB and nodes cannot rejoin |
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

### Restoring

Deliberately not automated.

```bash
gpg --decrypt --passphrase-file /root/.secrets/k3s-backup-passphrase \
    k3s-control-plane-<TS>.tar.gz.gpg | tar xzf - -C /somewhere
# then on the master: systemctl stop k3s
#   put state.db, tls/ and cred/ back in place
#   systemctl start k3s
# then on the workers: systemctl restart k3s-agent
```

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
30 1 * * * /root/homelab/scripts/k3s-backup.sh >> /var/log/homelab/k3s-backup.log 2>&1
```

01:30 keeps it clear of the 02:00 vzdump window on the same backup disk. The script
sets its own `PATH` because `kubectl` lives in `/usr/local/bin`, which cron does not
see - a trap that has silently killed three jobs in this homelab. Test with
`env -i PATH=/usr/bin:/bin HOME=/root ./k3s-backup.sh`.

Measured on 2026-08-24: 29 seconds end to end, 68 MB archive plus a 1.2 MB export.

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

Check 1 is the one that earns its keep today: the cluster has **zero** volumes, so
checks 3 and 4 have nothing to look at, but a broken key or a dead Garage still
turns the monitor red.

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
0 2 * * * KUMA_PUSH_URL=http://100.118.239.117:3001/api/push/<token> /root/homelab/scripts/longhorn-backup-check.sh >> /var/log/homelab/longhorn-backup-check.log 2>&1
```

**LXC 109 runs on UTC**, so 02:00 here really is one hour after the Longhorn job at
01:00 UTC and half an hour after `k3s-backup.sh`. The push token lives in the crontab
line, not in the script - this repository is public. Like `k3s-backup.sh`, the script
sets its own `PATH` because `kubectl` is in `/usr/local/bin`, which cron does not see.

Both paths verified on 2026-08-25: a healthy run pushed `up` with
`no-volumes, bucket 589B`, and a deliberately unreachable Garage pushed `down` with
the reason, which reached the Discord notification.

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
