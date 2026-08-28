# K3s: Infrastructure as Code

**Status:** In production. 3-node K3s v1.36.4+k3s1, one stateful workload, 60 pods.

The cluster is described by three separate layers of code, and the split is
deliberate: each one owns something the others cannot reach.

| Layer | Directory | Owns |
|-------|-----------|------|
| Config | [`ansible/`](https://github.com/Pironex9/homelab/tree/main/ansible) | k3s itself: server args, unit files, the installed version |
| Contents | [`k8s/`](https://github.com/Pironex9/homelab/tree/main/k8s) | everything inside the cluster, via an Argo CD app-of-apps |
| Proof | [`scripts/`](https://github.com/Pironex9/homelab/tree/main/scripts) | the backups, and the restores that prove them |

The current runtime state of the cluster - nodes, resource usage, pods per
namespace, volumes, Ingress - is on the
[K3s Cluster host page](../hosts/k3s-cluster.md).

---

## Layer 1: Ansible describes the cluster, it did not build it

The existing cluster was **adopted**, not rebuilt. The playbook was written
against a running system and then converged onto it, which is the harder
direction: nothing was allowed to change, so any difference between the code and
reality showed up as a broken cluster rather than a fresh one.

The evidence that it converged rather than drifted: after two consecutive live
runs, the sha256 of the systemd unit files is **byte for byte identical**.

Five tasks always report `changed`. That is the role's construction, not drift -
the install script runs unconditionally, the service is deliberately `restarted`
every run, and the installer rewrites the environment file so the role has to put
the token back.

### The two traps that cost real time

**The collection does not download the installer if the version already matches -
but then runs it unconditionally.** On a hand-installed cluster that fails with
`[Errno 2] No such file or directory: /usr/local/bin/k3s-install.sh`. The fix is
a local `site.yml` wrapper with a `get_url` pre-task; the upstream
`k3s.orchestration.site` must never be run directly.

**The `kubeconfig` variable is not left at its default on purpose.** At its
default the role merges the master's kubeconfig into the management node's own
`~/.kube/config` as a new active context, and rewrites the server address to the
API endpoint - which is not routable from that machine. The first live run hung
`kubectl` exactly this way.

### What it deliberately does not manage

Anything that lives *inside* the cluster: the Longhorn Helm release, the
StorageClass default patch, every Ingress and PVC. That gap is what layer 2
closes.

One item is worth naming separately, because losing it does not fail loudly:
`--secrets-encryption` in `host_vars`. Secrets are encrypted at rest in
`state.db`. A run that dropped that flag would start the server without
encryption, and it would **never become ready** - `/readyz` reports
`[-]informer-sync failed` forever, because the Secret informer dies on
`identity transformer tried to read encrypted data`. Non-Secret resources stay
readable throughout, so the failure does not look like an encryption problem.
Measured on a throwaway cluster rather than guessed.

---

## Layer 2: Argo CD owns the contents

A root app-of-apps watches `k8s/apps/` and reconciles automatically. Longhorn,
kube-prometheus-stack, the system-upgrade controller, the NetworkPolicy and Pod
Security Admission settings, and Forgejo all come from git.

### Version upgrades are two edited fields

The k3s version bump is not an SSH job. Two `version:` fields change in
`k8s/manifests/system-upgrade/plans.yaml`, commit, push. Argo CD syncs the Plans
and the system-upgrade controller drains and upgrades node by node, master first.

One minor at a time - a `1.34 -> 1.36` jump is not supported and the controller
does **not** protect against it. The 2026-08-28 upgrade therefore ran in three
hops, `v1.34.5 -> v1.34.11 -> v1.35.8 -> v1.36.4`: 3-7 minutes per hop, with
about 20 seconds of API downtime while the master itself was upgraded.

### Test before push, then let Argo CD adopt

Under GitOps a `git push` **is** a deploy, and undoing it costs another commit
plus a reconcile cycle. With a live workload that is a poor place to run an
experiment. The order that works:

1. `kubectl apply -f` the manifest straight from the repo, uncommitted
2. measure whether it does what it was supposed to
3. if not, `kubectl delete` - nothing remains in the cluster
4. if so, commit and push, and Argo CD **adopts the object that is already
   running**

Step 4 works because Argo CD compares content, not creation. A manifest from git
matching what is already there does not produce a second object; it stamps its
own tracking onto the existing one. An object applied by hand and absent from git
is never pruned either - with no tracking on it, it falls outside the
application's scope.

`Synced/Healthy` does not confirm the adoption. The annotation does:

```bash
kubectl -n apps get networkpolicy \
  -o jsonpath='{range .items[*]}{.metadata.name}{"  "}{.metadata.annotations.argocd\.argoproj\.io/tracking-id}{"\n"}{end}'
# default-deny-ingress  platform:networking.k8s.io/NetworkPolicy:apps/default-deny-ingress
```

An empty `tracking-id` means the object is still manual.

Applications also reconcile independently of each other. After one push, five of
six applications moved within a minute while the sixth stayed on the previous
commit for five - its cycle had run 52 seconds before the commit landed.

### What is deliberately left out of git

The **Longhorn Helm release**. The upstream blocker (Helm hooks running as
`PreSync` before the service account exists) was fixed in v1.6.0 and this cluster
runs 1.12.1, so the technical obstacle is gone. It stays out for a different
reason: adopting it requires `preUpgradeChecker.jobEnabled: false`, and that
check is what stops an invalid Longhorn upgrade such as a skipped minor. Giving
up that net on the **storage** layer - the one layer where a bad upgrade cannot
be rolled back, since there is no minor downgrade - buys declarativeness for an
operation that happens a few times a year and always starts with a backup. Bad
trade. For k3s the balance runs the other way, which is why that one does go
through the controller.

Two **Secrets** also stay out, because the repository is public: the Tailscale
operator's OAuth credentials and Forgejo's. Both are created once, by hand, and
live under `/root/.secrets/` on the management node.

---

## Layer 3: Backups that were restored, not just written

A backup that has never been restored is an assumption. Each of these has been
carried through to a working result:

- **Restic**, weekly: a snapshot is restored to a scratch directory and compared
  by checksum, every Sunday at 06:00, two hours after the backup.
- **K3s control plane**, daily: `state.db` via `VACUUM INTO` (not `cp`, which
  would copy a database mid-write), plus `tls/` and `cred/`, gpg-encrypted
  because the dump contains the cluster's secrets.
- **Control-plane restore**, proven 2026-08-28: restored into a throwaway k3s
  rather than merely decrypted. Two details that only appear when you actually do
  it - the kubeconfigs under `cred/` pin both a path and a port, and k3s rewrites
  its own argv, so the restored server does not come up where you expect it to.
- **Longhorn volumes** to a Garage S3 bucket running on the Docker host, with the
  restore proven on demand. It deliberately does not compare checksums: the
  workload writes a WAL, so a byte-identical comparison would fail on a restore
  that is perfectly correct.

Every one of these jobs pings an Uptime Kuma push monitor on success. That is the
part that matters operationally: a job that silently stops running raises an
alert, instead of being discovered the day it was needed.

---

## Related

- [K3s Cluster host reference](../hosts/k3s-cluster.md) - live state, DNS, the
  incidents and their measurements
- [`k8s/README.md`](https://github.com/Pironex9/homelab/blob/main/k8s/README.md) -
  the full Argo CD layer, in detail
- [`ansible/README.md`](https://github.com/Pironex9/homelab/blob/main/ansible/README.md) -
  the config layer, its scope and its traps
- [`scripts/README.md`](https://github.com/Pironex9/homelab/blob/main/scripts/README.md) -
  the backup layout and every restore proof
