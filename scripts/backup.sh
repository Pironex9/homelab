#!/bin/bash
# Automated backup script for homelab Docker volumes
# Uses restic for encrypted, deduplicated backups

set -euo pipefail

# Source configuration
if [ -f "$(dirname "$0")/.env" ]; then
    source "$(dirname "$0")/.env"
else
    echo "Error: .env file not found"
    exit 1
fi

# Configuration
BACKUP_SOURCE="/srv/docker-data"
LOG_FILE="/var/log/homelab/backup.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Functions
log() {
    echo "[$TIMESTAMP] $1" | tee -a "$LOG_FILE"
}

backup_service() {
    local service=$1
    log "Starting backup for: $service"

    # Restic backup
    restic -r "$BACKUP_DEST_NFS/$service" \
           --verbose backup "$BACKUP_SOURCE/$service" \
           2>&1 | tee -a "$LOG_FILE"

    # Retention policy
    restic -r "$BACKUP_DEST_NFS/$service" \
           forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6 \
           --prune 2>&1 | tee -a "$LOG_FILE"

    log "Backup completed for: $service"
}

backup_immich_db() {
    local dump_dir="/tmp/immich-db-dump"
    local dump_file="$dump_dir/immich-$(date +%Y%m%d-%H%M).sql"

    log "Starting Immich Postgres dump"
    mkdir -p "$dump_dir"

    docker exec immich_postgres pg_dumpall \
        --clean --if-exists -U postgres \
        > "$dump_file" 2>&1

    log "Backing up Immich Postgres dump with restic"
    restic -r "$BACKUP_DEST_NFS/immich-db" \
           --verbose backup "$dump_dir" \
           2>&1 | tee -a "$LOG_FILE"

    restic -r "$BACKUP_DEST_NFS/immich-db" \
           forget --keep-daily 7 --keep-weekly 4 --keep-monthly 6 \
           --prune 2>&1 | tee -a "$LOG_FILE"

    rm -rf "$dump_dir"
    log "Immich Postgres dump completed"
}

# Main
if [ "$#" -eq 0 ] || [ "$1" == "--all" ]; then
    log "Starting full backup"
    backup_immich_db
    for dir in "$BACKUP_SOURCE"/*; do
        if [ -d "$dir" ]; then
            service=$(basename "$dir")
            backup_service "$service"
        fi
    done
elif [ "$1" == "immich-db" ]; then
    backup_immich_db
else
    backup_service "$1"
fi

log "Backup process finished"

# Optional: Send notification
if [ -n "${NTFY_URL:-}" ]; then
    curl -d "Backup completed successfully" "$NTFY_URL"
fi
