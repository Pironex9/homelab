#!/bin/bash
# K3s control-plane backup restore test - into a throwaway cluster.
#
# Runs on 109 (claude-mgmt), because the gpg passphrase is here and pve never sees it.
#
# WHY IT IS NEEDED WHEN k3s-backup.sh ALREADY VERIFIES:
#   That one proves the archive CAN BE DECRYPTED and that state.db is in the tar
#   listing. Whether a k3s actually comes up from it and the objects inside are
#   reachable is a different question - before 2026-08-28 it had never been measured.
#   A tar that can be unpacked is not yet a backup; a backup is what the cluster comes
#   back from.
#
# WHAT IT DOES:
#   Downloads the most recent archive from pve, decrypts it here, puts state.db and the
#   tls/cred/token set into place, and starts a k3s server with --disable-agent on
#   127.0.0.1:6443. Then it compares against the live cluster: every object created
#   BEFORE THE TIME OF THE BACKUP has to be present on the restored side too. Finally
#   it checks that the content of the Secrets really decodes, not just that the counts
#   match.
#
#   There is no hardcoded list of expectations, and that is not a convenience decision:
#   the first version looked for the six Argo CD Applications by name and reported a
#   failure on the 06:49 backup, because monitoring was only installed at 07:30. The
#   creationTimestamp is the exact threshold; a name list starts lying after every new
#   installation.
#
# WHY --disable-agent:
#   Without it the restored control plane would also become a node, the kubelet would
#   start on it, and it would begin scheduling the pods found in the restored DB -
#   Longhorn, Argo CD, everything. Argo CD would pull the real GitHub that very
#   moment, Longhorn the real Garage S3. Without an agent not a single pod starts, and
#   the proof does not need one: the question is whether the DATA is there, not whether
#   it runs.
#
# THE TWO FINDINGS OF THE FIRST RUN (2026-08-28):
#   1. The six kubeconfigs under cred/ contain ABSOLUTE paths
#      (/var/lib/rancher/k3s/server/tls/...). Restored under a custom --data-dir, k3s
#      does not even start: "unable to read client-cert ... no such file". That is why
#      this script uses the default data-dir, and why the guard is needed.
#   2. The same kubeconfigs also pin the PORT: https://127.0.0.1:6444. k3s derives the
#      apiserver's internal port as --https-listen-port + 1, so with a non-default
#      listen-port the scheduler and the controller-manager call 6444 while the
#      apiserver listens elsewhere: "unable to load configmap based
#      request-header-client-ca-file ... dial tcp 127.0.0.1:6444: connect: connection
#      refused", and k3s stops. That is why this script has no port switch: 6443 is not
#      a matter of taste.
#   3. k3s unpacks its own bundle under /var/lib/rancher/k3s/data (253 MB) even when
#      --data-dir points elsewhere.
#
# WHAT IT TOUCHES:
#   It does NOT touch the live cluster - it only reads it, for comparison. It only
#   reads the archive on pve. On this machine it creates and then deletes:
#   /var/lib/rancher/k3s, /etc/rancher/k3s, /etc/rancher/node, and the work directory.
#
# SECURITY:
#   The unpacked archive contains the cluster CA PRIVATE KEYS and the join token. The
#   work directory is 700, sits on the local disk, and the script deletes it at the end
#   - even if it breaks off (trap). Never set WORK under /mnt/storage: that is an NFS
#   export with no_root_squash to the whole LAN.
#
# ROLLBACK, if it breaks off in a way where even the trap did not run:
#   pkill -f '/tmp/k3s-restore-test/k3s server'
#   rm -rf /var/lib/rancher/k3s /etc/rancher/k3s /etc/rancher/node
#   rm -rf /tmp/k3s-restore-test
#   There is nothing to undo on the live cluster.
#
# Usage:
#   ./k3s-restore-test.sh                       # the most recent archive
#   ./k3s-restore-test.sh k3s-control-plane-2026-08-27_01-30-01.tar.gz.gpg
#   KEEP=1 ./k3s-restore-test.sh                # do not clean up, so you can look around
#
set -uo pipefail

PVE="${K3S_BACKUP_PVE:-root@192.168.0.109}"
DEST_DIR="${K3S_BACKUP_DEST:-/mnt/storage/backup/k3s}"
PASSFILE="${K3S_BACKUP_PASSFILE:-/root/.secrets/k3s-backup-passphrase}"
WORK="${WORK:-/tmp/k3s-restore-test}"
KEEP="${KEEP:-0}"
ARCHIVE="${1:-}"

