# K3s Cluster

**Date:** 2026-04-08 (state verified 2026-08-24)
**Location:** Separate physical location (remote, Tailscale access only)
**Network:** 192.168.2.0/24 (separate router from Proxmox network, gateway 192.168.2.1)

!!! danger "Subnet changed on 2026-08-23 - the IPs below are stale"

    The router at the remote location was replaced or factory-reset at 15:10 on
    2026-08-23. The subnet became **192.168.1.0/24** (gateway 192.168.1.1) and every
    DHCP reservation was lost, so the nodes are on arbitrary leases: opt5060-i5 on
    192.168.1.90, opt3060-i3 on 192.168.1.152, opt3050-i5 on 192.168.1.231.

    K3s had `--node-ip` hardcoded to the old addresses and crash-looped for 16 hours
    (1855 restarts) with `error getting node subnet: failed to find interface with
    specified node ip`. Note that k3s exits **0** on this failure, so systemd logs
    `Deactivated successfully` - the unit-level messages look like a clean shutdown
    and hide the real cause, which is only visible in the k3s log lines themselves.

    Fixed on 2026-08-24 by pointing the config at the current DHCP leases. The IP
    tables in this document are deliberately **not** updated yet: the current
    addresses are temporary, and fixed reservations still have to be set on the new
    router. Everything else here - hardware, Longhorn, Traefik, DNS design - is
    current.

    The config lives in three places, not one:

    | Node | File | Key |
    |------|------|-----|
    | master | `/etc/systemd/system/k3s.service` | `--node-ip`, `--advertise-address` |
    | workers | `/etc/systemd/system/k3s-agent.service` | `--node-ip` |
    | workers | `/etc/systemd/system/k3s-agent.service.env` | `K3S_URL` (**not** in ExecStart) |

    Also delete `/var/lib/rancher/k3s/agent/etc/k3s-agent-load-balancer.json` on the
    workers - it caches the old server address and overrides the new `K3S_URL`.

    Tailscale access was never affected, because the kubeconfig and SSH both use
    Tailscale names, not LAN addresses.

---

## Cluster Overview

3-node K3s cluster built from used Dell OptiPlex hardware. Used for learning Kubernetes, experimenting with workloads, and eventually running production-grade services with Longhorn storage and a full monitoring stack.

| Property | Value |
|----------|-------|
| K3s version | v1.34.5+k3s1 |
| Kubernetes | v1.34 |
| Container runtime | containerd 2.1.5-k3s1 |
| CNI | Flannel |
| Ingress | Traefik 3.6.9 (built-in), no Ingress objects yet |
| Storage class | longhorn (sole default since 2026-08-24), local-path (available, not default) |
| Access | Tailscale mesh VPN |

---

## Hardware

| Node | Model | Role | CPU | RAM | Disk | Local IP | Tailscale IP | Interface |
|------|-------|------|-----|-----|------|----------|--------------|-----------|
| opt5060-i5 | Dell OptiPlex 5060 | control-plane | Intel i5-8500 @ 3.00GHz | 16 GB | 57 GB (35% used) | 192.168.2.101 | 100.68.209.53 | eno1 |
| opt3060-i3 | Dell OptiPlex 3060 | worker | Intel i3-8100 @ 3.60GHz | 8 GB | 98 GB (10% used) | 192.168.2.102 | 100.124.149.16 | enp1s0 |
| opt3050-i5 | Dell OptiPlex 3050 | worker | Intel i5-7500 @ 3.40GHz | 8 GB | 98 GB (10% used) | 192.168.2.103 | 100.102.92.89 | enp1s0 |

**OS:** Ubuntu 24.04.3 LTS, kernel 6.8.0-101-generic
**User:** `nex` (sudo access)
**Cost:** ~200 EUR compute + 50 EUR Orange Pi bundle + 40 EUR switch/cables = ~300 EUR total

---

## Network Topology

```
[Internet] → [Router (192.168.0.1)]
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
| `54:bf:64:68:a0:30` | opt5060-i5 | 192.168.2.101 |
| `54:bf:64:a2:ff:77` | opt3060-i3 | 192.168.2.102 |
| `d8:9e:f3:13:4d:97` | opt3050-i5 | 192.168.2.103 |
| Orange Pi MAC | orangepione | 192.168.2.100 |

---

## K3s Installation

### Master node (opt5060-i5)

```bash
curl -sfL https://get.k3s.io | \
  K3S_NODE_NAME=opt5060-i5 \
  INSTALL_K3S_EXEC='server --node-ip=192.168.2.101 --advertise-address=192.168.2.101 --flannel-iface=eno1' \
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
  K3S_URL=https://192.168.2.101:6443 \
  K3S_TOKEN=<node-token> \
  INSTALL_K3S_EXEC='agent --node-ip=192.168.2.102 --flannel-iface=enp1s0' \
  sh -

# opt3050-i5
curl -sfL https://get.k3s.io | \
  K3S_NODE_NAME=opt3050-i5 \
  K3S_URL=https://192.168.2.101:6443 \
  K3S_TOKEN=<node-token> \
  INSTALL_K3S_EXEC='agent --node-ip=192.168.2.103 --flannel-iface=enp1s0' \
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

## Wake-on-LAN

The cluster is powered off when not in use. An Orange Pi One (Armbian) on the same network handles WoL.

