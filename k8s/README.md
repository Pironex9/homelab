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

**Ez 2026-08-28 ota nem csak allitas.** A drain-meres soran a `ts-forgejo-99j4d-0` pod
a tobbivel egyutt evictelodott a kiuritett node-rol, es **ugyanazzal a tailnet
identitassal** jott vissza masik node-on - a HTTPS vegpont kezi lepes nelkul allt
helyre, ugyanazon a nevem. Ezt a `secret/ts-<nev>-<hash>-0` teszi lehetove: az
identitas allapot, es a StatefulSet ugyanazt a Secretet adja vissza az uj podnak.

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
tailscale debug prefs | grep CorpDNS       # "CorpDNS": false  <- ezert nem oldodik fel
tailscale status | grep <ingress nev>      # innen jon a proxy IP
curl --resolve argocd.tailc6abe2.ts.net:443:<proxy IP> https://argocd.tailc6abe2.ts.net/
```

Ez minden tailnetes Ingressre igaz, nem csak az argocd-re. Ha a 109-rol egy `.ts.net`
nev `Could not resolve host`-tal jon vissza, az **nem** azt jelenti, hogy az Ingress
rossz - eloszor a fenti `--resolve`-os hivassal ellenorizd.

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

## Kiprobalni push elott, aztan hagyni, hogy az Argo CD atvegye

Egy `git push` GitOps mellett **deploy**, es a visszavonasa egy ujabb commit plusz
egy reconcile-ciklus - eles workload mellett ez rossz hely a "nezzuk meg, mi
tortenik" kiserletnek. A mai NetworkPolicynel es elotte a monitoring
ertekeinel is ez a sorrend valt be:

1. `kubectl apply -f <a repobol, meg commit nelkul>`
2. megmerni, hogy azt csinalja-e, amit varunk
3. ha nem: `kubectl delete`, es a clusterben nyoma sem marad
4. ha igen: commit es push, es az Argo CD **atveszi** a mar futo objektumot

A 4. lepes azert mukodik, mert az Argo CD nem a letrehozas tenyet nezi, hanem a
tartalmat: ha a gitbol jovo manifest megegyezik a mar ott levovel, nem hoz letre
masodikat, hanem raírja a sajat nyomkovetesét. Kezzel felrakott, de gitben nem
szereplo objektumot viszont NEM prunol - nincs rajta nyomkovetes, tehat az
alkalmazas hatokoren kivul esik. Ez a kettő egyutt teszi biztonsagossa a fenti
sorrendet.

**Az atvetel ellenorzese**, mert a `Synced/Healthy` onmagaban nem mondja meg:

```bash
kubectl -n apps get networkpolicy -o jsonpath='{range .items[*]}{.metadata.name}{"  "}{.metadata.annotations.argocd\.argoproj\.io/tracking-id}{"\n"}{end}'
# default-deny-ingress  platform:networking.k8s.io/NetworkPolicy:apps/default-deny-ingress
```

Ures `tracking-id` = az objektum meg kezi, az Argo CD nem birtokolja.

**Az appok egymastol fuggetlenul reconcile-nak.** 2026-08-28-an a `70a1721` push
utan hat appbol ot egy percen belul atallt ra, a `platform` viszont ot percig a
`96d45c0`-n maradt - az o ciklusa 52 masodperccel a commit utan futott, es meg a
regi repo-cache-t latta. Ha egy app "le van maradva", eloszor a
`.status.reconciledAt` idobelyeget nezd, ne hibat keress.

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
   `docs/k3s/03_Longhorn_Storage.md`), tehat a `block-if-contains-last-replica` viselkedese
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
2FA titkok, a mirror jelszavak es az OAuth tokenek titkositva lennenek.

**A masik ket titokkal viszont nincs teendo,** es ez nem feltetelezes: az elso indulas
utan mind a harom bent van az `app.ini`-ben a koteten, tehat a mentesben is.

| Kulcs | Honnan jon | Mikor |
|---|---|---|
| `SECRET_KEY` | a kezi Secretbol, `FORGEJO__security__SECRET_KEY` | minden indulaskor ujrairva |
| `INTERNAL_TOKEN` | magatol generalodik, `generateSaveInternalToken` | egyszer, elmentve |
| `JWT_SECRET` | magatol generalodik, `createSymmeticSigningKeyCfg` | egyszer, elmentve |

Az elso indulas logjaban ezert lathato egy `[oauth2] JWT_SECRET or JWT_SECRET_URI failed
loading: invalid base64 decoded length: 0 - creating new key` sor. **Ez `[I]` szintu es
nem ismetlodik** - a fuggveny `saveCfg.Save()`-vel ki is irja, amit generalt.

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

### Harom dontes, ami keson fajna

- **`strategy: Recreate`.** A kotet ReadWriteOnce. RollingUpdate eseten az uj pod a regi
  mellett indulna, es `Multi-Attach error`-ral orokre Pendingben allna.
- **`Prune=false` a PVC-n.** Az Application `prune: true`-val fut. Enelkul a `pvc.yaml`
  gitbol valo kikerulese torolne a PVC-t, a `longhorn` StorageClass
  `reclaimPolicy: Delete`-je pedig vinne magat a kotetet is.
- **`fsGroup: 1000` a pod securityContextjeben.** A Longhorn kotet gyoker tulajdonuként
  jon letre, a rootless image viszont uid 1000-rel indul. `fsGroup` nelkul a kubelet nem
  chownolja a kotetet, es a `docker-setup.sh` mar az elso soranal elszall:
  `/var/lib/gitea/git is not writable`. Ez minden rootless imagere igaz Longhorn koteten,
  nem Forgejo-specifikus.

### Amit szandekosan nem telepitettunk hozza

**cert-managert.** A `tailscale` IngressClass valodi Let's Encrypt tanusitvanyt ad,
automatikus ujitassal - ugyanaz a minta, mint az argocd Ingressnel. Belso appokhoz nem
kell sem ClusterIssuer, sem sajat DNS bejegyzes. A publikus appok pedig a Hetzner VPS-en
futo Pangolinon mennek at.

**Git-over-SSH-t.** Egy Ingress csak HTTP-t visz, es a HTTPS clone mukodik. Ha megis
kell, a Tailscale operator `tailscale.com/expose` annotacioja tud egy kulon TCP
Service-t adni a konteneren belüli 2222-es portra, es akkor a
`FORGEJO__server__DISABLE_SSH` is `false`-ra vált.

## Monitoring: kube-prometheus-stack (2026-08-28)

A `monitoring` Argo CD Application a **kube-prometheus-stack 88.6.0**-t telepiti Helm
forrasbol, az ertekekkel egyutt a gitben (`k8s/apps/monitoring.yaml`). Prometheus,
Grafana, Alertmanager, node-exporter es kube-state-metrics. Grafana:
`https://grafana.tailc6abe2.ts.net`.

