# Minecraft Server Setup

**Date:** 2026-04-15
**Hostname:** minecraft
**IP address:** 192.168.0.213
**VMID:** 112
**System:** Proxmox VE 9.1

---

## Overview

Dedicated LXC container running a PaperMC server with GeyserMC + Floodgate, enabling both Java Edition (PC) and Bedrock Edition (phone, console) players to connect to the same server.

Public access via Pangolin raw TCP/UDP resources on the Hetzner VPS - no router port forwarding needed.

Stack: `itzg/minecraft-server` Docker image, Paper type, plugins auto-installed via environment variables.

---

## Architecture

```
Java client (PC)  ──────── TCP 25565 ──┐
                                        │
Bedrock client                          ├── Hetzner VPS (Pangolin)
(phone/console)   ── UDP 19132 ─────────┤     │ Newt tunnel
                                        │     ▼
                                   LXC 112 (192.168.0.213)
                                        │
                               Docker: itzg/minecraft-server
                                        │
                               PaperMC + GeyserMC + Floodgate
```

---

## Step 1 - Create the LXC

In the Proxmox web UI, create a new Debian 12 container.

| Parameter | Value |
|-----------|-------|
| Template | `debian-12-standard_12.12-1_amd64.tar.zst` |
| Hostname | `minecraft` |
| CPU cores | 2 |
| Memory | 6144 MB |
| Disk | 20 GB on `local-lvm` |
| Network | `vmbr0`, static IP `192.168.0.213/24`, GW `192.168.0.1` |
| DNS | 192.168.0.111 (AdGuard) |
| Unprivileged | Yes |
| Nesting | Enabled (`features: nesting=1`) |
| Start at boot | Yes |

Start the container and enter it:

```bash
pct start 112
pct enter 112
```

---

## Step 2 - Base System Setup

```bash
apt update && apt upgrade -y
apt install -y curl git openssh-server
```

### Static IP (if not set via Proxmox UI)

Edit `/etc/network/interfaces`:

```
auto eth0
iface eth0 inet static
    address 192.168.0.213/24
    gateway 192.168.0.1
```

Apply:

```bash
systemctl restart networking
```

---

## Step 3 - SSH Setup

```bash
# Enable and start SSH
systemctl enable ssh
systemctl start ssh

# Restrict to key-based auth (edit /etc/ssh/sshd_config if needed)
# PasswordAuthentication no  (default on Debian 12 for root)

# Add SSH key from Proxmox host
# Run this on the Proxmox host, not inside the LXC:
# pct exec 112 -- bash -c 'mkdir -p /root/.ssh && echo "YOUR_PUBLIC_KEY" >> /root/.ssh/authorized_keys && chmod 700 /root/.ssh && chmod 600 /root/.ssh/authorized_keys'
```

SSH watchdog (auto-restart on crash):

```bash
mkdir -p /etc/systemd/system/ssh.service.d
cat > /etc/systemd/system/ssh.service.d/restart.conf << 'EOF'
[Service]
Restart=always
RestartSec=5
EOF
systemctl daemon-reload
```

---

## Step 4 - Install Docker

```bash
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker
```

---

## Step 5 - Deploy Minecraft Stack

```bash
mkdir -p /opt/minecraft/data
cd /opt/minecraft
```

Copy the compose file from the repo (or paste manually):

```bash
# From LXC 109 (claude-mgmt) or any host with repo access:
# scp /root/homelab/compose/proxmox-lxc-112/minecraft/docker-compose.yml root@192.168.0.213:/opt/minecraft/

# Or create it directly on the LXC
cat > /opt/minecraft/docker-compose.yml << 'EOF'
services:
  minecraft:
    image: itzg/minecraft-server:latest
    container_name: minecraft
    environment:
      EULA: "TRUE"
      TYPE: PAPER
      MEMORY: 4G
      TZ: Europe/Budapest
      PLUGINS: |
        https://download.geysermc.org/v2/projects/geyser/versions/latest/builds/latest/downloads/spigot
        https://download.geysermc.org/v2/projects/floodgate/versions/latest/builds/latest/downloads/spigot
      MOTD: "Homelab Minecraft"
      MAX_PLAYERS: "10"
      DIFFICULTY: normal
    ports:
      - "25565:25565"
      - "19132:19132/udp"
    volumes:
      - /opt/minecraft/data:/data
    restart: unless-stopped
EOF
```

Start the server:

```bash
docker compose up -d
docker compose logs -f
```

Wait for the message `Done! For help, type "help"` - this confirms the server is ready.

---

## Step 6 - Configure GeyserMC + Floodgate

