**Date:** 2026-08-28
**Cluster:** 3x Dell OptiPlex, 192.168.1.0/24 (separate location, Tailscale access only)

---

# Cluster Hardening and Recovery

Three pieces of work from 2026-08-28 that only count once measured: a proven control-plane restore, a default-deny NetworkPolicy, and Secrets encrypted at rest.

Split out of the [K3s Cluster host page](../hosts/k3s-cluster.md) on 2026-08-28,
which had grown to 1983 lines and six unrelated projects. The host page keeps the
machine reference - hardware, addressing, live state, access - and this page keeps
the work. Nothing below was rewritten in the move.

---

## Control-plane restore, actually performed (2026-08-28)

The nightly `k3s-backup.sh` has run since 2026-08-24, and it verified that the
encrypted archive **decrypts** and that `state.db` is inside the tar. Whether a
cluster comes back from it was an assumption until this day. `scripts/k3s-restore-test.sh`
now answers it by doing the thing: restore into a throwaway k3s on LXC 109, then read
the objects back.

### The result

Against the 11:42 archive - 7.0 MB encrypted, 25 MB `state.db`, 3061 kine rows - the
API answered `/readyz` **6 seconds** after start, and every object that existed at
backup time came back:

| | nodes | ns | crd | secret | cm | pvc | pv | deploy | sts | ds | Applications | LH volumes | LH replicas |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| expected | 3 | 10 | 84 | 39 | 57 | 3 | 3 | 22 | 7 | 5 | 6 | 3 | 9 |
| missing | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |

116 Secret keys decoded cleanly. Three are empty, and they are empty on the live
cluster too - counting them as corruption is what the first version of the check did.

### The restored server runs with no agent, on purpose

`k3s server --disable-agent`. With an agent the restored control plane would also be a
node: the kubelet would start and begin scheduling the pods it found in the restored
database. Argo CD would pull the real GitHub repository and Longhorn would reach for
the real Garage S3 bucket, from a cluster that is meant to be a copy. With no agent not
one pod starts, and none is needed - the question is whether the data came back.

### The archive only fits back where it came from

Two constraints, both found by trying, both with error messages that name something
other than the actual cause. Every one of the six kubeconfigs in `cred/`:

- names `/var/lib/rancher/k3s/server/tls/...` as an **absolute path**. A different
  `--data-dir` and k3s dies immediately with `unable to read client-cert
  /var/lib/rancher/k3s/server/tls/client-supervisor.crt: no such file or directory`
- names `https://127.0.0.1:6444`, which is `--https-listen-port` **plus one**. Restore
  on any other listen port and the scheduler and controller-manager keep calling 6444
  while the apiserver listens elsewhere: `unable to load configmap based
  request-header-client-ca-file ... dial tcp 127.0.0.1:6444: connect: connection
  refused`, followed by `Shutdown request received`

On a real restore neither bites, because the files go back exactly where they came
from. They bite when you try to restore *beside* a running cluster - which is what a
test does, and what a cautious admin would try first.

### A backup is only as current as the last run

The first attempt used the 06:49 archive and reported five failures: no `forgejo`
Application, no `monitoring`, no PVCs, no Longhorn volumes. All correct - Forgejo went
in at 05:53 UTC and the monitoring stack at 07:25 UTC, and the 06:49 archive sits
between them. The restore was fine; the expectation was wrong.

So the check has no list of expected names. The rule is that **every live object older
than the backup must be present in the restored cluster**, by `creationTimestamp`;
anything newer is listed as drift with a prompt to take a fresh backup. A name list
would have to be edited after every deployment, and would quietly rot.

### Two things this cost that are worth remembering

**k3s rewrites its own argv.** After startup `/proc` shows only `<path>/k3s server` -
every flag is gone. `pkill -f 'k3s server --disable-agent'` therefore matches nothing.
The cleanup used exactly that pattern, so two orphaned control planes kept running on
their own already-deleted data directories, and the next run failed on a busy 6443. The
readiness loop had the same bug and made a perfectly healthy k3s look dead. Track the
PID, not the command line.

**`kubectl -o go-template` prints `<no value>` for a missing namespace.** That string
contains a space, so anything filtering on field count drops every cluster-scoped
object: the comparison table read 0 CRDs where there are 84, and reported it as a pass.
`jsonpath` prints an empty string. A check that reads zero and calls it agreement is
worse than no check.

---

## NetworkPolicy on the workload namespace (2026-08-28)

`apps` is default-deny ingress, with exactly one hole: the Tailscale proxy pod that
serves the Forgejo Ingress. Two files, on purpose - the deny sits with the namespace
(`k8s/manifests/platform/namespace-apps.yaml`), the allow sits with the application
(`k8s/manifests/forgejo/networkpolicy.yaml`). A future app in `apps` should not be
taking its permission out of Forgejo's file, and removing Forgejo should take its
exception with it and leave the deny standing.

The allow does not open the whole `tailscale` namespace. It names the pod by the labels
the operator puts on it - `tailscale.com/parent-resource: forgejo` - which survive an
Ingress being recreated, while the pod name (`ts-forgejo-99j4d-0`) does not.

### Three things measured before writing any of it

**The controller is actually running.** k3s enforces NetworkPolicy through a built-in
kube-router; if it were disabled, every policy here would be decoration. The master has
215 `KUBE-ROUTER` iptables rules and `KUBE-NWPLCY-*` chains, and the log says
`Starting network policy controller version v2.6.3-k3s1`.

