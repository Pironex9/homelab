#!/bin/bash
# K3s control-plane backup onto the pve backup HDD.
#
# The cluster runs at the other site and was protected by no backup at all (see the
# 2026-08-24 audit). Its entire cluster state is in a single sqlite file on the
# master: /var/lib/rancher/k3s/server/db/state.db. If that disk dies, a restore is
# impossible today - only a reinstall.
#
# This script runs on 109 (claude-mgmt), because only it holds an SSH key for the k3s
# nodes AND for pve at the same time. pve reaches the nodes over Tailscale, but it has
# no authorized_key there - deliberately, we did not give it a new one.
#
# The data never lands on 109's small disk: the tar streams straight through to pve.
# The target is backup-hdd, the same disk vzdump writes to.
#
# Why it is encrypted:
#   The archive contains the cluster CA private keys and the node join token.
#   /mnt/storage is at once a Samba share ([Storage]) AND an NFS export to the whole
#   192.168.0.0/24, with rw + no_root_squash. Because of no_root_squash the file
#   permissions alone do NOT protect it: root on any LAN machine is root on the server
#   too. So the content goes out encrypted, with gpg AES256.
#
#   The passphrase: /root/.secrets/k3s-backup-passphrase on 109. IF THIS IS LOST, THE
#   BACKUP CANNOT BE DECRYPTED. 109 is backed up by the daily vzdump, so the
#   passphrase is recoverable from there - but put it in Vaultwarden as well, because
#   if the homelab is lost as a whole, both copies go with it.
#
# Why VACUUM INTO and not a plain cp:
#   - it gives a consistent copy of a live database (a read transaction; with WAL the
#     writers are not blocked), so k3s does not have to be stopped
#   - it also compacts: on 2026-08-24 3.4 GB -> 623 MB, because 82% of the file was
#     free pages
#   - it completes in 2.3 seconds
#
# What it backs up:
#   - state.db (VACUUM INTO copy)         = the complete cluster state
#   - tls/, cred/, token, node-token      = without these the restored DB cannot be
#                                           connected to and the nodes cannot rejoin
#   - manifests/                          = the manifests of the k3s bundled addons
#   - the systemd unit + env files        = this is where --node-ip and K3S_URL live
#   - kubectl YAML export                 = a human-readable fallback, and the thing
#                                           you can rebuild from instead of
#                                           restoring
#
# Restore (not automated, deliberately):
#   0. unpack:
#      gpg --decrypt --passphrase-file /root/.secrets/k3s-backup-passphrase \
#          k3s-control-plane-<TS>.tar.gz.gpg | tar xzf - -C /somewhere
#   1. systemctl stop k3s on the master
#   2. state.db back into place, tls/ and cred/ back into place
#   3. systemctl start k3s
#   4. systemctl restart k3s-agent on the workers
#
# Usage:
#   ./k3s-backup.sh              # backup + ntfy notification
#   ./k3s-backup.sh --no-ntfy    # without a notification (for manual runs)

set -uo pipefail

# The cron PATH does not contain /usr/local/bin, and kubectl lives there. That has
# already killed three jobs silently in this homelab, hence it is explicit here.
# Check with: env -i PATH=/usr/bin:/bin HOME=/root bash -c 'which kubectl'
PATH="/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

MASTER="${K3S_BACKUP_MASTER:-nex@opt5060-i5}"
PVE="${K3S_BACKUP_PVE:-root@192.168.0.109}"
DEST_DIR="${K3S_BACKUP_DEST:-/mnt/storage/backup/k3s}"
KEEP="${K3S_BACKUP_KEEP:-30}"
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

# If there is no passphrase, we do not produce an unencrypted backup on a "at least
# something" basis - that would put the CA keys onto the shared disk.
if [ ! -s "$PASSFILE" ]; then
    echo "HIBA: a jelszófájl hiányzik vagy üres: $PASSFILE" >&2
    exit 1
fi
GPG=(gpg --batch --quiet --yes --symmetric --cipher-algo AES256
     --passphrase-file "$PASSFILE")

# The staging directory is cleaned up even if we fail halfway - otherwise a 623 MB
# copy would be left in the master's /tmp after every failed run.
cleanup() { ssh -o ConnectTimeout=10 "$MASTER" "sudo rm -rf $STAGE" >/dev/null 2>&1; }
trap cleanup EXIT