**Miert most:** a cluster ma szunt meg eldobhato lenni. Allapotot hordoz, es eddig
egyetlen dolog figyelte - a `longhorn-backup-check.sh` hajnali 4-kor, ami egyetlen
kerdesre valaszol. History nem volt: a mai szamok (drain 12s, restore 72s) csak azert
leteznek, mert kezzel mertem oket menet kozben.

### Negy komponens ki van kapcsolva, es ez nem izles kerdese

```yaml
kubeControllerManager: {enabled: false}
kubeScheduler:         {enabled: false}
kubeProxy:             {enabled: false}
kubeEtcd:              {enabled: false}
```

k3s-en ezek nem kulon podok, hanem ugyanabban a k3s processzben futnak, es a
metrika-portjaik a masteren loopbackra vannak kotve. Merve a masteren, `ss -tlnp`:

```
LISTEN 127.0.0.1:10257   kube-controller-manager
LISTEN 127.0.0.1:10259   kube-scheduler
LISTEN 127.0.0.1:10249   kube-proxy
```

`2381` (etcd) nincs is: a datastore **kine + sqlite**, etcd egyaltalan nem fut. Egy
podbol tehat egyik sem erheto el; bekapcsolva a ServiceMonitorok orokre `down`-t
mutatnanak es a hozzajuk tartozo riasztasok folyamatosan tuzelnenek.

