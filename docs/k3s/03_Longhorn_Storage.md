**Date:** 2026-08-28
**Cluster:** 3x Dell OptiPlex, 192.168.1.0/24 (separate location, Tailscale access only)

---

# Longhorn Storage

Distributed block storage on the three nodes: the real usable capacity, the restore that was actually performed, and the backup target on Garage S3.

Split out of the [K3s Cluster host page](../hosts/k3s-cluster.md) on 2026-08-28,
which had grown to 1983 lines and six unrelated projects. The host page keeps the
machine reference - hardware, addressing, live state, access - and this page keeps
the work. Nothing below was rewritten in the move.

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
| local-path-provisioner | v0.0.34 | Running, but **frozen** - see the `.skip` note in [Version Upgrades](02_Version_Upgrades.md) |

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