echo "== 1/5 staging összeállítása a masteren =="
ssh -o ConnectTimeout=15 "$MASTER" 'bash -s' <<'REMOTE' 2>&1 | sed 's/^/  /'
set -e
STAGE=/tmp/k3s-backup-staging
SRV=/var/lib/rancher/k3s/server
sudo rm -rf "$STAGE"
sudo mkdir -p "$STAGE"

# A consistent, compacted copy of a live database. k3s keeps running meanwhile.
sudo python3 -c "
import sqlite3
c = sqlite3.connect('$SRV/db/state.db')
c.execute(\"VACUUM INTO '$STAGE/state.db'\")
c.close()
"

# The integrity of the copy is checked here, not at restore time.
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
# K3S_URL and the join token live in the workers' env file - the master's backup does
# not contain those, and a rebuild needs exactly them.
for w in opt3060-i3 opt3050-i5; do
    ssh -o ConnectTimeout=15 "nex@$w" \
        "sudo tar czf - -C /etc/systemd/system k3s-agent.service k3s-agent.service.env" \
        2>/dev/null | ssh -o ConnectTimeout=15 "$MASTER" \
        "sudo mkdir -p $STAGE/systemd/$w && sudo tar xzf - -C $STAGE/systemd/$w" \
        || fail "a(z) $w unit fájljai nem jöttek át"
done

echo "== 3/5 átstreamelés a pve-re =="
# The permissions are set with an explicit chmod, not with umask: the target is
# MergerFS (fuse), which creates files as 666 and ignores the umask. chmod does work
# on it. The short window while the file is 666 is harmless here, because the content
# arrives already encrypted - chmod protects integrity here (so it cannot be
# overwritten or deleted from the LAN), not confidentiality.
ssh -o ConnectTimeout=15 "$PVE" "mkdir -p $DEST_DIR && chmod 700 $DEST_DIR" \
    || fail "a célkönyvtár nem hozható létre a pve-n"
if ! ssh -o ConnectTimeout=15 "$MASTER" "sudo tar czf - -C /tmp k3s-backup-staging" \
     | "${GPG[@]}" \
     | ssh -o ConnectTimeout=15 "$PVE" "cat > $ARCHIVE && chmod 600 $ARCHIVE"; then
    fail "az átvitel vagy a titkosítás megszakadt"
fi

echo "== 4/5 az átvitt archívum visszafejtése és ellenőrzése =="
# This step is the point: we do not check that a file was created, but that it CAN BE
# DECRYPTED with the existing passphrase and that the tar inside it reads end to end.
# An encrypted backup that cannot be decrypted is worse than none, because you believe
# you have a backup. The decryption runs on 109, not on pve, because the passphrase is
# here - pve never sees it.
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
# This is what you can REBUILD from, not restore. It is small, and it is exactly the
# view you need during a move to IaC.
# The Secrets are in it too, so this goes out encrypted as well.
if kubectl get all,cm,secret,pvc,pv,ingress,sc,crd -A -o yaml 2>/dev/null | gzip \
     | "${GPG[@]}" \
     | ssh -o ConnectTimeout=15 "$PVE" "cat > $EXPORT && chmod 600 $EXPORT"; then
    echo "  kubectl export kész"
else
    fail "a kubectl export nem sikerült"
fi

# The vzdump retention does not reach here (this is not a guest backup), so we do the
# cleanup ourselves. Only files matching our own name pattern.
ssh -o ConnectTimeout=15 "$PVE" "
    ls -1t $DEST_DIR/k3s-control-plane-*.tar.gz.gpg 2>/dev/null | tail -n +\$(($KEEP+1)) | xargs -r rm -f
    ls -1t $DEST_DIR/k3s-resources-*.yaml.gz.gpg 2>/dev/null | tail -n +\$(($KEEP+1)) | xargs -r rm -f
" || fail "a régi mentések takarítása nem sikerült"

COUNT="$(ssh -o ConnectTimeout=15 "$PVE" "ls -1 $DEST_DIR/k3s-control-plane-*.tar.gz.gpg 2>/dev/null | wc -l")"

# A failed run must not leave a file behind. Without this an interrupted transfer
# leaves a 70 byte "archive" at the target, which counts towards retention, and after
# a few bad days it would push out even the last good backup. Measured: 2026-08-24.
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
