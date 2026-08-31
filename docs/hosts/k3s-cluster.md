# K3s Cluster

**Date:** 2026-08-28 (state measured the same day)
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

## What is on the other pages

This page is the machine reference: hardware, addressing, live state, access, and
the node-level OS settings. The work done *on* the cluster lives beside it, split
out on 2026-08-28 when this file had reached 1983 lines and six unrelated
projects.

| Page | What |
|------|------|
| [Infrastructure as Code](../k3s/01_K3s_Infrastructure_as_Code.md) | the three code layers: Ansible, Argo CD, and the restore proofs |
| [Version Upgrades](../k3s/02_Version_Upgrades.md) | system-upgrade-controller, the one-minor-at-a-time rule, the three hops of 2026-08-28 |
| [Longhorn Storage](../k3s/03_Longhorn_Storage.md) | real usable capacity, the restore that was performed, the Garage S3 backup target |
| [Hardening and Recovery](../k3s/04_Hardening_and_Recovery.md) | proven control-plane restore, default-deny NetworkPolicy, Secrets encrypted at rest |
| [Wake-on-LAN](../k3s/05_Wake_on_LAN.md) | powering the remote nodes on, and why the obvious setup does not survive a shutdown |

---

## Cluster Overview

3-node K3s cluster built from used Dell OptiPlex hardware. Used for learning Kubernetes, experimenting with workloads, and eventually running production-grade services with Longhorn storage and a full monitoring stack.

| Property | Value |
|----------|-------|
| K3s version | v1.36.4+k3s1 (upgraded 2026-08-28, see [Version upgrades](../k3s/02_Version_Upgrades.md)) |
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
| `02:81:85:dc:83:d9` | orangepione | 192.168.1.100 (reserved 2026-08-29) |

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
- `orangepione` used to advertise the old `192.168.2.0/24` here. That is gone: on
  2026-08-29 its `AdvertiseRoutes` read `0.0.0.0/0`, `::/0`, `192.168.1.0/24`. Only
  the two exit-node prefixes are approved, so it duplicates the advertisement of
  this subnet without serving it - `PrimaryRoutes` on it is empty and `opt3060-i3`
  remains the one carrying the prefix.


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

## Current Cluster State (2026-08-28)

Measured live, not carried over: `kubectl get nodes -o wide`, `kubectl top nodes`,
`kubectl get pods -A`, `kubectl get pvc -A`. The section header carried a March
date for months while the tables under it drifted, which is exactly the failure
this line is meant to make visible - re-measure before editing it.

### Nodes

```
NAME         STATUS   ROLES           VERSION        INTERNAL-IP     KERNEL
opt5060-i5   Ready    control-plane   v1.36.4+k3s1   192.168.1.101   6.8.0-138-generic
opt3060-i3   Ready    <none>          v1.36.4+k3s1   192.168.1.102   6.8.0-138-generic
opt3050-i5   Ready    <none>          v1.36.4+k3s1   192.168.1.103   6.8.0-138-generic
```

### Resource usage

Not idle any more, and the difference is the point: in March the two workers sat
at 30m CPU and ~380 MB. Longhorn, kube-prometheus-stack and the Tailscale
operator are what changed.

| Node | CPU | RAM |
|------|-----|-----|
| opt5060-i5 | 623m (10%) | 4602 Mi (29%) - control plane |
| opt3060-i3 | 243m (6%) | 2771 Mi (35%) |
| opt3050-i5 | 208m (5%) | 1389 Mi (17%) |

### Pods by namespace

60 pods across 7 namespaces. The March table listed five.

| Namespace | Pods | What |
|-----------|------|------|
| longhorn-system | 28 | Longhorn v1.12.1: manager, CSI, engine and instance managers |
| kube-system | 10 | 2x coredns, local-path-provisioner, metrics-server, traefik, 3x svclb-traefik, 2 completed traefik helm-install jobs |
| monitoring | 8 | kube-prometheus-stack: Prometheus, Grafana, Alertmanager, operator, node exporters |
| argocd | 7 | Argo CD v3.5.1 |
| tailscale | 6 | Tailscale Kubernetes operator, one device per Ingress |
| apps | 3 | Forgejo, Umami + its Postgres |
| system-upgrade | 1 | system-upgrade-controller, which performs the k3s version bumps |

### Persistent volumes

All four on Longhorn, which is the default StorageClass. `local-path` is still
installed and usable, just no longer the default.

| Namespace | Claim | Size |
|-----------|-------|------|
| apps | forgejo-data | 10 Gi |
| apps | umami-db-data | 10 Gi |
| monitoring | prometheus-...-db-...-0 | 20 Gi |
| monitoring | monitoring-grafana | 5 Gi |

### Ingress

Five, all `ingressClassName: tailscale`. Traefik is still the cluster default
IngressClass, so the class name has to be written out on every one of these or
the Ingress silently lands on Traefik instead.

| Namespace | Host |
|-----------|------|
| apps | forgejo.tailc6abe2.ts.net |
| apps | umami.tailc6abe2.ts.net |
| argocd | argocd.tailc6abe2.ts.net |
| longhorn-system | longhorn.tailc6abe2.ts.net |
| monitoring | grafana.tailc6abe2.ts.net |

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

Re-measured on 2026-08-28. Three rows were wrong before that, and the firewall one
was wrong in the direction that matters: it claimed a control that does not exist.

