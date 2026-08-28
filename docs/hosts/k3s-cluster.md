# K3s Cluster

**Date:** 2026-04-08 (state verified 2026-08-24)
**Location:** Separate physical location (remote, Tailscale access only)
**Network:** 192.168.1.0/24 (separate router from Proxmox network, gateway 192.168.1.1)

!!! success "Subnet moved on 2026-08-23, fixed addresses restored on 2026-08-24"

    The router at the remote location was replaced or factory-reset at 15:10 on
    2026-08-23. The subnet became **192.168.1.0/24** (gateway 192.168.1.1) and every
    DHCP reservation was lost, so the nodes landed on arbitrary leases (192.168.1.90,
    .152, .231).

    K3s had `--node-ip` hardcoded to the old addresses and crash-looped for 16 hours
    (1855 restarts) with `error getting node subnet: failed to find interface with
    specified node ip`. Note that k3s exits **0** on this failure, so systemd logs
    `Deactivated successfully` - the unit-level messages look like a clean shutdown
    and hide the real cause, which is only visible in the k3s log lines themselves.

    Reservations were re-entered on the new router on 2026-08-24 with the same last
    octets as before, so every IP in this document is current again.

    At the time of the incident the config lived in **five** places across three
    machines, not three:

    | Node | File | Key |
    |------|------|-----|
    | master | `/etc/systemd/system/k3s.service` | `--node-ip`, `--advertise-address` |
    | workers | `/etc/systemd/system/k3s-agent.service` | `--node-ip` |
    | workers | `/etc/systemd/system/k3s-agent.service.env` | `K3S_URL` (**not** in ExecStart) |

    That layout changed later the same day when the cluster was brought under Ansible -
    see "Ansible: the config layer as code" below. The server URL now lives in the
    worker `ExecStart` as `--server`, and the env file holds only `K3S_TOKEN`. The
    IP-change checklist is therefore two files per worker no longer, but the point
    stands: it is never only the one you are looking at.

    Also delete `/var/lib/rancher/k3s/agent/etc/k3s-agent-load-balancer.json` on the
    workers - it caches the old server address and overrides the new `K3S_URL`.

    Tailscale access was never affected, because the kubeconfig and SSH both use
    Tailscale names, not LAN addresses. The apiserver certificate carries
    `DNS:opt5060-i5` in its SAN list but **not** the Tailscale IP, which is why
    `server: https://opt5060-i5:6443` in the kubeconfig survives an IP change while a
    kubeconfig pointing at `100.68.209.53` would not.

!!! warning "A new DHCP reservation does not take effect while the old lease is alive"

    Entering the reservation on the router is not enough. A DHCP server hands back the
    address it has already leased to that MAC and ignores the reservation until that
    lease is gone. Adding a reservation does not purge the existing lease.

    This showed up as two nodes obeying the reservation instantly and the third
    refusing three attempts in a row. The lease lifetime here is `LIFETIME=1d`,
    `T1=12h`. The two workers had booted on 2026-08-23 at 13:12, so their leases had
    expired 21 minutes before the reservation was entered. The master had rebooted at
    09:38 that morning for a kernel update, so its lease was still valid for another 20
    hours.

    Order of operations that works:

    ```bash
    # 1. force a fresh DHCPDISCOVER - renew is NOT enough, the server just extends
    #    the current address on a unicast RENEW
    sudo networkctl reconfigure eno1

    # 2. if the address does not change, the router still holds the lease.
    #    Delete it in the router UI, or reboot the router, then repeat step 1.
    ```

    Deleting the cached lease under `/run/systemd/netif/leases/` does not help: the
    address is being offered by the server, not remembered by the client.

---

## Cluster Overview

3-node K3s cluster built from used Dell OptiPlex hardware. Used for learning Kubernetes, experimenting with workloads, and eventually running production-grade services with Longhorn storage and a full monitoring stack.

