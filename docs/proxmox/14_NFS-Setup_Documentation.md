**Date:** 2026-02-11
**Updated:** 2026-04-08 (replace SSHFS automount with systemd service)
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
systemctl restart nfs-server
exportfs -v
```

### Enable NFS server at boot
```bash
systemctl enable nfs-server
```

Note: the service name is `nfs-server` (not `nfs-kernel-server`) on recent Debian/Proxmox versions.

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

**Do not use `/etc/fstab` for these mounts.** Hard fstab NFS entries freeze Nobara's boot if Proxmox is offline. Use systemd automount instead.

### Install NFS client on Nobara
```bash
sudo dnf install nfs-utils
```

### Create mount points
```bash
sudo mkdir -p /mnt/storage /mnt/disk1 /mnt/disk2 /mnt/disk3 /mnt/disk4
```

### Create systemd mount + automount units

Run as root (`sudo -i`) to avoid heredoc indentation issues:

```bash
for share in storage disk1 disk2 disk3 disk4; do
cat > /etc/systemd/system/mnt-${share}.mount << EOF
[Unit]
Description=NFS /mnt/${share} from Proxmox
After=network-online.target
Wants=network-online.target

[Mount]
What=192.168.0.109:/mnt/${share}
Where=/mnt/${share}
Type=nfs
Options=noauto,nfsvers=4,soft,timeo=30,retrans=3,_netdev

[Install]
WantedBy=multi-user.target
EOF
cat > /etc/systemd/system/mnt-${share}.automount << EOF
[Unit]
Description=Automount /mnt/${share}

[Automount]
Where=/mnt/${share}
TimeoutIdleSec=600

[Install]
WantedBy=multi-user.target
EOF
done
```

### Enable and start
```bash
systemctl daemon-reload
systemctl enable --now mnt-storage.automount mnt-disk1.automount mnt-disk2.automount mnt-disk3.automount mnt-disk4.automount
```

### Verify
```bash
ls /mnt/storage
df -h | grep mnt/
```

The first `ls` triggers the automount. All 5 shares should appear in `df -h`.

### How it works

- The `.automount` unit watches the directory
- First access triggers the mount automatically
- After 600 seconds (10 min) of inactivity it unmounts
- If Proxmox is offline: `soft` + `timeo=30` + `retrans=3` means mount attempt times out after ~90 seconds - Nobara does not freeze

---

## Nobara SSHFS Mount (LXC 109 claude-mgmt)

Nobara mounts `/root` from LXC 109 (claude-mgmt) via SSHFS. NFS server cannot run inside an unprivileged LXC, so SSHFS is used instead.

### Prerequisites

Root's SSH key on Nobara must be in LXC 109's `authorized_keys`. Since LXC 109 has password auth disabled, add it via the existing user key:

```bash
sudo ssh-keygen -t ed25519 -f /root/.ssh/id_ed25519 -N ""
sudo cat /root/.ssh/id_ed25519.pub | ssh root@192.168.0.204 "cat >> /root/.ssh/authorized_keys"
```

Also add LXC 109 to root's known_hosts on Nobara:

```bash
sudo ssh-keyscan 192.168.0.204 | sudo tee -a /root/.ssh/known_hosts
```

### Create mount point

```bash
sudo mkdir -p /mnt/claudemgmt
```

Note: no hyphen in `claudemgmt` - systemd unit file names encode hyphens as `\x2d` which causes shell escaping issues.

### Create systemd service

A service unit is used instead of mount+automount. The automount approach caused Dolphin and the KDE desktop to lag/freeze for up to 15 seconds on each access attempt when LXC 109 was offline (the mount unit blocked D-Bus via systemd-hostnamed). The service approach with `reconnect` mounts once and maintains the connection in the background.

```bash
sudo tee /etc/systemd/system/mnt-claudemgmt.service << 'EOF'
[Unit]
Description=SSHFS /root from LXC 109 claude-mgmt
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStartPre=/bin/bash -c 'ssh -o ConnectTimeout=3 -o BatchMode=yes root@192.168.0.204 exit 2>/dev/null'
ExecStart=/usr/bin/sshfs root@192.168.0.204:/root /mnt/claudemgmt \
    -f \
    -o allow_other \
    -o IdentityFile=/home/nex/.ssh/id_ed25519 \
    -o reconnect \
    -o ServerAliveInterval=5 \
    -o ServerAliveCountMax=2
ExecStop=/bin/fusermount3 -u /mnt/claudemgmt
Restart=on-failure
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF
```

### Enable and start

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now mnt-claudemgmt.service
ls /mnt/claudemgmt
```

Should show: `homelab  learning  youtube`

### How it works

- At boot: `ExecStartPre` checks SSH connectivity (3s timeout). If LXC 109 is down, fails fast and retries every 30 seconds.
- When connected: SSHFS runs in foreground (`-f`), systemd owns the process.
- If LXC 109 goes down: `reconnect` + `ServerAliveInterval=5, ServerAliveCountMax=2` detects the drop in 10 seconds, retries in background. File accesses return I/O errors immediately - no desktop freeze.
- When LXC 109 comes back: reconnect re-establishes automatically, no manual intervention needed.
- If reconnect gives up: process exits, `Restart=on-failure` restarts the service after 30 seconds.

---

## Notes

- `fsid=` is required for non-root filesystem exports on Proxmox
- `no_root_squash` allows root access from the client
- Nobara runs NFSv4 only (no rpcbind) - `showmount -e` will fail from Proxmox, but mounts work fine
- Nobara is not always on - the soft mount on Proxmox ensures it never freezes the host
- If NFS shares stop working after a Proxmox reboot: check `systemctl status nfs-server` on the Proxmox host - it may need `systemctl start nfs-server`
- **Automount units must not have `After=network-online.target`** - this creates an ordering cycle with `local-fs.target` on Fedora/Nobara and causes the unit to silently fail at boot. Network dependency belongs only in the `.mount` unit, not the `.automount` unit. Access-triggered automounts work correctly without it since the network is already up when the user first accesses the path.