**A chart `jobNameOverride: k3s-server` javaslata ezen nem segit** - az csak a Grafana
dashboardok es a Prometheus szabalyok cimkevalasztojat irja at, az elerhetoseget nem.

A `kubelet` bekapcsolva marad, mert a 10250 `*`-on figyel. A `coredns` ServiceMonitor is
megmarad: az valodi Deployment k3s-en is.

Ha valaha kellenek, a `--kube-controller-manager-arg=bind-address=0.0.0.0` es tarsai
nyitjak meg oket - az viszont a control-plane metrikakat kiteszi a halozatra, tehat
kulon dontes.

### Meretezes

| Ertek | Miert |
|---|---|
| `retention: 15d` + `retentionSize: 15GiB` | amelyik elobb jon |
| Prometheus PVC 20 Gi | a `retentionSize`-nak a PVC merete ALATT kell lennie, kulonben a TSDB tolti tele a kotetet ahelyett, hogy o maga vagna vissza |
| Grafana PVC 5 Gi | a chart dashboardjai ConfigMapbol jonnek; ez a kezzel keszitetteket menti at |

Harom replikaval ez 75 GiB a 457 GiB-bol. A node-ok terhelese a telepites elott 5% CPU
es 18% memoria volt, tehat van hely.

### A Grafana jelszo nincs a gitben

```bash
openssl rand -base64 24 | tr -d '\n' > /root/.secrets/grafana-admin-password
kubectl create namespace monitoring
kubectl -n monitoring create secret generic grafana-admin \
    --from-literal=admin-user=admin \
    --from-file=admin-password=/root/.secrets/grafana-admin-password
```

A `tr -d '\n'` itt is szamit, ugyanabbol az okbol, mint a Forgejonal.

**A namespace ELOTT kell letrehozni,** vagy legalabbis a Grafana podja addig
`CreateContainerConfigError`-ban all. Az Application `CreateNamespace=true`-val fut,
tehat ha kesobb keszul a Secret, magatol helyreall.

A `monitoring` namespace **szandekosan nem kap PSA cimket**, ellentetben az `apps`-szal:
a node-exporter `hostNetwork`-ot es `hostPath`-ot hasznal, amit a `baseline` elutasitana.

### Mit talalt az elso napjan

`NodeClockNotSynchronising` a masteren, es valodi volt: az ora **0.687 masodpercet
sietett, korrekcio nelkul**. A DHCP a router IPv6 link-local cimet adta NTP szervernek,
ami interfesz-hatokor nelkul elerhetetlen, a `FallbackNTP` pedig sosem kerult sorra,
mert a systemd csak akkor nyul hozza, ha EGYETLEN szerver sincs konfiguralva.

A teljes meres es a javitas a `docs/hosts/k3s-cluster.md` "Clock synchronisation"
szakaszaban. Itt csak a lenyeg: **ez a stack elso napjan talalt egy hibat, ami havak ota
allt fenn es `date -u`-val nem latszott** - 0.687 masodperc a `date` egy masodperces
felbontasa alatt van.

### Ket dolog, ami elsore rosszul ment

**A Grafana persistence melle `deploymentStrategy: Recreate` is kell, es ez kimaradt.**
A chart alapertelmezese `RollingUpdate`. Egy RWO Longhorn koteten ez holtpont: az uj pod
`FailedAttachVolume`-mal var a kotetre, a regi pedig sosem all le, mert az uj nem lesz
Ready. 2026-08-28-an 25 percig allt igy, es emiatt a Grafana memoria-limit emelese sem
lepett eletbe:

```
Warning  FailedAttachVolume  25m  attachdetach-controller
  Waiting for detach for volume "pvc-8d6accc7-..."
  Volume is already used by pod(s) monitoring-grafana-765dcb66d6-fwt9j
```

