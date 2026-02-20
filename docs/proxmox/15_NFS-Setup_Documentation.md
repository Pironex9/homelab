

## Proxmox NFS Server Configuration

### Install NFS Server
```bash
apt update
apt install nfs-kernel-server
```

### Configure Exports
Edit `/etc/exports`:
```bash
nano /etc/exports
```

Add exports:
```
/mnt/storage 192.168.0.0/24(rw,sync,no_subtree_check,no_root_squash,fsid=1)
/mnt/disk1 192.168.0.0/24(rw,sync,no_subtree_check,no_root_squash,fsid=2)
/mnt/disk2 192.168.0.0/24(rw,sync,no_subtree_check,no_root_squash,fsid=3)
/mnt/disk3 192.168.0.0/24(rw,sync,no_subtree_check,no_root_squash,fsid=4)
/mnt/disk4 192.168.0.0/24(rw,sync,no_subtree_check,no_root_squash,fsid=5)
/home/nex/homelab-docs 192.168.0.0/24(rw,sync,no_subtree_check,no_root_squash,all_squash,anonuid=1000,anongid=1000)
```

### Apply Exports
```bash
exportfs -a
systemctl restart nfs-kernel-server
```

### Verify Exports
```bash
exportfs -v
showmount -e localhost
```

## Nobara PC NFS Client Configuration

### Install NFS Client
```bash
sudo dnf install nfs-utils
```

### Create Mount Points
```bash
sudo mkdir -p /mnt/storage /mnt/disk1 /mnt/disk2 /mnt/disk3 /mnt/disk4
```

### Configure Auto-Mount
Edit `/etc/fstab`:
```bash
sudo nano /etc/fstab
```

Add entries:
```
192.168.0.109:/mnt/storage /mnt/storage nfs vers=3,defaults 0 0
192.168.0.109:/mnt/disk1 /mnt/disk1 nfs vers=3,defaults 0 0
192.168.0.109:/mnt/disk2 /mnt/disk2 nfs vers=3,defaults 0 0
192.168.0.109:/mnt/disk3 /mnt/disk3 nfs vers=3,defaults 0 0
192.168.0.109:/mnt/disk4 /mnt/disk4 nfs vers=3,defaults 0 0
```

### Mount All
```bash
systemctl daemon-reload
sudo mount -a
```

### Verify Mounts
```bash
df -h | grep mnt
mount | grep nfs
```

## n8n LXC Configuration

### Mount NFS on Proxmox Host
```bash
# Install NFS client on Proxmox
apt install nfs-common

# Create mount point
mkdir -p /mnt/nobara-docs

# Mount from Nobara PC
mount -t nfs 192.168.0.100:/home/nex/homelab-docs /mnt/nobara-docs

# Make permanent in /etc/fstab
echo "192.168.0.100:/home/nex/homelab-docs /mnt/nobara-docs nfs defaults 0 0" >> /etc/fstab
systemctl daemon-reload
```

### Bind Mount to n8n LXC
Get n8n LXC ID:
```bash
pct list | grep n8n
```

Stop LXC:
```bash
pct stop <n8n-id>
```

Edit LXC config:
```bash
nano /etc/pve/lxc/<n8n-id>.conf
```

Add bind mount:
```
mp0: /mnt/nobara-docs,mp=/mnt/nobara-docs
```

Start LXC:
```bash
pct start <n8n-id>
```

### Verify in n8n LXC
```bash
pct enter <n8n-id>
ls -la /mnt/nobara-docs
```

## n8n Workflow Configuration

### Execute Command Node
Use **Execute Command** node (not SSH node) with:

```bash
cat > /mnt/nobara-docs/infrastructure/logs/proxmox/log-analysis-$(date +%Y-%m-%d).md << 'EOF'
{{ $json.response }}
EOF
```

This writes directly to the NFS mount without needing SSH or sudo.

## Troubleshooting

### Check Available Exports
From client:
```bash
showmount -e 192.168.0.109
```

### Remount NFS
```bash
umount /mnt/nobara-docs
mount -t nfs 192.168.0.100:/home/nex/homelab-docs /mnt/nobara-docs
```

### LXC Can't Access Mount
Restart LXC after host-level mount changes:
```bash
pct stop <n8n-id>
pct start <n8n-id>
```

## Notes

- Use NFSv3 for compatibility (`vers=3` option)
- `fsid=` required for non-root filesystem exports
- `no_root_squash` allows root access from client
- File manager shows mounts twice: once in Network section (detection), once in /mnt/ (actual mounts)
- n8n runs as root in LXC, can write to 777 permissions