RC=1
step() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
ok()   { printf '  \033[32mOK\033[0m   %s\n' "$*"; }
bad()  { printf '  \033[31mHIBA\033[0m %s\n' "$*"; FAILED=$((FAILED+1)); }
fail() { printf '\033[31mHIBA: %s\033[0m\n' "$*"; exit 1; }
FAILED=0

CACHE="${CACHE:-/root/.cache/k3s-restore-test}"

cleanup() {
    # The log is saved before the cleanup, otherwise the cleanup would take away the
    # very reason a run failed. It contains no secrets: paths, node names and SANs, no
    # keys.
    [ -s "$WORK/k3s.log" ] && { mkdir -p "$CACHE"; cp "$WORK/k3s.log" "$CACHE/last-run.log"; \
        echo; echo "a k3s teljes logja: $CACHE/last-run.log"; }
    [ "$KEEP" = "1" ] && { echo "KEEP=1, a takarítás kimarad. Kézzel:"; \
        echo "  pkill -f '$WORK/k3s server'"; \
        echo "  rm -rf /var/lib/rancher/k3s /etc/rancher/k3s /etc/rancher/node $WORK"; return; }
    # The pattern must NOT contain the flags: after startup k3s rewrites its own argv,
    # and only "<path>/k3s server" remains in /proc. The first version searched for
    # 'k3s server --disable-agent', never found anything, and two orphaned control
    # planes were left running on their already deleted data directory - and the next
    # run then died on the occupied 6443.
    [ -n "${K3SPID:-}" ] && kill "$K3SPID" 2>/dev/null
    pkill -f "^$WORK/k3s server" >/dev/null 2>&1
    for _ in 1 2 3 4 5 6 7 8 9 10; do
        pgrep -f "^$WORK/k3s server" >/dev/null || break
        sleep 1
    done
    pkill -9 -f "^$WORK/k3s server" >/dev/null 2>&1
    rm -rf /var/lib/rancher/k3s /etc/rancher/k3s /etc/rancher/node "$WORK"
}
trap cleanup EXIT

# --- guards ----------------------------------------------------------------
# This script DELETES under /var/lib/rancher/k3s. On a real k3s node that would be the
# destruction of the cluster, so there it does not start at all.
for u in k3s k3s-agent; do
    systemctl list-unit-files "$u.service" 2>/dev/null | grep -q "^$u.service" \
        && fail "ezen a gépen van $u.service - ez egy éles k3s node, itt nem futhat"
done
[ -e /var/lib/rancher/k3s/server/db/state.db ] \
    && fail "/var/lib/rancher/k3s/server/db/state.db már létezik - előbb nézd meg, mi az"
[ -s "$PASSFILE" ] || fail "a jelszófájl hiányzik vagy üres: $PASSFILE"
# 6443 cannot be swapped out (see point 2 in the header), so if it is occupied we do
# not even try.
ss -tln 2>/dev/null | grep -q ':6443 ' \
    && fail "a 6443-as port foglalt ezen a gépen - a mentés csak ezen a porton állítható vissza"
command -v gpg >/dev/null || fail "nincs gpg"

# --- 1. archive ------------------------------------------------------------
step "1/6 archívum kiválasztása a pve-n"
if [ -z "$ARCHIVE" ]; then
    ARCHIVE=$(ssh -o ConnectTimeout=15 "$PVE" \
        "ls -1t $DEST_DIR/k3s-control-plane-*.tar.gz.gpg 2>/dev/null | head -1")
    [ -n "$ARCHIVE" ] || fail "nincs archívum itt: $PVE:$DEST_DIR"
