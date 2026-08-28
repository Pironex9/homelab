**Date:** 2026-08-28
**Cluster:** 3x Dell OptiPlex, 192.168.1.0/24 (separate location, Tailscale access only)

---

# K3s Version Upgrades

How the k3s version is bumped: two edited fields in git, the system-upgrade controller, and the one-minor-at-a-time rule it does not enforce for you.

Split out of the [K3s Cluster host page](../hosts/k3s-cluster.md) on 2026-08-28,
which had grown to 1983 lines and six unrelated projects. The host page keeps the
machine reference - hardware, addressing, live state, access - and this page keeps
the work. Nothing below was rewritten in the move.

---

## Version upgrades (system-upgrade-controller)

Set up 2026-08-28. Before that, upgrading k3s meant SSH plus a manual
`INSTALL_K3S_VERSION` re-run on three machines, and the Ansible layer had no path for
it at all.

Now the target version lives in git. Argo CD syncs the `Plan` objects, the
[system-upgrade-controller](https://github.com/rancher/system-upgrade-controller) (SUC)
runs the upgrade node by node. No SSH, no manual `kubectl`.

| Piece | Where |
|-------|-------|
| SUC controller + CRD, upstream v0.20.1, unmodified | `k8s/manifests/system-upgrade/{controller,crd}.yaml` |
| The two Plans (this is the file you edit) | `k8s/manifests/system-upgrade/plans.yaml` |
| Argo CD Application | `k8s/apps/system-upgrade.yaml` |

To upgrade: change both `version:` fields in `plans.yaml`, commit, push. That is the
whole procedure.

### One minor at a time

Skipping an intermediate minor is **not supported**, and the SUC will not stop you - it
will happily run an invalid path. The 2026-08-28 upgrade went in three hops, each one
verified before the next started:

| Hop | From | To | Wall clock | API outage |
|-----|------|----|-----------|------------|
| 1 | v1.34.5+k3s1 | v1.34.11+k3s1 | ~440 s | one 20 s poll |
| 2 | v1.34.11+k3s1 | v1.35.8+k3s1 | ~220 s | one 20 s poll |
| 3 | v1.35.8+k3s1 | v1.36.4+k3s1 | ~200 s | one 20 s poll |

Hop 1 was deliberately a patch-only hop inside the 1.34 line. If the Plan, the RBAC or
the `nodeSelector` had been wrong, it would have surfaced there, where rolling back is
trivial - not in the middle of a minor.

Most of hop 1's 440 s was pulling the `rancher/k3s-upgrade` image for the first time.
The later hops are the honest steady-state number: **3 to 4 minutes per hop**.

### Where the version number comes from - not the newest tag

**This is a correction to what the 2026-08-28 upgrade actually did.** All three hops
took the newest existing tag rather than what k3s itself calls stable, and every one of
them landed one patch *ahead* of the release channel:

| Hop target used | Channel said, checked 2026-08-28 |
|---|---|
| v1.34.11+k3s1 | v1.34.10+k3s1 |
| v1.35.8+k3s1 | v1.35.7+k3s1 |
| v1.36.4+k3s1 | v1.36.3+k3s1 (`stable` and `latest` both) |

`v1.36.4+k3s1` is additionally marked `prerelease: true` on GitHub, published
2026-08-27 - one day before it was installed here. It is not a release candidate and
nothing is broken by it, but upstream had not promoted it yet.

The check that was missing:

```bash
curl -s https://update.k3s.io/v1-release/channels | jq -r '.data[] | "\(.id) \(.latest)"'
```

**This cannot be undone.** k3s does not support downgrading, so the only way back onto
the channel is forward, when the channel catches up. The rule from here: the target
version should appear in its channel, and going ahead of it has to be a deliberate
decision rather than a side effect of reading the releases page.

### The `version` field is not the image tag

The Plan takes `version: v1.36.4+k3s1`, with a **plus**. The SUC turns that into the
image tag `v1.36.4-k3s1`, with a **hyphen**, because a `+` is not legal in a Docker tag.

A typo here does not fail loudly - the plan just sits there while the job's pod cannot
pull. Check that the tag exists before committing:

```bash
curl -s -o /dev/null -w '%{http_code}\n' \
  https://hub.docker.com/v2/repositories/rancher/k3s-upgrade/tags/v1.36.4-k3s1
```

`200` means the tag is published. All three tags used on 2026-08-28 were checked this
way first.

### What to check between hops

```bash
kubectl get nodes -o wide                 # all three on the new version, none cordoned
kubectl get nodes.longhorn.io -n longhorn-system   # every node and disk Ready
kubectl get applications -n argocd        # all Synced/Healthy
./scripts/longhorn-backup-check.sh        # the 5-step gate
```

!!! danger "There is one control plane"
    While the master upgrades, the Kubernetes API is unreachable for a couple of
    minutes. That is the price of the non-HA setup, not a fault. Argo CD, `kubectl` and
    anything reading the API will fail during that window.

    The recovery path is SSH, and it stays available the whole time - the upgrade
    replaces the binary and restarts the service, it does not reboot the node. Verify
    before starting: `ssh nex@opt5060-i5 'sudo -n true'` on all three. Root SSH is
    **not** enabled on these nodes; the user is `nex` with passwordless sudo.

!!! note "`FAILED 1` on the agent jobs is normal"
    After a hop, `kubectl get jobs -n system-upgrade` shows the two agent jobs with
    `COMPLETIONS 1` **and** `FAILED 1`, and two pods stuck in `Unknown`.

    That is not a failed upgrade. The k3s agent restarts underneath the pod that is
    performing the upgrade, so the first attempt's pod loses its kubelet and goes
    `Unknown`; the retry finishes the job. The server plan never shows this, because the
    master's job is already done by the time the API returns. Judge the outcome by
    `kubectl get nodes`, not by the pod list.

### `drain`, and the PDB that looked like it would block it

The Plans use `drain` (2026-08-28). Before that they used `cordon: true`, on the
assumption that with zero volumes there is nothing to evict. **That assumption was
wrong,** and the way it was wrong is the useful part.

Longhorn keeps one PodDisruptionBudget per node for its `instance-manager` pod. Read with
**zero** volumes on the cluster, all three said:

```
minAvailable=1  currentHealthy=1  desiredHealthy=1  disruptionsAllowed=0
```

`disruptionsAllowed: 0` means the eviction API rejects that pod. And the pod is owned by
an `InstanceManager` CR, **not** a DaemonSet, so `--ignore-daemonsets` does not cover it.
On paper, a drain stalls there.

It does not, and one drain settled it:

```
$ kubectl drain opt3050-i5 --ignore-daemonsets --delete-emptydir-data --force --timeout=120s
node/opt3050-i5 cordoned
Warning: ignoring DaemonSet-managed Pods: ... longhorn-manager-sdwg6
evicting pod longhorn-system/instance-manager-067cfdfdabf25fe0c8f8a8a0becb9fd3
pod/instance-manager-067cfdfdabf25fe0c8f8a8a0becb9fd3 evicted
node/opt3050-i5 drained
```

After `uncordon` all three PDBs came back on their own, and every pod returned to
`Running`.

#### Repeated on a live volume, and the mechanism turned out to be different

The empty-cluster run left one question open: with volumes present, the last-replica
check actually has something to check. That was measured on 2026-08-28 with Forgejo
running, a 10 GiB volume and three healthy replicas, one per node, with the workload pod
on the node being drained:

```
node/opt3050-i5 cordoned
evicting pod tailscale/ts-forgejo-99j4d-0
evicting pod apps/forgejo-6dcd59d94d-gvz7c
evicting pod longhorn-system/instance-manager-067cfdfdabf25fe0c8f8a8a0becb9fd3
error when evicting pods/"instance-manager-067..." -n "longhorn-system"
  (will retry after 5s): Cannot evict pod as it would violate the pod's disruption budget.
pod/ts-forgejo-99j4d-0 evicted
pod/forgejo-6dcd59d94d-gvz7c evicted
evicting pod longhorn-system/instance-manager-067cfdfdabf25fe0c8f8a8a0becb9fd3
error when evicting pods/"instance-manager-067..." -n "longhorn-system"
  (will retry after 5s): Cannot evict pod as it would violate the pod's disruption budget.
evicting pod longhorn-system/instance-manager-067cfdfdabf25fe0c8f8a8a0becb9fd3
pod/instance-manager-067cfdfdabf25fe0c8f8a8a0becb9fd3 evicted
node/opt3050-i5 drained
```

**The PDB does reject the eviction, twice, and the drain's own retry absorbs it.** So the
earlier explanation on this page - "Longhorn drops the PDB in response to the cordon" -
was wrong. Longhorn removes the PDB when the node no longer runs an engine, which is
*after* the workload pod has gone and the volume has detached. Until then the eviction
API refuses, correctly. On the empty cluster there was no engine to wait for, so the
first attempt succeeded and the retry never showed.

Measured, end to end:

| Stage | Time |
|---|---|
| `kubectl drain` complete (incl. ~10 s of PDB rejections) | 12 s |
| Forgejo pod `Ready` again on `opt3060-i3` | 42 s |
| HTTPS 200 on `/api/healthz` through the Tailscale Ingress | 42 s |
| Third replica back after `uncordon` | 8 s |
| Volume `robustness: healthy` again | 37 s |

The volume went `attached/healthy` on `opt3050-i5` → `attaching/unknown` → `degraded`
with 2 replicas → `attached/healthy` on `opt3060-i3`. Total user-visible outage was
under a minute, against the ~90 s estimated from the 2026-08-24 reattach measurement.

One thing that was claimed but never tested also held: the Tailscale proxy pod
`ts-forgejo-99j4d-0` was evicted with the rest and came back with the same tailnet
identity, because its StatefulSet secret carries the node key. The HTTPS endpoint
recovered without any manual step.

!!! danger "`block-for-eviction` would deadlock this cluster"
    The common advice for Longhorn plus system-upgrade-controller is to set the
    `node-drain-policy` setting to `block-for-eviction` before an upgrade. **Do not do
    that here.** That policy blocks the drain until *every* replica has been rebuilt
    somewhere else. With 3 nodes and the default 3-replica volumes there is no spare
    node to rebuild onto, so the condition can never be satisfied and the upgrade hangs
    forever with a node cordoned.

    That advice assumes more nodes than replicas. This cluster has exactly as many.

    The right setting here is the default, `block-if-contains-last-replica`: draining one
    of three nodes leaves two healthy replicas, so nothing blocks, and the volume runs
    degraded for the length of the upgrade and rebuilds afterwards. Current value,
    checked: `block-if-contains-last-replica`.

What is in both Plans now - the same flags the drain above ran with, field names taken
from the vendored CRD rather than guessed:

```yaml
  drain:
    force: true
    ignoreDaemonSets: true
    deleteEmptydirData: true
    timeout: 300s
```

No `cordon: true` alongside it: `drain` cordons first by itself, so the two together are
redundant.

The `timeout` is deliberately generous, and the live-volume measurement is the reason it
is not cosmetic. There is a window - about 10 seconds here - in which the instance-manager
PDB legitimately refuses the eviction while the volume is still detaching. A tight timeout
would die inside that window and look exactly like a stuck drain. On an empty cluster the
window does not exist, so a tight timeout would have passed the test and failed in
production.

300 s also exists so that a drain which genuinely gets stuck **fails visibly** instead of
hanging forever with a node cordoned. If it ever trips, that is a signal, not a tuning
problem.

`Cannot evict pod as it would violate the pod's disruption budget` on an instance-manager
pod is therefore **normal and transient** - expect it in the log of every drain on a node
holding a running engine. It is only a problem if the drain never gets past it. If that
happens, the fix is a `podSelector` on the Plan that skips the instance-manager pods, not
a shorter timeout and not `disableEviction`.

!!! note "Changing `drain` does not re-run anything"
    After the switch landed, `status.latestHash` on both Plans was unchanged
    (`85914216d295…`, the same value as before), no jobs were created and no node was
    cordoned. The SUC plan hash covers the target version and the upgrade image, not the
    drain configuration.

    That is convenient - editing drain settings is free and never disturbs a running
    cluster. It also means the SUC drain path cannot be exercised by editing the Plan.
    There is a way around that, below.

    A second thing worth knowing about timing: Argo CD picked the commit up about
    5 minutes after the push. If a Plan edit looks like it did not land, check
    `status.sync.revision` against `git rev-parse HEAD` before assuming something broke.

    That check works here because this Application has a **git** source. It does **not**
    work for an Application with a Helm chart source - there `status.sync.revision` is
    the chart version (`88.6.0` for `monitoring`), which never moves when only the values
    change. For those, check the rendered object itself.

#### Exercising the SUC drain path without a version bump (2026-08-28)

The Plan wiring can be tested at the current version, because of how the SUC decides
which nodes still need work. Each node carries the plan's hash as a label:

```
opt3060-i3   plan.upgrade.cattle.io/agent-plan  = 85914216d295…
opt5060-i5   plan.upgrade.cattle.io/server-plan = 85914216d295…
```

Remove that label and the SUC treats the node as not yet upgraded, and runs the whole
job on it - `prepare`, `drain`, `upgrade` - against the version already installed:

```bash
kubectl label node opt3060-i3 plan.upgrade.cattle.io/agent-plan-
```

No git change, no fake version, and the label is written back by the SUC when the job
succeeds. The job started 5 seconds after the label went away and finished in **43 s**.

**What this proved.** The `drain` init container ran with the flags from the Plan and
hit the same PDB behaviour as the manual drain, inside the real SUC path:

```
evicting pod apps/forgejo-6dcd59d94d-gwb6m
evicting pod longhorn-system/instance-manager-e6288312e2b1783e76b72ebd0e03d0fe
error when evicting pods/"instance-manager-e628…" (will retry after 5s):
  Cannot evict pod as it would violate the pod's disruption budget.
... rejected a second time, then:
pod/instance-manager-e6288312e2b1783e76b72ebd0e03d0fe evicted
node/opt3060-i3 drained
```

`prepare` also did its job: it read `server-plan`, found `applying` empty, and verified
`CONTROLPLANE_NODE_VERSION=v1.36.4-k3s1` against the target before letting the drain
start. The worker cannot overtake the control plane.

**What it did not prove.** The binary swap and the k3s restart. The `upgrade` container
compared checksums, found them equal and stopped:

```
[INFO]  Comparing old and new binaries
835873f37245fc61…  /opt/k3s
835873f37245fc61…  /host/usr/local/bin/k3s
[INFO]  Binary already been replaced
+ exit 0
```

!!! note "This also confirms why `FAILED 1` appears on a real hop"
    This job reported `succeeded: 1` and **no** failures, unlike every agent job during
    the 2026-08-28 hops. The difference is the restart: with no binary change there is no
    k3s-agent restart, so no pod loses its kubelet mid-run. That was previously an
    inference from the timing; it is now the controlled case that isolates it.

!!! warning "A node drain takes more with it than the workload"
    The drain log from this run lists what actually left `opt3060-i3`:
    `argocd-server`, `coredns`, `metrics-server`, `longhorn-ui`, every `csi-*` controller
    (`attacher`, `provisioner`, `resizer`, `snapshotter`), the Longhorn `instance-manager`
    and the Forgejo pod.

    **`coredns` runs a single replica here** (`readyReplicas: 1`), so a drain that lands
    on its node briefly takes cluster DNS with it. Nothing broke in this run, but with a
    workload that resolves names under load it would show. Worth scaling to 2 before the
    cluster carries anything that matters; not done yet.

### Side effect: local-path-provisioner is frozen

Measured on 2026-08-28, immediately after the upgrade:

```
running:  rancher/local-path-provisioner:v0.0.34
on disk:  local-path-provisioner:v0.0.37   (in the manifest k3s just rewrote)
```

This is the cost of the `local-storage.yaml.skip` file that fixed the dual-default
StorageClass problem on 2026-08-24. k3s rewrites `local-storage.yaml` on every start
(the timestamp does move), but the `.skip` stops it being applied - so the bundled
`local-path-provisioner` never gets its new image either. It has been drifting since
2026-08-24 and will keep drifting.

Today that costs nothing: `local-path` is not the default class and nothing uses it -
zero PVCs on the cluster, and Longhorn is the default for everything planned.

Deleting the `.skip` is **not** the fix. That brings back two default StorageClasses, and
a PVC created without an explicit `storageClassName` while both claim the title does not
bind. The three real options:

| Option | What it costs |
|--------|---------------|
| **Leave it frozen** | `local-path` drifts further from the bundled version every k3s upgrade. Free until something uses it. |
| Argo CD owns the `is-default-class: "false"` annotation, `.skip` removed | k3s keeps local-path current again, but every k3s restart opens a window - up to one Argo CD sync interval - where both classes claim to be default |
| Vendor `local-storage.yaml` into `k8s/manifests/` under Argo CD | No race, no drift, but the file has to be re-copied from the master on **every** k3s upgrade. Same manual work as today, plus a file to maintain |
| `--disable local-storage` via the Ansible `extra_server_args` | Removes the component, the `.skip` and the dual-default problem in one move. Costs the `local-path` StorageClass entirely |

**Decision (2026-08-28): leave it frozen.** Both Argo CD variants cost more than the
problem, and removing the component is a "do we want this capability" question rather
than a fix. Revisit when something actually needs `local-path` - at that point option 2
or 4 gets chosen deliberately, with a reason.

What matters is that the drift is now visible instead of silent. Check with:

```bash
kubectl get deploy local-path-provisioner -n kube-system \
  -o jsonpath='{.spec.template.spec.containers[0].image}'
```

### Longhorn is upgraded separately

Longhorn is a Helm release and deliberately **not** under Argo CD (the pre-upgrade hook
would run as a `PreSync` before its service account exists, longhorn/longhorn#6415). So
it is a manual `helm upgrade`, and it goes **before** the k3s hops - the CSI layer should
already know the target Kubernetes version, not the other way round.

```bash
helm repo update longhorn
helm upgrade longhorn longhorn/longhorn -n longhorn-system --version 1.12.1 \
  --set defaultSettings.defaultDataPath=/var/lib/longhorn --timeout 15m
```

Pass the values explicitly rather than `--reuse-values`: across a chart version bump,
`--reuse-values` replays the old computed values and silently drops new chart defaults.
`helm get values longhorn -n longhorn-system` prints the short list to reproduce.

One minor at a time here too (1.11.x -> 1.12.x). The v1.12 breaking changes - V2 backing
images removed, the pre-allocated LUKS2 header on encrypted volumes, no live upgrade
between v1.12 patch releases for V2 volumes - touch none of this cluster: V1 data engine,
no encryption, no backing images.

### Before you start

Run `scripts/k3s-backup.sh` by hand, so the newest archive is the pre-upgrade state.
`KEEP` defaults to 30 archives (raised from 7 on 2026-08-28 - it counts archives, not
days, and seven manual runs in one afternoon had once collapsed the whole restore window
to a single day).

Rollback, if the master does not come back: `sudo /usr/local/bin/k3s-killall.sh` on the
node, reinstall the old version with `INSTALL_K3S_VERSION=<previous>`, and restore
`state.db` from the archive:

```bash
gpg --pinentry-mode loopback --decrypt <file>.tar.gz.gpg | tar xzf - -C /somewhere
```

`/somewhere` is staging only. The files then go back to `/var/lib/rancher/k3s/server`
and nowhere else, and the restored server has to listen on the default 6443 - the six
kubeconfigs in `cred/` hard-code both the path and the port. See the control-plane
restore section below.

Longhorn cannot be rolled back to an earlier minor at all. Its recovery path is the
14-day Garage backup and a `fromBackup` StorageClass, verified byte-for-byte on
2026-08-25. That asymmetry is exactly why the whole upgrade was done on an empty
cluster.