Pontosan ugyanaz a csapda, ami a Forgejo Deploymentjenel ki van irva a manifestbe -
csak oda beirtam, ide nem. **Barmi, aminek RWO kotete van, `Recreate`-tel megy.** A regi
pod addig kiszolgalt, tehat kiesés nem volt, de az uj ertekek nem ertek foldet.

**A `RollingUpdate` -> `Recreate` valtas merge patch-csel NEM megy.** A javitas
kipusholasa utan az Argo CD otszor probalta es feladta, ezzel a hibaval:

```
Deployment.apps "monitoring-grafana" is invalid: spec.strategy.rollingUpdate:
  Forbidden: may not be specified when strategy `type` is 'Recreate'
```

Az elo objektumban ott ul a `rollingUpdate: {maxSurge: 25%, maxUnavailable: 25%}`, amit
az API szerver defaultolt oda. A patch a `type`-ot atirja, de a regi blokkot **nem
tavolitja el**, es az igy keletkezo objektum ervenytelen. A manifest kozben vegig jo
volt - a `helm template` `{type: Recreate}`-et ad, `rollingUpdate` nelkul -, tehat ez
tisztan az elo objektum es a patch-szemantika problemaja. A `ServerSideApply=true` sem
oldja meg: nem tavolit el olyan mezot, amit mas manager birtokol.

Egyszeri JSON patch oldja fel, ami kifejezetten **torli** a mezot:

```bash
kubectl -n monitoring patch deploy monitoring-grafana --type=json \
  -p='[{"op":"remove","path":"/spec/strategy/rollingUpdate"},
       {"op":"replace","path":"/spec/strategy/type","value":"Recreate"}]'
```

Utana az Argo CD szinkronja atmegy, es a gitbol tovabbra is `Recreate` jon. **Ez barmely
mar letezo Deploymentre igaz**, nem csak a Grafanara - ha egy RWO kotetet kap egy addig
RollingUpdate-es Deployment, ez a ket lepes kell hozza.

**Helm forras eseten a `status.sync.revision` NEM a git commit.** A SUC szakaszban az
all, hogy ha egy valtozas nem latszik, hasonlitsd a `status.sync.revision`-t a
`git rev-parse HEAD`-hez. **Ez a `monitoring` Applicationre nem mukodik**, mert annak a
forrasa Helm chart, nem git path:

```
$ kubectl -n argocd get app monitoring -o jsonpath='{.status.sync.revision}'
88.6.0
```

A chart verzioja jon vissza, ami sosem valtozik egy values-modositastol. Itt a magan az
objektumon kell nezni, hogy landolt-e - peldaul
`kubectl -n monitoring get alertmanager -o jsonpath='{.items[0].spec.configSecret}'`.

### Uzemeltetesi apro dolgok, amik elsore meglepnek

**A `Watchdog` riasztas mindig tuzel, es ez szandekos.** Nem hiba es nem kell
elnemitani: azt bizonyitja, hogy maga a riasztasi lanc el. Ha egyszer eltunik, az a
jelzes.

**Egy javitas utan a riasztas nem azonnal all el.** Olvasd el a szabaly kifejezeset,
mielott azt hiszed, hogy a javitas nem hatott:

```
NodeClockNotSynchronising
  expr: min_over_time(node_timex_sync_status[5m]) == 0 and node_timex_maxerror_seconds >= 16
  for : 600s
```

Az ora javitasa utan a metrika azonnal `1`-re valt, de a riasztas meg ~5 percig tuzel,
amig az `[5m]`-es ablakbol ki nem esik az utolso `0`. A `for: 600s` **csak a
bekapcsolasra** vonatkozik, a megszunesre nem.

**A chartot rendereld le helyben, mielott pusholsz.** Az Argo CD Helm forrast hasznal,
tehat egy rossz ertek csak a clusteren derulne ki:

```bash
helm template monitoring prometheus-community/kube-prometheus-stack --version 88.6.0 \
    -n monitoring -f <a values blokk kimasolva> > /tmp/rendered.yaml
```

Igy derult ki a push ELOTT, hogy a kilenc ServiceMonitor helyes, a tiltott
komponensekre egy sem keszul, a PVC-k es a retention jok, es a Grafana Ingress alakja
pontosan az, amit a Tailscale operator var. Telepites utan 22/22 target `up`.

