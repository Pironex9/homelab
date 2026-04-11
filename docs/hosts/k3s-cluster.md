# K3s Cluster

**Date:** 2026-04-08
**Location:** Separate physical location (remote, Tailscale access only)
**Network:** 192.168.2.0/24 (separate router from Proxmox network, gateway 192.168.2.1)

---

## Cluster Overview

3-node K3s cluster built from used Dell OptiPlex hardware. Used for learning Kubernetes, experimenting with workloads, and eventually running production-grade services with Longhorn storage and a full monitoring stack.

| Property | Value |
|----------|-------|
| K3s version | v1.34.5+k3s1 |
| Kubernetes | v1.34 |
| Container runtime | containerd 2.1.5-k3s1 |
| CNI | Flannel |
| Ingress | Traefik (built-in) |
| Storage class | local-path (default) |
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

**Storage classes:**
```
NAME                 PROVISIONER             DEFAULT
local-path           rancher.io/local-path   -
longhorn             driver.longhorn.io      yes
longhorn-static      driver.longhorn.io      -
```

**Longhorn UI** is available via port-forward (no ingress yet):
```bash
kubectl port-forward -n longhorn-system svc/longhorn-frontend 8080:80
# then open http://localhost:8080
```

---

## Planned

- [x] DHCP reservations on router (prevent IP drift)
- [x] fstab entries for Longhorn HDDs on all 3 nodes
- [x] Longhorn install via Helm
- [ ] Verify Longhorn UI + test PVC
- [ ] Prometheus + Grafana monitoring stack
- [ ] Traefik ingress with Let's Encrypt SSL
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
