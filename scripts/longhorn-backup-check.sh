#!/bin/bash
# Dead man's switch for the Longhorn volume backups and the Garage S3 target.
#
# Runs on 109, because this is where both kubectl for the K3s cluster AND the SSH key
# for LXC 100, where Garage lives, are.
#
# Why a plain Kuma HTTP monitor on Garage is not enough:
#   That would tell you that Garage answers - but Garage answers just as well when
#   Longhorn cannot write into it (wrong key, expired permission, full pool), and
#   also when the RecurringJob never ran at all. "Is something running" and "did
#   something happen" are two different questions; this script asks the second one.
#
# What it checks, in this order:
#   1. is the BackupTarget available     - this is meaningful today, even with zero volumes
#   2. is the Garage bucket readable     - and how large it is
#   3. does every volume have a Completed backup newer than MAX_AGE_HOURS
#   4. is there any Backup object in Error state
#   5. is every Longhorn node and disk Ready
#
# Point 5 was added on 2026-08-27: that day the USB disk of opt3050-i5 re-enumerated,
# systemd unmounted it and did not mount it back, Longhorn wrote a fresh
# longhorn-disk.cfg onto the root FS, and the disk dropped out with
# DiskFilesystemChanged. This script pushed "up - no-volumes" at the time, because
# with zero volumes step 3 looks at nothing. Disk health is independent of whether
# there is a volume today - a dead disk has to be known about anyway.
#
# Zero volumes is NOT an error: there really is no PVC on the cluster today. But it
# gets its own message ("no-volumes"), otherwise the heartbeat history could not tell
# it apart from everything having been backed up fine.
#
# Usage:
#   ./longhorn-backup-check.sh
#   KUMA_PUSH_URL="http://.../api/push/<token>" ./longhorn-backup-check.sh
#
# The push token is deliberately NOT in this file: the repo is public. The token lives
# in the crontab line, the same way as for the other Kuma watchers.

set -uo pipefail

# The cron PATH does not contain /usr/local/bin, and kubectl lives there. That has
# already killed three jobs silently in this homelab. Check with:
#   env -i PATH=/usr/bin:/bin HOME=/root bash -c 'which kubectl'
PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

NS="longhorn-system"
DOCKER_HOST_SSH="${GARAGE_SSH:-root@192.168.0.110}"
BUCKET="${GARAGE_BUCKET:-longhorn}"
# The RecurringJob runs at 01:00 UTC. 26 hours gives one missed run of slack without
# leaving room for two consecutive misses.
MAX_AGE_HOURS="${LONGHORN_BACKUP_MAX_AGE_HOURS:-26}"

ERRORS=()
NOTES=()
fail() { ERRORS+=("$1"); echo "HIBA: $1" >&2; }
note() { NOTES+=("$1"); echo "  $1"; }

echo "== 1/5 BackupTarget =="
BT_JSON="$(kubectl get backuptarget default -n "$NS" -o json 2>/dev/null)"
if [ -z "$BT_JSON" ]; then
    fail "a BackupTarget/default nem olvasható (kubectl)"
else
    BT_URL="$(printf '%s' "$BT_JSON" | jq -r '.spec.backupTargetURL // ""')"
    # Longhorn reports this inverted: Unavailable=False means it is available.
    BT_UNAVAIL="$(printf '%s' "$BT_JSON" | jq -r '.status.conditions[]? | select(.type=="Unavailable") | .status')"
    BT_MSG="$(printf '%s' "$BT_JSON" | jq -r '.status.conditions[]? | select(.type=="Unavailable") | .message')"
    if [ -z "$BT_URL" ]; then
        fail "a BackupTarget URL-je üres - nincs hova menteni"
    elif [ "$BT_UNAVAIL" != "False" ]; then
        fail "a BackupTarget nem elérhető: ${BT_MSG:-nincs indoklás}"
    else
        note "elérhető: $BT_URL"
    fi
fi

echo "== 2/5 Garage bucket =="
BUCKET_INFO="$(ssh -o ConnectTimeout=10 -o BatchMode=yes "$DOCKER_HOST_SSH" \
    "docker exec garage /garage bucket info $BUCKET 2>/dev/null" 2>/dev/null)"
if [ -z "$BUCKET_INFO" ]; then
    fail "a Garage bucket ($BUCKET) nem kérdezhető le a $DOCKER_HOST_SSH gépen"
    BUCKET_SIZE="?"
else
    BUCKET_SIZE="$(printf '%s' "$BUCKET_INFO" | awk -F': *' '/^Size:/{print $2}' | awk '{print $1 $2}')"
    BUCKET_OBJ="$(printf '%s' "$BUCKET_INFO" | awk -F': *' '/^Objects:/{print $2}' | tr -d ' ')"
    note "bucket $BUCKET: ${BUCKET_SIZE:-?}, ${BUCKET_OBJ:-?} objektum"
fi

