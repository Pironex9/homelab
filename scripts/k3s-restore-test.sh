#!/bin/bash
# K3s control-plane mentés visszaállítási próbája - eldobható clusterbe.
#
# A 109-en fut (claude-mgmt), mert a gpg jelszó itt van és a pve sose látja.
#
# MIÉRT KELL, HA A k3s-backup.sh MÁR ELLENŐRIZ:
#   Az azt bizonyítja, hogy az archívum VISSZAFEJTHETŐ és a state.db benne van a
#   tar listájában. Az, hogy abból egy k3s tényleg feláll és a benne lévő
#   objektumok elérhetők, más kérdés - 2026-08-28 előtt sose volt megmérve.
#   Egy tar, ami kicsomagolható, még nem mentés; az a mentés, amiből a cluster
#   visszajön.
#
# MIT CSINÁL:
#   Letölti a legfrissebb archívumot a pve-ről, visszafejti ide, a state.db-t és
#   a tls/cred/token készletet a helyére teszi, és elindít egy k3s servert
#   --disable-agent móddal a 127.0.0.1:6443-on. Aztán összeveti az élő
#   clusterrel: minden objektumnak, ami a mentés IDEJE ELŐTT keletkezett, meg
#   kell lennie a visszaállított oldalon is. Végül megnézi, hogy a Secretek
#   tartalma tényleg dekódolódik-e, nem csak a darabszám stimmel.
#
#   Nincs hardkódolt elváráslista, és ez nem kényelmi döntés: az első változat
#   névre kereste a hat Argo CD Applicationt, és a 06:49-es mentésen hibát
#   jelentett, mert a monitoring csak 07:30-kor került fel. A creationTimestamp
#   a pontos küszöb; egy névlista minden új telepítés után hazudni kezd.
#
# MIÉRT --disable-agent:
#   Enélkül a visszaállított control plane node-dá is válna, elindulna rajta a
#   kubelet, és ütemezni kezdené a visszaállított DB-ben talált podokat -
#   Longhornt, Argo CD-t, mindent. Az Argo CD abban a pillanatban a valódi
#   GitHubot húzná, a Longhorn a valódi Garage S3-at. Agent nélkül egyetlen pod
#   sem indul el, a bizonyításhoz pedig nem is kell: a kérdés az, hogy az
#   ADATOK megvannak-e, nem az, hogy futnak-e.
#
# AZ ELSŐ FUTÁS KÉT TALÁLATA (2026-08-28):
#   1. A cred/ hat kubeconfigja ABSZOLÚT útvonalat tartalmaz
#      (/var/lib/rancher/k3s/server/tls/...). Egyedi --data-dir alá visszatéve a
#      k3s el sem indul: "unable to read client-cert ... no such file". Ezért
#      használ ez a script alapértelmezett data-dirt, és ezért kell a guard.
#   2. Ugyanezek a kubeconfigok a PORTOT is rögzítik: https://127.0.0.1:6444. A
#      k3s az apiserver belső portját a --https-listen-port + 1 képlettel adja,
#      tehát egy nem alapértelmezett listen-port mellett a scheduler és a
#      controller-manager a 6444-et hívja, miközben az apiserver máshol figyel:
#      "unable to load configmap based request-header-client-ca-file ... dial tcp
#      127.0.0.1:6444: connect: connection refused", és a k3s leáll. Ezért nincs
#      ezen a scripten port-kapcsoló: a 6443 nem ízlés kérdése.
#   3. A k3s a saját bundle-jét akkor is /var/lib/rancher/k3s/data alá csomagolja
#      ki (253 MB), ha a --data-dir máshova mutat.
#
# AMIHEZ HOZZÁNYÚL:
#   Az éles clustert NEM érinti - csak olvassa, összehasonlításhoz. A pve-n lévő
#   archívumot csak olvassa. Ezen a gépen létrehozza és a végén törli:
#   /var/lib/rancher/k3s, /etc/rancher/k3s, /etc/rancher/node, és a munkakönyvtárat.
#
# BIZTONSÁG:
#   A kicsomagolt archívum a cluster CA PRIVÁT KULCSAIT és a join tokent
#   tartalmazza. A munkakönyvtár 700-as, a lokális lemezen van, és a script a
#   végén törli - akkor is, ha félbeszakad (trap). Soha ne állítsd a WORK-öt a
#   /mnt/storage alá: az NFS-export no_root_squash-sal a teljes LAN-nak.
#
# ROLLBACK, ha félbeszakad úgy, hogy a trap sem futott le:
#   pkill -f '/tmp/k3s-restore-test/k3s server'
#   rm -rf /var/lib/rancher/k3s /etc/rancher/k3s /etc/rancher/node
#   rm -rf /tmp/k3s-restore-test
#   Az éles clusteren nincs mit visszavonni.
#
# Használat:
#   ./k3s-restore-test.sh                       # a legfrissebb archívum
#   ./k3s-restore-test.sh k3s-control-plane-2026-08-27_01-30-01.tar.gz.gpg
#   KEEP=1 ./k3s-restore-test.sh                # ne takarítson, hogy nézelődhess
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
    # A logot a takarítás előtt átmentjük, különben egy sikertelen futás okát
    # pont a takarítás viszi el. Titkot nem tartalmaz: útvonalak, node-nevek és
    # SAN-ok vannak benne, kulcs nincs.
    [ -s "$WORK/k3s.log" ] && { mkdir -p "$CACHE"; cp "$WORK/k3s.log" "$CACHE/last-run.log"; \
        echo; echo "a k3s teljes logja: $CACHE/last-run.log"; }
    [ "$KEEP" = "1" ] && { echo "KEEP=1, a takarítás kimarad. Kézzel:"; \
        echo "  pkill -f '$WORK/k3s server'"; \
        echo "  rm -rf /var/lib/rancher/k3s /etc/rancher/k3s /etc/rancher/node $WORK"; return; }
    # A mintában NEM szerepelhetnek a kapcsolók: a k3s indulás után átírja a
    # saját argv-jét, és a /proc-ban csak "<utvonal>/k3s server" marad. Az első
    # változat 'k3s server --disable-agent'-re keresett, sose talált, és két
    # árva control plane maradt futva a már letörölt adatkönyvtárán - a
    # következő futás pedig a foglalt 6443-on hasalt el.
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

