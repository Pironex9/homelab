#!/bin/bash
# Mirror the Proxmox backup dumps onto the Nobara desktop's backup HDD over NFS.
#
# Deployed to /root/sync-to-nobara.sh on pve and run from root's crontab there,
# not from this repo:
#
#   0 11,19 * * 0 /root/sync-to-nobara.sh
#
# Twice on Sunday on purpose: the desktop is not always on, and the second slot
# catches the weeks when it was off at 11:00.
#
# The Kuma push URL, token included, lives in /etc/nobara-sync.env (mode 600, NOT
# in this repo) because docs/ and scripts/ are public. The ping cannot move into
# the crontab line the way restore-test.sh does its own, because this script
# pushes from two different paths with two different messages.

KUMA_PUSH_URL=""
[ -r /etc/nobara-sync.env ] && . /etc/nobara-sync.env

# One run at a time. The 11:00 sync can overrun into the 19:00 slot: on
# 2026-09-13 the 19:00 run finished at 17:33 the next day, 22.5 hours later. Two
# rsyncs against the same destination with --delete remove each other's files.
#
# No Kuma push on the skip path. If the sync still running succeeds it pings for
# itself; if it fails there genuinely was no successful backup, and the monitor
# SHOULD go down.
exec 9>/var/lock/nobara-sync.lock
flock -n 9 || { echo "$(date) - another sync is running, skipped" >> /var/log/nobara-sync.log; exit 0; }

if mountpoint -q /mnt/pve/nobara-backup; then
    echo "$(date) - Syncing to Nobara..." >> /var/log/nobara-sync.log
    rc=0
    rsync -av --delete /mnt/storage/backup/proxmox/ /mnt/pve/nobara-backup/proxmox-vms/ >> /var/log/nobara-sync.log 2>&1 || rc=1
    rsync -av --delete /mnt/disk1/backup/proxmox-host/ /mnt/pve/nobara-backup/proxmox-host/ >> /var/log/nobara-sync.log 2>&1 || rc=1
    echo "$(date) - Sync done (rc=$rc)" >> /var/log/nobara-sync.log
    [ "$rc" -eq 0 ] && [ -n "$KUMA_PUSH_URL" ] && curl -fsS -m 10 -o /dev/null "$KUMA_PUSH_URL?status=up&msg=synced"
else
    # Skipping is a legitimate outcome too: the Nobara desktop is simply off.
    # Without a ping here Kuma would alert on every week the machine stayed off.
    echo "$(date) - NFS not mounted, skipping" >> /var/log/nobara-sync.log
    [ -n "$KUMA_PUSH_URL" ] && curl -fsS -m 10 -o /dev/null "$KUMA_PUSH_URL?status=up&msg=nobara-offline-skipped"
fi
