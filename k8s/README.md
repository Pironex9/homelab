# k8s

A K3s cluster **tartalmanak** deklarativ leirasa. Ez a harmadik reteg:

| Reteg | Eszkoz | Hol |
|---|---|---|
| 1. Vas + OS | kezi | - |
| 2. k3s telepites es node config | Ansible | `ansible/` |
| 3. Cluster tartalom | **Argo CD** | itt |

## Bootstrap

Az Argo CD sajat telepitese nem gitbol jon - az a tyuk-tojas problema. Egyszer,
kezzel, verziora pinelve:

```bash
curl -fsSLO https://raw.githubusercontent.com/argoproj/argo-cd/v3.5.1/manifests/install.yaml
sha256sum install.yaml   # 795a3a972224da6a7f9d32c3e946445f062b60fb46028476715affeb688236e3
kubectl create namespace argocd
kubectl apply --server-side --force-conflicts -n argocd -f install.yaml
kubectl apply -f k8s/bootstrap/root-app.yaml
```

**`--server-side` kell.** Sima `kubectl apply` eseten az `applicationsets.argoproj.io`
CRD elhasal `metadata.annotations: Too long: may not be more than 262144 bytes`
hibaval, mert a kliensoldali apply a teljes manifestet beleteszi egy annotacioba.

A `stable` tag helyett konkret verzio (`v3.5.1`, 2026-08-12), mert a `stable` mozog,
es akkor a telepites nem reprodukalhato. A sha256 azert van itt, hogy a pontos bajtok
kesobb is ellenorizhetok legyenek anelkul, hogy egy 1.9 MB-os manifestet a repoba
tennenk.

## Hozzaferes

```
https://argocd.tailc6abe2.ts.net
```

Barmely tailnetes gepröl, felhasznalo `admin`. Valodi Let's Encrypt tanusitvany, a
Tailscale automatikusan ujitja - nincs cert-manager, nincs sajat DNS bejegyzes, es
nincs port-forward, ami a session-nel egyutt meghalna.

Ezt a **Tailscale Kubernetes operator** adja. Minden `ingressClassName: tailscale`
Ingresshez felvesz egy kulon proxy podot, ami sajat eszkozkent csatlakozik a
tailnethez; a nev a `spec.tls[0].hosts[0]` ertekebol es a tailnet domainbol all ossze.
A telepitese nem gitbol jon, mert OAuth secretet igenyel, a repo pedig publikus:

```bash
helm repo add tailscale https://pkgs.tailscale.com/helmcharts
helm upgrade --install tailscale-operator tailscale/tailscale-operator \
    --version 1.102.3 --namespace tailscale --create-namespace \
    -f <values fajl az oauth.clientId es oauth.clientSecret ertekekkel>
```

A hitelesito adatok a `/root/.secrets/tailscale-operator-oauth` fajlban vannak a
109-en. A tailnet oldalan ket dolog kell hozza: `tagOwners` bejegyzes a
`tag:k8s-operator` es a `tag:k8s` tagekre, es egy OAuth kliens **write** joggal a
`devices:core` es az `auth_keys` scope-ra, `tag:k8s-operator` cimkevel.

### Hogyan mukodik, es mit kell fenntartani

Semmit. A proxy pod a clusterben fut, StatefulSetkent, tehat magatol ujraindul es
tulel egy node rebootot is. Ez a lenyegi kulonbseg a port-forwardhoz kepest, ami egy
folyamat volt a 109-en, es a session-nel egyutt meghalt.

Amit az operator egy Ingresshez letrehoz:

```
statefulset.apps/ts-argocd-<hash>    <- egy pod, benne tailscale/tailscale:v1.102.3
service/ts-argocd-<hash>
secret/ts-argocd-<hash>-0            <- ennek a node-nak az identitasa
```

A podban egy **teljes ertekű Tailscale node** fut: az OAuth hitelesitessel kér magának
auth key-t, csatlakozik a tailnethez sajat nevvel es IP-vel. A Secret azert kell, mert
az identitas allapot - ujrainduláskor ugyanazzal a kulccsal kell visszajonnie, kulonben
uj eszkozkent regisztralna es megvaltozna a neve.

Forgalom utja:

```
bongeszo -> WireGuard (direkt vagy DERP) -> proxy pod (itt terminalodik a TLS)
         -> service/argocd-server:80 a clusteren belul -> argocd-server pod
```