**A Grafana memoria-limitje 512Mi-rol 768Mi-re ment.** Merve 405Mi-n allt be, ami a regi
limit 79%-a. Stabil volt, nem kuszott, de egy OOMKill itt csendes hiba: a pod
ujraindul, a dashboardok ConfigMapbol visszajonnek, es semmi nem mondja meg, miert volt
egy lyuk a grafikonokon.

### A `cluster` cimke, es hogy hol NEM latszik

```yaml
prometheus:
  prometheusSpec:
    externalLabels:
      cluster: homelab-k3s
```

Enelkul a chart szabalyainak szovege ugy vegzodik, hogy **`on cluster .`** - a
`cluster` cimkere hivatkoznak, az pedig ures. A 2026-08-28-i elso valodi riasztasokon
pontosan igy jott ki.

**Az `external_labels` NEM kerul ra a tarolt idosorokra.** Ez a leggyakoribb
felreertes: a Prometheus akkor adja hozza, amikor riasztast kuld az Alertmanagernek,
illetve federacionál es remote-write-nal. A **sajat lekerdezeseiden egyaltalan nem
fogod latni**, sem a regi, sem az uj adatokon. A riasztasokon es a Grafana-ertesiteseken
viszont igen.

**Egy cimke megvaltoztatasa uj riasztas-identitast hoz letre.** A valtas utan atmenetileg
ket `Watchdog` volt bent az Alertmanagerben - egy `cluster=homelab-k3s`-szel es egy
`cluster=null`-lal. A regi a `resolve_timeout: 5m` letelte utan magatol eltunt. Nem hiba,
de aki eloszor latja, azt hiszi, duplikalodott valami.

### A config-reloader miatt sem a Prometheus, sem az Alertmanager nem indul ujra

Merve mindket valtoztatasnal (`configSecret` csere, `externalLabels` felvetele): a pod
**ugyanaz maradt** - a Prometheusnal 83 perces uptime-mal -, es az uj konfig megis
eletbe lepett. A sidecar figyeli a mountolt Secretet es helyben ujratolt.

Ebbol ket dolog kovetkezik. Egy: **a pod uptime-jabol nem lehet arra kovetkeztetni, hogy
a konfig regi.** Ketto: az ellenorzes a futo konfigon tortenjen, ne a CR-en -
`/api/v1/status/config` a Prometheusnal, `/api/v2/status` az Alertmanagernel.

### Amit az elso napjan ellenorizhetoen elkapott

Nem elmeleti haszon. A Grafana beragadt rolloutjara (amit en okoztam a hianyzo
`Recreate`-tel) magatol kiadta a `KubeDeploymentRolloutStuck` es a `KubePodNotReady`
riasztast 15 perc utan, es a javitas utan a RESOLVED is megjott Telegramra. Plusz az
elso napon a `NodeClockNotSynchronising`-ot, ami honapok ota fennallo valodi hiba volt.

Ket hiba, amirol enelkul csak akkor szereztunk volna tudomast, ha valaki eppen odanez.

### Az Alertmanager Telegramra kuld

**Nem az ntfy-ra, es ennek meresi oka van.** Az ntfy a homelab bevett csatornaja
(`https://ntfy.lan/homelab-digest` a Caddyn at, 192.168.0.208), de a k3s cluster a
**masik helyszinen** van, es nem eri el. Merve a masterrol es egy podbol is:

```
curl --max-time 8 -k --resolve ntfy.lan:443:192.168.0.208 https://ntfy.lan/   ->  000
ip route get 192.168.0.208   ->  via 192.168.1.1 dev eno1
```

A `192.168.0.0/24` utvonala a helyszini gatewayen megy ki, tehat kisetal az internetre
es elhal - **nincs subnet route hazafele**. (A meglevo route a masik iranyba mutat: az
`opt3060-i3` hirdeti a `192.168.1.0/24`-et a tailnetre.) Az `api.telegram.org` viszont a
clusterbol elerheto, merve. Ha valaha kell az ntfy, az egy home-oldali subnet router
lenne - kulon dontes, nem mellekesen elintezendo.