echo "== 3/5 kötetek mentési kora =="
VOL_JSON="$(kubectl get volumes.longhorn.io -n "$NS" -o json 2>/dev/null)"
VOLUMES="$(printf '%s' "$VOL_JSON" | jq -r '.items[]?.metadata.name')"
VOL_COUNT=0
STALE=0
GRACE=0
if [ -n "$VOLUMES" ]; then
    BACKUPS="$(kubectl get backups.longhorn.io -n "$NS" -o json 2>/dev/null)"
    NOW="$(date -u +%s)"
    for v in $VOLUMES; do
        VOL_COUNT=$((VOL_COUNT + 1))
        # A volume created today may legitimately have no backup yet: the RecurringJob
        # runs at 01:00 UTC. Without this every new PVC would go red immediately, and
        # after a few of those nobody looks at the alert any more.
        VOL_CREATED="$(printf '%s' "$VOL_JSON" | jq -r --arg v "$v" \
            '.items[]? | select(.metadata.name == $v) | .metadata.creationTimestamp')"
        VOL_AGE_H=$(( (NOW - $(date -u -d "$VOL_CREATED" +%s)) / 3600 ))

        # backupCreatedAt is RFC3339 UTC; we want the most recent Completed one
        NEWEST="$(printf '%s' "$BACKUPS" | jq -r --arg v "$v" '
            [.items[]? | select(.status.volumeName == $v and .status.state == "Completed")
             | .status.backupCreatedAt] | sort | last // ""')"
        if [ -z "$NEWEST" ] || [ "$NEWEST" = "null" ]; then
            if [ "$VOL_AGE_H" -le "$MAX_AGE_HOURS" ]; then
                note "$v: ${VOL_AGE_H}h korú, még nem esedékes az első mentése"
                GRACE=$((GRACE + 1))
            else
                fail "a(z) $v kötetnek nincs egyetlen befejezett mentése sem (${VOL_AGE_H}h korú)"
                STALE=$((STALE + 1))
            fi
            continue
        fi
        AGE_H=$(( (NOW - $(date -u -d "$NEWEST" +%s)) / 3600 ))
        if [ "$AGE_H" -gt "$MAX_AGE_HOURS" ]; then
            fail "a(z) $v kötet legfrissebb mentése ${AGE_H} órás (küszöb: ${MAX_AGE_HOURS}h)"
            STALE=$((STALE + 1))
        else
            note "$v: ${AGE_H}h"
        fi
    done
else
    note "nincs Longhorn kötet a clusteren - nincs mit menteni"
fi

echo "== 4/5 hibás Backup objektumok =="
ERR_BACKUPS="$(kubectl get backups.longhorn.io -n "$NS" -o json 2>/dev/null \
    | jq -r '[.items[]? | select(.status.state == "Error") | .metadata.name] | join(",")')"
if [ -n "$ERR_BACKUPS" ] && [ "$ERR_BACKUPS" != "null" ]; then
    fail "Error állapotú Backup: $ERR_BACKUPS"
else
    note "nincs hibás Backup objektum"
fi

echo "== 5/5 Longhorn node-ok es lemezek =="
LHNODE_JSON="$(kubectl get nodes.longhorn.io -n "$NS" -o json 2>/dev/null)"
if [ -z "$LHNODE_JSON" ]; then
    fail "a Longhorn node objektumok nem olvashatók (kubectl)"
else
    # Node Ready plus the per-disk Ready condition. The disk's message carries the
    # reason (e.g. "record diskUUID doesn't match the one on the disk"), so we pass
    # that on into the Kuma message, not just the disk name.
    BAD_NODES="$(printf '%s' "$LHNODE_JSON" | jq -r '
        [.items[]? | select([.status.conditions[]? | select(.type=="Ready") | .status] | index("True") | not)
         | .metadata.name] | join(",")')"
    [ -n "$BAD_NODES" ] && fail "nem Ready Longhorn node: $BAD_NODES"

    BAD_DISKS="$(printf '%s' "$LHNODE_JSON" | jq -r '
        [.items[]? as $n | ($n.status.diskStatus // {}) | to_entries[]
         | select([.value.conditions[]? | select(.type=="Ready") | .status] | index("True") | not)
         | "\($n.metadata.name)/\(.value.diskPath // .key)"] | join(",")')"
    if [ -n "$BAD_DISKS" ]; then
        fail "nem Ready Longhorn lemez: $BAD_DISKS"
    elif [ -z "$BAD_NODES" ]; then
        NODE_N="$(printf '%s' "$LHNODE_JSON" | jq -r '.items | length')"
        SCHED_GIB="$(printf '%s' "$LHNODE_JSON" | jq -r '
            [.items[]?.status.diskStatus // {} | to_entries[] | .value.storageAvailable // 0]
            | add / 1073741824 | floor')"
        note "$NODE_N node, minden lemez Ready, ${SCHED_GIB} GiB szabad"
    fi
fi

# --- summary and Kuma push ----------------------------------------------------
if [ ${#ERRORS[@]} -gt 0 ]; then
    STATUS="down"
    MSG="$(printf '%s; ' "${ERRORS[@]}")"
    MSG="${MSG%; }"
elif [ "$VOL_COUNT" -eq 0 ]; then
    STATUS="up"
    MSG="no-volumes, bucket ${BUCKET_SIZE:-?}"
else
    STATUS="up"
    # Volumes still inside the grace period are called out separately: those do NOT
    # have a backup yet, which is not the same as being backed up.
    OKC=$((VOL_COUNT - GRACE))
    MSG="${OKC}/${VOL_COUNT} kotet mentve"
    [ "$GRACE" -gt 0 ] && MSG="$MSG, ${GRACE} uj (meg nincs mentes)"
    MSG="$MSG, bucket ${BUCKET_SIZE:-?}"
fi

echo
echo "eredmeny: $STATUS - $MSG"

if [ -n "${KUMA_PUSH_URL:-}" ]; then
    curl -fsS -m 10 -o /dev/null -G "$KUMA_PUSH_URL" \
        --data-urlencode "status=$STATUS" \
        --data-urlencode "msg=$MSG" \
        || echo "FIGYELEM: a Kuma push nem ment át" >&2
fi

[ "$STATUS" = "up" ] || exit 1