A pod belul `tailscale serve`-et futtat (`TS_SERVE_CONFIG`), es **userspace halozati
modban** dolgozik (`TS_USERSPACE`), tehat nem hoz letre TUN eszkozt es nem kell neki
`NET_ADMIN`. A tanusitvanyt maga keri a Tailscale ACME-jen keresztul, ezert nincs
`secretName` a `tls` blokkban - nem letezik Kubernetes Secret, amiben a tanusitvany
ulne.

Koltseg: **Ingressenkent egy tailnet-eszkoz.** Az Ingress torlesevel a proxy pod es az
eszkoz is eltunik, a cim pedig megszunik letezni.

### Az argocd-server insecure modja - nem hanyagsag

Az `argocd-cmd-params-cm` ConfigMapben `server.insecure: "true"` all. Enelkul az
Argo CD sajat maga is HTTPS-t beszelne, es **barmely TLS-t terminalo Ingress mogott
vegtelen atiranyitasi hurokba fut**. Ez a beallitas nem ebben a repoban el, mert az
Argo CD sajat telepitese sem.

### Nevfeloldas

A `.ts.net` nev csak ott oldodik fel, ahol a MagicDNS aktiv. **A 109-en nem**, ott az
`accept-dns` szandekosan ki van kapcsolva egy korabbi incidens miatt. Innen IP-vel es
SNI-vel lehet tesztelni:

```bash
curl --resolve argocd.tailc6abe2.ts.net:443:<proxy IP> https://argocd.tailc6abe2.ts.net/
```

Az admin jelszo a jelszokezeloben van, az `argocd-initial-admin-secret` torolve.

## K3s verziofrissites (2026-08-28)

A `system-upgrade` Application a `k8s/manifests/system-upgrade/` alatti harom fajlt
kezeli: az upstream SUC v0.20.1 `crd.yaml`-jat es `controller.yaml`-jat valtozatlanul,
plusz a sajat `plans.yaml`-t.

**A frissites menete: atirod a ket `version:` mezot a `plans.yaml`-ben, commit, push.**
Semmi mas. Az ArgoCD kiszinkronizalja a Planeket, a controller pedig node-onkent
lefuttatja, a masterrel kezdve.

Egyszerre egy minort - a `1.34 -> 1.36` ugras nem tamogatott, es a SUC nem ved ellene.
A 2026-08-28-i frissites harom hopban ment: `v1.34.5 -> v1.34.11 -> v1.35.8 -> v1.36.4`,
hoponkent 3-7 perc, hoponkent ~20 masodperc API-kimaradassal a master frissitese kozben.

Az `ansible/group_vars/k3s_cluster.yml` `k3s_version` valtozojat a frissites utan kezzel
kell atvezetni, kulonben a kovetkezo `site.yml` futas visszaminositene a clustert.

A Longhorn NEM igy frissul (lasd a kovetkezo szakaszt): az Helm release, es kezzel megy,
a k3s hopok **elott**.

## Amit az Argo CD NEM kezel

A **Longhorn Helm release-t** szandekosan nem adoptaljuk.

**Az indok 2026-08-28-an felulvizsgalva, mert a korabbi mar nem igaz.** Eddig az allt
itt, hogy a longhorn/longhorn#6415 miatt nem lehet: az Argo CD a Helm hookokat
`PreSync`-kent futtatja, ezert a pre-upgrade job mar az elso szinkronnal lefutna, amikor
a service account meg nem letezik. **Ez 2023-10-23-an lezarult, a v1.6.0-ban javitva** -
mi az 1.12.1-en vagyunk, tehat hat minorral a javitas utan. Technikai akadaly nincs.

A chart 1.12.1 sajat leirasa mondja ki a modjat:

```
preUpgradeChecker:
  # -- ... Disable this setting when installing Longhorn using Argo CD or other GitOps solutions.
  jobEnabled: true
```

**Megis nem adoptaljuk, mas okbol:** a `jobEnabled: false` pont azt a
verziout-ellenorzest kapcsolja ki, ami megakadalyozna egy ervenytelen Longhorn-frissitest
(pl. egy minor kihagyasat). Azt a biztonsagi halot a **tarolo** retegen adnank fel - azon
az egyetlen retegen, ahol egy elrontott frissites nem visszavonhato (minorra nincs
downgrade, csak a Garage backup + `fromBackup` StorageClass ut). Cserebe egy evente
parszor eloforduló, tudatos, mentessel kezdodo muvelet lenne deklarativ.

Rossz csere. A k3s-nel forditva all a merleg, ezert megy az SUC-on keresztul.

Ha valaha megis, akkor `preUpgradeChecker.jobEnabled: false` **es** a `plans.yaml`-hez
hasonlo, kiirt hop-szabaly a Longhorn verziokra.