A **teljes** `alertmanager.yaml` egy kezzel keszitett Secretbol jon
(`alertmanagerSpec.configSecret`), mert ket titkot tartalmaz. A sablon itt van, hogy
reprodukalhato maradjon - a `.env.example` mintajara:

```yaml
# alertmanager.yaml
global:
  resolve_timeout: 5m
route:
  group_by: ["alertname", "namespace"]
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 12h
  receiver: telegram
  routes:
    # A Watchdog SZANDEKOSAN tuzel mindig - a riasztasi lanc eletjele. Ide nem
    # kell ertesites belole, kulonben 12 orankent szolna a semmirol. Ha egyszer
    # dead man's switchet akarsz belole, az egy Kuma push URL lenne receiverkent.
    - matchers: ['alertname = "Watchdog"']
      receiver: "null"
receivers:
  - name: "null"
  - name: telegram
    telegram_configs:
      - bot_token: <BOT_TOKEN>
        chat_id: <CHAT_ID>
        parse_mode: HTML
        message: |-
          <b>{{ .Status | toUpper }}</b> {{ .CommonLabels.alertname }}
          {{ range .Alerts }}{{ .Annotations.summary }}
          {{ .Annotations.description }}
          {{ end }}
```

**A cel egy kulon Telegram csoport, NEM az AI digest chatje.** A
`/root/.secrets/telegram-bot` masodik sora a `scripts/ai-digest.py` celja - a sajat
privat chated a bottal (pozitiv azonosito). A riasztasok kulon "Homelab alerts"
csoportba mennek (negativ azonosito), hogy a napi hirosszefoglalo es az infra-riasztas
ne keveredjen.

A csoport azonositojat a bot csak akkor tudja megmondani, ha **latott** ott uzenetet -
a bot alapbol csak kuld, sosem fogad, ezert a `getUpdates` uresen jon vissza:

```bash
TOK=$(sed -n '1p' /root/.secrets/telegram-bot)
curl -s "https://api.telegram.org/bot${TOK}/getUpdates" | jq '.result[].message.chat'
```

A sorrend tehat: csoport letrehozasa -> a bot hozzaadasa -> **egy tetszoleges uzenet a
csoportba** -> csak ezutan adja vissza a `getUpdates` az azonositot.

> **Ha a csoportot Telegram kesobb szupercsoportta alakitja, az azonosito MEGVALTOZIK**,
> es a riasztasok csendben elhalnak - a `..._failed_total{reason="clientError"}` szamlalo
> viszont jelezni fogja. Ilyenkor ugyanez a lepessor kell ujra.

Letrehozas:

```bash
kubectl -n monitoring create secret generic alertmanager-telegram \
    --from-file=alertmanager.yaml=/root/.secrets/alertmanager.yaml
```

**Az elleorzes ne a telefonod legyen.** Az Alertmanager sajat szamlaloi mondjak meg, hogy
a kezbesites tenylegesen sikerult-e, nem csak hogy megprobalta:

```bash
curl -s http://alertmanager-operated.monitoring.svc:9093/metrics \
  | grep -E '^alertmanager_notifications(_failed)?_total\{integration="telegram"'
```

Egy teszt-riasztas beszurasa (2 perc mulva magatol lejar, tehat FIRING es RESOLVED
uzenetet is general):

```bash
curl -X POST -H 'Content-Type: application/json' \
  -d '[{"labels":{"alertname":"TestAlert","severity":"info"},
        "annotations":{"summary":"teszt"},
        "startsAt":"<most>","endsAt":"<most+2perc>"}]' \
  http://alertmanager-operated.monitoring.svc:9093/api/v2/alerts
```

2026-08-28-i eredmeny: `notifications_total{telegram} 6`, es mind a het `failed_total`
ok (`authError`, `clientError`, `serverError`, `rateLimited`, a ket timeout es az
`other`) nulla.