| Property | Value |
|----------|-------|
| K3s version | v1.36.4+k3s1 (upgraded 2026-08-28, see [Version upgrades](#version-upgrades-system-upgrade-controller)) |
| Kubernetes | v1.36 |
| Container runtime | containerd 2.3.4-k3s1.36 |
| CNI | Flannel |
| Ingress | Traefik 3.7.1 (built-in), one Ingress (Argo CD, `tailscale` class) |
| Storage class | longhorn (sole default since 2026-08-24), local-path (available, not default) |
| Access | Tailscale mesh VPN |

---

## Hardware

| Node | Model | Role | CPU | RAM | Disk | Local IP | Tailscale IP | Interface |
|------|-------|------|-----|-----|------|----------|--------------|-----------|
| opt5060-i5 | Dell OptiPlex 5060 | control-plane | Intel i5-8500 @ 3.00GHz | 16 GB | 57 GB (35% used) | 192.168.1.101 | 100.68.209.53 | eno1 |
| opt3060-i3 | Dell OptiPlex 3060 | worker | Intel i3-8100 @ 3.60GHz | 8 GB | 98 GB (10% used) | 192.168.1.102 | 100.124.149.16 | enp1s0 |
| opt3050-i5 | Dell OptiPlex 3050 | worker | Intel i5-7500 @ 3.40GHz | 8 GB | 98 GB (10% used) | 192.168.1.103 | 100.102.92.89 | enp1s0 |

**OS:** Ubuntu 24.04.3 LTS, kernel 6.8.0-101-generic
**User:** `nex` (sudo access)
**Cost:** ~200 EUR compute + 50 EUR Orange Pi bundle + 40 EUR switch/cables = ~300 EUR total

---

## Network Topology

```
[Internet] → [Router (192.168.1.1)]
                      |
              [Unmanaged Switch]
               |        |        |
          [OPi One]  [opt5060] [opt3060] [opt3050]
               |
         [Tailscale VPN mesh]
                |
         Reachable from LXC 109 (claude-mgmt)
         and Nobara PC via Tailscale
```

**DHCP reservations (router):**

| MAC Address | Hostname | Reserved IP |
|-------------|----------|-------------|
| `54:bf:64:68:a0:30` | opt5060-i5 | 192.168.1.101 |
| `54:bf:64:a2:ff:77` | opt3060-i3 | 192.168.1.102 |
| `d8:9e:f3:13:4d:97` | opt3050-i5 | 192.168.1.103 |
| Orange Pi MAC | orangepione | 192.168.1.51 (DHCP, no reservation) |

### Reaching the remote router UI (2026-08-24)

There is no out-of-band access at this location, and the router only listens on its
own LAN. `opt3060-i3` therefore advertises the whole subnet as a Tailscale subnet
route, which makes `https://192.168.1.1` reachable from any device on the tailnet,
including a phone:

```bash
ssh nex@opt3060-i3 'sudo -n tailscale set --advertise-routes=192.168.1.0/24'
```

Then approve the route in the Tailscale admin console under the **opt3060-i3**
machine. It has to be approved per prefix - approval of an earlier prefix is not
inherited, and this tailnet has no `autoApprovers` rule. To undo, set
`--advertise-routes=` with an empty value.

Notes:

- Use `tailscale set`, never `tailscale up`. `up` resets every flag that is not
  passed on the command line.
- iOS and Android accept approved subnet routes automatically; there is no toggle in
  the mobile app, unlike Windows and macOS.
- If the client device is itself on a 192.168.1.0/24 network, its local subnet wins
  and 192.168.1.1 resolves to its own gateway instead.
- `orangepione` used to advertise the old `192.168.2.0/24` here. That route is dead
  and was left in place rather than removed.


---

## K3s Installation

### Master node (opt5060-i5)

```bash
curl -sfL https://get.k3s.io | \
  K3S_NODE_NAME=opt5060-i5 \
  INSTALL_K3S_EXEC='server --node-ip=192.168.1.101 --advertise-address=192.168.1.101 --flannel-iface=eno1' \
  sh -
```

Get node token for workers:
```bash
sudo cat /var/lib/rancher/k3s/server/node-token
```

### Worker nodes

```bash
# opt3060-i3
curl -sfL https://get.k3s.io | \
  K3S_NODE_NAME=opt3060-i3 \
  K3S_URL=https://192.168.1.101:6443 \
  K3S_TOKEN=<node-token> \
  INSTALL_K3S_EXEC='agent --node-ip=192.168.1.102 --flannel-iface=enp1s0' \
  sh -

# opt3050-i5
curl -sfL https://get.k3s.io | \
  K3S_NODE_NAME=opt3050-i5 \
  K3S_URL=https://192.168.1.101:6443 \
  K3S_TOKEN=<node-token> \
  INSTALL_K3S_EXEC='agent --node-ip=192.168.1.103 --flannel-iface=enp1s0' \
  sh -
```

> Always specify `--node-ip` and `--flannel-iface` explicitly. Without these, K3s uses the wrong interface after a network change.

---

## Management from LXC 109 (claude-mgmt)

LXC 109 manages the K3s cluster via Tailscale + kubectl.

### Setup done (2026-03-19, updated 2026-04-06)

1. **Tailscale on LXC 109** - requires TUN device in LXC config:
   ```bash
   # On Proxmox host - load tun module
   modprobe tun
   echo tun >> /etc/modules-load.d/tun.conf

   # Add to /etc/pve/lxc/109.conf (via /tmp workaround - pmxcfs blocks direct append)
   cp /etc/pve/lxc/109.conf /tmp/109.conf
   echo 'lxc.cgroup2.devices.allow: c 10:200 rwm' >> /tmp/109.conf
   echo 'lxc.mount.entry: /dev/net/tun dev/net/tun none bind,create=file 0 0' >> /tmp/109.conf
   cp /tmp/109.conf /etc/pve/lxc/109.conf
   pct reboot 109
   ```

2. **kubectl installed** at `/usr/local/bin/kubectl` on LXC 109

3. **kubeconfig** at `/root/.kube/config`, server set to `opt5060-i5:6443` (Tailscale hostname)

4. **SSH key auth** from LXC 109 root to `nex@` on all 3 nodes (no password)

5. **Hostname resolution** for k3s nodes on LXC 109 - add entries to `/etc/hosts` (Tailscale IP → hostname):
   ```
   100.68.209.53   opt5060-i5
   100.124.149.16  opt3060-i3
   100.102.92.89   opt3050-i5
   100.120.73.44   orangepione
   ```
   Tailscale already adds individual peer routes to table 52 for each 100.x IP, so kubectl and SSH work over Tailscale without any additional routing config.

   > **WARNING: do NOT use `tailscale set --accept-routes=true` on LXC 109.** pve advertises `192.168.0.0/24` as a subnet route. If LXC 109 accepts it, all outbound traffic to the homelab LAN gets routed through Tailscale (table 52, rule 5270 runs before the main table). TCP reply packets take an asymmetric path and connections hang. SSH and NFS become unreachable. This caused a full SSH/NFS outage on 2026-04-08 after a Proxmox + LXC update restarted Tailscale and re-applied the route. See also: `docs/proxmox/deprecated/Scanopy.md` which had the identical issue.

6. **Passwordless sudo** for kubeconfig on master:
   ```
   /etc/sudoers.d/k3s-kubeconfig: nex ALL=(ALL) NOPASSWD: /bin/cat /etc/rancher/k3s/k3s.yaml
   ```

### Refresh kubeconfig

```bash
ssh nex@opt5060-i5 "sudo cat /etc/rancher/k3s/k3s.yaml" | sed 's/127.0.0.1/opt5060-i5/' > ~/.kube/config
chmod 600 ~/.kube/config
```

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

Longhorn cannot be rolled back to an earlier minor at all. Its recovery path is the
14-day Garage backup and a `fromBackup` StorageClass, verified byte-for-byte on
2026-08-25. That asymmetry is exactly why the whole upgrade was done on an empty
cluster.

---

## Wake-on-LAN

The cluster is powered off when not in use. An Orange Pi One (Armbian) on the same network handles WoL.

### Orange Pi One

| Property | Value |
|----------|-------|
| OS | Armbian 25.8.1 Noble |
| Role | WoL server + Tailscale exit node |
| Interface | end0 |
| Local IP | 192.168.1.52 |
| Tailscale IP | 100.120.73.44 |
| Tailscale hostname | orangepione |
| User | nex |

### WoL script

**File:** `/usr/local/bin/wakeonlan.sh` on the Orange Pi, root-owned.

**It has three callers, all pointing at this one file** - that matters, because on
2026-08-27 a fix landed in a second copy under `/home/nex/` and the web UI kept running
the old broken one for an hour:

| Caller | How |
|---|---|
| `nex` crontab | `@reboot sleep 60 && /usr/local/bin/wakeonlan.sh` |
| Web UI on port 5000 | `/usr/local/bin/wol-web.py` -> `GET /wake` -> `subprocess.run` |
| By hand | `ssh nex@orangepione "sudo /usr/local/bin/wakeonlan.sh"` |

Editing it needs the `nex` sudo password: the passwordless sudo on that box covers only
`/usr/sbin/etherwake` and the script itself, and there is no root SSH key. That is
annoying but it is the right trade - the alternative, a user-owned copy elsewhere, is
exactly what produced the two-copies bug above.

```bash
#!/bin/bash
# K3s Cluster wake up script
#
# Two packet formats per MAC, over several rounds. Both decisions come from
# measurement - see "Why the master never woke" below.
#
# The first round runs in the foreground, the rest in the background. Otherwise the
# web UI blocks for 104 s (measured), because wol-web.py calls it with
# capture_output=True. The background block redirects to /dev/null on purpose: if it
# inherited the pipe, subprocess.run would still wait for it to finish.

MAC1="54:bf:64:68:a0:30"  # opt5060-i5  (Intel I219 - ONLY the UDP form wakes it)
MAC2="54:bf:64:a2:ff:77"  # opt3060-i3  (Realtek RTL8168h)
MAC3="d8:9e:f3:13:4d:97"  # opt3050-i5  (Realtek RTL8168h)
INTERFACE="end0"
BCAST="192.168.1.255"
ROUNDS=6      # 6 rounds x 20 s = ~100 s of coverage
GAP=20

send_udp() {
    python3 -c '
import socket, sys
mac, bcast = sys.argv[1], sys.argv[2]
pkt = b"\xff" * 6 + bytes.fromhex(mac.replace(":", "")) * 16
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
for port in (7, 9):
    s.sendto(pkt, (bcast, port))
' "$1" "$BCAST"
}

send_round() {
    for MAC in $MAC1 $MAC2 $MAC3; do
        sudo etherwake -i $INTERFACE $MAC
        send_udp "$MAC"
    done
}

echo "Waking up nodes ($ROUNDS rounds over $((ROUNDS * GAP))s, etherwake + UDP magic packet)..."
send_round
echo "  round 1/$ROUNDS sent, rounds 2-$ROUNDS continue in the background"

(
    for r in $(seq 2 $ROUNDS); do
        sleep $GAP
        send_round
    done
) >/dev/null 2>&1 &

echo "Wake packets sent to all nodes"
```

Previous version kept as `/usr/local/bin/wakeonlan.sh.bak-2026-08-27` (the original
412-byte `etherwake`-only script).

### Web UI (port 5000)

`/usr/local/bin/wol-web.py`, a Flask app run as root by `wol-web.service`, listening on
`0.0.0.0:5000` - reachable over Tailscale at `http://100.120.73.44:5000/`. `GET /wake`
shells out to `wakeonlan.sh` and returns its stdout.

Because it uses `subprocess.run(..., capture_output=True)`, **anything the script leaves
holding stdout keeps the HTTP request open**. That is why the retry rounds background
themselves with `>/dev/null 2>&1` rather than just `&`. Measured before and after:
104.65 s -> 0.82 s, with the background rounds confirmed still running afterwards.

**Auto-start on boot** (`nex` user crontab):
```
@reboot sleep 60 && /usr/local/bin/wakeonlan.sh
```

Passwordless sudo configured for both `etherwake` and the script:
```
/etc/sudoers.d/etherwake:  nex ALL=(ALL) NOPASSWD: /usr/sbin/etherwake
/etc/sudoers.d/wakeonlan:  nex ALL=(ALL) NOPASSWD: /usr/local/bin/wakeonlan.sh
```

**Remote trigger from any Tailscale node:**
```bash
ssh nex@orangepione "sudo /usr/local/bin/wakeonlan.sh"
```

### WoL reliability notes

WoL is unreliable after extended offline periods (hours/days). Known causes:

- **Packet format** - the biggest one, and the one that cost years of "WoL is flaky here": `etherwake`'s raw `0x0842` frame never woke the master. See the section below; the script now sends a UDP magic packet as well.
- **GS305 Green Ethernet (IEEE 802.3az)** - the switch puts ports into low-power idle when a device disconnects. Unmanaged - cannot be disabled. Suspected for a long time, never actually confirmed as a cause.
- **NIC WoL state** - `ethtool wol g` is re-applied on each boot via `wol.service`. If the machine was power-cut before booting, the state may be lost.

**Workaround:** If WoL fails, power-cycle the node physically or via a smart PDU. BIOS should be set to `AC Power Recovery = Power On` so the node boots automatically on power restore.

### Why the master never woke, and the two workers always did (2026-08-27)

**The packet format, not the BIOS and not the switch.** `etherwake` sends a raw
Ethernet frame with EtherType `0x0842`. The master's Intel I219 does not wake on that
frame in any form; it wakes on the identical payload wrapped in a UDP broadcast. Both
Realtek workers accept either. Proven with three controlled shutdown-and-wake cycles
on the live master:

| Sent from the Orange Pi | Result |
|---|---|
| `etherwake` unicast, 3x (the original script) | nothing in 180 s |
| `etherwake -b` broadcast frame, 5x | nothing in 75 s |
| **UDP magic packet to `192.168.1.255:9`** | **awake in 24 s** |

Timing on the first successful wake, from the machine's own side: `uptime -s` said
16:45:23 CEST and `systemd-analyze` reported 14.274 s firmware + 2.924 s loader, which
puts the power-on at ~14:45:06 UTC - two seconds after the UDP packet, and five minutes
after the `etherwake` batch that did nothing.

**And a second, independent cause: timing.** A magic packet sent ~40 seconds after
`systemctl poweroff` was simply lost - the deployed script fired that early on the
fourth test cycle and the master stayed dark for 75 seconds. The identical packet sent
2 to 5 minutes after shutdown woke it every time. The NIC does not arm its WoL filter
the instant the OS stops; there is a window at the start of S5 where magic packets go
nowhere. The exact threshold is somewhere between 40 s and 2.5 minutes and was not
narrowed further - four power cycles on a remote machine was enough.

This is very likely a large part of the historical "WoL is unreliable here", and it is
why the script now sends **6 rounds 20 seconds apart** rather than one burst: with
~100 seconds of coverage the timing does not have to be guessed.

The fix is in `wakeonlan.sh` above: **both** formats, to every MAC, over several rounds.
`etherwake` stays because it demonstrably works on the workers and costs nothing.

!!! warning "The retrying version has not been proven against a powered-off machine"

    The format and the timing were each proven on a live master. The 6-round script
    that combines both was verified only to run cleanly end to end (no sudo prompt, all
    rounds sent) - it has not itself been tested on a machine that was actually off,
    because that would have needed a fifth power cycle after the `Auto On 17:30`
    backstop had already passed for the day.

Everything else was measured and ruled out first, rather than assumed:

| Checked | opt5060-i5 (master) | opt3060-i3 (worker) | Verdict |
|---|---|---|---|
| MAC in `wakeonlan.sh` vs `/sys/class/net/*/address` | `54:bf:64:68:a0:30` = matches | matches | not it |
| BIOS `WakeOnLan` | `LanWlan` | `LanWlan` | not it |
| BIOS `DeepSleepCtrl` | `Disabled` | `Disabled` | not it |
| OS `ethtool ... Wake-on` | `g` | `g` | not it |
| `wol.service` | enabled, active | enabled, active | not it |
| EEE (802.3az) on the link | was `enabled - active` | `disabled` | see below |
| NIC | Intel I219 (`e1000e`) | Realtek RTL8168h (`r8169`) | explains the format difference |

`DeepSleepCtrl` is the setting Dell's own troubleshooting guide names first, and it was
already `Disabled` here, so the usual answer never applied to this machine.

!!! note "EEE was disabled too, and it is **not** proven to have mattered"

    Energy Efficient Ethernet was `enabled - active` on the master and `disabled` on
    both workers, which looked like the answer before the packet formats were separated.
    It was turned off (`ethtool --set-eee eno1 eee off`, link stayed up at 1000Mb/s) and
    made persistent as a second `ExecStart` in `wol.service` **before** the wake tests
    ran, so every test above happened with EEE already off. That means the tests say
    nothing about EEE either way: plain `etherwake` failed with EEE off just as it had
    with EEE on.

    It is being kept because it costs nothing and matches the two working nodes, not
    because it was shown to fix anything. Unit backup:
    `/etc/systemd/system/wol.service.bak-2026-08-27`; to revert, drop the line and run
    `ethtool --set-eee eno1 eee on`.

**Independent of all this, the master now has a backstop:** BIOS `AC Power Recovery =
Power On` plus `Auto On = Everyday 17:30`. The two workers are on `Last State`, which is
why they returned after the 2026-08-25 outage and the master did not.

After three power cycles in twenty minutes the cluster came back clean every time: all
3 nodes `Ready`, all Argo CD apps `Synced/Healthy`, all Longhorn disks `Ready`, one
default StorageClass, and `journalctl -u k3s -b | grep -c corrupt` returning 0.

#### Reading Dell BIOS settings from Linux, without a reboot

The 5060 and 3060 expose their BIOS through the `dell-wmi-sysman` kernel driver, so the
settings above were read over SSH rather than from a BIOS screen at the remote site:

```bash
cd /sys/class/firmware-attributes/dell-wmi-sysman/attributes
sudo cat WakeOnLan/current_value      # LanWlan
sudo cat WakeOnLan/possible_values    # Disabled;LanOnly;WlanOnly;LanWlan;LanWithPxeBoot;
sudo cat DeepSleepCtrl/current_value  # Disabled
sudo cat AutoOn/current_value         # Everyday
```

`current_value` reads as empty without root - it is not missing, it is unreadable.
The older `opt3050-i5` has no `dell-wmi-sysman`, so its BIOS still needs a screen.

### WoL persistence on K3s nodes

WoL resets to disabled after reboot on Linux. Each node has a systemd service to re-enable it:

**`/etc/systemd/system/wol.service`** (opt5060-i5 uses `eno1`, workers use `enp1s0`):
```ini
[Unit]
Description=Enable Wake-on-LAN on eno1
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/sbin/ethtool -s eno1 wol g
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
```

Status: all 3 nodes have `wol.service` enabled and active.

---

## Current Cluster State (2026-03-19)

### Nodes

```
NAME         STATUS   ROLES           VERSION        INTERNAL-IP     KERNEL
opt5060-i5   Ready    control-plane   v1.36.4+k3s1   192.168.1.101   6.8.0-138-generic
opt3060-i3   Ready    <none>          v1.36.4+k3s1   192.168.1.102   6.8.0-138-generic
opt3050-i5   Ready    <none>          v1.36.4+k3s1   192.168.1.103   6.8.0-138-generic
```

### Resource usage (idle)

| Node | CPU | RAM |
|------|-----|-----|
| opt5060-i5 | 130m (2%) | 4.9 GB (31%) - master overhead |
| opt3060-i3 | 30m (0%) | 385 MB (4%) |
| opt3050-i5 | 30m (0%) | 380 MB (4%) |

### Running system pods

| Pod | Namespace | Node |
|-----|-----------|------|
| coredns | kube-system | opt5060-i5 |
| local-path-provisioner | kube-system | opt5060-i5 |
| metrics-server | kube-system | opt5060-i5 |
| traefik | kube-system | opt5060-i5 |
| svclb-traefik | kube-system | all 3 nodes |

### Services

| Service | Type | External IP | Ports |
|---------|------|-------------|-------|
| kubernetes | ClusterIP | - | 443 |
| kube-dns | ClusterIP | - | 53 |
| traefik | LoadBalancer | 192.168.1.101/102/103 | 80, 443 |

---

## DNS Configuration

All K3s nodes use `--accept-dns=false` - Tailscale does not manage DNS on these nodes. The local router (192.168.1.1) handles all DNS resolution.

**Why:** Tailscale pushes a `~.` catch-all routing domain via systemd-resolved which redirects all DNS queries through 100.100.100.100. On the 192.168.1.x network this caused external DNS resolution to fail (e.g. `apt` could not reach `archive.ubuntu.com`).

**Applied on all 3 nodes (2026-03-31):**
```bash
sudo tailscale set --accept-dns=false
```

This setting persists across reboots.

---

## Security Status

| Item | Status |
|------|--------|
| Tailscale mesh VPN | Active |
| SSH key auth | Configured |
| UFW firewall | Active on all nodes |
| WoL only on local network | Yes |
| K3s RBAC | Default (not hardened) |
| Network policies | Not configured |
| Pod Security Standards | Not configured |

---

## Longhorn Storage

Dedicated HDDs formatted and labeled for Longhorn. Mount point: `/var/lib/longhorn`.

| Node | Device | Label | UUID | Size | Type |
|------|--------|-------|------|------|------|
| opt5060-i5 | /dev/sda1 | longhorn-sdb | `1d358359-cb60-4974-93b3-df15e49741ec` | 931 GB | SATA internal |
| opt3060-i3 | /dev/sda1 | longhorn-sdd | `297b57c3-2ff7-4c7b-b821-2e2cb3e2c5e0` | 931 GB | SATA internal |
| opt3050-i5 | /dev/sdc1 (was sdb1) | longhorn-sdc | `e1623077-2dcc-44d2-acf8-8df8242ea481` | 465 GB | USB external |

Filesystem: ext4. Formatted 2026-04-06.

**Excluded:** Toshiba MK5055GSXN (33 reallocated sectors + 2 pending) - bad health, not used.

**fstab entries (applied 2026-04-11):**
```
# opt5060-i5 /etc/fstab
UUID=1d358359-cb60-4974-93b3-df15e49741ec /var/lib/longhorn ext4 defaults,nofail 0 2

# opt3060-i3 /etc/fstab
UUID=297b57c3-2ff7-4c7b-b821-2e2cb3e2c5e0 /var/lib/longhorn ext4 defaults,nofail 0 2

# opt3050-i5 /etc/fstab (USB - extra timeout + automount, see below)
UUID=e1623077-2dcc-44d2-acf8-8df8242ea481 /var/lib/longhorn ext4 defaults,nofail,x-systemd.automount,x-systemd.device-timeout=30s 0 2
```

All 3 nodes: `/var/lib/longhorn` mounted and verified (870GB/870GB/435GB free).

!!! danger "The USB disk re-enumerates, and `nofail` alone silently loses it (2026-08-27)"

    On 2026-08-27 at 12:22:21 UTC the external disk on `opt3050-i5` dropped off the
    USB bus and came back as a **different device node** - `sdb` before, `sdc` after:

    ```
    kernel: Buffer I/O error on dev sdb1, logical block 60850176, lost sync page write
    kernel: JBD2: I/O error when updating journal superblock for sdb1-8.
    kernel: scsi host7: uas
    kernel: sd 7:0:0:0: [sdc] Attached SCSI disk
    systemd[1]: var-lib-longhorn.mount: Deactivated successfully.
    ```

    systemd unmounted it and **never mounted it back**. With plain `nofail` there is
    no trigger to retry: `nofail` only says "do not fail the boot", it does nothing
    at runtime. The UUID in fstab was correct the whole time, and the disk was
    present and healthy - nothing was wrong except that no one asked for the mount.

    `/var/lib/longhorn` then resolved to the **root filesystem**, where Longhorn
    immediately wrote a fresh `longhorn-disk.cfg` with a new `diskUUID`. That is what
    surfaced in the Longhorn API:

    ```
    Disk default-disk-8fbd9a4d53e0e209(/var/lib/longhorn) on node opt3050-i5 is not ready:
    record diskUUID doesn't match the one on the disk   (reason: DiskFilesystemChanged)
    ```

    This condition is Longhorn's own guard and it worked: rather than replicate onto
    the root disk, it took the disk out of service. The node stayed `Ready` in
    `kubectl get nodes` - **only `kubectl get nodes.longhorn.io` showed the failure**,
    so the cluster looked entirely healthy from the Kubernetes side while a third of
    the storage was gone.

    **The fix is one fstab option:**

    ```
    ...,nofail,x-systemd.automount,x-systemd.device-timeout=30s 0 2
    ```

    `x-systemd.automount` turns the mount point into an autofs trigger, so the first
    access after the device returns mounts it again. It also means an access while the
    device is genuinely missing **blocks** instead of falling through to the root
    filesystem, which is the safer of the two failure modes.

    Verified live on 2026-08-27 without a reboot (there is no out-of-band access to
    the remote site, so a node that fails to come back means a car trip):

    ```
    systemctl stop var-lib-longhorn.mount   # mount: inactive
    ls /var/lib/longhorn                    # mount: active, /dev/sdc1, correct diskUUID
    ```

    The other two nodes are internal SATA and keep plain `nofail`; they cannot
    re-enumerate the same way.

    **Recovery, if it happens again before the automount is in place:** mount the disk
    read-only somewhere else first and check that `longhorn-disk.cfg` carries the
    `diskUUID` Longhorn has on record - if it does, `systemctl start
    var-lib-longhorn.mount` is enough and no data is at risk. `longhorn-manager`
    mounts `/var/lib/longhorn/` with `mountPropagation: Bidirectional`, so a host
    mount reaches the containers and **no pod restart is needed**. The files Longhorn
    wrote onto the root filesystem in the meantime are then hidden under the mount;
    to delete them, `mount --bind / /mnt/rootfs` and remove them under that path.

### Prerequisites (installed 2026-04-11)

Every node requires:
- `open-iscsi` - already present; Longhorn uses iSCSI to attach block devices to pods over the network
- `nfs-common` - installed; required for Longhorn NFS backup targets

```bash
sudo apt-get install -y open-iscsi nfs-common
```

### Longhorn installation (2026-04-11)

Helm v3.20.2 installed on LXC 109 (`/usr/local/bin/helm`).

```bash
helm repo add longhorn https://charts.longhorn.io
helm repo update

kubectl create namespace longhorn-system

helm upgrade --install longhorn longhorn/longhorn \
  --namespace longhorn-system \
  --set defaultSettings.defaultDataPath=/var/lib/longhorn \
  --wait --timeout 10m
```

Installed version: **v1.12.1** (upgraded from v1.11.1 on 2026-08-28, chart revision 2)

After install, `local-path` was removed from default to avoid dual-default conflict:
```bash
kubectl patch storageclass local-path -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"false"}}}'
```

**Storage classes (as configured in 2026-04):**
```
NAME                 PROVISIONER             DEFAULT
local-path           rancher.io/local-path   -
longhorn             driver.longhorn.io      yes
longhorn-static      driver.longhorn.io      -
```

!!! success "Fixed 2026-08-24 - the `.skip` file, not another patch"

    **The problem:** the `kubectl patch` above was reverted every time the k3s
    server started, leaving two default StorageClasses at once. K3s re-writes its
    packaged manifests from `/var/lib/rancher/k3s/server/manifests/` on every
    startup "in order to ensure their integrity", which restored
    `storageclass.kubernetes.io/is-default-class: "true"` on `local-path`. After
    1855 restarts in a single day, that was guaranteed.

    Nothing was broken by it: the DefaultStorageClass admission plugin picks the
    class with the most recent `creationTimestamp`, and `longhorn` (134 days old)
    beat `local-path` (157 days old). But that is an accident, not configuration -
    recreating the Longhorn StorageClass would have silently flipped the winner.

    **The fix.** Re-patching would have reverted again, so the manifest had to stop
    being re-applied:

    ```bash
    # 1. stop k3s from applying the packaged manifest
    sudo touch /var/lib/rancher/k3s/server/manifests/local-storage.yaml.skip

    # 2. now the patch sticks
    kubectl patch storageclass local-path \
      -p '{"metadata":{"annotations":{"storageclass.kubernetes.io/is-default-class":"false"}}}'
    ```

    `--disable local-storage` was rejected: it actively uninstalls the component and
    deletes the source file, which would remove local-path entirely. A `.skip` file
    created after an AddOn already exists does not remove or modify it, so
    `local-path` keeps working - node-local, unreplicated, faster than Longhorn, and
    genuinely useful for caches and build directories alongside it.

    **Verified by restarting k3s**, which is the step the 2026-04-11 attempt never
    took. After the restart `local-storage.yaml` had a fresh timestamp (k3s did
    re-write it) but was not applied, `local-path` was no longer default, and the
    `local-path-provisioner` deployment was still `1/1`:

    ```
    NAME                 PROVISIONER             DEFAULT
    local-path           rancher.io/local-path   -
    longhorn (default)   driver.longhorn.io      yes
    longhorn-static      driver.longhorn.io      -
    ```

### Datastore: 3.4 GB -> 10 MB (2026-08-24)

The sqlite datastore (`/var/lib/rancher/k3s/server/db/state.db`) had grown to
**3.4 GB** on a cluster with 34 pods and no workloads. Two separate problems were
behind it, and they needed different fixes.

**1. Free pages - fixed with VACUUM.** SQLite never returns deleted pages to the OS
on its own, and k3s never runs `VACUUM`. `VACUUM INTO` produces a compacted copy of
a live database in about two seconds, so the k3s downtime is only the file swap:

```bash
sudo systemctl stop k3s
sudo python3 -c "
import sqlite3
c = sqlite3.connect('/var/lib/rancher/k3s/server/db/state.db')
c.execute(\"VACUUM INTO '/var/lib/rancher/k3s/server/db/state.db.new'\")
c.close()"
# integrity_check, then mv the new file over state.db, then start k3s
```

Result: 3.4 GB -> **577 MB**. 82% of the file was free pages. The `Slow SQL`
warnings (`wal_checkpoint(FULL)` taking over a second on an idle cluster)
disappeared: the first compaction on the new file processed 5278 revisions in
1.576s with **zero** `Slow SQL` entries, against ~4850-revision batches on the old
file where every cycle logged several.

**2. Half a million expired Events - the actual bloat.** After the VACUUM the file
was still 577 MB, and a breakdown of the `kine` table showed why:

```
188 503  /registry/events/default
172 531  /registry/events/longhorn-system
167 082  /registry/events/kube-system
    ...
      27  /registry/pods/longhorn-system
```

**528 116 of 530 071 rows (99.6%) were Kubernetes Events.** All of them had
`lease > 0` (a TTL was set) and `deleted = 0` (none had been marked for removal),
spanning nearly a million revisions.

The cause is visible in the k3s shutdown log line `TTL events watch channel closed`:
kine schedules expiry deletions **in memory**, by watching keys as they are created.
Every k3s restart loses that schedule, and it is not rebuilt for rows that already
exist. After 1855 restarts in one day the backlog was permanent - k3s would never
have cleaned it up.

This was not only disk usage. `kubectl get events -n default` **did not return
within 60 seconds**, because the apiserver was reading every one of those rows.

!!! warning "There is no upstream procedure for this"

    kine issue [#213](https://github.com/k3s-io/kine/issues/213) asks exactly this
    question and was closed with no maintainer answer. Deleting rows directly from
    the `kine` table is what compaction itself does, and Events are non-authoritative
    diagnostics with a 1-hour TTL, so nothing depends on them - but this is judgement,
    not a vendor-blessed step. Take a verified backup first.

    Delete only rows **below** `max(id) - 1000`. Kine derives the current revision
    from `max(id)`; removing the highest row would make the revision counter go
    backwards. The newest rows are left alone for that reason.

```bash
sudo systemctl stop k3s
sudo python3 -c "
import sqlite3
c = sqlite3.connect('/var/lib/rancher/k3s/server/db/state.db')
cutoff = c.execute('SELECT max(id) FROM kine').fetchone()[0] - 1000
c.execute(\"DELETE FROM kine WHERE name GLOB ? AND id < ?\", ('/registry/events/*', cutoff))
c.commit(); c.close()"
# then VACUUM INTO as above, swap, start k3s
```

| Milestone | `state.db` |
|-----------|-----------|
| Morning of 2026-08-24 | 3 456 999 424 B (3.4 GB) |
| After `VACUUM` | 577 294 336 B (577 MB) |
| After the event purge | **10 145 792 B (10.1 MB)** |

528 486 rows deleted, **2 718 left** - 54 pods, 24 services, 15 configmaps, 12
deployments, 11 secrets and 742 recent events. `max(id)` was unchanged at 7 360 323.
`kubectl get events -A` now returns in **0.150 s**.

One pod (`csi-provisioner`) went into CrashLoopBackOff during the restart with
`dial tcp 10.43.0.1:443: connect: connection refused`, timestamped a minute before
k3s finished starting - the same class of failure as every other apiserver-outage
restart, not damage from the purge. It recovered on its own after the backoff
expired, with no intervention. A PVC provisioning test afterwards bound and deleted
cleanly.

---

### Ansible: the config layer as code (2026-08-24)

The cluster is described in `ansible/` in this repo and converged with the official
`k3s-io/k3s-ansible` collection (`k3s.orchestration` 1.2.2). This is the **second** of
three layers - hardware/OS is still manual, and cluster contents (Longhorn, Traefik,
future Ingresses) are still applied by hand until ArgoCD lands. `ansible/README.md`
carries the full detail; the parts worth knowing here:

- **Nothing was rebuilt.** The existing cluster was adopted. `extra_server_args`
  reproduces the previous `ExecStart` verbatim, and after two consecutive real runs the
  systemd unit files are byte-identical, so the description now matches reality rather
  than describing an intent.
- **A converge restarts k3s on all three nodes**, with no cordon or drain. Free today
  with zero PVCs and zero Ingresses; it needs a maintenance window once anything runs.
- **What Ansible does not manage:** the `local-storage.yaml.skip` file, the Longhorn
  Helm release, and the `is-default-class` patch. These survived the converge - checked,
  `longhorn` is still the only default StorageClass - but nothing would restore them if
  they were lost. That gap is what layer three closes.

Two collection behaviours cost real time and are worth knowing before anyone repeats
this on another cluster:

1. The role downloads `/usr/local/bin/k3s-install.sh` **only** when the requested
   version is newer than the installed one, then runs it unconditionally. On a cluster
   installed by hand from `get.k3s.io` - which leaves no copy at that path - the first
   run dies with `[Errno 2] No such file or directory`. The local `site.yml` wrapper
   adds a `get_url` pre-task to close this.
2. With the default `kubeconfig: ~/.kube/config.new`, the role merges the master's
   kubeconfig into the **control node's** `~/.kube/config` as a `k3s-ansible` context,
   makes it current, and rewrites the server address to `api_endpoint`. On a control
   node that reaches the cluster over Tailscale rather than the LAN, that silently
   breaks `kubectl` - it hangs, it does not error. Pinning `kubeconfig` to any other
   path avoids the merge entirely.

### Argo CD: the content layer as code (2026-08-24)

Third and last layer. `k8s/` in the repo holds what runs *inside* the cluster, and Argo
CD **v3.5.1** keeps the cluster matching it. Full detail in `k8s/README.md`; the parts
worth knowing here:

- **Pinned, not `stable`.** The install manifest is referenced by tag with its sha256
  recorded, because `stable` moves and an install that cannot be reproduced is not
  infrastructure as code.
- **`kubectl apply --server-side` is mandatory.** A plain client-side apply fails on the
  `applicationsets.argoproj.io` CRD with `metadata.annotations: Too long: may not be
  more than 262144 bytes` - client-side apply stuffs the whole manifest into an
  annotation and that CRD is over the limit.
- **The Longhorn Helm release is deliberately left out of Argo CD.** Argo CD runs Helm
  hooks as `PreSync`, so Longhorn's pre-upgrade job fires on the very first sync, at a
  point where its service account does not exist yet, and fails
  ([longhorn/longhorn#6415](https://github.com/longhorn/longhorn/issues/6415)). This
  costs nothing: `BackupTarget` and `RecurringJob` are separate CRDs, so the pieces that
  matter can live in git without Argo CD touching the release.
- **Footprint:** 7 pods, 23m CPU and 253Mi memory in total. All seven land on the
  control-plane node - the non-HA manifests carry no anti-affinity. That adds no new
  single point of failure, because the single control plane already is one.

The loop was verified end to end rather than assumed: a commit was pushed to GitHub with
no `kubectl apply` of any kind, and Argo CD created the objects on its own within one
poll interval.

**First child app.** `apps` is the landing namespace for real workloads, and it closes
part of two audit findings:

| Setting | Value | Verified by |
|---|---|---|
| PSA enforce | `baseline` | a privileged pod is rejected: `violates PodSecurity "baseline:latest"` |
| PSA warn / audit | `restricted` | a normal pod is created, with a warning listing what `restricted` would additionally require |
| LimitRange defaults | 500m / 512Mi limits, 50m / 64Mi requests | a pod created with no resources of its own comes back carrying exactly those |

`kube-system` and `longhorn-system` are deliberately left unlabelled. `baseline` would
break more in system components than it buys.

**Access: the Tailscale Kubernetes operator, not cert-manager.** The UI lives at
`https://argocd.tailc6abe2.ts.net`, reachable from any device on the tailnet, with a
real Let's Encrypt certificate that Tailscale renews on its own. The operator gives
every `ingressClassName: tailscale` Ingress its own proxy pod that joins the tailnet as
a device, and builds the name from `spec.tls[0].hosts[0]` plus the tailnet domain.

This is a better fit here than the usual Ingress plus cert-manager plus DNS work,
because the cluster sits at a remote site and is only reachable over Tailscale anyway.
It removes three moving parts and adds one. The cost is one tailnet device per Ingress.

Two details that are easy to get wrong:

- **`server.insecure: "true"` in `argocd-cmd-params-cm` is required, not sloppiness.**
  Argo CD speaks HTTPS itself, so behind any TLS-terminating Ingress it lands in an
  endless redirect loop without it.
- **The `.ts.net` name only resolves where MagicDNS is active.** It is deliberately off
  on LXC 109, so from there the endpoint has to be tested by IP with SNI
  (`curl --resolve`), not by name. A name that does not resolve on the management host
  is not evidence that the Ingress is broken.

### Verified state (2026-08-24)

Checked live against the cluster after the subnet incident described above.

| Component | Version | State |
|-----------|---------|-------|
| Longhorn | v1.12.1 | All 3 nodes `Ready` and schedulable, **0 volumes** |
| Traefik | 3.7.1 | Running, LoadBalancer has an external IP per node, 1 Ingress (Argo CD) |
| metrics-server | - | Running |
| local-path-provisioner | v0.0.34 | Running, but **frozen** - see the `.skip` note under [Version upgrades](#version-upgrades-system-upgrade-controller) |

**Longhorn disk capacity per node**, read from `nodes.longhorn.io` status rather than
`df`, so it reflects what the scheduler actually sees:

| Node | Disk | Mount | Max | Available | Scheduled |
|------|------|-------|-----|-----------|-----------|
| opt5060-i5 | /dev/sda1 | /var/lib/longhorn | 915 GiB | 915 GiB | 0 |
| opt3060-i3 | /dev/sda1 | /var/lib/longhorn | 915 GiB | 915 GiB | 0 |
| opt3050-i5 | /dev/sdb1 | /var/lib/longhorn | 457 GiB | 457 GiB | 0 |

Total raw Longhorn capacity ~2.24 TiB. With the default 3-replica policy the usable
figure is bounded by the smallest node, so roughly 457 GiB of replicated volumes -
not 2.24 TB.

Traefik is **installed and healthy but unused**: nothing routes through it because
no Ingress object exists, so "it is running" is not yet evidence that it works.

**Move to the reserved addresses, verified end to end (2026-08-24):** all three nodes
report the reserved IP as their `InternalIP`, the `flannel.alpha.coreos.com/public-ip`
annotation follows on each, and the VXLAN forwarding table on the master lists
192.168.1.102 and 192.168.1.103 as tunnel endpoints. A throwaway pod pinned to
`opt3060-i3` reached a `longhorn-manager` pod on `opt3050-i5` over the pod network, so
the overlay was tested across nodes rather than assumed from "everything is Running".

A control-plane backup was taken immediately afterwards so the restore point contains
the new systemd units. It came to 2.5 MB, down from 62 MB before the datastore work
described below.

### Longhorn end-to-end test (2026-08-24)

Longhorn had never provisioned a single PVC in the 134 days since it was installed,
so its health was unproven. The test below writes on one node and reads back on a
**different** one - that is the step that actually proves the volume is replicated
and network-attachable rather than node-local.

| Step | Result |
|------|--------|
| PVC provisioning | `Bound` within seconds, 1 GiB |
| Replicas | **3, one per node**, all `running`, volume `robustness: healthy` |
| Write | 64 MB from `/dev/urandom` on opt5060-i5 |
| sha256 at write | `dd4e3a5360bff4548abe981b84fda3ad81c6fb19c836cec7d7a52bf982468ed1` |
| Pod deleted, volume reattached | opt5060-i5 -> **opt3050-i5**, about 90 seconds |
| Read back on the other node | `payload.bin: OK` |
| Teardown | PVC, PV, volume and all 3 replicas removed; `storageScheduled` back to 0 |

Two numbers worth keeping. The **~90 second reattach** is what a stateful workload's
recovery costs when the node under it dies - worth knowing before anything
time-sensitive lands on this cluster. And the teardown completed fully: the `Delete`
reclaim policy removed the PV, the Longhorn volume and every replica with no orphans
left behind, which is exactly where a misconfigured CSI driver quietly accumulates
garbage.

### Volume backups: Garage S3 (2026-08-25)

Until now Longhorn had a backup target of `""` - an empty string, which the
`BackupTarget/default` object reports as `Unavailable: backup target URL is empty`.
Snapshots existed, but a snapshot lives on the same disks as the volume, so a lost
node took its snapshots with it. Backups go somewhere else, and that somewhere is now
a **Garage** S3 server on LXC 100.

| Piece | Value |
|---|---|
| S3 server | Garage v2.3.0, container on LXC 100, `compose/proxmox-lxc-100/garage/` |
| Endpoint the nodes use | `http://100.97.95.101:3900` (Tailscale) |
| Bucket / region | `longhorn` / `garage` |
| Backup target URL | `s3://longhorn@garage/` |
| Data directory | `/mnt/storage/backup/garage` on the MergerFS pool |
| Metadata | LMDB under `/srv/docker-data/garage/meta` |
| Schedule | `RecurringJob backup-daily`, `0 1 * * *` UTC, `retain: 14` |
| Managed by | Argo CD, `k8s/manifests/longhorn/` |

Three decisions that are not obvious:

**Garage rather than MinIO.** The MinIO Community Edition GitHub repository was
archived in February 2026 and is read-only; the web admin console had already been
removed from it in March 2025. Garage is a single Rust binary, runs in about 1 GB of
RAM, and is actively maintained. What it lacks - S3 lifecycle policies - does not
matter here, because retention is the `RecurringJob`'s `retain` value, not the
bucket's job.

**Plain HTTP, no TLS.** The whole path is inside the Tailscale WireGuard tunnel
between the remote site and the homelab. Terminating TLS on top of an already
encrypted tunnel would add a certificate to renew and nothing else.

**Data on the pool, metadata on the root disk.** LXC 100's root disk is at 78% with
11 GB free, so a growing backup bucket cannot live there. But LMDB metadata does not
belong on a MergerFS pool either, so the two are split.

The other thing worth writing down: `replication_factor = 1` is what the Garage
documentation calls a test-only setting, and at the Garage layer that is exactly
right - one node, no redundancy. It is acceptable here because the content is itself
a second copy, and because SnapRAID covers the pool against a disk failure. It is not
acceptable as a general pattern.

#### Verified end to end (2026-08-25)

| Step | Result |
|---|---|
| `BackupTarget` after apply | `Unavailable: False` - Longhorn reached Garage |
| 1 GiB PVC with a known file | created, pod ready |
| `Snapshot` -> `Backup` | `Completed` in about 25 seconds |
| Objects in the bucket | 11 objects, 86.1 kB |
| Restore into a new PVC (`fromBackup` StorageClass) | file content byte-identical |
| Teardown | pods, PVCs, backup, snapshot and StorageClass removed; 589 bytes of volume metadata left in the bucket |

The restore is the half that matters. A backup that has never been read back is a
guess, and this one was read back into a different volume.

#### Re-verified on a live application volume (2026-08-28)

The 2026-08-25 test used a synthetic 1 GiB PVC holding one known file. That proves the
mechanism, but not the case that actually matters: a running application with an open
database. Repeated against the Forgejo volume, **without stopping Forgejo**, so the
snapshot is crash-consistent exactly as it would be if the node died.

| Step | Result |
|---|---|
| `Snapshot` on the running volume | `readyToUse` in 6 s |
| `Backup` to Garage | `Completed` in 11 s |
| Restore into a new PVC (`fromBackup` StorageClass) | pod `Running` after 72 s |
| Verification | Forgejo's own binary listed the admin user off the restored volume |
| Teardown | verify pod, PVC and StorageClass removed; snapshot and backup kept |

The restored volume contained this:

```
gitea.db        1 257 472 bytes
gitea.db-wal    4 128 272 bytes   <- larger than the database itself
gitea.db-shm       32 768 bytes
```

The snapshot caught SQLite mid-WAL. `forgejo -c <app.ini> admin user list` run against the
restored copy recovered the WAL and returned the correct user, so the restore is a usable
Forgejo data directory, not just matching bytes.

!!! warning "A checksum of the database file would have given the wrong answer"
    Comparing `gitea.db` byte-for-byte against the live copy would have failed, and
    comparing it against the pre-snapshot copy would have "passed" while hiding 4 MB of
    unmerged WAL. With SQLite, verify a restore by opening it with the application, not
    by hashing the file.

!!! note "`status.size` is not what the backup costs"
    The `Backup` object reported `size: 283115520` (270 MiB) for a volume holding 5.4 MB
    of data. That field is the snapshot's logical extent. What actually moved was
    `newlyUploadDataSize: 554286` (541 KiB, lz4-compressed), and the Garage bucket
    independently reported 570.4 kB across 35 objects for its entire contents.

    Plan `RecurringJob` retention against `newlyUploadDataSize`. Using `size` overestimates
    by roughly 500x here.

The 72 s restore is almost entirely volume creation and attach, not transfer - 541 KiB
does not take 70 seconds. It matches the ~90 s reattach measured on 2026-08-24, so the
recovery time for a volume this size is set by attach, not by data size.

#### It is monitored, and by the right question

`scripts/longhorn-backup-check.sh` runs on LXC 109 at 02:00 UTC - an hour after the
`RecurringJob`, half an hour after `k3s-backup.sh` - and pushes to the Uptime Kuma
monitor `cron: longhorn-backup-check (109)`.

It deliberately does not monitor whether Garage is up. Garage answers just as happily
when Longhorn cannot write to it and when the job never ran, so the script checks the
`BackupTarget` condition, reads the bucket, and compares every volume's newest
`Completed` backup against a 26 hour window. A missed run turns the monitor red by
heartbeat timeout; a run that failed turns it red with the reason attached.

Two things it had to be taught, both of which would otherwise have made it cry wolf:
zero volumes is a legitimate state and gets its own `no-volumes` message rather than a
silent pass, and a volume younger than the window has not missed anything yet, because
the job only runs once a day. Details in
[scripts/README.md](https://github.com/Pironex9/homelab/blob/main/scripts/README.md).

A third check was added on 2026-08-27, after the USB re-enumeration above: **step 5
walks `nodes.longhorn.io` and fails on any node or disk whose `Ready` condition is not
`True`.** The incident exposed a hole in the original design - with zero volumes on the
cluster, steps 1 to 4 all pass and the script pushed a cheerful `up - no-volumes` while
a third of the storage was out of service. Disk health is independent of whether there
is anything to back up today, so it gets its own gate. The message carries the offending
`node/path`, and a healthy run now reports the fleet size and free space:

```
== 5/5 Longhorn node-ok es lemezek ==
  3 node, minden lemez Ready, 2288 GiB szabad
```

#### Two more monitors (2026-08-27)

| Monitor | Type | Interval | What it answers |
|---|---|---|---|
| `cron: k3s-backup (LXC 109)` | push | 25 h | did the control-plane backup finish? |
| `K3s helyszin (orangepione)` | ping | 1 h, 2 retries at 15 min | is there power and network at the remote site? |

`k3s-backup.sh` had been the only cron line on LXC 109 without a Kuma push. It exits
non-zero on failure, so the crontab uses the same `&& curl .../api/push/...?status=up`
pattern as the other jobs: no push means no heartbeat means red. It went two days
unnoticed on 2026-08-26 and 2026-08-27, failing with
`ssh: connect to host opt5060-i5 port 22: Connection timed out` while the master was
down, and only the log recorded it.

The ping monitor targets the **Orange Pi's Tailscale address**, not a K3s node, for two
reasons: it is an SBC with no BIOS AC-power gate, so it comes back first and by itself,
and it makes the monitor a question about the *site* rather than about Kubernetes. The
interval is deliberately slow - planned outages at that location run for hours, and a
monitor that fires on every five-minute blip stops being read.

#### The access key

The repository is public, so the S3 key is not in it. It lives in the
`garage-backup-secret` Secret in `longhorn-system`, created by hand with
`kubectl create secret generic`, and the `BackupTarget` only references it by name.
Note that `garage key create` prints the secret key on stdout - do not run it in a
terminal whose output is logged.

---

## Clock synchronisation: found by the monitoring stack on day one (2026-08-28)

`kube-prometheus-stack` went in and immediately raised `NodeClockNotSynchronising`
against the master. It was real.

### The measurement

Four independent probes agreed on the drift to within 20 ms:

| Probe from `opt5060-i5` | Result |
|---|---|
| router IPv6 link-local, no scope | `TimeoutError` - **this is what timesyncd was doing** |
| router IPv6 link-local, `scope=eno1` | answers, offset **-0.687 s**, 1 ms RTT |
| router IPv4 `192.168.1.1` | answers, stratum 2, offset **-0.687 s**, 1 ms RTT |
| `ntp.ubuntu.com` / `pool.ntp.org` | answer, offset **-0.668 s** / **-0.683 s** |

The master's clock was **0.687 s fast and free-running** - `node_timex_sync_status=0`,
`Frequency=0`, no correction being applied at all.

### Why, exactly

DHCP hands out the router's **IPv6 link-local** address as the NTP server
(`fe80::62d8:a4ff:fe2c:a93f`, derived from the router MAC `60:d8:a4:2c:a9:3f`). A
link-local address needs an interface scope; without one the packet goes nowhere. That
is what the master's journal had been logging every 34 minutes:

```
systemd-timesyncd: Timed out waiting for reply from [fe80::62d8:a4ff:fe2c:a93f]:123
```

**The router is not at fault** - the workers reach it fine (`Contacted time server`,
stratum 2, jitter ~200 µs). And `FallbackNTPServers=ntp.ubuntu.com` was configured but
never used, because:

!!! warning "A configured-but-dead NTP server blocks the working fallback"
    systemd only falls back to `FallbackNTP=` when **no** server is configured at all.
    One unreachable DHCP-provided server is enough to keep a perfectly good fallback
    from ever being tried. A non-empty server list looks like success from the outside.

### The fix

A drop-in, so the original `timesyncd.conf` stays untouched and the rollback is one
`rm`. Applied to all three nodes, because the workers depend on the same fragile
construction - `opt3050-i5` also has timeouts in its journal, it just gets through
sometimes:

```bash
sudo mkdir -p /etc/systemd/timesyncd.conf.d
printf '[Time]\nNTP=192.168.1.1\n' | sudo tee /etc/systemd/timesyncd.conf.d/10-router-ipv4.conf
sudo systemctl restart systemd-timesyncd
```

The router's IPv4 address needs no scope, keeps the traffic local (1 ms) and adds no
internet dependency. Result, re-measured against `pool.ntp.org` - a server the node does
*not* sync to, so it is an independent check:

```
opt5060-i5   NTPSynchronized=yes   ServerAddress=192.168.1.1
opt3060-i3   NTPSynchronized=yes   ServerAddress=192.168.1.1
opt3050-i5   NTPSynchronized=yes   ServerAddress=192.168.1.1

master offset   -0.687 s  ->  +0.0024 s
```

Rollback if anything looks wrong: delete that one file and restart the service. This is
safe to do at a site with no out-of-band access - `systemd-timesyncd` is not part of the
network stack, so a bad config cannot make a node unreachable.

!!! danger "`date -u` agreeing does not prove the clocks are synchronised"
    This page previously recorded that the workers run UTC and the master runs CEST, and
    that `date -u` showed all three in agreement - so the two-hour difference was only a
    timezone display artefact, not drift. That was true and also **hid this problem**.

    A 0.687 s offset is invisible at `date`'s one-second granularity. The timezone
    difference is still cosmetic; the sync status was not, and only
    `timedatectl` / `node_timex_sync_status` showed it.

Not yet in Ansible: this was applied by hand. The `ansible/` layer uses the
`k3s-io/k3s-ansible` collection, which does not manage NTP, so it would need a custom
task. Until then, a rebuilt node will come back with the broken DHCP-provided server.

## Planned

- [x] DHCP reservations on router (prevent IP drift) - **lost 2026-08-23**, see the subnet note
- [x] fstab entries for Longhorn HDDs on all 3 nodes
- [x] Longhorn install via Helm
- [x] Longhorn healthy on all 3 nodes (2026-08-24)
- [x] Test PVC end-to-end - written, reattached to another node, checksum verified, cleanly torn down (2026-08-24)
- [x] Longhorn UI reachable over the tailnet, no port-forward (2026-08-28)
- [x] Fix the dual-default StorageClass durably - `.skip` file + patch, verified across a k3s restart (2026-08-24)
- [x] Longhorn disk health in the daily check - added after the 2026-08-27 USB unmount (`longhorn-backup-check.sh` step 5)
- [x] Out-of-band signal for the remote site - Kuma ping monitor on the Orange Pi (2026-08-27)
- [ ] Verify `AC Power Recovery = Power On` in the BIOS of all three OptiPlexes - the master stayed down for 2 d 4 h after the 2026-08-25 outage while the workers returned a day earlier, so at least the master is not set
- [x] Automated, GitOps-driven version upgrades - system-upgrade-controller v0.20.1 under Argo CD (2026-08-28)
- [x] k3s v1.34.5 -> v1.36.4 and Longhorn v1.11.1 -> v1.12.1, done on an empty cluster (2026-08-28)
- [x] Switch the Plans from `cordon` to `drain` - **done 2026-08-28**; the mechanism was re-measured on a live volume the same day and the first explanation turned out to be wrong, see the drain section
- [x] Re-verify the drain path once real volumes exist - **done 2026-08-28** on the Forgejo volume with 3 healthy replicas: drain 12 s, workload serving again in 42 s, replica rebuilt 37 s after uncordon, nothing blocked
- [x] local-path-provisioner frozen at v0.0.34 by the `.skip` file - **decided 2026-08-28: leave it**, four options weighed, revisit when something needs `local-path`
- [x] Re-check whether Longhorn can go under Argo CD - longhorn/longhorn#6415 was fixed in v1.6.0, so the old reason is stale; **still not adopting**, new reason in `k8s/README.md`
- [x] Exercise the SUC drain wiring - **done 2026-08-28** by removing the plan-hash label from a worker; job in 43 s, `prepare` gate and `drain` both correct, PDB rejected twice then released
- [x] Scale `coredns` to 2 replicas - **done 2026-08-28**. Not via a `.skip` file: k3s's bundled `coredns.yaml` has no `replicas` field at all, so re-applying it does not reset the count. Re-check after the next k3s restart anyway - that check is exactly what was skipped in April, which is why the local-path patch silently reverted for four months
- [ ] k3s is one patch ahead of the release channel on all three hops (v1.36.4 vs `stable` v1.36.3) - cannot be undone, wait for the channel to catch up
- [x] Prometheus + Grafana monitoring stack - **kube-prometheus-stack 88.6.0 under Argo CD (2026-08-28)**, `https://grafana.tailc6abe2.ts.net`, details in `k8s/README.md`
- [x] Fix NTP on the k3s nodes - **done 2026-08-28**, found by the new monitoring stack on its first day; master was 0.687 s fast with no correction
- [ ] Home-side Tailscale subnet router for `192.168.0.0/24`, so the cluster could reach ntfy and Uptime Kuma directly - only a route exists in the other direction today
- [x] Move the NTP drop-in into Ansible - **done 2026-08-28**, own play in `ansible/site.yml`, so a rebuilt node no longer returns to the broken DHCP server
- [x] Route Alertmanager somewhere - **Telegram (2026-08-28)**, not ntfy: the cluster is at the other site and cannot reach `192.168.0.208` (measured, HTTP 000 from both a node and a pod) - it runs, but no receiver is configured, so alerts are only visible in its own UI. Needs a webhook URL, so an out-of-band Secret
- [x] Longhorn UI reachable without port-forward - `https://longhorn.tailc6abe2.ts.net` (2026-08-28). **It has no authentication**; the tailnet is the only thing protecting it
- [x] Ingress with real TLS - solved by the `tailscale` IngressClass, not by cert-manager: two live Ingresses (`argocd`, `forgejo`) with Let's Encrypt certificates renewed by Tailscale. Traefik still runs and is still the **default** IngressClass, so every tailnet Ingress must set `ingressClassName: tailscale` explicitly
- [ ] RBAC policies
- [ ] Network policies
- [x] Volume backup target - Garage S3 on LXC 100, backup and restore verified (2026-08-25), re-verified on a live application volume with an open SQLite database (2026-08-28)
- [ ] Velero backup (cluster-object backup; the volume half is covered by Longhorn + Garage)
- [x] First workload deployment - Forgejo 16.0.3 on a 10 GiB Longhorn volume behind a Tailscale Ingress (2026-08-28), see `k8s/README.md`

---

## Common Commands

```bash
# From LXC 109 (claude-mgmt)
kubectl get nodes -o wide
kubectl get pods -A
kubectl top nodes
kubectl cluster-info

# Wake up cluster (from any Tailscale node)
ssh nex@orangepione "sudo /usr/local/bin/wakeonlan.sh"

# SSH to nodes
ssh nex@opt5060-i5
ssh nex@opt3060-i3
ssh nex@opt3050-i5

# K3s service management (on nodes)
sudo systemctl status k3s          # master
sudo systemctl status k3s-agent    # workers
sudo journalctl -u k3s -f          # master logs
sudo journalctl -u k3s-agent -f    # worker logs

# Reinstall (if needed - always specify node-ip and flannel-iface)
/usr/local/bin/k3s-uninstall.sh         # master
/usr/local/bin/k3s-agent-uninstall.sh   # workers
sudo rm -rf /etc/rancher /var/lib/rancher

# Longhorn
kubectl get pods -n longhorn-system
kubectl get volumes -n longhorn-system
kubectl port-forward -n longhorn-system svc/longhorn-frontend 8080:80  # UI

# Helm
helm list -n longhorn-system
helm upgrade longhorn longhorn/longhorn --namespace longhorn-system --reuse-values
```