else
    case "$ARCHIVE" in /*) ;; *) ARCHIVE="$DEST_DIR/$ARCHIVE" ;; esac
fi
echo "  $ARCHIVE"
ssh -o ConnectTimeout=15 "$PVE" "ls -l --time-style=long-iso $ARCHIVE" | sed 's/^/  /'

# --- 2. decryption ---------------------------------------------------------
step "2/6 visszafejtés és kicsomagolás"
rm -rf "$WORK"; mkdir -p "$WORK"; chmod 700 "$WORK"
if ! ssh -o ConnectTimeout=15 "$PVE" "cat $ARCHIVE" \
     | gpg --batch --quiet --decrypt --passphrase-file "$PASSFILE" 2>/dev/null \
     | tar xzf - -C "$WORK"; then
    fail "a visszafejtés vagy a kicsomagolás elszállt"
fi
SRC="$WORK/k3s-backup-staging"
[ -s "$SRC/state.db" ] || fail "nincs state.db az archívumban"
echo "  state.db: $(du -h "$SRC/state.db" | cut -f1), teljes: $(du -sh "$WORK" | cut -f1)"

# The integrity_check ran at backup time, but that applied to the file AS IT WAS THEN.
# This copy went through gpg, tar and two SSH hops; damage in transit shows up here.
python3 - "$SRC/state.db" <<'PY' || fail "a state.db sérült"
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
r = c.execute('PRAGMA integrity_check').fetchone()[0]
n = c.execute('SELECT count(*) FROM kine').fetchone()[0]
print('  integrity_check: %s, kine sorok: %d' % (r, n))
sys.exit(0 if r == 'ok' else 1)
PY

# --- 3. version ------------------------------------------------------------
step "3/6 k3s binaris letoltese"
# The version comes from the backup itself, not from the live cluster: an old archive
# has to be restored with the version that belongs to it. The kubeletVersion field of
# the node objects is in state.db; the highest one is the version running at backup time.
VER=$(strings -a "$SRC/state.db" | grep -oE 'v1\.[0-9]+\.[0-9]+\+k3s[0-9]+' \
      | sort -uV | tail -1)
[ -n "$VER" ] || fail "nem tudom kiolvasni a k3s verziót a state.db-bol"
echo "  a mentésben talált verzió: $VER"
# The binary is cached outside WORK, because the trap deletes WORK: a repeated run then
# does not download the 79 MB again. The cache holds no secrets, so it can safely
# outlive the run.
mkdir -p "$CACHE"
if [ ! -x "$CACHE/k3s-$VER" ]; then
    curl -fsSL -o "$CACHE/k3s-$VER.part" \
        "https://github.com/k3s-io/k3s/releases/download/${VER/+/%2B}/k3s" \
        || fail "a k3s $VER binaris nem tolthető le"
    chmod +x "$CACHE/k3s-$VER.part"; mv "$CACHE/k3s-$VER.part" "$CACHE/k3s-$VER"
else
    echo "  a binaris a gyorsítótárból jön: $CACHE/k3s-$VER"
fi
cp "$CACHE/k3s-$VER" "$WORK/k3s"
"$WORK/k3s" --version | head -1 | sed 's/^/  /'

# --- 4. startup ------------------------------------------------------------
step "4/6 eldobható control plane indítása"
# Default data-dir, because the kubeconfigs under cred/ contain absolute paths (see the
# header). This is also the real restore procedure.
S=/var/lib/rancher/k3s/server
mkdir -p "$S/db"
cp "$SRC/state.db" "$S/db/state.db"
cp -a "$SRC/tls" "$SRC/cred" "$S/"
cp -a "$SRC/token" "$SRC/node-token" "$SRC/agent-token" "$S/"

# On an encrypted cluster --secrets-encryption CANNOT be omitted. encryption-config.json
# is there under cred/, but k3s only passes it to the apiserver because of this flag.
# MEASURED on 2026-08-28, without the flag:
#
#   Error from server (InternalError): Internal error occurred:
#   identity transformer tried to read encrypted data
#
# and the server NEVER becomes ready - /readyz returns "[-]informer-sync failed"
# forever, because the Secret informer cannot sync (474 of 962 log lines were this one
# error). Meanwhile the non-Secret resources stay readable, so the restore LOOKS
# successful. This line works from the backup, not from configuration: if the file is
# in the archive, the flag is needed too.
ENC_ARGS=()
if [ -f "$SRC/cred/encryption-config.json" ]; then
    ENC_ARGS=(--secrets-encryption)
    echo "  az archivum titkositott clusterbol jon, --secrets-encryption bekapcsolva"
fi

nohup "$WORK/k3s" server \
    --disable-agent \
    --egress-selector-mode disabled \
    --bind-address 127.0.0.1 \
    --tls-san 127.0.0.1 \
    --node-name k3s-restore-test \
    --write-kubeconfig "$WORK/kubeconfig" \
    --write-kubeconfig-mode 600 \
    "${ENC_ARGS[@]+"${ENC_ARGS[@]}"}" \
    > "$WORK/k3s.log" 2>&1 < /dev/null &
K3SPID=$!
disown

export KUBECONFIG="$WORK/kubeconfig"
K="$WORK/k3s kubectl"
T0=$(date +%s)
# The process is watched by PID, not with pgrep: after startup k3s REWRITES its own
# argv, only "<path>/k3s server" remains in /proc, the flags disappear. The first
# version searched for 'k3s server --disable-agent', exited immediately, and it looked
# as if the API had never come up. `kill -0` still points at the same PID after the
# argv rewrite.
for _ in $(seq 1 120); do
    [ -s "$WORK/kubeconfig" ] && $K get --raw /readyz >/dev/null 2>&1 && break
    kill -0 "$K3SPID" 2>/dev/null || { echo "  a k3s folyamat elszállt"; break; }
    sleep 2
done
if ! $K get --raw /readyz >/dev/null 2>&1; then
    echo "  --- az elso hibasorok a logban:"
    grep -nE 'level=(fatal|error)|unknown flag|invalid argument' "$WORK/k3s.log" \
        | head -12 | cut -c1-220 | sed 's/^/  /'
    fail "az API nem jött fel"
fi
echo "  az API $(( $(date +%s) - T0 )) másodperc alatt jött fel a 127.0.0.1:6443-on"

# --- 5. verification -------------------------------------------------------
step "5/6 mi van a visszaállított clusterben"

# The TIME of the backup comes from the file name, and it is the basis of the verdict.
# There is no hardcoded list of expectations, because that starts lying after every
# installation: on the first run the 06:49 backup rightly did not contain the
# monitoring installed at 07:30, and the script reported that as a failure. The correct
# question is whether every object of the live cluster that ALREADY EXISTED at the
# moment of the backup is present on the restored side. Anything created since then is drift.
BASE=$(basename "$ARCHIVE")
TS=$(echo "$BASE" | sed -E 's/.*-([0-9]{4}-[0-9]{2}-[0-9]{2})_([0-9]{2})-([0-9]{2})-([0-9]{2}).*/\1 \2:\3:\4/')
# The file name is written by k3s-backup.sh in 109's LOCAL time, while creationTimestamp
# is UTC. `date -u -d "2026-08-28 11:42:04"` would read the naive timestamp as UTC,
# which here is a two hour shift in the strict direction: it would report real objects
# as missing. So first to epoch as local time, then to UTC.
# (109 has only been on Europe/Budapest since 2026-08-26; archives older than that have
# names made in UTC. The NEWEST check below catches that.)
EPOCH=$(date -d "$TS" +%s 2>/dev/null)
[ -n "$EPOCH" ] || fail "nem tudom kiolvasni a mentés idejét a fájlnévből: $BASE"
# 60 seconds of slack: the file name marks the START of the backup, the state.db copy is
# made a few seconds later. Objects falling into that gap prove nothing either way, so
# they do not count as a failure.
CUTOFF=$(date -u -d "@$((EPOCH - 60))" +%Y-%m-%dT%H:%M:%SZ)