# --- guardok ---------------------------------------------------------------
# Ez a script /var/lib/rancher/k3s alatt TÖRÖL. Egy valódi k3s node-on ez a
# cluster megsemmisítése lenne, ezért ott egyáltalán nem indul el.
for u in k3s k3s-agent; do
    systemctl list-unit-files "$u.service" 2>/dev/null | grep -q "^$u.service" \
        && fail "ezen a gépen van $u.service - ez egy éles k3s node, itt nem futhat"
done
[ -e /var/lib/rancher/k3s/server/db/state.db ] \
    && fail "/var/lib/rancher/k3s/server/db/state.db már létezik - előbb nézd meg, mi az"
[ -s "$PASSFILE" ] || fail "a jelszófájl hiányzik vagy üres: $PASSFILE"
# A 6443 nem cserélhető ki (ld. a fejléc 2. pontját), tehát ha foglalt, inkább
# meg sem próbáljuk.
ss -tln 2>/dev/null | grep -q ':6443 ' \
    && fail "a 6443-as port foglalt ezen a gépen - a mentés csak ezen a porton állítható vissza"
command -v gpg >/dev/null || fail "nincs gpg"

# --- 1. archívum -----------------------------------------------------------
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

# --- 2. visszafejtés -------------------------------------------------------
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