### Orange Pi One

| Property | Value |
|----------|-------|
| OS | Armbian 25.8.1 Noble |
| Role | WoL server + Tailscale exit node |
| Interface | end0 |
| Local IP | 192.168.2.100 |
| Tailscale IP | 100.120.73.44 |
| Tailscale hostname | orangepione |
| User | nex |

### WoL script

**File:** `/usr/local/bin/wakeonlan.sh`

```bash
#!/bin/bash
# K3s Cluster wake up script

MAC1="54:bf:64:68:a0:30"  # opt5060-i5
MAC2="54:bf:64:a2:ff:77"  # opt3060-i3
MAC3="d8:9e:f3:13:4d:97"  # opt3050-i5
INTERFACE="end0"

echo "Waking up nodes (3x retry each)..."
for MAC in $MAC1 $MAC2 $MAC3; do
    for i in 1 2 3; do
        sudo etherwake -i $INTERFACE $MAC
        sleep 1
    done
    echo "Sent 3x to $MAC"
done
echo "Wake packets sent to all nodes"
```

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

- **GS305 Green Ethernet (IEEE 802.3az)** - the switch puts ports into low-power idle when a device disconnects. Unmanaged - cannot be disabled.
- **NIC WoL state** - `ethtool wol g` is re-applied on each boot via `wol.service`. If the machine was power-cut before booting, the state may be lost.

**Workaround:** If WoL fails, power-cycle the node physically or via a smart PDU. BIOS should be set to `AC Power Recovery = Power On` so the node boots automatically on power restore.

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
opt5060-i5   Ready    control-plane   v1.34.5+k3s1   192.168.2.101   6.8.0-106-generic
opt3060-i3   Ready    <none>          v1.34.5+k3s1   192.168.2.102   6.8.0-106-generic
opt3050-i5   Ready    <none>          v1.34.5+k3s1   192.168.2.103   6.8.0-106-generic
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
| traefik | LoadBalancer | 192.168.2.101/102/103 | 80, 443 |

---

## DNS Configuration

All K3s nodes use `--accept-dns=false` - Tailscale does not manage DNS on these nodes. The local router (192.168.2.1) handles all DNS resolution.

**Why:** Tailscale pushes a `~.` catch-all routing domain via systemd-resolved which redirects all DNS queries through 100.100.100.100. On the 192.168.2.x network this caused external DNS resolution to fail (e.g. `apt` could not reach `archive.ubuntu.com`).

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
| opt3050-i5 | /dev/sdb1 | longhorn-sdc | `e1623077-2dcc-44d2-acf8-8df8242ea481` | 465 GB | USB external |

Filesystem: ext4. Formatted 2026-04-06.

**Excluded:** Toshiba MK5055GSXN (33 reallocated sectors + 2 pending) - bad health, not used.

**fstab entries (applied 2026-04-11):**
```
# opt5060-i5 /etc/fstab
UUID=1d358359-cb60-4974-93b3-df15e49741ec /var/lib/longhorn ext4 defaults,nofail 0 2

# opt3060-i3 /etc/fstab
UUID=297b57c3-2ff7-4c7b-b821-2e2cb3e2c5e0 /var/lib/longhorn ext4 defaults,nofail 0 2

# opt3050-i5 /etc/fstab (USB - extra timeout)
UUID=e1623077-2dcc-44d2-acf8-8df8242ea481 /var/lib/longhorn ext4 defaults,nofail,x-systemd.device-timeout=30s 0 2
```

All 3 nodes: `/var/lib/longhorn` mounted and verified (870GB/870GB/435GB free).

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

Installed version: **v1.11.1**

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

### Verified state (2026-08-24)

Checked live against the cluster after the subnet incident described above.

| Component | Version | State |
|-----------|---------|-------|
| Longhorn | v1.11.1 | All 3 nodes `Ready` and schedulable, **0 volumes** |
| Traefik | 3.6.9 | Running, LoadBalancer has an external IP per node, **0 Ingress objects** |
| metrics-server | - | Running |
| local-path-provisioner | - | Running |

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

---

## Planned

- [x] DHCP reservations on router (prevent IP drift) - **lost 2026-08-23**, see the subnet note
- [x] fstab entries for Longhorn HDDs on all 3 nodes
- [x] Longhorn install via Helm
- [x] Longhorn healthy on all 3 nodes (2026-08-24)
- [x] Test PVC end-to-end - written, reattached to another node, checksum verified, cleanly torn down (2026-08-24)
- [ ] Longhorn UI still only reachable via port-forward (no ingress)
- [x] Fix the dual-default StorageClass durably - `.skip` file + patch, verified across a k3s restart (2026-08-24)
- [ ] Prometheus + Grafana monitoring stack
- [ ] Traefik ingress with Let's Encrypt SSL - Traefik runs, but 0 Ingress objects and no cert-manager/ClusterIssuer
- [ ] RBAC policies
- [ ] Network policies
- [ ] Velero backup
- [ ] First workload deployment

---

## Common Commands

```bash
# From LXC 109 (claude-mgmt)
kubectl get nodes -o wide
kubectl get pods -A
kubectl top nodes
kubectl cluster-info

# Wake up cluster (from any Tailscale node)
ssh nex@opi-one "sudo /usr/local/bin/wakeonlan.sh"

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
