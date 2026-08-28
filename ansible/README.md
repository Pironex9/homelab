# ansible

Az `ansible/` mappa a K3s cluster **2. retegenek** (k3s telepites es config) IaC leirasa.
A cel nem ujraepites: a meglevo, futo clustert irja le, es a `k3s-io/k3s-ansible`
collection idempotens futasaval tartja szinkronban.

A retegek szetvalasztasa es az indoklas: `private/k3s-iac-kutatas-2026-08-24.md`.
Rovid osszefoglalva: a Terraformnak nincs API-ja amivel egy bare-metal node-ot
kezelhetne, ezert a 2. reteg Ansible, a 3. reteg (cluster tartalom) pedig kesobb
ArgoCD lesz.

## Elofeltetel

```bash
apt install -y pipx
pipx install --include-deps ansible      # ansible-core 2.19.x
pipx inject ansible netaddr              # az ansible.utils.ipaddr szurokhoz
ansible-galaxy collection install git+https://github.com/k3s-io/k3s-ansible.git,main
```

A Debian 12 apt-os `ansible-core`-ja **2.14.18**, a collection viszont **2.15+**-t
ker, ezert nem az apt-os csomag megy.

A `pipx` a `~/.local/bin`-be telepit. Ez interaktiv shellben a PATH-on van, **cronban
nem** - ott a teljes utat kell kiirni.

## Hasznalat

Mindig eloszor `--check`, ez a Proxmox-oldali `tofu plan` megfeleloje:

```bash
cd ansible
ansible-playbook k3s.orchestration.site --check --diff
```

Csak akkor futtasd `--check` nelkul, ha a diffet atnezted. Konvergalas elott
erdemes egy friss mentest keszitteni: `scripts/k3s-backup.sh`.

## Amit ez a leiras kezel

| Ami | Hol |
|---|---|
| k3s verzio (v1.34.5+k3s1) | `group_vars/k3s_cluster.yml` |
| `--node-ip`, `--advertise-address`, `--flannel-iface`, `--secrets-encryption` | `host_vars/<node>.yml` |
| api endpoint es port | `group_vars/k3s_cluster.yml` |
| cluster token | `/root/.secrets/k3s-token`, a repon **kivul** |

## Amit szandekosan NEM kezel

Ezek a cluster belsejeben elnek, es egy Ansible futas nem allitja vissza oket. Amig
a 3. reteg (ArgoCD) nincs meg, ezek kezi allapotok:

- **`local-storage.yaml.skip`** a masteren, `/var/lib/rancher/k3s/server/manifests/`
  alatt. Ez akadalyozza meg, hogy a k3s minden induláskor visszairja a
  `local-path` StorageClass-t default-kent. Nelkule ket default StorageClass lesz.
- A **Longhorn** Helm release es a `longhorn` StorageClass `is-default-class` patch-e.
- Barmely Ingress, PVC vagy egyeb cluster objektum.

## Csapdak

- A `k3s_version` emelese a `site.yml`-ben **nem** tamogatott in-place upgrade ut.
  2026-08-28 ota a frissitest a **system-upgrade-controller** vegzi, a
  `k8s/manifests/system-upgrade/plans.yaml`-bol, ArgoCD-n keresztul - se ssh, se kezi
  kubectl. Reszletek: `docs/hosts/k3s-cluster.md`, "Version upgrades".
  A `k3s_version` itt azt irja le, ami **telepitve van**, es a frissites utan kezzel
  kell atvezetni. Ha nem teszed meg, a kovetkezo `site.yml` futas visszaminositi a
  clustert a regi verziora.
- Az `extra_server_args` a **teljes** `INSTALL_K3S_EXEC`, ezert kezdodik `server`-rel.
  Az agenteknel viszont az `agent --server https://...` reszt a role teszi ele, oda
  csak a tovabbi kapcsolok jonnek.
