# Scripts

## backup.sh

Automated backup using restic. Backs up Docker volumes and configs with encryption, deduplication, and automatic retention.

```bash
./backup.sh [service_name]
./backup.sh --all
./backup.sh --dry-run service_name
```

### Configuration

Both scripts read `scripts/.env` (gitignored). See `.env.example` for every key.

```bash
BACKUP_DEST_NFS="/mnt/backup"
BACKUP_DEST_CLOUD="b2:bucket-name"
RESTIC_PASSWORD="your-encryption-password"
NTFY_URL="https://ntfy.sh/your-topic"
```

### Scheduling

```bash
# Daily backup at 2 AM
0 2 * * * /path/to/homelab/scripts/backup.sh --all
```

Logs to `/var/log/homelab/backup.log`.

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

```bash
# Restore test every Sunday at 4 AM
0 4 * * 0 /path/to/homelab/scripts/restore-test.sh
```

Logs to `/var/log/homelab/restore-test.log`.

## Related Documentation

- [Backup Strategy](../docs/proxmox/15_Proxmox_Backup_System_Documentation.md)
