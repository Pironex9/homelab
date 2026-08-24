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

## Amit az Argo CD NEM kezel

A **Longhorn Helm release-t** szandekosan nem adoptaljuk. Ismert utkozes: az Argo CD a
Helm hookokat `PreSync`-kent futtatja, ezert a Longhorn pre-upgrade jobja mar a legelso
szinkronnal lefut, olyankor amikor a service account meg nem letezik, es elhasal.
Lasd longhorn/longhorn#6415.

Ez nem korlat: amit deklarativva akarunk tenni, az nagyreszt nem a Helm release, hanem
sima objektum - a Longhorn `BackupTarget` es `RecurringJob` kulon CRD-k, a
NetworkPolicy, a Pod Security Admission es a resource limitek pedig eleve azok. A
Longhorn telepiteset tovabbra is a Helm kezeli.