A szamlalot **ne kozvetlenul a teszt utan olvasd**: elsore 2-t mutatott, mert a
csoportositas es a resolve-uzenetek meg uton voltak. A vegleges szam 6 lett (a teszt
FIRING+RESOLVED, plusz a beragadt Grafana rolloutra magatol kiadott
`KubeDeploymentRolloutStuck` es `KubePodNotReady` resolve-jai).

> **Csereles kozben van egy csendes ablak.** Amikor a `useExistingSecret: true` elvette a
> chart sajat Secretjet, de a `configSecret` meg nem lepett eletbe, az operator naploja
> ezt irta: `config secret not found, using default Alertmanager configuration`. Ket
> masodperc volt, es itt artalmatlan, mert a beepitett default mindent a `null`
> receiverbe kuld - de abban az ablakban riasztas nem ment volna sehova.

**A Secret kulcsa `alertmanager.yaml` kell legyen** - a prometheus-operator ezt varja,
mas nevvel az Alertmanager ures konfiggal indul.

A `configSecret` melle **`useExistingSecret: true` is kell**. Enelkul a chart melle
generalna egy sajat, alapertelmezett configot tartalmazo Secretet
(`alertmanager-monitoring-kube-prometheus-alertmanager`). Az operator nem hasznalna, de
ott ulne - es aki debugolas kozben beleolvas, azt hinne, hogy az a futo konfig.
Ellenorizve `helm template`-tel: a kapcsoloval a chart nem general Secretet.

PVC-je nincs: az allapota nemitasokbol all, ami ujrainduláskor elveszik.

## Longhorn felulet: `https://longhorn.tailc6abe2.ts.net`

Eddig csak `kubectl port-forward`-dal volt elerheto, ami egy folyamat a 109-en es a
session-nel egyutt meghal. Az Ingress a `longhorn-backup` Application alatt van
(`k8s/manifests/longhorn/ingress.yaml`), ugyanaz a Tailscale minta.

> **FIGYELEM: a Longhorn feluleten nincs hitelesites.** Az argocd-nek es a forgejonak
> van sajat bejelentkezese, ennek nincs. Aki eleri, az kotetet torolhet es mentest
> allithat vissza. A vedelmet itt kizarolag a tailnet adja.
>
> Ebbol ket dolog kovetkezik: ez az Ingress **soha** nem kerulhet a Pangolin ala vagy
> mas publikus utra, es ha valaha megosztott eszkoz kerul a tailnetre, a dontes
> ujragondolando (a Tailscale ACL-jeivel szukitheto, melyik eszkoz eri el).

## coredns: egy replika volt

A 2026-08-28-i SUC drain logja mutatta meg, hogy egyetlen node kiuritese ezt viszi
magaval: `argocd-server`, **`coredns`**, `metrics-server`, `longhorn-ui`, mind a negy
`csi-*` controller, az `instance-manager` es a workload podja. A `coredns`
`readyReplicas: 1` volt, tehat egy drain rovid idore elvitte a cluster DNS-et is.

```bash
kubectl -n kube-system scale deployment coredns --replicas=2
```

**Miert nem a `.skip` utja, mint a local-path-nal:** a k3s becsomagolt
`/var/lib/rancher/k3s/server/manifests/coredns.yaml`-je **nem tartalmaz `replicas`
mezot** (ellenorizve grep-pel a masteren). Amit a manifest nem ir elo, azt az
ujraalkalmazas nem is allitja vissza - ellentetben az `is-default-class` annotacioval,
amit a k3s minden induláskor felulirt. A `.skip` itt karos is lenne: befagyasztana a
coredns verziojat, ugyanugy, ahogy a local-path-provisionert v0.0.34-en tartja.

**Ezt viszont a kovetkezo k3s ujrainduláskor ellenorizni kell**, mert a 2026-04-11-i
local-path patch pontosan azert veszett el negy honapra, mert ez a lepes elmaradt:

```bash
kubectl -n kube-system get deploy coredns -o jsonpath='{.spec.replicas}'
```

## NetworkPolicy az `apps` namespace-ben (2026-08-28)

