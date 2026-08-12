#!/bin/bash
# Restore test for the restic repositories under $BACKUP_DEST_NFS.
#
# It discovers them rather than carrying a repository list of its own, so a new
# restic repo is picked up without editing this script. Live on pve that is one
# repo, proxmox-host, written weekly by /root/backup-proxmox-restic.sh. For
# every repository it:
#   1. reports the age of the newest snapshot and fails past RESTORE_TEST_MAX_AGE_DAYS
#   2. runs `restic check --read-data-subset=<RESTORE_TEST_SUBSET>`
#   3. restores a few files from a randomly picked snapshot into a temp dir and
#      compares their checksums against `restic dump` of the same snapshot
#
# Every repository is tested even if an earlier one failed, then one summary is
# posted to ntfy. The exit code is non-zero if anything failed, so cron surfaces it.
#
# Usage:
#   ./restore-test.sh                  # test every discovered repository
#   ./restore-test.sh immich immich-db # test only these repositories
#   ./restore-test.sh --no-ntfy        # run without posting the summary

set -uo pipefail

# Source configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -f "$SCRIPT_DIR/.env" ]; then
    # shellcheck disable=SC1091
    source "$SCRIPT_DIR/.env"
else
    echo "Error: .env file not found" >&2
    exit 1
fi

# Configuration
MAX_AGE_DAYS="${RESTORE_TEST_MAX_AGE_DAYS:-2}"
FILE_COUNT="${RESTORE_TEST_FILES:-3}"
READ_DATA_SUBSET="${RESTORE_TEST_SUBSET:-1%}"
LOG_FILE="${RESTORE_TEST_LOG:-/var/log/homelab/restore-test.log}"
TMPDIR_BASE="${RESTORE_TEST_TMPDIR:-/tmp}"
NTFY_TOPIC="${NTFY_TOPIC:-homelab-digest}"
NTFY_CURL_OPTS="${NTFY_CURL_OPTS:-}"

# An older NTFY_URL key holds a full URL including its own topic; if no explicit
# base URL is configured, reuse it with the topic stripped off.
NTFY_BASE_URL="${NTFY_BASE_URL:-}"
if [ -z "$NTFY_BASE_URL" ] && [ -n "${NTFY_URL:-}" ]; then
    NTFY_BASE_URL="${NTFY_URL%/*}"
fi

SEND_NTFY=1
REPO_FILTER=()
for arg in "$@"; do
    case "$arg" in
        --no-ntfy) SEND_NTFY=0 ;;
        -h|--help) sed -n '2,20p' "${BASH_SOURCE[0]}"; exit 0 ;;
        -*) echo "Unknown option: $arg" >&2; exit 2 ;;
        *) REPO_FILTER+=("$arg") ;;
    esac
done

SUMMARY=()
FAILURES=0
TMPROOT=""

# Functions
log() {
    local line
    line="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    if [ -n "$LOG_FILE" ]; then
        echo "$line" | tee -a "$LOG_FILE"
    else
        echo "$line"
    fi
}

cleanup() {
    if [ -n "$TMPROOT" ] && [ -d "$TMPROOT" ]; then
        rm -rf "$TMPROOT"
    fi
}
trap cleanup EXIT

# Record a per-repository result line for the ntfy summary.
ok_line() {
    SUMMARY+=("OK $1")
    log "OK $1"
}

fail_line() {
    SUMMARY+=("FAIL $1")
    log "FAIL $1"
    FAILURES=$((FAILURES + 1))
}

fmt_age() {
    printf '%dd %dh' $(($1 / 86400)) $((($1 % 86400) / 3600))
}

# Reduce restic output to the lines worth putting in a notification: drop the
# progress and status chatter, keep the last few real messages.
trim_err() {
    local text
    text=$(printf '%s\n' "$1" |
        grep -vE '^(using temporary cache|create exclusive lock|load indexes|check |read |repository |restoring |Summary: |\[|[[:space:]]*$)' |
        tail -3 | tr '\n' ' ' | tr -s ' ')
    [ -z "$text" ] && text=$(printf '%s' "$1" | tail -1)
    printf '%.240s' "$text"
}

# A restic repository always contains these entries.
is_restic_repo() {
    [ -f "$1/config" ] && [ -d "$1/data" ] && [ -d "$1/snapshots" ]
}

