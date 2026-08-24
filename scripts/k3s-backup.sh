#!/bin/bash
# K3s control-plane mentés a pve backup HDD-jére.
#
# A cluster a másik helyszínen fut és semmilyen mentés nem védte (ld. a
# 2026-08-24-i auditot). A teljes cluster-állapot egyetlen sqlite fájlban van a
# masteren: /var/lib/rancher/k3s/server/db/state.db. Ha az a lemez meghal, a
# visszaállítás ma lehetetlen - csak újratelepítés.
#
# Ez a script a 109-en (claude-mgmt) fut, mert csak neki van egyszerre SSH
# kulcsa a k3s node-okhoz ÉS a pve-hez. A pve eléri a node-okat Tailscale-en,
# de nincs rajta authorized_key - szándékosan nem adtunk neki újat.
#
# Az adat sehol nem áll meg a 109 kis lemezén: a tar közvetlenül átfolyik a
# pve-re. A cél a backup-hdd, ugyanaz a lemez, ahova a vzdump ír.
#
# Miért van titkosítva:
#   Az archívum a cluster CA privát kulcsait és a node join tokent tartalmazza.
#   A /mnt/storage egyszerre Samba-megosztás ([Storage]) ÉS NFS-export a teljes
#   192.168.0.0/24-re, rw + no_root_squash opciókkal. A no_root_squash miatt a
#   fájljogok önmagukban NEM védenek: a LAN bármely gépén a root a szerveren is
#   rootként ír-olvas. Ezért a tartalom titkosítva megy ki, gpg AES256-tal.
#
#   A jelszó: /root/.secrets/k3s-backup-passphrase a 109-en. HA EZ ELVÉSZ, A
#   MENTÉS VISSZAFEJTHETETLEN. A 109-et a napi vzdump menti, tehát a jelszó
#   onnan visszanyerhető - de tedd be Vaultwardenbe is, mert ha a homelab
#   egyben vész el, mindkét példány vele megy.
#
# Miért VACUUM INTO és nem sima cp:
#   - élő adatbázison konzisztens másolatot ad (olvasó tranzakció, WAL mellett
#     az írók nem blokkolódnak), tehát nem kell leállítani a k3s-t
#   - tömörít is: 2026-08-24-én 3.4 GB -> 623 MB, mert a fájl 82%-a szabad lap
#   - 2.3 másodperc alatt lefut
#
# Mit ment:
#   - state.db (VACUUM INTO másolat)      = a teljes cluster-állapot
#   - tls/, cred/, token, node-token      = enélkül a visszaállított DB-hez nem
#                                           lehet csatlakozni, a node-ok nem
#                                           tudnak visszajoinolni
#   - manifests/                          = a k3s bundled addon manifestjei
#   - a systemd unit + env fájlok         = itt lakik a --node-ip és a K3S_URL
#   - kubectl YAML export                 = ember által olvasható tartalék, és
#                                           ez az, amiből újra lehet építeni
#                                           ahelyett hogy visszaállítanánk
#
# Visszaállítás (nem automatizált, szándékosan):
#   0. kicsomagolás:
#      gpg --decrypt --passphrase-file /root/.secrets/k3s-backup-passphrase \
#          k3s-control-plane-<TS>.tar.gz.gpg | tar xzf - -C /valahova
#   1. systemctl stop k3s a masteren
#   2. a state.db a helyére, a tls/ és cred/ a helyére
#   3. systemctl start k3s
#   4. a workereken systemctl restart k3s-agent
#
# Használat:
#   ./k3s-backup.sh              # mentés + ntfy értesítés
#   ./k3s-backup.sh --no-ntfy    # értesítés nélkül (kézi futtatáshoz)

set -uo pipefail

# A cron PATH-ában nincs /usr/local/bin, a kubectl viszont ott lakik. Ez a
# homelabban már három jobot megölt csendben, ezért itt explicit. Ellenőrzés:
#   env -i PATH=/usr/bin:/bin HOME=/root bash -c 'which kubectl'
PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

MASTER="${K3S_BACKUP_MASTER:-nex@opt5060-i5}"
PVE="${K3S_BACKUP_PVE:-root@192.168.0.109}"
DEST_DIR="${K3S_BACKUP_DEST:-/mnt/storage/backup/k3s}"
KEEP="${K3S_BACKUP_KEEP:-7}"
STAGE="/tmp/k3s-backup-staging"
PASSFILE="${K3S_BACKUP_PASSFILE:-/root/.secrets/k3s-backup-passphrase}"