Ket szabaly, ket fajlban. A tiltas a namespace-nel ul
(`manifests/platform/namespace-apps.yaml`), az engedely az alkalmazasnal
(`manifests/forgejo/networkpolicy.yaml`) - hogy egy uj app ne a Forgejo
fajljabol kerjen maganak engedelyt, es hogy a Forgejo eltavolitasa a kivetelt
vigye, a tiltast ne.

| Szabaly | Mit tesz |
|---|---|
| `default-deny-ingress` | `podSelector: {}`, csak `Ingress`. Az `apps` minden podja zart befele |
| `forgejo-allow-tailscale-ingress` | a Forgejo 3000-es portja nyitva EGY podnak: a Tailscale operator altal ehhez az Ingresshez generalt proxynak |

Nem a teljes `tailscale` namespace-t engedjuk at, hanem a
`tailscale.com/parent-resource: forgejo` cimkeju podot. A pod NEVE valtozik egy
Ingress-ujraletrehozasnal (`ts-forgejo-99j4d-0`), a cimke nem.

### Amit meg kellett merni, mielott ez felkerult

**A kubelet probe-jai atmennek a default-deny alatt.** A k3s-io/k3s#10030 szerint
egy default-deny megolte a liveness es readiness probe-okat, es az issue lezart
allapotban van anelkul, hogy a javitas verzioja kiderulne. Eldobhato
namespace-ben lemerve ezen a verzion (v1.36.4+k3s1, beepitett kube-router
v2.6.3-k3s1): a pod **60 masodpercen at Ready maradt**, 5 masodperces
probe-periodus es 2-es kuszob mellett - ha blokkolva lenne, 10 masodperc alatt
kiesik. Tehat nincs szukseg node-kivetelre. Ha egy jovobeli k3s frissites utan
egy pod a policy felrakasa utan ~10 masodperccel NotReady-re valt, ez az elso
hely, ahova nezni kell.

**Az `apps`-ba egyetlen ServiceMonitor sem nez bele**, tehat a Prometheusnak nem
kell kivetel. Ha valaha kerul ide ServiceMonitor, ez a szabaly az elso, amit
bovitni kell, kulonben a target csendben `down` lesz.

**A netpol controller tenyleg fut**, ezt sem feltetelezzuk: a masteren 215
`KUBE-ROUTER` iptables szabaly es `KUBE-NWPLCY-*` lancok vannak, a k3s log pedig
kiirja: `Starting network policy controller version v2.6.3-k3s1`.

### Ahogy bizonyitva lett

Egy nem-ervenyesitett NetworkPolicy rosszabb a semminel, mert vedelemnek latszik.
Ezert a proba MINDKET iranyt merte, es a sorrend szamit:

1. policy **elott** egy masik namespace podja eleri a `forgejo.apps.svc:3000`-et
   (enelkul a "mar nem eri el" semmit nem bizonyitana)
2. policy **utan** ugyanaz a pod nem eri el
3. a Forgejo a tailneten valtozatlanul HTTP 200
4. a pod `Ready`, ujrainditasok szama **0**

A kube-router nehany masodperc alatt forditja a policyt iptables szabalyokra, a
merest tehat nem szabad azonnal elvegezni - a proba ezert var a tiltas
megjelenesere.

### Amit szandekosan NEM tilt

**Az egress szabad marad.** A Forgejonak DNS kell, es kesobb git remote, webhook
vagy avatar-lekeres is jöhet; egy egress-tiltas most tobbet torne el, mint
amennyit vedene.

**A tobbi namespace nyitva.** A `monitoring` a kovetkezo jelolt, de ott tobb a
mozgo alkatresz: a Prometheusnak minden namespace-t el kell ernie, a Grafana a
tailneten van, es az operator mindharommal beszel. A `kube-system` es a
`tailscale` szandekosan marad ki - a coredns-t minden pod hivja, a Tailscale
proxykhoz pedig host szintu forgalom erkezik.

Az `argocd` (7 szabaly) es a `longhorn-system` (6) sajat NetworkPolicykat hoz a
Helm chartjabol; azokat nem mi irtuk es nem is nyulunk hozzajuk.
