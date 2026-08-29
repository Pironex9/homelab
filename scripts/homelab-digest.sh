#!/bin/bash
# Morning homelab status summary - sent to ntfy.
# Deterministic data collection, needs no LLM (see private/todo.md, point 7).
set -uo pipefail

PVE=192.168.0.109
DOCKER_HOST=192.168.0.110
# ntfy.lan is proxied through Caddy (192.168.0.208); this machine does not use AdGuard
# DNS, so we bind the hostname to the Caddy IP with --resolve (curl still sends the
# SNI correctly, we only bypass the system DNS).
NTFY_URL="https://ntfy.lan/homelab-digest"
NTFY_RESOLVE="--resolve ntfy.lan:443:192.168.0.208 -k"

pve() { ssh -o ConnectTimeout=10 "root@$PVE" "$@"; }
dock() { ssh -o ConnectTimeout=10 "root@$DOCKER_HOST" "$@"; }

lines=()
warn=0

# --- Storage ---
storage=$(pve pvesm status 2>/dev/null)
lvm_pct=$(pve lvs --noheadings -o data_percent pve/data 2>/dev/null | tr -d ' %')
if [[ -n "${lvm_pct:-}" ]]; then
    lvm_int=${lvm_pct%.*}
    flag=""
    [[ "$lvm_int" -ge 80 ]] && { flag=" ⚠️"; warn=1; }
    lines+=("LVM thin pool (pve/data): ${lvm_pct}%${flag}")
fi
backup_pct=$(echo "$storage" | awk '/backup-hdd/{print $NF}')
[[ -n "$backup_pct" ]] && lines+=("backup-hdd storage: ${backup_pct}")

# --- LXC/VM status ---
down_lxc=$(pve "pct list" 2>/dev/null | awk 'NR>1 && $2!="running"{print $4"("$2")"}')
down_vm=$(pve "qm list" 2>/dev/null | awk 'NR>1 && $3!="running"{print $2"("$3")"}')
down=$(printf '%s\n%s\n' "$down_lxc" "$down_vm" | sed '/^$/d' | tr '\n' ' ')
if [[ -n "$down" ]]; then
    lines+=("⚠️ Nem fut: $down")
    warn=1
else
    lines+=("LXC/VM: mind fut")
fi

# --- Backups (did every guest get backed up today?) ---
today=$(date +%Y_%m_%d)
# The vmid list of the vzdump job = what should have been backed up today. Only the
# archive counts as success (.tar.zst for LXC, .vma.zst for VM); a failed run leaves a
# .log too, so a bare file count would show green even with guests missing.
want=$(pve "grep -h vmid /etc/pve/jobs.cfg 2>/dev/null | tr -d ' \t' | sed 's/^vmid//' | tr ',' '\n' | sed '/^\$/d' | sort -un")
have=$(pve "ls /mnt/storage/backup/proxmox/dump/ 2>/dev/null | grep '$today' | grep -E '\.(tar|vma)\.zst\$' | grep -oE 'vzdump-(lxc|qemu)-[0-9]+' | grep -oE '[0-9]+\$' | sort -un")

if [[ -z "$want" ]]; then
    # No readable vmid list - fall back to the "did anything run today" check.
    if [[ -z "$have" ]]; then
        lines+=("⚠️ Nincs mai vzdump backup")
        warn=1
    else
        lines+=("Backup: ma lefutott ($(echo "$have" | wc -w) guest)")
    fi
else
    missing=""
    done_n=0
    for id in $want; do
        if grep -qx "$id" <<<"$have"; then
            done_n=$((done_n + 1))
        else
            missing+="$id "
        fi
    done
    lines+=("Backup: $done_n/$(echo "$want" | wc -w) guest ma lementve")
    if [[ -n "$missing" ]]; then
        lines+=("⚠️ Backup hiányzik: ${missing% }")
        warn=1
    fi
fi

# --- Restic (is the host-config repo fresh?) ---
# Weekly backup (Sunday 04:00), hence the 8 day threshold: one missed run still fits,
# two do not. --no-lock so it never collides with the backup or with the Sunday
# restore test - this only reads.
restic_out=$(pve "RESTIC_PASSWORD_FILE=/root/.secrets/restic-password timeout 60 restic -r /mnt/disk1/backup/proxmox-host snapshots --latest 1 --no-lock 2>/dev/null")
restic_dt=$(echo "$restic_out" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}' | tail -1)
if [[ -z "$restic_dt" ]]; then
    lines+=("⚠️ Restic: nem olvasható a repo")
    warn=1
else
    restic_age=$(( ( $(date +%s) - $(date -d "$restic_dt" +%s) ) / 86400 ))
    if [[ "$restic_age" -gt 8 ]]; then
        lines+=("⚠️ Restic: a legutolsó snapshot ${restic_age} napos")
        warn=1
    else
        lines+=("Restic: friss (${restic_age} napos snapshot)")
    fi
fi

# --- SnapRAID ---
snap_status=$(pve "timeout 60 snapraid status 2>&1")
if echo "$snap_status" | grep -q "not fully synced\|NOT fully synced"; then
    lines+=("⚠️ SnapRAID: nincs teljesen szinkronban")
    warn=1