NTFY_URL="https://ntfy.lan/homelab-digest"
NTFY_RESOLVE="--resolve ntfy.lan:443:192.168.0.208 -k"
SEND_NTFY=1
[ "${1:-}" = "--no-ntfy" ] && SEND_NTFY=0

TS="$(date +%Y-%m-%d_%H-%M-%S)"
ARCHIVE="$DEST_DIR/k3s-control-plane-$TS.tar.gz.gpg"
EXPORT="$DEST_DIR/k3s-resources-$TS.yaml.gz.gpg"

ERRORS=()
fail() { ERRORS+=("$1"); echo "HIBA: $1" >&2; }

# Ha nincs jelszó, nem készítünk titkosítatlan mentést "legalább valami" alapon -
# az pont a megosztott lemezre tenné ki a CA kulcsokat.
if [ ! -s "$PASSFILE" ]; then
    echo "HIBA: a jelszófájl hiányzik vagy üres: $PASSFILE" >&2
    exit 1
fi
GPG=(gpg --batch --quiet --yes --symmetric --cipher-algo AES256
     --passphrase-file "$PASSFILE")

# A staging könyvtárat akkor is takarítjuk, ha félúton elszállunk - különben egy
# 623 MB-os másolat marad a master /tmp-jében minden hibás futás után.
cleanup() { ssh -o ConnectTimeout=10 "$MASTER" "sudo rm -rf $STAGE" >/dev/null 2>&1; }
trap cleanup EXIT

echo "== 1/5 staging összeállítása a masteren =="
ssh -o ConnectTimeout=15 "$MASTER" 'bash -s' <<'REMOTE' 2>&1 | sed 's/^/  /'
set -e
STAGE=/tmp/k3s-backup-staging
SRV=/var/lib/rancher/k3s/server
sudo rm -rf "$STAGE"
sudo mkdir -p "$STAGE"

