#!/bin/bash
# Reggeli homelab állapot-összefoglaló - ntfy-ra küldi.
# Determinisztikus adatgyűjtés, nem igényel LLM-et (ld. private/todo.md 7. pont).
set -uo pipefail

PVE=192.168.0.109
DOCKER_HOST=192.168.0.110
# ntfy.lan proxyol a Caddyn (192.168.0.208) át; ez a gép nem AdGuard DNS-t
# használ, ezért --resolve-lal kötjük a hostname-et a Caddy IP-hez (SNI-t
# így is helyesen küldi curl, csak a rendszer-DNS-t kerüljük meg).
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

# --- Backups (last vzdump run today?) ---
today=$(date +%Y_%m_%d)
backup_count=$(pve "ls /mnt/storage/backup/proxmox/dump/ 2>/dev/null | grep -c '$today'")
if [[ "${backup_count:-0}" -eq 0 ]]; then
    lines+=("⚠️ Nincs mai vzdump backup")
    warn=1
else
    lines+=("Backup: ma lefutott ($backup_count fájl)")
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

# --- Uptime ---
up=$(pve "uptime -p" 2>/dev/null)
lines+=("pve uptime: $up")

title="Homelab digest $(date +%Y-%m-%d)"
[[ "$warn" -eq 1 ]] && title="⚠️ $title - figyelmeztetés"
body=$(printf '%s\n' "${lines[@]}")

curl -s $NTFY_RESOLVE -H "Title: $title" -d "$body" "$NTFY_URL" >/dev/null
