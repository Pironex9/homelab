# Scripts

There is no backup script here. `backup.sh` used to sit in this directory,
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

## Related Documentation

- [Backup Strategy](../docs/proxmox/15_Proxmox_Backup_System_Documentation.md)
- [HTTPS for .lan on Windows](../docs/hosts/winpc.md#https-for-lan-services)