discover_repos() {
    local dir
    for dir in "$BACKUP_DEST_NFS"/*; do
        [ -d "$dir" ] || continue
        is_restic_repo "$dir" || continue
        basename "$dir"
    done
}

# 1. Age of the newest snapshot.
test_snapshot_age() {
    local name=$1 repo=$2
    local json ts snap_epoch age_secs max_secs

    if ! json=$(restic -r "$repo" snapshots --latest 1 --json 2>&1); then
        fail_line "$name: cannot list snapshots: $(trim_err "$json")"
        return 1
    fi

    ts=$(printf '%s' "$json" | grep -o '"time":"[^"]*"' | head -1 | cut -d'"' -f4)
    if [ -z "$ts" ]; then
        fail_line "$name: repository has no snapshots"
        return 1
    fi

    snap_epoch=$(date -d "$ts" +%s 2>/dev/null)
    if [ -z "$snap_epoch" ]; then
        fail_line "$name: cannot parse snapshot timestamp: $ts"
        return 1
    fi

    age_secs=$(( $(date +%s) - snap_epoch ))
    max_secs=$((MAX_AGE_DAYS * 86400))
    if [ "$age_secs" -gt "$max_secs" ]; then
        fail_line "$name: newest snapshot is $(fmt_age "$age_secs") old (max ${MAX_AGE_DAYS}d)"
        return 1
    fi

    ok_line "$name: newest snapshot $(fmt_age "$age_secs") old"
    return 0
}

# 2. Integrity check including a subset of the actual data packs.
test_check() {
    local name=$1 repo=$2
    local out

    if out=$(restic -r "$repo" check --read-data-subset="$READ_DATA_SUBSET" 2>&1); then
        ok_line "$name: check --read-data-subset=$READ_DATA_SUBSET passed"
        return 0
    fi

    fail_line "$name: check failed: $(trim_err "$out")"
    return 1
}

# 3. Restore a few files from a random snapshot and verify their checksums.
test_restore() {
    local name=$1 repo=$2
    local snap target out restored have want size actual entry f
    local ids=() entries=() files=() sizes=() include_args=()
    local verified=0 checked=0

    mapfile -t ids < <(restic -r "$repo" snapshots --json 2>/dev/null |
        grep -o '"short_id":"[^"]*"' | cut -d'"' -f4)
    if [ "${#ids[@]}" -eq 0 ]; then
        fail_line "$name: no snapshots to restore from"
        return 1
    fi
    snap="${ids[RANDOM % ${#ids[@]}]}"

    # Regular, non-empty files only: an empty file matches any checksum test.
    # Keep the size the snapshot recorded alongside the path, as "size<TAB>path".
    mapfile -t entries < <(restic -r "$repo" ls --long "$snap" 2>/dev/null |
        grep '^-' | grep -vE '^\S+ +\S+ +\S+ +0 ' |
        sed -E 's/^\S+ +\S+ +\S+ +(\S+) +\S+ +\S+ +/\1\t/' | shuf -n "$FILE_COUNT")
    if [ "${#entries[@]}" -eq 0 ]; then
        fail_line "$name: snapshot $snap contains no regular files to restore"
        return 1
    fi

    for entry in "${entries[@]}"; do
        sizes+=("${entry%%$'\t'*}")
        files+=("${entry#*$'\t'}")
    done

    target="$TMPROOT/$name"
    mkdir -p "$target"

    for f in "${files[@]}"; do
        include_args+=(--include "$f")
    done

    if ! out=$(restic -r "$repo" restore "$snap" --target "$target" "${include_args[@]}" 2>&1); then
        fail_line "$name: restore of snapshot $snap failed: $(trim_err "$out")"
        rm -rf "$target"
        return 1
    fi

    local i
    for i in "${!files[@]}"; do
        f="${files[$i]}"
        size="${sizes[$i]}"
        checked=$((checked + 1))
        restored="$target$f"
        if [ ! -f "$restored" ]; then
            fail_line "$name: $f missing after restore of $snap"
            continue
        fi
        # Size comes from the snapshot tree, checksum from the data blobs: two
        # independent sources, so a truncated restore cannot pass both.
        actual=$(stat -c %s "$restored" 2>/dev/null)
        if [ "$actual" != "$size" ]; then
            fail_line "$name: $f restored with $actual bytes, snapshot $snap says $size"
            continue
        fi
        have=$(sha256sum < "$restored" | cut -d' ' -f1)
        want=$(restic -r "$repo" dump "$snap" "$f" 2>/dev/null | sha256sum | cut -d' ' -f1)
        if [ -z "$want" ]; then
            fail_line "$name: cannot dump $f from $snap for comparison"
            continue
        fi
        if [ "$have" != "$want" ]; then
            fail_line "$name: checksum mismatch for $f in $snap ($have != $want)"
            continue
        fi
        verified=$((verified + 1))
    done

    rm -rf "$target"

    if [ "$verified" -ne "$checked" ]; then
        return 1
    fi
    ok_line "$name: restored $verified/$checked files from $snap, checksums match"
    return 0
}

test_repo() {
    local name=$1
    local repo="$BACKUP_DEST_NFS/$name"

    log "Testing repository: $name"
    test_snapshot_age "$name" "$repo"
    test_check "$name" "$repo"
    test_restore "$name" "$repo"
}

notify() {
    local title=$1 tags=$2 priority=$3 body=$4

    if [ "$SEND_NTFY" -eq 0 ]; then
        log "ntfy skipped (--no-ntfy)"
        return 0
    fi
    if [ -z "$NTFY_BASE_URL" ]; then
        log "warning: neither NTFY_BASE_URL nor NTFY_URL set, no summary sent"
        return 1
    fi

    # NTFY_CURL_OPTS is intentionally unquoted: it carries extra curl options.
    # shellcheck disable=SC2086
    if curl -sSf $NTFY_CURL_OPTS \
        -H "Title: $title" -H "Tags: $tags" -H "Priority: $priority" \
        -d "$body" "$NTFY_BASE_URL/$NTFY_TOPIC" >/dev/null 2>&1; then
        return 0
    fi

    log "warning: could not post summary to $NTFY_BASE_URL/$NTFY_TOPIC"
    return 1
}

# Main
if [ -z "${BACKUP_DEST_NFS:-}" ]; then
    echo "Error: BACKUP_DEST_NFS is not set in .env" >&2
    exit 1
fi
if [ -z "${RESTIC_PASSWORD:-}" ] && [ -z "${RESTIC_PASSWORD_FILE:-}" ]; then
    echo "Error: RESTIC_PASSWORD or RESTIC_PASSWORD_FILE is not set in .env" >&2
    exit 1
fi
export RESTIC_PASSWORD="${RESTIC_PASSWORD:-}"
[ -n "${RESTIC_PASSWORD_FILE:-}" ] && export RESTIC_PASSWORD_FILE

if ! command -v restic >/dev/null 2>&1; then
    echo "Error: restic is not installed" >&2
    exit 1
fi

# Keep logging best effort: a failed log write must not hide a backup problem.
if ! { mkdir -p "$(dirname "$LOG_FILE")" && touch "$LOG_FILE"; } 2>/dev/null; then
    LOG_FILE=""
fi

if [ ! -d "$BACKUP_DEST_NFS" ]; then
    log "FAIL backup destination $BACKUP_DEST_NFS is not a directory (NFS not mounted?)"
    notify "Restic restore test FAILED" "rotating_light" "high" \
        "Backup destination $BACKUP_DEST_NFS is not a directory (NFS not mounted?)"
    exit 1
fi

TMPROOT=$(mktemp -d "$TMPDIR_BASE/restore-test-XXXXXX") || exit 1

mapfile -t REPOS < <(discover_repos)

if [ "${#REPO_FILTER[@]}" -gt 0 ]; then
    FILTERED=()
    for want in "${REPO_FILTER[@]}"; do
        found=0
        for have in "${REPOS[@]}"; do
            if [ "$want" == "$have" ]; then
                FILTERED+=("$want")
                found=1
                break
            fi
        done
        if [ "$found" -eq 0 ]; then
            log "FAIL no restic repository named '$want' under $BACKUP_DEST_NFS"
            FAILURES=$((FAILURES + 1))
            SUMMARY+=("FAIL $want: no such repository")
        fi
    done
    REPOS=("${FILTERED[@]}")
fi

if [ "${#REPOS[@]}" -eq 0 ] && [ "$FAILURES" -eq 0 ]; then
    log "FAIL no restic repositories found under $BACKUP_DEST_NFS"
    notify "Restic restore test FAILED" "rotating_light" "high" \
        "No restic repositories found under $BACKUP_DEST_NFS"
    exit 1
fi

log "Starting restore test for ${#REPOS[@]} repositories (max snapshot age ${MAX_AGE_DAYS}d)"

for name in "${REPOS[@]}"; do
    test_repo "$name"
done

# Summary
if [ "$FAILURES" -eq 0 ]; then
    TITLE="Restic restore test OK (${#REPOS[@]} repos)"
    TAGS="white_check_mark"
    PRIORITY="default"
else
    TITLE="Restic restore test FAILED ($FAILURES problems)"
    TAGS="rotating_light"
    PRIORITY="high"
fi

BODY=$(printf '%s\n' "${SUMMARY[@]}")
log "$TITLE"

notify "$TITLE" "$TAGS" "$PRIORITY" "$BODY" || FAILURES=$((FAILURES + 1))

[ "$FAILURES" -eq 0 ] || exit 1
exit 0