| Item | Status |
|------|--------|
| Tailscale mesh VPN | Active |
| SSH key auth | Configured |
| UFW firewall | **Inactive on all three nodes** - `ufw status` returns `Status: inactive` on each. This is also why `manage_firewall: false` is set in `ansible/group_vars/k3s_cluster.yml`: the collection would otherwise start writing rules on a host with no active firewall |
| WoL only on local network | Yes |
| K3s RBAC | Default (not hardened) |
| Secrets encryption at rest | **Enabled 2026-08-28**, AES-CBC, all 39 secrets re-encrypted. See [Hardening and Recovery](../k3s/04_Hardening_and_Recovery.md) for what it does and does not protect |
| Network policies | Partial: `apps` is default-deny ingress since 2026-08-28 with one explicit allow, `longhorn-system` gained a hand-written allow for Prometheus on 2026-08-29, and 13 more come from the `argocd` and `longhorn-system` Helm charts. `monitoring`, `kube-system`, `system-upgrade` and `tailscale` still have none. Enforcement verified, not assumed - see [Hardening and Recovery](../k3s/04_Hardening_and_Recovery.md) |
| Pod Security Standards | Partial: `apps` is `baseline`, `system-upgrade` is `privileged`. The other eight namespaces are unlabelled, `monitoring` deliberately so - node-exporter needs `hostNetwork` and `hostPath` |

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
- [x] Longhorn metrics in Grafana - **done 2026-08-29**. The stack's 25 bundled dashboards saw nothing of the storage layer; a ServiceMonitor, a second NetworkPolicy and dashboard 16888 fixed that, 3/3 targets up. Longhorn's own chart policy held every target at `up=0` first, reporting `connection refused` while the manager was demonstrably listening - see [Longhorn Storage](../k3s/03_Longhorn_Storage.md#monitoring-the-storage-layer-2026-08-29)
- [x] Longhorn alerting - **done 2026-08-30**. Six PrometheusRules to the existing Telegram receiver (faulted, degraded, disk not schedulable, disk >85%, backup failed, backup older than 36h). The metrics were visible on a dashboard for one day and that is not the same as noticed. It also turned up that dashboard 16888's three robustness panels report wrong numbers on Longhorn 1.12.1 - the metric is one-hot with a `state` label, not the numeric enum the panels expect - see [Longhorn Storage](../k3s/03_Longhorn_Storage.md#alerting-on-the-storage-layer-2026-08-30)
- [x] Fix NTP on the k3s nodes - **done 2026-08-28**, found by the new monitoring stack on its first day; master was 0.687 s fast with no correction
- [ ] Home-side Tailscale subnet router for `192.168.0.0/24`, so the cluster could reach ntfy and Uptime Kuma directly - only a route exists in the other direction today
- [x] Move the NTP drop-in into Ansible - **done 2026-08-28**, own play in `ansible/site.yml`, so a rebuilt node no longer returns to the broken DHCP server
- [x] Route Alertmanager somewhere - **Telegram (2026-08-28)**, not ntfy: the cluster is at the other site and cannot reach `192.168.0.208` (measured, HTTP 000 from both a node and a pod) - it runs, but no receiver is configured, so alerts are only visible in its own UI. Needs a webhook URL, so an out-of-band Secret
- [x] Longhorn UI reachable without port-forward - `https://longhorn.tailc6abe2.ts.net` (2026-08-28). **It has no authentication**; the tailnet is the only thing protecting it
- [x] Ingress with real TLS - solved by the `tailscale` IngressClass, not by cert-manager: two live Ingresses (`argocd`, `forgejo`) with Let's Encrypt certificates renewed by Tailscale. Traefik still runs and is still the **default** IngressClass, so every tailnet Ingress must set `ingressClassName: tailscale` explicitly
- [ ] RBAC policies
- [x] Volume backup target - Garage S3 on LXC 100, backup and restore verified (2026-08-25), re-verified on a live application volume with an open SQLite database (2026-08-28)
- [x] Actually restore a control-plane backup, not just decrypt one - **done 2026-08-28**, `scripts/k3s-restore-test.sh`: API up in 6 s, nothing missing, three traps found on the way
- [x] Secrets encryption at rest - **done 2026-08-28** after the restore proof, deliberately in that order. AES-CBC, all 39 secrets re-encrypted, verified by reading the raw kine values. Protects a leaked database, not a stolen disk - the key sits on the same disk
- [x] NetworkPolicy on `apps` - **done 2026-08-28**, default-deny ingress plus one allow for the Tailscale proxy pod. Enforcement proven in both directions; probes measured to survive default-deny on this k3s version
- [ ] NetworkPolicy for `monitoring` - the next candidate, and the harder one: Prometheus must reach every namespace, Grafana is on the tailnet, the operator talks to all three. `kube-system` and `tailscale` stay out on purpose
- [ ] Velero backup (cluster-object backup; the volume half is covered by Longhorn + Garage)
- [x] First workload deployment - Forgejo 16.0.3 on a 10 GiB Longhorn volume behind a Tailscale Ingress (2026-08-28), see `k8s/README.md`
- [x] Second workload - Umami 3.3.1 web analytics with its own Postgres 17 on a 10 GiB Longhorn volume (2026-08-31), see `k8s/README.md`. The dashboard is on the tailnet; the public tracker endpoint is still to be published through Pangolin

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
