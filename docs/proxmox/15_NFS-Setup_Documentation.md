**Date:** 2026-02-11
**Updated:** 2026-03-04
**Hostname:** pve
**IP address:** 192.168.0.109

---

## Overview

NFS is used in both directions:

- **Proxmox → LAN**: exports the media storage pool so Nobara (and others) can mount it
- **Nobara → Proxmox**: exports a backup HDD so Proxmox can rsync LXC backups onto it

---

## Proxmox as NFS Server

Proxmox exports its storage to the local network.

### Install NFS server
```bash
apt update
apt install nfs-kernel-server
```

### `/etc/exports`
```
/mnt/storage 192.168.0.0/24(rw,sync,no_subtree_check,no_root_squash,fsid=1)
/mnt/disk1 192.168.0.0/24(rw,sync,no_subtree_check,no_root_squash,fsid=2)
/mnt/disk2 192.168.0.0/24(rw,sync,no_subtree_check,no_root_squash,fsid=3)
/mnt/disk3 192.168.0.0/24(rw,sync,no_subtree_check,no_root_squash,fsid=4)
/mnt/disk4 192.168.0.0/24(rw,sync,no_subtree_check,no_root_squash,fsid=5)
```

### Apply and verify
```bash
exportfs -a
systemctl restart nfs-kernel-server
exportfs -v
```

---

## Nobara PC as NFS Server (backup target)

Nobara exports its backup HDD so Proxmox can rsync LXC dump files onto it.

### Nobara `/etc/exports`
```
/mnt/hdd/Backup 192.168.0.109(rw,sync,no_subtree_check,no_root_squash)
```

Only the Proxmox host (192.168.0.109) has access - not the whole LAN.

### Apply on Nobara
```bash
sudo exportfs -ra
```

### Proxmox mounts it in `/etc/fstab`
```
192.168.0.100:/mnt/hdd/Backup /mnt/pve/nobara-backup nfs soft,timeo=30,retrans=3,_netdev,x-systemd.automount 0 0
```

- `soft` + `timeo=30` + `retrans=3` - times out gracefully if Nobara is offline, does not freeze Proxmox
- `x-systemd.automount` - mounts on first access, not at boot

---

## Nobara as NFS Client (mounts Proxmox storage)

### Install NFS client on Nobara
```bash
sudo dnf install nfs-utils
```

### Create mount points
```bash
sudo mkdir -p /mnt/storage /mnt/disk1 /mnt/disk2 /mnt/disk3 /mnt/disk4
```

### Nobara `/etc/fstab` entries
```
192.168.0.109:/mnt/storage /mnt/storage nfs vers=3,defaults 0 0
192.168.0.109:/mnt/disk1 /mnt/disk1 nfs vers=3,defaults 0 0
192.168.0.109:/mnt/disk2 /mnt/disk2 nfs vers=3,defaults 0 0
192.168.0.109:/mnt/disk3 /mnt/disk3 nfs vers=3,defaults 0 0
192.168.0.109:/mnt/disk4 /mnt/disk4 nfs vers=3,defaults 0 0
```

---

## Notes

- `fsid=` is required for non-root filesystem exports on Proxmox
- `no_root_squash` allows root access from the client
- Nobara runs NFSv4 only (no rpcbind) - `showmount -e` will fail from Proxmox, but mounts work fine
- Nobara is not always on - the soft mount on Proxmox ensures it never freezes the host
