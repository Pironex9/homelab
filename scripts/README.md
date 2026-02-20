# Scripts

## backup.sh

Automated backup using restic. Backs up Docker volumes and configs with encryption, deduplication, and automatic retention.

```bash
./backup.sh [service_name]
./backup.sh --all
./backup.sh --dry-run service_name
```

### Configuration

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

## Related Documentation

- [Backup Strategy](../docs/proxmox/16_Proxmox_Backup_System_Documentation.md)
