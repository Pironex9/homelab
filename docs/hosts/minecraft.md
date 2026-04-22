# minecraft LXC

## Overview

| Property | Value |
|----------|-------|
| Hostname | minecraft |
| IP Address | 192.168.0.213 |
| VMID | 112 |
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
| 8100 | TCP | BlueMap web map (LAN only) |

## Docker Stack

Single compose stack at `/opt/minecraft/`.

| Container | Image | Description |
|-----------|-------|-------------|
| `minecraft` | `itzg/minecraft-server:latest` | PaperMC server with auto-installed plugins |

### Plugins (auto-installed via env)

| Plugin | Purpose |
|--------|---------|
| GeyserMC | Translates Bedrock protocol to Java - allows phone/console players |
| Floodgate | Microsoft account auth for Bedrock players (no Java licence needed) |

### Plugins (manually placed in `/opt/minecraft/data/plugins/`)

| Plugin | Version | Purpose |
|--------|---------|---------|
| EssentialsX | 2.21.2 | 130+ extra commands: /home, /tpa, /warp, /spawn, /kit, /afk |
| EssentialsXSpawn | 2.21.2 | Spawn management addon for EssentialsX |
| WorldEdit | 7.4.2 | Bulk block editing, copy/paste, area fills |
| WorldGuard | 7.0.15 | Region protection - restrict building in defined areas |
| BlueMap | 5.16 | Live 3D web map, accessible at `http://192.168.0.213:8100` |

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
pct exec 112 -- bash -c 'echo "YOUR_PUBLIC_KEY" >> /root/.ssh/authorized_keys'
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

## Admin (OP) Management

```bash
# Op a player (Java - use Java profile name visible in tab list)
ssh root@192.168.0.213 "docker exec minecraft rcon-cli op PlayerName"

# Op a Bedrock player (GeyserMC adds a dot prefix to Xbox gamertag)
ssh root@192.168.0.213 "docker exec minecraft rcon-cli op .XboxGamertag"

# Remove op
ssh root@192.168.0.213 "docker exec minecraft rcon-cli deop PlayerName"

# Interactive console (run multiple commands)
ssh root@192.168.0.213 "docker exec -i minecraft rcon-cli"
```

Useful in-game admin commands (after getting op):
```
gamemode creative PlayerName   # creative mode
gamemode survival PlayerName   # survival mode
time set day                   # set daytime
weather clear                  # clear weather
whitelist add PlayerName       # add to whitelist
tp PlayerName1 PlayerName2     # teleport
```

**Note:** Use the name exactly as shown in the in-game Tab list - that is how the server identifies the player. Java profile name and Xbox gamertag can differ.

## New World Generation

```bash
ssh root@192.168.0.213
cd /opt/minecraft
docker stop minecraft
rm -rf data/world data/world_nether data/world_the_end
docker start minecraft
```

> Warning: the old world is permanently deleted. Back up `/opt/minecraft/data/world/` first if needed.

## Lessons Learned

- **GeyserMC auth-type:** After the first start, edit `/opt/minecraft/data/plugins/Geyser-Spigot/config.yml` and set `auth-type: floodgate`. Without this, Bedrock players also need a Java Edition account.
- **UDP through Pangolin:** Pangolin raw UDP resources can have higher latency for Bedrock players compared to direct port forwarding. If Bedrock feels laggy, consider adding a direct UDP port forward on the router as an alternative path.
- **EULA:** `EULA: "TRUE"` must be set - the server refuses to start without accepting the Minecraft EULA.
- **Memory:** The `MEMORY: 4G` env var sets both `-Xms` and `-Xmx`. 4G is comfortable for up to ~10 players with vanilla Paper. Increase to 6G for modpacks.
- **World persistence:** The world lives in `/opt/minecraft/data/world/`. Back this up separately if needed - it is not included in the standard Restic backup script.
- **Paper version naming:** Paper labels the current Minecraft 26.1.x releases as "1.21.11" internally (for API compatibility). This is not an old version - the build date in the logs confirms it. Use the latest launcher client; it connects fine despite the name difference.
- **Multiplayer disabled on Java launcher:** If the launcher shows "Multiplayer disabled - please check your Microsoft account settings", go to `account.xbox.com/settings` and enable "You can join multiplayer games" under Privacy settings. This is triggered by age restrictions on the Microsoft/Xbox account.
- **Bedrock players cannot chat (enforce-secure-profile):** By default Paper has `enforce-secure-profile=true` in `server.properties`. Bedrock players (via GeyserMC) don't have a Java chat signing key, so they cannot chat. Fix: edit `/opt/minecraft/data/server.properties` and set `enforce-secure-profile=false`, then restart the container. Note: the `ENFORCE_SECURE_PROFILE` env var in the compose file does NOT override an existing `server.properties` value - direct file edit is required.
- **BlueMap requires accept-download:** On first start BlueMap needs `accept-download: true` in `/opt/minecraft/data/plugins/BlueMap/core.conf`, then reload with `/bluemap reload`. Without this it starts but the webserver doesn't serve the map. BlueMap uses port 8100, not 8123 like dynmap.
- **dynmap incompatible with 1.21.11:** dynmap 3.2.1 (latest GitHub release) cannot find internal Minecraft classes on 1.21.11. The 3.8 version that supports it is only on SpigotMC (requires login). Use BlueMap instead - actively maintained, supports 1.21.11, available on Modrinth.
- **Minecraft Flatpak on Nobara/KDE - use Prism Launcher:** The official `com.mojang.Minecraft` Flatpak has a token storage bug on KDE/non-GNOME desktops - it cannot save the Microsoft account token, causing "couldn't connect to Minecraft services" errors on every launch. Fix: install Prism Launcher instead (`flatpak install flathub org.prismlauncher.PrismLauncher`). Prism handles auth via browser login which bypasses the keyring issue. Remove the official Flatpak with `sudo flatpak uninstall com.mojang.Minecraft --delete-data`.
- **EssentialsX unsupported version warning:** EssentialsX 2.21.2 logs "You are running an unsupported server version!" on 1.21.11. The plugin loads and works despite the warning - commands function normally.
- **Komodo GitOps for compose changes:** Always edit the repo compose file and deploy via Komodo (Pull + Deploy). Do not edit `/opt/minecraft/docker-compose.yml` directly on the server - it will be overwritten on the next Komodo deploy.
- **Pangolin health check false negatives:** Pangolin's built-in health check sends HTTP requests to ports 25565 and 19132. Minecraft TCP returns EOF (not HTTP) and UDP is unreachable via HTTP, so both show as offline in the UI. The actual tunnel works - verify with `nc -z pangolin.homelabor.net 25565`. Disable health checks in the Pangolin resource settings to avoid confusion.
