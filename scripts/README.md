# Automation Scripts

Collection of bash scripts for homelab automation and maintenance.

## Scripts

### backup.sh
Automated backup script using restic.

**Features:**
- Backs up Docker volumes and configurations
- Encrypted and deduplicated
- Multiple destinations (NFS, cloud)
- Automatic retention management

**Usage:**
```bash
./backup.sh [service_name]
# Or backup all:
./backup.sh --all
```

## Installation

1. Clone repository to automation server:
```bash
git clone https://github.com/yourusername/homelab.git
cd homelab/scripts
```

2. Make scripts executable:
```bash
chmod +x *.sh
```

3. Configure environment variables (copy `.env.example` to `.env`)

4. Test scripts in dry-run mode first

## Configuration

Create `.env` file with:
```bash
# Backup configuration
BACKUP_DEST_NFS="/mnt/backup"
BACKUP_DEST_CLOUD="b2:bucket-name"
RESTIC_PASSWORD="your-encryption-password"

# Notification settings
NTFY_URL="https://ntfy.sh/your-topic"
```

## Scheduling

Add to crontab for automation:

```bash
# Daily backup at 2 AM
0 2 * * * /path/to/homelab/scripts/backup.sh --all

# Monthly cleanup
0 4 1 * * docker system prune -af
```

## Logging

All scripts log to `/var/log/homelab/`:
- `backup.log`

View logs:
```bash
tail -f /var/log/homelab/backup.log
```

## Error Handling

Scripts include:
- Exit on error (`set -e`)
- Undefined variable checks (`set -u`)
- Cleanup on exit (trap handlers)
- Detailed error messages

## Testing

Test scripts in dry-run mode:
```bash
# Backup test (no actual backup)
./backup.sh --dry-run service_name
```

## Contributing

When adding new scripts:
1. Follow bash best practices (shellcheck)
2. Include help text (`--help` flag)
3. Add dry-run mode for safety
4. Document in this README
5. Add example usage

## Security

- Store secrets in `.env` (gitignored)
- Use SSH keys instead of passwords
- Limit script permissions (chmod 700)
- Run with least privilege when possible

## Related Documentation

- [Backup Strategy](../docs/proxmox/16_Proxmox_Backup_System_Documentation.md)
- [LXC & Docker Setup](../docs/proxmox/2_Proxmox_Docker_LXC_Setup_-_Detailed_Process.md)