Ez nem korlat: amit deklarativva akarunk tenni, az nagyreszt nem a Helm release, hanem
sima objektum - a Longhorn `BackupTarget` es `RecurringJob` kulon CRD-k, a
NetworkPolicy, a Pod Security Admission es a resource limitek pedig eleve azok. A
Longhorn telepiteset tovabbra is a Helm kezeli.

Ket **Secret** sem gitbol jon, mert a repo publikus: a Tailscale operator OAuth
hitelesito adatai (lasd fentebb) es a `forgejo-secrets` (lasd lentebb). Mindketto
kezzel keszul, egyszer, es a `/root/.secrets/` alatt marad a 109-en.

## Longhorn kotetmentes Garage S3-ra (2026-08-25)

A `longhorn-backup` Argo CD Application a `k8s/manifests/longhorn/` alatti ket CRD-t
kezeli: a `BackupTarget/default`-ot es a `RecurringJob/backup-daily`-t. A cel egy
**Garage** S3 szerver a 100-as LXC-n (`compose/proxmox-lxc-100/garage/`), amit a
node-ok Tailscale-en ernek el: `http://100.97.95.101:3900`.

| Miert igy | Indok |
|---|---|
| Garage, nem MinIO | a MinIO Community Edition GitHub repojat 2026 februarjaban archivaltak, olvashato csak; a webes admin felulet mar 2025 marciusaban kikerult belole |
| sima HTTP, nem HTTPS | a forgalom vegig a Tailscale WireGuard alagutban megy, TLS-t nem kell fole huzni |
| adat a `/mnt/storage`-en | a 100-as root diszkje 78%-on all (11 GB szabad), a poolban 3.8 TB van |
| metaadat a rooton | LMDB, kis meret, SSD-t szeret - a mergerfs poolra nem valo |
| `replication_factor = 1` | egyetlen node. A Garage doksi ezt "csak tesztre" minositi, es ez igaz is: a Garage szintjen nincs redundancia. Amit ad: a tartalom maga is masolat, es a `/mnt/storage`-t a SnapRAID vedi lemezvesztes ellen |

### A `BackupTarget/default` adoptalas, nem letrehozas

A Longhorn a telepiteskor maga hozza letre az ures `default` nevu BackupTargetet.
Ezert az Application `ServerSideApply=true`-val fut - anelkul az Argo CD egy mar
letezo, idegen objektumra probalna client-side apply-t.

### A hozzaferesi kulcs nincs a repoban

A repo publikus. Az S3 kulcs a `longhorn-system` namespace `garage-backup-secret`
Secretjeben ul, kezzel letrehozva:

```bash
kubectl -n longhorn-system create secret generic garage-backup-secret \
  --from-literal=AWS_ACCESS_KEY_ID=<GK...> \
  --from-literal=AWS_SECRET_ACCESS_KEY=<...> \
  --from-literal=AWS_ENDPOINTS=http://100.97.95.101:3900
```

Uj kulcs a 100-ason: `docker exec garage /garage key create <nev>`, majd
`docker exec garage /garage bucket allow --read --write --owner longhorn --key <nev>`.
A parancs kiirja a titkos kulcsot, ezert **ne olyan terminalba fusson, aminek a
kimenete naplozodik** - a 109-en a Claude session jsonl-je es a memsearch DB is
ilyen, es azok az NFS-exporton keresztul a LAN-rol olvashatok.

### A `default` csoport nem ures halmaz

A `RecurringJob` a `default` csoportban van. Az minden olyan kotetre vonatkozik,
amelyik nem jelol meg sajat recurring jobot - vagyis alapertelmezesben mindenre. Ma
nulla PVC van a clusterben, tehat a job most nem csinal semmit; az elso letrehozott
kotet automatikusan bekerul.

Idozites: `0 1 * * *` UTC, fel oraval a 109-en futo `k3s-backup.sh` (01:30) ele.
`retain: 14`.

### Ellenorizve, nem feltetelezve (2026-08-25)

1 Gi Longhorn kotet, benne egy ismert tartalmu fajl -> `Snapshot` -> `Backup`
`Completed` 25 masodperc alatt -> a bucketben 11 objektum, 86.1 kB -> visszaallitas
egy `fromBackup` parameteru StorageClasson at egy uj PVC-be -> a fajl tartalma
byte-ra ugyanaz. A teszt eroforrasok utana torolve; a bucketben 1 db 589 bajtos
kotet-metaadat maradt.

## Forgejo - az elso workload (2026-08-28)

A cluster 161 napig nulla alkalmazassal es nulla PVC-vel futott. A `forgejo` Argo CD
Application (`k8s/manifests/forgejo/`) ezt zarja le: **Forgejo 16.0.3**, rootless image,
sqlite3, egy 10 GiB-os Longhorn koteten, `https://forgejo.tailc6abe2.ts.net`.