# Az integrity_check a mentéskor lefutott, de az az AKKORI fájlra vonatkozott.
# Ez a példány átment gpg-n, tar-on és két SSH-n; itt derül ki, ha útközben sérült.
python3 - "$SRC/state.db" <<'PY' || fail "a state.db sérült"
import sqlite3, sys
c = sqlite3.connect(sys.argv[1])
r = c.execute('PRAGMA integrity_check').fetchone()[0]
n = c.execute('SELECT count(*) FROM kine').fetchone()[0]
print('  integrity_check: %s, kine sorok: %d' % (r, n))
sys.exit(0 if r == 'ok' else 1)
PY

# --- 3. verzió -------------------------------------------------------------
step "3/6 k3s binaris letoltese"
# A verzió magából a mentésből jön, nem az élő clusterből: a régi archívumot a
# hozzá tartozó verzióval kell visszaállítani. A node-objektumok kubeletVersion
# mezője a state.db-ben van, a legmagasabb a mentés idején futó verzió.
VER=$(strings -a "$SRC/state.db" | grep -oE 'v1\.[0-9]+\.[0-9]+\+k3s[0-9]+' \
      | sort -uV | tail -1)
[ -n "$VER" ] || fail "nem tudom kiolvasni a k3s verziót a state.db-bol"
echo "  a mentésben talált verzió: $VER"
# A binárist a WORK-on kívül gyorsítótárazzuk, mert a WORK-öt a trap törli: egy
# ismételt futás így nem tölti le újra a 79 MB-ot. A gyorsítótár nem tartalmaz
# titkot, tehát nyugodtan túléli a futást.
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

# --- 4. indítás ------------------------------------------------------------
step "4/6 eldobható control plane indítása"
# Alapértelmezett data-dir, mert a cred/ kubeconfigjai abszolút útvonalat
# tartalmaznak (ld. a fejlécet). Ez egyben a valódi restore-eljárás is.
S=/var/lib/rancher/k3s/server
mkdir -p "$S/db"
cp "$SRC/state.db" "$S/db/state.db"
cp -a "$SRC/tls" "$SRC/cred" "$S/"
cp -a "$SRC/token" "$SRC/node-token" "$SRC/agent-token" "$S/"

# A titkositott clusternel a --secrets-encryption NEM elhagyhato. Az
# encryption-config.json ott van a cred/ alatt, de a k3s csak ettol a kapcsolotol
# adja at az apiservernek. MEGMERVE 2026-08-28-an, a kapcsolo nelkul:
#
#   Error from server (InternalError): Internal error occurred:
#   identity transformer tried to read encrypted data
#
# es a szerver SOHA nem lesz ready - a /readyz vegtelenul "[-]informer-sync failed"-et
# ad, mert a Secret informer nem tud szinkronizalni (962 log sorbol 474 volt ez az
# egy hiba). Kozben a nem-Secret eroforrasok olvashatok maradnak, tehat a
# visszaallitas sikeresnek LATSZIK. Ez a sor a mentesbol dolgozik, nem beallitasbol:
# ha az archivumban ott a fajl, a kapcsolo is kell.
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
# A folyamatot PID-del figyeljük, nem pgrep-pel: a k3s indulás után ÁTÍRJA a
# saját argv-jét, a /proc-ban csak "<utvonal>/k3s server" marad, a kapcsolók
# eltűnnek. Az első változat 'k3s server --disable-agent'-re keresett, azonnal
# kilépett, és úgy tűnt, mintha az API nem jött volna fel. A `kill -0` az argv
# átírása után is ugyanarra a PID-re mutat.
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

# --- 5. ellenőrzés ---------------------------------------------------------
step "5/6 mi van a visszaállított clusterben"