**Kubelet probes survive a default-deny.** [k3s-io/k3s#10030](https://github.com/k3s-io/k3s/issues/10030)
reports a default-deny killing liveness and readiness probes, and the issue is closed
without the fix version being obvious. Trying that on the live Forgejo would have been
expensive: three failed liveness probes restart the pod, and that pod runs an SQLite
database. So it was measured in a throwaway namespace instead - the pod stayed `Ready`
for a full 60 seconds under default-deny, with a 5-second probe period and a threshold
of 2, where a block would have shown within 10 seconds. No node exemption needed on this
version.

**Nothing scrapes into `apps`.** All nine ServiceMonitors live in `monitoring` and none
targets `apps`, so Prometheus needs no exception. The day a ServiceMonitor does point
here, this policy is the first thing to widen, or the target goes `down` quietly.

### Proving it, in both directions

A NetworkPolicy nobody tested is the same shape of mistake as the firewall row in the
table above: a control that reads as protection and is not one. So the check ran both
ways, in this order:

1. **before** the policy, a pod in another namespace reaches `forgejo.apps.svc:3000` -
   without this step, "it cannot reach it" proves nothing
2. **after** the policy, the same pod cannot
3. Forgejo still answers HTTP 200 on the tailnet
4. the pod is `Ready` with **0 restarts**

kube-router takes a few seconds to turn a new policy into iptables rules, so measuring
immediately after `kubectl apply` gives a false "still reachable".

### What is deliberately left open

Egress. Forgejo needs DNS, and git remotes, webhooks or avatar fetches may follow; an
egress policy today would break more than it protects.

And the other namespaces. `monitoring` is the next candidate but has more moving parts -
Prometheus has to reach every namespace, Grafana is on the tailnet, and the operator
talks to all three. `kube-system` and `tailscale` stay out on purpose: every pod calls
coredns, and the Tailscale proxies receive host-level traffic.

---

## Secrets encryption at rest (2026-08-28)

Until this day every Secret sat in `state.db` as plaintext protobuf: the Telegram bot
token, the Garage S3 key, the Forgejo `SECRET_KEY`, the Grafana admin password. The
control-plane restore test above is what made that concrete - it read all 116 Secret
keys back out of a restored database without anything resembling a key.

It was deliberately done **after** the restore proof, in that order. Enabling encryption
makes one file on the master load-bearing for every Secret in the cluster; doing that
before you can restore is how you lose them.

### What it protects, and what it does not

The key lives in `/var/lib/rancher/k3s/server/cred/encryption-config.json`, on the same
disk as `state.db`. Anyone who takes the disk takes both. This protects a **copied or
leaked database** - a stray `state.db`, an unencrypted backup, a support dump. It is not
protection against the machine being stolen, and it should not be described as such.

### The procedure

Single server, so no per-node dance. On the master:

```bash
# 1. a rollback point first
scripts/k3s-backup.sh --no-ntfy

# 2. add the flag to the unit, restart
#    ExecStart gets a new line:  '--secrets-encryption' \
sudo systemctl daemon-reload && sudo systemctl restart k3s
sudo k3s secrets-encrypt status          # Enabled, stage: start

# 3. re-encrypt the secrets that are already there
sudo k3s secrets-encrypt rotate-keys     # wait for stage: reencrypt_finished
sudo systemctl restart k3s
```

Step 3 is not optional. `--secrets-encryption` alone only encrypts Secrets written
**after** the restart; the 39 already in the database would have stayed in plaintext
while `status` cheerfully reported `Enabled`.

### Verified by reading the database, not the status output

```
titkositott Secret sor:   39
titkositatlan Secret sor: 0
pelda (/registry/secrets/apps/forgejo-secrets):
  b'k8s:enc:aescbc:v1:aescbckey-2026-08-28T12:21:41+'
```

`kubectl` reads them normally afterwards - the transformation happens inside the
apiserver - so `forgejo-secrets` still decodes to 44 bytes and the Alertmanager config
still contains its `telegram_configs` block.

### `secrets-encrypt status` lies for the first few seconds

Immediately after the restart it returns
`Internal error occurred: secret-encrypt error ID 73844`, and the server log spells it
out: `missing annotation on node opt5060-i5`. Encryption is already on at that point;
the node annotation that `status` reads has just not been written yet. Retry rather than
roll back.

### The flag is now part of the restore procedure

`--secrets-encryption` is in `ansible/host_vars/opt5060-i5.yml`, because an Ansible run
would otherwise remove it. And `scripts/k3s-restore-test.sh` passes it automatically
when the archive contains `cred/encryption-config.json` - which is the interesting half,
because restoring an encrypted cluster **without** it was measured the same day:

```
Error from server (InternalError): Internal error occurred:
identity transformer tried to read encrypted data
```

The restored server never becomes ready. `/readyz` returns
`[+]ping ok [+]log ok [+]etcd ok [+]etcd-readiness ok [-]informer-sync failed` forever,
because the Secret informer cannot sync - 474 of the 962 log lines were that one error.
Meanwhile nodes, CRDs and Deployments all read back fine, which is exactly what makes it
dangerous: the restore looks like it worked until something asks for a Secret.

The whole 2026-08-28 backup archive grew from 7.0 MB to 14 MB, and `state.db` from 25 MB
to 34 MB. Encrypted values do not compress, and the re-encryption wrote a new kine row
for every Secret.
