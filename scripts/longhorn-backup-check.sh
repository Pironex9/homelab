#!/bin/bash
# Dead man's switch a Longhorn kötetmentésre és a Garage S3 célpontra.
#
# A 109-en fut, mert itt van a kubectl a K3s clusterhez ÉS az SSH kulcs a
# 100-as LXC-hez, ahol a Garage lakik.
#
# Miért nem elég a Kuma sima HTTP monitorja a Garage-ra:
#   Az azt mondaná meg, hogy a Garage válaszol - de a Garage attól még
#   válaszol, hogy a Longhorn nem tud beleírni (rossz kulcs, lejárt jog,
#   megtelt pool), és attól is, hogy a RecurringJob egyáltalán nem futott le.
#   A "fut-e valami" és a "megtörtént-e valami" két külön kérdés; ez a script
#   a másodikat teszi fel.
#
# Mit ellenőriz, ebben a sorrendben:
#   1. a BackupTarget elérhető-e         - ez ma is értelmes, nulla kötettel is
#   2. a Garage bucket olvasható-e       - és mekkora
#   3. minden kötetnek van-e MAX_AGE_HOURS-nál frissebb, Completed mentése
#   4. van-e Error állapotú Backup objektum
#
# A nulla kötet NEM hiba: a clusteren ma tényleg nincs PVC. De külön üzenetet
# kap ("no-volumes"), különben a heartbeat-előzményben nem lehet megkülönböztetni
# attól, hogy minden rendben lement.
#
# Használat:
#   ./longhorn-backup-check.sh
#   KUMA_PUSH_URL="http://.../api/push/<token>" ./longhorn-backup-check.sh
#
# A push tokent szándékosan NEM tartalmazza ez a fájl: a repo publikus. A token
# a crontab sorban él, ugyanúgy, mint a többi Kuma-figyelőnél.

set -uo pipefail

# A cron PATH-ában nincs /usr/local/bin, a kubectl viszont ott lakik. Ez a
# homelabban már három jobot megölt csendben. Ellenőrzés:
#   env -i PATH=/usr/bin:/bin HOME=/root bash -c 'which kubectl'
PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

NS="longhorn-system"
DOCKER_HOST_SSH="${GARAGE_SSH:-root@192.168.0.110}"
BUCKET="${GARAGE_BUCKET:-longhorn}"
# A RecurringJob 01:00 UTC-kor fut. 26 óra ad egy kimaradt futásnyi ráhagyást
# anélkül, hogy két egymást követő kimaradás elférne benne.
MAX_AGE_HOURS="${LONGHORN_BACKUP_MAX_AGE_HOURS:-26}"

ERRORS=()
NOTES=()
fail() { ERRORS+=("$1"); echo "HIBA: $1" >&2; }
note() { NOTES+=("$1"); echo "  $1"; }

echo "== 1/4 BackupTarget =="
BT_JSON="$(kubectl get backuptarget default -n "$NS" -o json 2>/dev/null)"
if [ -z "$BT_JSON" ]; then
    fail "a BackupTarget/default nem olvasható (kubectl)"
else
    BT_URL="$(printf '%s' "$BT_JSON" | jq -r '.spec.backupTargetURL // ""')"
    # A Longhorn fordítva jelzi: Unavailable=False jelenti azt, hogy elérhető.
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

echo "== 2/4 Garage bucket =="
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

echo "== 3/4 kötetek mentési kora =="
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
        # Egy ma létrehozott kötetnek még jogosan nincs mentése: a RecurringJob
        # 01:00 UTC-kor fut. Enélkül minden új PVC azonnal pirosat adna, és pár
        # ilyen után senki nem nézi meg a riasztást.
        VOL_CREATED="$(printf '%s' "$VOL_JSON" | jq -r --arg v "$v" \
            '.items[]? | select(.metadata.name == $v) | .metadata.creationTimestamp')"
        VOL_AGE_H=$(( (NOW - $(date -u -d "$VOL_CREATED" +%s)) / 3600 ))

        # backupCreatedAt RFC3339 UTC-ben; a legfrissebb Completed kell
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

echo "== 4/4 hibás Backup objektumok =="
ERR_BACKUPS="$(kubectl get backups.longhorn.io -n "$NS" -o json 2>/dev/null \
    | jq -r '[.items[]? | select(.status.state == "Error") | .metadata.name] | join(",")')"
if [ -n "$ERR_BACKUPS" ] && [ "$ERR_BACKUPS" != "null" ]; then
    fail "Error állapotú Backup: $ERR_BACKUPS"
else
    note "nincs hibás Backup objektum"
fi

# --- összegzés és Kuma push ---------------------------------------------------
if [ ${#ERRORS[@]} -gt 0 ]; then
    STATUS="down"
    MSG="$(printf '%s; ' "${ERRORS[@]}")"
    MSG="${MSG%; }"
elif [ "$VOL_COUNT" -eq 0 ]; then
    STATUS="up"
    MSG="no-volumes, bucket ${BUCKET_SIZE:-?}"
else
    STATUS="up"
    # A türelmi időben lévő köteteket külön mondjuk ki: azoknak MÉG nincs
    # mentésük, tehát nem ugyanaz, mint a "mentve" állapot.
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