# Self-check on the file name: the restored cluster cannot hold an object NEWER than the
# threshold, since it cannot contain the moment after the backup. If it does, then the
# threshold computed from the file name is too early (different timezone, adjusted
# clock), and the real data is authoritative, not the file name.
NEWEST=$($K get namespace,secret,configmap,deployment,pvc,applications.argoproj.io -A \
    -o jsonpath='{range .items[*]}{.metadata.creationTimestamp}{"\n"}{end}' 2>/dev/null \
    | grep -E '^2[0-9]{3}-' | sort | tail -1)
if [ -n "$NEWEST" ] && [ "$NEWEST" \> "$CUTOFF" ]; then
    echo "  a fájlnév szerinti küszöb ($CUTOFF) korábbi, mint a mentésben talált"
    echo "  legfrissebb objektum ($NEWEST) - a küszöb az utóbbi lesz"
    CUTOFF="$NEWEST"
fi
echo "  a mentés ideje: $TS (helyi), a küszöb: $CUTOFF (UTC)"

NODES=$($K get nodes --no-headers 2>/dev/null | awk '{print $1}' | sort | tr '\n' ' ')
echo "  node-ok a visszaállított clusterben: $NODES"

LIVE_OK=0
if ! KUBECONFIG=/root/.kube/config kubectl get ns >/dev/null 2>&1; then
    bad "az éles cluster nem elérhető, így nincs mihez hasonlítani"