The server runs in online mode (default) - Java players need a valid Mojang account, Bedrock players authenticate via Microsoft account through Floodgate.

After the first successful start, set GeyserMC to use Floodgate for Bedrock auth:

```bash
nano /opt/minecraft/data/plugins/Geyser-Spigot/config.yml
```

Find and change:

```yaml
auth-type: online
```

To:

```yaml
auth-type: floodgate
```

Restart the server:

```bash
docker compose restart
```

Bedrock players can now join using their Microsoft/Xbox account without needing a Java Edition licence.

### Optional: whitelist

If you want to restrict the server to specific players only:

```bash
# Edit compose file - uncomment and fill:
# WHITELIST: "Player1,Player2"
# ENFORCE_WHITELIST: "TRUE"
docker compose up -d
```

Or add players on the fly via server console:

```bash
docker attach minecraft
# In the console:
whitelist add PlayerName
# Detach: Ctrl+P then Ctrl+Q
```

---

## Step 7 - Komodo Periphery

Install the Komodo periphery agent so the server is managed via Komodo (LXC 105).

```bash
curl -fsSL https://raw.githubusercontent.com/moghtech/komodo/main/scripts/setup-periphery.py | python3
```

Add the Core public key to the periphery config:

```bash
cat > /etc/komodo/periphery.config.toml << 'EOF'
core_public_keys = ["MCowBQYDK2VuAyEAanLhSIyYAQmX7NLhn1PH+fiTClnhp+jrv5BPAnKgdCM="]
core_addresses = ["http://192.168.0.105:9120"]
connect_as = "minecraft"
EOF
```

Enable and start:

```bash
systemctl enable periphery
systemctl start periphery
```

Add the server in Komodo UI: **Servers - New Server** - the server will self-register via outbound connection.

---

## Step 8 - Pangolin Public Access (VPS)

Minecraft needs two raw resources in Pangolin: one TCP (Java), one UDP (Bedrock).

### On the Hetzner VPS

SSH to the VPS and install a Newt client for this LXC, or reuse the existing Newt if already tunneling the homelab network.

In the **Pangolin web UI**:

1. Go to **Sites** - select (or create) the site for LXC 112
2. **Resources - New Resource - Raw**

**Resource 1 - Java Edition:**

| Field | Value |
|-------|-------|
| Name | Minecraft Java |
| Protocol | TCP |
| VPS Port | 25565 |
| Target Host | 192.168.0.213 |
| Target Port | 25565 |

**Resource 2 - Bedrock Edition:**

| Field | Value |
|-------|-------|
| Name | Minecraft Bedrock |
| Protocol | UDP |
| VPS Port | 19132 |
| Target Host | 192.168.0.213 |
| Target Port | 19132 |

### Open ports on VPS (UFW)

```bash
ufw allow 25565/tcp comment "Minecraft Java"
ufw allow 19132/udp comment "Minecraft Bedrock"
```

### Newt on LXC 112

Install Newt on LXC 112 to establish the tunnel:

```bash
# Get the install command from Pangolin UI (Sites - your site - Install Newt)
# It looks like:
curl -fsSL https://your-vps-ip/newt/install.sh | bash -s -- --secret YOUR_NEWT_SECRET
```

Enable Newt to start on boot:

```bash
systemctl enable newt
systemctl start newt
```

---

## Step 9 - Test

### Java Edition

From any PC with Minecraft Java installed:

```
Server address: YOUR_VPS_IP:25565
```

or if you have a domain pointing to the VPS:

```
Server address: mc.yourdomain.com
```

### Bedrock Edition (phone/console)

```
Server address: YOUR_VPS_IP
Port: 19132
```

On **Nintendo Switch / PlayStation / Xbox**: these platforms block custom server IPs by default. A workaround exists using DNS redirection (BedrockConnect) - see the GeyserMC wiki for console setup.

---

## Troubleshooting

**Server does not start:**
```bash
docker compose logs minecraft | tail -50
```
Common cause: `EULA: "TRUE"` not set, or insufficient memory.

**Bedrock players cannot connect:**
- Check GeyserMC logs: `/opt/minecraft/data/plugins/Geyser-Spigot/logs/`
- Confirm `auth-type: floodgate` in `config.yml`
- Confirm UDP 19132 is open in UFW on the VPS
- Pangolin UDP tunnels can be slower than TCP - test with a direct connection first if possible

**Plugins not installing:**
- The `PLUGINS` env var requires internet access from the LXC on first start
- Check: `docker compose logs minecraft | grep -i plugin`

**Check open ports inside LXC:**
```bash
ss -tlnup | grep -E "25565|19132"
```