else
    lines+=("SnapRAID: szinkronban")
fi
stale_days=$(echo "$snap_status" | grep -oP 'oldest block was scrubbed \K[0-9]+' || true)
[[ -n "$stale_days" && "$stale_days" -gt 30 ]] && lines+=("⚠️ SnapRAID: legrégebbi scrub $stale_days napja (>30)")

snap_smart=$(pve "timeout 30 snapraid smart 2>&1")
fail_prob=$(echo "$snap_smart" | grep -oP 'least one disk.*?\K[0-9]+(?=%)' || true)
if [[ -n "$fail_prob" && "$fail_prob" -ge 50 ]]; then
    lines+=("🔴 SnapRAID SMART: ${fail_prob}% esély lemezhibára 1 éven belül!")
    warn=1
fi

# --- Docker health (LXC 100) ---
bad=$(dock "docker ps -a --format '{{.Names}}|{{.Status}}'" 2>/dev/null | awk -F'|' '$2 !~ /^Up/ && $2 !~ /^Exited \(0\)/')
if [[ -n "$bad" ]]; then
    lines+=("⚠️ Docker konténer probléma: $bad")
    warn=1
else
    lines+=("Docker (LXC 100): minden konténer OK")
fi

# --- Vaultwarden version (LXC 103) ---
# The password manager deliberately does NOT update itself: an unattended apk upgrade
# would fail on exactly the machine that holds every other credential, and would lock
# you out at exactly the moment you need access.
# What was missing so far was not the upgrade but the noticing: on 2026-08-28 the
# server was on 1.37.0 while the release notes of 1.37.2 state that it is mandatory
# for 2026.8.0+ clients. This kind of lag does not show up here but on a client, as
# "An error has occurred", which says nothing about the server version - hence this check.
#
# It reports TWO SEPARATE things, because the action differs:
#
#   VW=  package lag. The container release and the repo are the same, so
#        `apk upgrade` is a plain patch-level operation.
#   REL= `alpine-release` is lagging as well, meaning `latest-stable` has rolled over
#        to the next Alpine release. In that case the same `apk upgrade` IS ALREADY A
#        RELEASE JUMP, and it needs a backup and a maintenance window. That was the
#        situation on 2026-08-28, only nobody saw it at the time.
#
# `apk update` only refreshes the index cache in the container, it installs no
# packages. Its result is on a separate OK/FAIL line because without it a broken DNS
# (a known failure mode on these LXCs) would return an empty list and the block would
# report "up to date" while actually being blind.
vw_out=$(pve "pct exec 103 -- sh -c '
    if apk update >/dev/null 2>&1; then echo RC=OK; else echo RC=FAIL; fi
    apk list -I vaultwarden 2>/dev/null | cut -d\" \" -f1 | sed \"s/^/INST=/\"
    apk version -l \"<\" 2>/dev/null | grep \"^alpine-release\" | tr -s \" \" | sed \"s/ *\$//; s|^|REL=|\"
    apk version -l \"<\" 2>/dev/null | grep \"^vaultwarden\" | tr -s \" \" | sed \"s/ *\$//; s|^|VW=|\"
'" 2>/dev/null)

vw_rc=$(sed -n 's/^RC=//p' <<<"$vw_out")
vw_inst=$(sed -n 's/^INST=//p' <<<"$vw_out")
vw_rel=$(sed -n 's/^REL=//p' <<<"$vw_out")
vw_old=$(sed -n 's/^VW=//p' <<<"$vw_out")

if [[ "$vw_rc" != "OK" || -z "$vw_inst" ]]; then
    lines+=("⚠️ Vaultwarden: nem kérdezhető le a verzió (LXC 103)")
    warn=1
else
    if [[ -n "$vw_old" ]]; then
        lines+=("⚠️ Vaultwarden frissítés vár (LXC 103):")
        while IFS= read -r l; do lines+=("    $l"); done <<<"$vw_old"
        warn=1
    else
        lines+=("Vaultwarden: naprakész (${vw_inst#vaultwarden-})")
    fi
    # A separate line, and shown even if vaultwarden happens to be up to date: the
    # release jump makes the next apk upgrade dangerous regardless of whether there is
    # anything to upgrade right now.
    if [[ -n "$vw_rel" ]]; then
        lines+=("⚠️ LXC 103: az Alpine latest-stable átbillent ($vw_rel)")
        lines+=("    a következő apk upgrade KIADÁSUGRÁS - mentés + ablak kell")
        lines+=("    eljárás: docs/proxmox/09_Vaultwarden.md, Updating")
        warn=1
    fi
fi

# --- Uptime ---
up=$(pve "uptime -p" 2>/dev/null)
lines+=("pve uptime: $up")

title="Homelab digest $(date +%Y-%m-%d)"
[[ "$warn" -eq 1 ]] && title="⚠️ $title - figyelmeztetés"
body=$(printf '%s\n' "${lines[@]}")

curl -s $NTFY_RESOLVE -H "Title: $title" -d "$body" "$NTFY_URL" >/dev/null