else
    LIVE_OK=1
    # jsonpath, NOT go-template: for cluster-scoped objects go-template writes
    # "<no value>" into the missing namespace, which CONTAINS A SPACE, and that made
    # the field-count based filter drop every CRD, namespace and PV - it showed zero
    # where there are 84 objects. jsonpath returns an empty string.
    TPL='{range .items[*]}{.metadata.namespace}/{.metadata.name} {.metadata.creationTimestamp}{"\n"}{end}'
    printf '  %-28s %12s %10s %8s\n' "erőforrás" "mentés előtt" "mentésben" "hiányzó"
    for R in namespace crd secret configmap pvc pv deployment statefulset daemonset \
             applications.argoproj.io volumes.longhorn.io replicas.longhorn.io; do
        LIVE=$(KUBECONFIG=/root/.kube/config kubectl get "$R" -A -o jsonpath="$TPL" 2>/dev/null)
        [ -z "$LIVE" ] && continue
        # only objects that already existed before the backup count
        WANT=$(echo "$LIVE" | awk -v c="$CUTOFF" 'NF==2 && $2 < c {print $1}' | sort -u)
        HAVE=$($K get "$R" -A -o jsonpath="$TPL" 2>/dev/null | awk 'NF==2{print $1}' | sort -u)
        MISS=$(comm -23 <(echo "$WANT") <(echo "$HAVE"))
        NW=$(echo "$WANT" | grep -c .); NH=$(echo "$HAVE" | grep -c .); NM=$(echo "$MISS" | grep -c .)
        printf '  %-28s %12s %10s %8s\n' "$R" "$NW" "$NH" "$NM"
        if [ "$NM" -ne 0 ]; then
            bad "$R: $NM olyan objektum hiányzik, ami a mentéskor már létezett"
            echo "$MISS" | head -10 | sed 's/^/       /'
        fi
    done
fi

# The single most important check: not that the Secret OBJECTS are there, but that
# their CONTENT is usable. If the kine rows had been truncated, an empty or
# undecodable value would come back here while the counts still matched.
# (The Secrets are unencrypted in kine - there is no --secrets-encryption. Once we
# turn it on, the key will be in encryption-config.json next to tls/, and without it
# this step would be the first to fail.)
$K get secret -A -o json > "$WORK/secrets-restore.json" 2>/dev/null
KUBECONFIG=/root/.kube/config kubectl get secret -A -o json > "$WORK/secrets-live.json" 2>/dev/null
python3 - "$WORK/secrets-restore.json" "$WORK/secrets-live.json" <<'PYSEC'
import base64, json, sys

def load(path):
    out = {}
    try:
        d = json.load(open(path))
    except Exception:
        return out
    for it in d.get("items", []):
        m = it["metadata"]
        for k, v in (it.get("data") or {}).items():
            try:
                out[(m.get("namespace", ""), m["name"], k)] = len(
                    base64.b64decode(v, validate=True))
            except Exception:
                out[(m.get("namespace", ""), m["name"], k)] = -1
    return out

r, live = load(sys.argv[1]), load(sys.argv[2])
broken = sorted(k for k, v in r.items() if v == -1)
# An EMPTY value is NOT an error in itself: Kubernetes allows it, and there are three
# such keys in this cluster. The first version treated every zero as a failure and fell
# over on those three while there was nothing wrong with the backup. The real error is
# content on the LIVE side and none on the restored one.
lost = sorted(k for k, v in r.items() if v == 0 and live.get(k, 0) > 0)
empty = sum(1 for v in r.values() if v == 0)
print("  %d Secret-kulcs jott vissza, ebbol %d szandekosan ures (elesen is az)"
      % (len(r), empty))
for label, items in (("dekodolhatatlan", broken),
                     ("elesen van tartalma, itt ures", lost)):
    for k in items[:10]:
        print("    %s: %s/%s -> %s" % (label, k[0], k[1], k[2]))
sys.exit(1 if broken or lost else 0)
PYSEC
if [ $? -eq 0 ]; then
    ok "minden Secret-kulcs tartalma hiánytalanul visszaolvasható"
else
    bad "van olyan Secret-kulcs, aminek élesen van tartalma, a mentésben nincs"
fi

# --- 6. drift --------------------------------------------------------------
step "6/6 mi keletkezett a mentés óta"
if [ "$LIVE_OK" -eq 1 ]; then
    NEW=$(KUBECONFIG=/root/.kube/config kubectl get \
        namespace,pvc,deployment,applications.argoproj.io,volumes.longhorn.io -A \
        -o jsonpath="$TPL" 2>/dev/null \
        | awk -v c="$CUTOFF" 'NF==2 && $2 >= c {print "    " $1 "  (" $2 ")"}')
    if [ -n "$NEW" ]; then
        echo "  ezek a mentés UTÁN keletkeztek, tehát jogosan nincsenek benne:"
        echo "$NEW"
        echo "  ha ezeket is védeni akarod, futtass egy friss mentést:"
        echo "    /root/homelab/scripts/k3s-backup.sh --no-ntfy"
    else
        echo "  semmi - a mentés a jelenlegi állapotot fedi"
    fi
fi

step "eredmény"
if [ "$FAILED" -eq 0 ]; then
    echo -e "\033[32mA mentés visszaállítható. Minden ellenőrzés átment.\033[0m"
    RC=0
else
    echo -e "\033[31m$FAILED ellenőrzés bukott el - a mentésre így NEM lehet számítani.\033[0m"
fi
exit $RC
