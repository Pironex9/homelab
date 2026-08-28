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

# --- Backups (ma minden guest lement?) ---
today=$(date +%Y_%m_%d)
# A vzdump job vmid listája = amit ma le kellett volna menteni. Sikert csak az
# archívum jelent (.tar.zst LXC-nél, .vma.zst VM-nél); hibás futás is hagy .log-ot,
# ezért a puszta fájlszám zöldet mutatna kiesett guestek mellett is.
want=$(pve "grep -h vmid /etc/pve/jobs.cfg 2>/dev/null | tr -d ' \t' | sed 's/^vmid//' | tr ',' '\n' | sed '/^\$/d' | sort -un")
have=$(pve "ls /mnt/storage/backup/proxmox/dump/ 2>/dev/null | grep '$today' | grep -E '\.(tar|vma)\.zst\$' | grep -oE 'vzdump-(lxc|qemu)-[0-9]+' | grep -oE '[0-9]+\$' | sort -un")

if [[ -z "$want" ]]; then
    # Nincs kiolvasható vmid lista - visszaesünk a "futott-e ma bármi" ellenőrzésre.
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

# --- Restic (a host-config repo friss-e?) ---
# Heti mentés (vasárnap 04:00), ezért 8 nap a küszöb: egy kihagyott futás még
# belefér, kettő már nem. --no-lock, hogy sose ütközzön a mentéssel vagy a
# vasárnapi restore-teszttel - ez csak olvas.
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

# --- Vaultwarden verzió (LXC 103) ---
# A jelszókezelő szándékosan NEM frissül magától: egy felügyelet nélküli
# apk upgrade pont azon a gépen hibázna, ami az összes többi hitelesítő adatot
# tartja, és pont akkor zárna ki mindenből, amikor a hozzáférés kellene.
# Ami eddig hiányzott, az nem a frissítés volt, hanem az észrevétel:
# 2026-08-28-án a szerver 1.37.0-n állt, miközben az 1.37.2 kiadási jegyzete
# kimondja, hogy a 2026.8.0+ kliensekhez kötelező. Ez a fajta elmaradás nem itt
# jelentkezik, hanem egy kliensen, "An error has occurred" formájában, ami
# semmit nem árul el a szerver verziójáról - ezért kell ide.
#
# Az `apk update` csak az index-cache-t frissíti a containerben, csomagot nem
# telepít. A kimenete azért van külön OK/FAIL sorban, mert nélküle egy megszakadt
# DNS (ismert hibamód ezeken az LXC-ken) üres listát adna, és a blokk
# "naprakész"-t jelentene, miközben valójában vak.
vw_out=$(pve "pct exec 103 -- sh -c '
    if apk update >/dev/null 2>&1; then echo OK; else echo FAIL; fi
    apk list -I vaultwarden 2>/dev/null | cut -d\" \" -f1
    apk version -l \"<\" 2>/dev/null | grep \"^vaultwarden\" | tr -s \" \" | sed \"s/ *\$//\"
'" 2>/dev/null)

vw_rc=$(echo "$vw_out" | sed -n 1p)
vw_inst=$(echo "$vw_out" | sed -n 2p)
vw_old=$(echo "$vw_out" | tail -n +3 | sed '/^$/d')

if [[ "$vw_rc" != "OK" || -z "$vw_inst" ]]; then
    lines+=("⚠️ Vaultwarden: nem kérdezhető le a verzió (LXC 103)")
    warn=1
elif [[ -n "$vw_old" ]]; then
    lines+=("⚠️ Vaultwarden frissítés vár (LXC 103):")
    while IFS= read -r l; do lines+=("    $l"); done <<<"$vw_old"
    warn=1
else
    lines+=("Vaultwarden: naprakész (${vw_inst#vaultwarden-})")
fi

# --- Uptime ---
up=$(pve "uptime -p" 2>/dev/null)
lines+=("pve uptime: $up")

title="Homelab digest $(date +%Y-%m-%d)"
[[ "$warn" -eq 1 ]] && title="⚠️ $title - figyelmeztetés"
body=$(printf '%s\n' "${lines[@]}")

curl -s $NTFY_RESOLVE -H "Title: $title" -d "$body" "$NTFY_URL" >/dev/null