# A mentés IDEJE a fájlnévből jön, és ez a verdikt alapja. Nincs hardkódolt
# elváráslista, mert az minden telepítés után hazudni kezd: az első futásnál a
# 06:49-es mentésben jogosan nem volt benne a 07:30-kor telepített monitoring,
# és a script ezt hibának jelentette. A helyes kérdés az, hogy az élő cluster
# minden olyan objektuma megvan-e a visszaállított oldalon, ami MÁR LÉTEZETT a
# mentés pillanatában. Ami azóta keletkezett, az sodródás.
BASE=$(basename "$ARCHIVE")
TS=$(echo "$BASE" | sed -E 's/.*-([0-9]{4}-[0-9]{2}-[0-9]{2})_([0-9]{2})-([0-9]{2})-([0-9]{2}).*/\1 \2:\3:\4/')
# A fájlnevet a k3s-backup.sh a 109 HELYI idejében írja, a creationTimestamp
# viszont UTC. A `date -u -d "2026-08-28 11:42:04"` a naiv időpontot UTC-ként
# értelmezné, ami itt két óra csúszás a szigorú irányba: valódi objektumokat
# jelentene hiányzónak. Ezért előbb helyi időként epochra, aztán UTC-re.
# (A 109 csak 2026-08-26 óta van Europe/Budapest-en; az annál régebbi archívumok
# neve UTC-ben készült. Ezt fogja ki lentebb a NEWEST-ellenőrzés.)
EPOCH=$(date -d "$TS" +%s 2>/dev/null)
[ -n "$EPOCH" ] || fail "nem tudom kiolvasni a mentés idejét a fájlnévből: $BASE"
# 60 másodperc ráhagyás: a fájlnév a mentés INDULÁSÁT jelöli, a state.db másolat
# néhány másodperccel később készül. Az ebbe a résbe eső objektumok se így, se
# úgy nem bizonyítanak semmit, ezért nem számítanak bukásnak.
CUTOFF=$(date -u -d "@$((EPOCH - 60))" +%Y-%m-%dT%H:%M:%SZ)

# Önellenőrzés a fájlnévre: a visszaállított clusterben nem lehet a küszöbnél
# ÚJABB objektum, hiszen a mentés utáni pillanatot már nem tartalmazhatja. Ha
# mégis van, akkor a fájlnévből számolt küszöb túl korai (más időzóna, átállított
# óra), és a valódi adat a mérvadó, nem a fájlnév.
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
    # jsonpath, NEM go-template: a go-template a cluster-scope-os objektumok
    # hiányzó namespace-ére "<no value>"-t ír, amiben SZÓKÖZ van, és attól a
    # mezőszám alapú szűrés minden CRD-t, namespace-t és PV-t eldobott - nullát
    # mutatott ott, ahol 84 objektum van. A jsonpath üres sztringet ad.
    TPL='{range .items[*]}{.metadata.namespace}/{.metadata.name} {.metadata.creationTimestamp}{"\n"}{end}'
    printf '  %-28s %12s %10s %8s\n' "erőforrás" "mentés előtt" "mentésben" "hiányzó"
    for R in namespace crd secret configmap pvc pv deployment statefulset daemonset \
             applications.argoproj.io volumes.longhorn.io replicas.longhorn.io; do
        LIVE=$(KUBECONFIG=/root/.kube/config kubectl get "$R" -A -o jsonpath="$TPL" 2>/dev/null)
        [ -z "$LIVE" ] && continue
        # csak az az objektum számít, ami a mentés előtt már megvolt
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

# A legfontosabb egyetlen ellenőrzés: nem az, hogy a Secret OBJEKTUMOK megvannak,
# hanem hogy a TARTALMUK használható. Ha a kine sorai csonkultak volna, itt üres
# vagy dekódolhatatlan érték jönne vissza, miközben a darabszám stimmel.
# (A Secretek titkosítatlanul vannak a kine-ban - nincs --secrets-encryption. Ha
# egyszer bekapcsoljuk, a kulcs a tls/ melletti encryption-config.json-ben lesz,
# és e nélkül ez a lépés bukna el elsőként.)
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
# Egy URES ertek onmagaban NEM hiba: a Kubernetes engedi, es ebben a clusterben
# harom ilyen kulcs van. Az elso valtozat minden nullat hibanak vett, es ezen a
# harmon bukott el ugy, hogy a mentessel semmi baj nem volt. A valodi hiba az,
# ha az ELES oldalon van tartalom, a visszaallitotton meg nincs.
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

# --- 6. sodródás -----------------------------------------------------------
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
