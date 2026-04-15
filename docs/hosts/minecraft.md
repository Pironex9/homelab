# minecraft LXC

## Overview

| Property | Value |
|----------|-------|
| Hostname | minecraft |
| IP Address | 192.168.0.213 |
| VMID | 111 |
| OS | Debian GNU/Linux 12 (bookworm) |
| CPU | 2 cores |
| RAM | 6 GB |
| Disk | 20 GB (local-lvm) |
| Purpose | Minecraft Java + Paper server with Bedrock cross-play via GeyserMC |

## Running Services

| Service | Description |
|---------|-------------|
| `sshd` | OpenSSH server |
| Docker daemon | Container runtime |
| `minecraft` container | PaperMC + GeyserMC + Floodgate |

## Open Ports

| Port | Protocol | Service |
|------|----------|---------|
| 22 | TCP | SSH |
| 25565 | TCP | Minecraft Java Edition |
| 19132 | UDP | Minecraft Bedrock Edition (GeyserMC) |

## Docker Stack

Single compose stack at `/opt/minecraft/`.

| Container | Image | Description |
|-----------|-------|-------------|
| `minecraft` | `itzg/minecraft-server:latest` | PaperMC server with auto-installed plugins |

### Plugins (auto-installed via env)

| Plugin | Purpose |
|--------|---------|
| GeyserMC | Translates Bedrock protocol to Java - allows phone/console players |

> Floodgate is NOT used - incompatible with offline mode. GeyserMC runs with `auth-type: offline`.

### Volumes

| Path | Description |
|------|-------------|
| `/opt/minecraft/data` | Server data - world, plugins, configs, logs |

## Public Access

Exposed via Pangolin raw TCP/UDP resources on the Hetzner VPS:

| Resource | Type | VPS Port | Target |
|----------|------|----------|--------|
| Minecraft Java | TCP | 25565 | 192.168.0.213:25565 |
| Minecraft Bedrock | UDP | 19132 | 192.168.0.213:19132 |

## Komodo

Managed by Komodo (LXC 105) via periphery agent in outbound mode.

- Periphery config: `/etc/komodo/periphery.config.toml`
- Core address: `http://192.168.0.105:9120`

## SSH Access

Key-based authentication only. Password login disabled.

```bash
ssh root@192.168.0.213
```

To add a new key from the Proxmox host:

```bash
pct exec 111 -- bash -c 'echo "YOUR_PUBLIC_KEY" >> /root/.ssh/authorized_keys'
```

## Common Operations

```bash
# View live logs
docker compose -f /opt/minecraft/docker-compose.yml logs -f

# Restart server
docker compose -f /opt/minecraft/docker-compose.yml restart

# Update to latest Paper + plugins
docker compose -f /opt/minecraft/docker-compose.yml pull
docker compose -f /opt/minecraft/docker-compose.yml up -d

# Open server console (RCON-like)
docker attach minecraft
# Detach: Ctrl+P then Ctrl+Q
```

## Lessons Learned

- **GeyserMC auth-type:** After the first start, edit `/opt/minecraft/data/plugins/Geyser-Spigot/config.yml` and set `auth-type: offline`. This matches the server's `online-mode=false` setting and allows Bedrock clients without a Java licence.
- **UDP through Pangolin:** Pangolin raw UDP resources can have higher latency for Bedrock players compared to direct port forwarding. If Bedrock feels laggy, consider adding a direct UDP port forward on the router as an alternative path.
- **EULA:** `EULA: "TRUE"` must be set - the server refuses to start without accepting the Minecraft EULA.
- **Memory:** The `MEMORY: 4G` env var sets both `-Xms` and `-Xmx`. 4G is comfortable for up to ~10 players with vanilla Paper. Increase to 6G for modpacks.
- **World persistence:** The world lives in `/opt/minecraft/data/world/`. Back this up separately if needed - it is not included in the standard Restic backup script.