- **A `--secrets-encryption` kihagyasa a `host_vars/opt5060-i5.yml`-bol nem kozombos.**
  2026-08-28 ota a Secretek titkositva vannak a `state.db`-ben. Ha egy `site.yml` futas
  leszedne a kapcsolot, a szerver titkositas nelkul indulna, es **soha nem lenne ready**:
  a `/readyz` vegtelenul `[-]informer-sync failed`-et adna, mert a Secret informer
  `identity transformer tried to read encrypted data`-val elhasal. A nem-Secret
  eroforrasok kozben olvashatok maradnak, tehat a hiba nem nyilvanvalo. Megmerve
  eldobhato clusteren ugyanaznap.
- `manage_firewall: false`. A collection alapertelmezese `true` lenne, ami tuzfal
  szabalyokat kezdene felvenni olyan gepeken, ahol se ufw, se firewalld nem aktiv.
- `user_kubectl: false`. `true` eseten a role a masteren `~/.kube/config.new`-t irna
  es egy `k3s-ansible` nevu contextet venne fel, a mar meglevo hozzaferes melle.
- Az inventory a node **neveit** hasznalja, nem IP-t. A 109 `/etc/hosts`-ja ezeket a
  Tailscale cimre oldja fel, igy az inventory tulel egy LAN subnet valtast is. A
  `--node-ip` ettol fuggetlenul LAN cim marad.
- **A collection nem tolti le a telepito szkriptet, ha a verzio mar egyezik** - de utana
  feltetel nelkul lefuttatja. Egy kezzel telepitett clusteren ez
  `[Errno 2] No such file or directory: /usr/local/bin/k3s-install.sh`-val elhasal.
  Ezert van a sajat `site.yml` wrapper egy `get_url` pre_taskkal. Ne futtasd kozvetlenul
  a `k3s.orchestration.site`-ot, mindig a helyi `site.yml`-t.
- **A `kubeconfig` valtozot szandekosan nem alapertelmezetten hagyjuk.** Ha az erteke
  `~/.kube/config.new`, a role a 109 sajat `~/.kube/config`-jaba fesuli be a master
  kubeconfigjat `k3s-ansible` contextkent, aktivva teszi, es a szervercimet az
  `api_endpoint`-ra (192.168.1.101) irja - ami a 109-rol nem routolhato. Az elso eles
  futas igy akasztotta meg a `kubectl`-t.

## Idempotencia

Ket egymas utani eles futas utan a unit fajlok sha256-ja **bajtra azonos**. Ot task
mindig `changed`-et jelent, ez a role felepitesebol adodik, nem drift:

| Task | Miert mindig changed |
|---|---|
| `Run K3s install script` | `changed_when: true`, feltetel nelkul |
| `Enable and start K3s service/agent` | `state: restarted`, szandekosan minden futasnal |
| `Add the token ... to the environment` | a telepito szkript ujragenralja az env fajlt es kitorli a tokent, a role utana visszairja |

**Egy eles futas ujraindítja a k3s-t mind a harom node-on.** Nincs cordon vagy drain,
tehat futo workloaddal ezt karbantartasi ablakban kell csinalni.

## NTP - sajat play, nem a collection resze

A `site.yml` elso jatszmai kozott van egy sajat play, ami minden node-ra kiteszi a
`/etc/systemd/timesyncd.conf.d/10-router-ipv4.conf` drop-int (`ntp_server` valtozo,
`group_vars/k3s_cluster.yml`).

**Miert kellett:** 2026-08-28-ig egyik node sem volt megbizhatoan szinkronban, es a
masteren egyaltalan nem - az oraja 0.687 masodpercet sietett, korrekcio nelkul. A DHCP a
router IPv6 **link-local** cimet adja NTP szervernek, ami interfesz-hatokor nelkul
elerhetetlen, a `FallbackNTP` pedig sosem kerul sorra, mert a systemd csak akkor nyul
hozza, ha egyetlen szerver sincs konfiguralva. A teljes meres:
`docs/hosts/k3s-cluster.md`, "Clock synchronisation".

**Miert itt, es nem kezi lepeskent:** egy ujraepitett node kulonben visszaterne a torott,
DHCP-bol jovo szerverhez. A `k3s-io/k3s-ansible` collection nem kezel NTP-t, ezert sajat
task.