# Élő adatbázisról konzisztens, tömörített másolat. A k3s fut közben.
sudo python3 -c "
import sqlite3
c = sqlite3.connect('$SRV/db/state.db')
c.execute(\"VACUUM INTO '$STAGE/state.db'\")
c.close()
"

# A másolat épségét itt ellenőrizzük, nem a visszaállításkor.
sudo python3 -c "
import sqlite3, sys
c = sqlite3.connect('$STAGE/state.db')
r = c.execute('PRAGMA integrity_check').fetchone()[0]
n = c.execute('SELECT count(*) FROM kine').fetchone()[0]
c.close()
if r != 'ok':
    sys.exit('integrity_check: ' + r)
print('integrity_check: ok, kine sorok: %d' % n)
"

sudo cp -a "$SRV/tls" "$SRV/cred" "$SRV/manifests" "$STAGE/"
sudo cp -a "$SRV/token" "$SRV/node-token" "$SRV/agent-token" "$STAGE/"
sudo mkdir -p "$STAGE/systemd"
sudo cp -a /etc/systemd/system/k3s.service "$STAGE/systemd/"
sudo du -sh "$STAGE" | sed 's/^/staging méret: /'
REMOTE
[ "${PIPESTATUS[0]}" -ne 0 ] && fail "a staging összeállítása elszállt a masteren"

echo "== 2/5 worker unit fájlok =="
# A workerek env fájljában lakik a K3S_URL és a join token - a master mentése
# ezeket nem tartalmazza, pedig egy újraépítésnél pont ezek kellenek.
for w in opt3060-i3 opt3050-i5; do
    ssh -o ConnectTimeout=15 "nex@$w" \
        "sudo tar czf - -C /etc/systemd/system k3s-agent.service k3s-agent.service.env" \
        2>/dev/null | ssh -o ConnectTimeout=15 "$MASTER" \
        "sudo mkdir -p $STAGE/systemd/$w && sudo tar xzf - -C $STAGE/systemd/$w" \
        || fail "a(z) $w unit fájljai nem jöttek át"
done

echo "== 3/5 átstreamelés a pve-re =="
# A jogokat utólagos chmod-dal állítjuk, nem umask-kal: a cél MergerFS (fuse),
# ami a létrehozáskor 666-ot ad és az umask-ot figyelmen kívül hagyja. A chmod
# viszont működik rajta. A rövid ablak, amíg a fájl 666, itt ártalmatlan, mert
# a tartalom már titkosítva érkezik - a chmod itt az integritást védi (hogy a
# LAN-ról ne lehessen felülírni vagy törölni), nem a bizalmasságot.
ssh -o ConnectTimeout=15 "$PVE" "mkdir -p $DEST_DIR && chmod 700 $DEST_DIR" \
    || fail "a célkönyvtár nem hozható létre a pve-n"
if ! ssh -o ConnectTimeout=15 "$MASTER" "sudo tar czf - -C /tmp k3s-backup-staging" \
     | "${GPG[@]}" \
     | ssh -o ConnectTimeout=15 "$PVE" "cat > $ARCHIVE && chmod 600 $ARCHIVE"; then
    fail "az átvitel vagy a titkosítás megszakadt"
fi

echo "== 4/5 az átvitt archívum visszafejtése és ellenőrzése =="
# Ez a lépés a lényeg: nem azt nézzük, hogy létrejött-e egy fájl, hanem hogy a
# meglévő jelszóval VISSZAFEJTHETŐ-e és a tar végigolvasható-e benne. Egy
# titkosított mentés, amit nem lehet visszafejteni, rosszabb a semminél, mert
# azt hiszed, van mentésed. A visszafejtés a 109-en fut, nem a pve-n, mert a
# jelszó itt van - a pve sose látja.
if ssh -o ConnectTimeout=15 "$PVE" "cat $ARCHIVE" \
     | gpg --batch --quiet --decrypt --passphrase-file "$PASSFILE" 2>/dev/null \
     | tar tzf - 2>/dev/null | grep -q 'k3s-backup-staging/state.db'; then
    SIZE="$(ssh -o ConnectTimeout=15 "$PVE" "du -h $ARCHIVE | cut -f1")"
    echo "  visszafejtés OK, a state.db benne van, méret: $SIZE"
else
    fail "az archívum nem fejthető vissza vagy hiányos - NINCS HASZNÁLHATÓ MENTÉS"
    SIZE="?"
fi

echo "== 5/5 kubectl export + régiek takarítása =="
# Ez az, amiből újra lehet ÉPÍTENI, nem visszaállítani. Kicsi, és pont az a
# nézet, ami egy IaC-átálláskor kell.
# A Secretek is benne vannak, tehát ez is titkosítva megy.
if kubectl get all,cm,secret,pvc,pv,ingress,sc,crd -A -o yaml 2>/dev/null | gzip \
     | "${GPG[@]}" \
     | ssh -o ConnectTimeout=15 "$PVE" "cat > $EXPORT && chmod 600 $EXPORT"; then
    echo "  kubectl export kész"
else
    fail "a kubectl export nem sikerült"
fi

# A vzdump retenciója ide nem ér el (ez nem guest-mentés), ezért itt magunk
# takarítunk. Csak a saját névmintánkra illeszkedő fájlokat.
ssh -o ConnectTimeout=15 "$PVE" "
    ls -1t $DEST_DIR/k3s-control-plane-*.tar.gz.gpg 2>/dev/null | tail -n +\$(($KEEP+1)) | xargs -r rm -f
    ls -1t $DEST_DIR/k3s-resources-*.yaml.gz.gpg 2>/dev/null | tail -n +\$(($KEEP+1)) | xargs -r rm -f
" || fail "a régi mentések takarítása nem sikerült"

COUNT="$(ssh -o ConnectTimeout=15 "$PVE" "ls -1 $DEST_DIR/k3s-control-plane-*.tar.gz.gpg 2>/dev/null | wc -l")"

# Egy hibás futás ne hagyjon maga után fájlt. Enélkül egy megszakadt átvitel
# 70 bájtos "archívumot" hagy a célban, ami beleszámít a retencióba, és néhány
# hibás nap után kiszorítja az utolsó jó mentést is. Mérve: 2026-08-24.
if [ ${#ERRORS[@]} -ne 0 ]; then
    ssh -o ConnectTimeout=15 "$PVE" "rm -f $ARCHIVE $EXPORT" >/dev/null 2>&1
    echo "  a futás hibás volt, a részleges fájlok törölve a célból"
fi

if [ ${#ERRORS[@]} -eq 0 ]; then
    TITLE="K3s mentés OK"
    BODY="Archívum: $SIZE, megőrzött mentések: $COUNT, cél: $PVE:$DEST_DIR"
    RC=0
else
    TITLE="K3s mentés HIBA"
    BODY="$(printf '%s\n' "${ERRORS[@]}")"
    RC=1
fi

echo
echo "$TITLE - $BODY"
[ "$SEND_NTFY" -eq 1 ] && curl -s $NTFY_RESOLVE -H "Title: $TITLE" -d "$BODY" "$NTFY_URL" >/dev/null

exit $RC
