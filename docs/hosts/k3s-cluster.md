# K3s Cluster

**Date:** 2026-03-31
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
  INSTALL_K3S_EXEC='server --node-ip=192.168.0.104 --advertise-address=192.168.0.104 --flannel-iface=eno1' \
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
  K3S_URL=https://192.168.0.104:6443 \
  K3S_TOKEN=<node-token> \
  INSTALL_K3S_EXEC='agent --node-ip=192.168.0.105 --flannel-iface=enp1s0' \
  sh -

# opt3050-i5
curl -sfL https://get.k3s.io | \
  K3S_NODE_NAME=opt3050-i5 \
  K3S_URL=https://192.168.0.104:6443 \
  K3S_TOKEN=<node-token> \
  INSTALL_K3S_EXEC='agent --node-ip=192.168.0.106 --flannel-iface=enp1s0' \
  sh -
```

> Always specify `--node-ip` and `--flannel-iface` explicitly. Without these, K3s uses the wrong interface after a network change.

---

## Management from LXC 109 (claude-mgmt)

LXC 109 manages the K3s cluster via Tailscale + kubectl.

### Setup done (2026-03-19)

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

5. **Passwordless sudo** for kubeconfig on master:
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
MAC1="54:bf:64:68:a0:30"  # opt5060-i5
MAC2="54:bf:64:a2:ff:77"  # opt3060-i3
MAC3="d8:9e:f3:13:4d:97"  # opt3050-i5
INTERFACE="end0"

echo "Waking up K3s cluster nodes..."
sudo etherwake -i $INTERFACE $MAC1
sleep 2
sudo etherwake -i $INTERFACE $MAC2
sleep 2
sudo etherwake -i $INTERFACE $MAC3
echo "Wake packets sent to all nodes"
```

**Auto-start on boot** (`nex` user crontab):
```
@reboot sleep 60 && /usr/local/bin/wakeonlan.sh
```

The script uses `sudo etherwake` - passwordless sudo is configured:
```
/etc/sudoers.d/etherwake: nex ALL=(ALL) NOPASSWD: /usr/sbin/etherwake
```

**Remote trigger from any Tailscale node:**
```bash
ssh nex@orangepione "sudo /usr/local/bin/wakeonlan.sh"
```

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

## Planned

- [ ] DHCP reservations on router (prevent IP drift)
- [ ] Longhorn storage - 1 TB + 2x500 GB HDDs
- [ ] Prometheus + Grafana monitoring stack
- [ ] Traefik ingress with Let's Encrypt SSL
- [ ] RBAC policies
- [ ] Network policies
- [ ] Velero backup
- [ ] Passwordless sudo on all nodes (for full remote management from LXC 109)
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
```