**Miert ez lett az elso:** egy konteneres, nincs melle Postgres, es egyetlen PVC-t
hasznal. Nem a legimpozansabb valasztas, hanem az, amelyiken a ket eddig nem merheto
dolog vegre merheto:

1. **A Longhorn visszaallitas a Garage S3-rol.** A `RecurringJob/backup-daily` 2026-08-25
   ota minden hajnali 1-kor lefut, es eddig **semmit** nem mentett, mert nem volt kotet.
   Az elso valodi backup ettol a kotettol keletkezik.
2. **A drain last-replica aga.** A 2026-08-28-i meres ures clusteren futott (lasd
   `docs/hosts/k3s-cluster.md`), tehat a `block-if-contains-last-replica` viselkedese
   nem volt kiprobalhato.

Haszna is van: a homelab repo GitOps-a ma egyetlen kulso olvasasi uton, a github.com-on
lóg. Egy helyi tukor ezt oldja. **Az Argo CD `repoURL`-je marad a GitHubon** - ha a
cluster sajat forgejaból olvasna a sajat telepiteset, korkoros bootstrap lenne belole.

### A SECRET_KEY nincs a gitben, es nem elhagyhato

A repo publikus, ezert a Secret kezzel keszul, egyszer:

```bash
openssl rand -base64 32 | tr -d '\n' > /root/.secrets/forgejo-secret-key
chmod 600 /root/.secrets/forgejo-secret-key
kubectl -n apps create secret generic forgejo-secrets \
    --from-file=SECRET_KEY=/root/.secrets/forgejo-secret-key
```

A `tr -d '\n'` **nem** kozmetika: a `--from-file` a fajl minden bajtjat beleteszi, a zaro
ujsorral egyutt, es az `environment-to-ini` azt irna bele az `app.ini`-be.

**Miert kotelezo:** a Forgejo nem general maganak SECRET_KEY-t. Ha ures, a
`modules/setting/security.go` `loadSecurityFrom` fuggvenye a forraskodba drotozott
`"!#@FDEWREWR&*("` erteket hasznalja - vagyis egy nyilvanosan ismert kulcsot, amivel a
2FA titkok, a mirror jelszavak es az OAuth tokenek titkositva lennenek. (Az
`INTERNAL_TOKEN` ezzel szemben magatol generalodik es kimentodik az `app.ini`-be, azzal
nincs teendo.)

A kulcs `/root/.secrets/forgejo-secret-key` alatt marad a 109-en. **Ha elvesz, a vele
titkositott mezok olvashatatlanok** - a repok es a felhasznalok megmaradnak, a 2FA es a
tarolt hitelesito adatok nem.

### Admin felhasznalo

`INSTALL_LOCK=true`-val nincs webes telepito, tehat az elso admin CLI-bol keszul:

```bash
kubectl -n apps exec deploy/forgejo -- \
    forgejo admin user create --admin --username <nev> \
    --email <cim> --random-password
```

A kiirt jelszo egyszer latszik. Ez tudatos csere: a webes telepitot barki elerhetne a
tailnetrol, aki elobb nyitja meg, mint te.

### Ket dontes, ami keson fajna

- **`strategy: Recreate`.** A kotet ReadWriteOnce. RollingUpdate eseten az uj pod a regi
  mellett indulna, es `Multi-Attach error`-ral orokre Pendingben allna.
- **`Prune=false` a PVC-n.** Az Application `prune: true`-val fut. Enelkul a `pvc.yaml`
  gitbol valo kikerulese torolne a PVC-t, a `longhorn` StorageClass
  `reclaimPolicy: Delete`-je pedig vinne magat a kotetet is.

### Amit szandekosan nem telepitettunk hozza

**cert-managert.** A `tailscale` IngressClass valodi Let's Encrypt tanusitvanyt ad,
automatikus ujitassal - ugyanaz a minta, mint az argocd Ingressnel. Belso appokhoz nem
kell sem ClusterIssuer, sem sajat DNS bejegyzes. A publikus appok pedig a Hetzner VPS-en
futo Pangolinon mennek at.

**Git-over-SSH-t.** Egy Ingress csak HTTP-t visz, es a HTTPS clone mukodik. Ha megis
kell, a Tailscale operator `tailscale.com/expose` annotacioja tud egy kulon TCP
Service-t adni a konteneren belüli 2222-es portra, es akkor a
`FORGEJO__server__DISABLE_SSH` is `false`-ra vált.
