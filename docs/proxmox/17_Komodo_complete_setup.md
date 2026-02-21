
## Architecture Overview

**Komodo Core:** LXC 105 (Alpine-based, installed via community script)
**Periphery Agent:** LXC 100 (docker-host, systemd service)
**Docker Stacks:** `/srv/docker-compose/` on LXC 100

**Why systemd Periphery instead of Docker:**
- No filesystem separation issues
- Direct host access to compose files
- Simpler mount management
- Recommended by Komodo maintainers for Files on Server mode

---

## 1. Komodo Core Installation (LXC 105)

### Install via Proxmox Community Script

```bash
# On Proxmox host, run the community script
bash -c "$(wget -qLO - https://github.com/community-scripts/ProxmoxVE/raw/main/ct/komodo.sh)"
```

**Script creates:**
- Alpine-based LXC (ID: 105)
- Komodo Core with MongoDB
- Auto-configured networking
- Default port: 9120

**Manual verification:**
```bash
# Check LXC is running
pct status 105

# View Komodo logs
pct exec 105 -- docker logs komodo

# Check services
pct exec 105 -- docker ps
```

**Access:** http://192.168.0.105:9120

**First login:** Create admin account via UI

### Post-Installation Configuration

```bash
# Enter Komodo LXC
pct enter 105

# View configuration
cat /etc/komodo/.env

# Restart if needed
docker restart komodo
docker restart mongodb
```

---

## 2. Periphery systemd Installation (LXC 100)

### Prerequisites

```bash
# Enter LXC
pct enter 100

# Stop old Docker periphery if running
docker stop komodo_periphery
docker rm komodo_periphery
```

### Install systemd Periphery

```bash
# Run installer as root
curl -sSL https://raw.githubusercontent.com/moghtech/komodo/main/scripts/setup-periphery.py | python3

# Enable on boot
systemctl enable periphery

# Check status
systemctl status periphery

# View config
cat /etc/komodo/periphery.config.toml
```

### Configure Periphery

Edit `/etc/komodo/periphery.config.toml`:

```toml
port = 8120
bind_ip = "[::]"

# Add Core passkey - must match what's set in Komodo Core UI
passkeys = ["YOUR_RANDOM_PASSKEY_HERE"]

# Optional: whitelist Core IP
allowed_ips = ["192.168.0.109"]
```

**Passkey synchronization:**
1. Generate a random passkey:
   ```bash
   openssl rand -base64 32
   ```
2. Add it to `/etc/komodo/periphery.config.toml` on LXC 100
3. In Komodo UI when adding the Server: paste the same passkey in the **Passkey** field

Restart after changes:
```bash
systemctl restart periphery
```

---

## 3. Connect Periphery to Core

### Get Komodo Core IP

```bash
# On Proxmox host
pct exec 105 -- hostname -I
# Example output: 192.168.0.115
```

### In Komodo UI

1. Navigate to **Servers** → **New Server**
2. Fill in:
   - **Name:** LXC 100
   - **Address:** http://192.168.0.109:8120 (LXC 100's IP)
   - **Passkey:** (same as in periphery.config.toml)
3. **Save** and **Refresh** - should show green (OK)

**Note:** Komodo Core (LXC 105) connects TO Periphery (LXC 100), not the other way around.

---

## 4. Import Existing Docker Compose Stacks

### Important: Dockge Path Trap

If stacks were previously managed by Dockge, be aware of this:

**Dockge mounts `/srv/docker-compose` as `/opt/stacks` inside its container.**

```bash
# docker compose ls shows /opt/stacks paths
NAME       CONFIG FILES
bazarr     /opt/stacks/bazarr/docker-compose.yml   # ← Dockge container path

# But on host the files are actually at:
ls /srv/docker-compose/bazarr/docker-compose.yml   # ← Real host path
```

**This means:**
- `STACKS_FROM=compose` would generate wrong paths (`/opt/stacks/`)
- `STACKS_FROM=dir` reads the directory directly → generates correct paths (`/srv/docker-compose/`)
- Always use `STACKS_FROM=dir` when compose files are on host

### Why systemd Periphery Was Required

Docker-based Periphery had the same filesystem separation problem:
- Periphery inside Docker container couldn't see `/srv/docker-compose/` unless explicitly mounted
- Even with mounts, path resolution caused "Remote Error" failures
- systemd Periphery runs directly on the host → sees all host paths natively

### Setup komodo-import Tool

Create `/srv/docker-compose/import/compose.yml`:

```yaml
services:
  komodo-import:
    image: foxxmd/komodo-import:latest
    restart: no
    volumes:
      - /srv/docker-compose/:/filesOnServer
    environment:
      - HOST_DIR=/srv/docker-compose/
      - STACKS_FROM=dir  # Use 'dir' NOT 'compose' - 'compose' reads Docker daemon which returns Dockge container paths (/opt/stacks/) instead of real host paths (/srv/docker-compose/)
      - SERVER_NAME=LXC 100
      - DOCKER_HOST=tcp://socket-proxy:2375
    depends_on:
      - socket-proxy
      
  socket-proxy:
    image: lscr.io/linuxserver/socket-proxy:latest
    environment:
      - CONTAINERS=1
      - INFO=1
      - POST=0
      - PING=1
      - VERSION=1
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
    read_only: true
    tmpfs:
      - /run
```

### Run Import

```bash
# Enter LXC
pct enter 100
cd /srv/docker-compose/import

# Run
docker compose up

# View logs and copy TOML output
docker compose logs komodo-import

# Clean output - REQUIRED: remove docker log prefixes before pasting into Komodo
# Raw log output has "komodo-import-1  | " prefix on every line which breaks TOML parsing
docker compose logs komodo-import | sed 's/^komodo-import-1  | //' > /tmp/stacks.toml

# Verify clean TOML
cat /tmp/stacks.toml
```

**Note:** If you paste the raw log output directly into Komodo you will get:
```
TOML parse error at line 2, column 18 - key with no value, expected `=`
```
This is because the log prefixes break TOML parsing. Always use the `sed` command above first.

### Import to Komodo

1. Copy TOML content from `/tmp/stacks.toml`
2. Komodo UI: **Syncs** → **New Sync**
3. **Resource File** tab: Paste TOML
4. **General** tab:
   - **Sync Resources:** ENABLED
   - **Delete Unmatched:** DISABLED
5. **Execute Sync**

### Verify Import

1. Go to **Stacks** menu
2. All stacks should be visible with status indicators
3. Click any stack → should show compose file contents
4. Status should change from "DOWN" to actual state after refresh

---

## 5. Stack Management

### Files on Server Mode

**What it means:**
- Compose files stay in `/srv/docker-compose/`
- Komodo doesn't move or copy them
- Komodo just runs `docker compose` commands on existing files

**Editing stacks:**
- Edit files directly on host OR through Komodo UI
- Changes persist across Komodo updates

### Common Operations

**Deploy stack:**
```bash
# Via UI: Stack → Deploy button
# Or manually:
cd /srv/docker-compose/STACK_NAME
docker compose up -d
```

**View logs:**
- Komodo UI: Stack → Log tab
- Or: `docker compose logs -f`

**Update images:**
- Komodo UI: Stack → Pull Images → Deploy
- Or: `docker compose pull && docker compose up -d`

---

## 6. Git Sync Setup (Future)

### Option A: Resource Sync (Komodo Config Only)

**What it syncs:** Komodo's TOML configurations (not compose files)

1. Create git repo for Komodo configs
2. Komodo UI: **Syncs** → Edit sync
3. **General** tab → **Managed** mode: ENABLED
4. Configure git provider (GitHub/GitLab/Gitea)
5. Komodo pushes TOML changes to git automatically

**Files stay:** `/srv/docker-compose/` (not in git)

### Option B: Git-Backed Stacks (Full Version Control)

**What it syncs:** Actual compose files in git

#### Setup Process

1. **Initialize git in compose directory:**
```bash
cd /srv/docker-compose
git init
git add .
git commit -m "Initial commit"
git remote add origin YOUR_REPO_URL
git push -u origin main
```

2. **Configure Git Provider in Komodo:**
   - Settings → Providers → Git Accounts
   - Add GitHub/GitLab account with access token

3. **Convert Stacks to Git-Backed:**

For each stack:
- Stack → Config → **Source:** Change to "Git"
- **Repository:** Select repo
- **Branch:** main
- **Path:** Stack subdirectory path
- **Save**

4. **Komodo behavior:**
   - Clones repo to `/etc/komodo/stacks/STACK_NAME`
   - Pulls updates on schedule or manual trigger
   - Can push changes back if Managed mode enabled

#### Workflow

**Pull changes:**
```bash
# Git: Make changes, commit, push
git add docker-compose.yml
git commit -m "Update nginx config"
git push

# Komodo: Stack → Refresh button
# Or enable auto-pull on schedule
```

**Push changes from Komodo:**
- Edit in Komodo UI
- Changes auto-committed and pushed to git

### Recommended Approach

**Start with Option A (Resource Sync):**
- Simpler setup
- Versions your Komodo configurations
- Files stay in familiar location

**Migrate to Option B later if needed:**
- When you want full compose file versioning
- When collaborating with team
- When you need rollback capabilities

---

## 7. Maintenance

### Disk Space Management

**LXC 100 (Periphery + Stacks):**
```bash
# Check disk usage
pct exec 100 -- df -h /

# Clean Docker
pct exec 100 -- docker image prune -a    # Remove unused images
pct exec 100 -- docker volume prune      # Remove unused volumes
pct exec 100 -- docker system prune -a   # Full cleanup
```

**LXC 105 (Komodo Core):**
```bash
# Check disk usage
pct exec 105 -- df -h /

# Clean Core logs if needed
pct exec 105 -- docker logs komodo --tail 100
```

### Update Komodo Core

**Via community script (recommended):**
```bash
# Re-run the community script on Proxmox host
bash -c "$(wget -qLO - https://github.com/community-scripts/ProxmoxVE/raw/main/ct/komodo.sh)"
# Choose "Update" option
```

**Manual update:**
```bash
pct enter 105
docker pull ghcr.io/moghtech/komodo:latest
docker restart komodo
```

### Update Periphery

```bash
pct exec 100 -- systemctl stop periphery
pct exec 100 -- curl -sSL https://raw.githubusercontent.com/moghtech/komodo/main/scripts/setup-periphery.py | python3
pct exec 100 -- systemctl start periphery
```

### Backup Strategy

**What to backup:**
1. **LXC 105 (Komodo Core):**
   - Full LXC backup: `vzdump 105 --storage local --compress zstd`
   - Or just database: `/var/lib/docker/volumes/komodo_mongo-data/`
   
2. **LXC 100 (Periphery + Stacks):**
   - Periphery config: `/etc/komodo/periphery.config.toml`
   - Docker compose files: `/srv/docker-compose/`
   - Docker data: `/srv/docker-data/` (per-service)

**Backup script:**
```bash
#!/bin/bash
BACKUP_DIR=/mnt/backup/komodo-$(date +%Y%m%d)
mkdir -p $BACKUP_DIR

# Komodo Core LXC
vzdump 105 --storage local --compress zstd --dumpdir $BACKUP_DIR

# LXC 100 compose files
pct exec 100 -- tar -czf /tmp/compose-backup.tar.gz /srv/docker-compose
pct exec 100 -- tar -czf /tmp/periphery-backup.tar.gz /etc/komodo
cp /var/lib/lxc/100/rootfs/tmp/*.tar.gz $BACKUP_DIR/
```

**Restore:**
```bash
# Restore Komodo Core
pct restore 105 $BACKUP_DIR/vzdump-lxc-105-*.tar.zst

# Restore compose files
tar -xzf compose-backup.tar.gz -C /
```

---

## 8. Troubleshooting

### Stack shows "DOWN" but containers running

**Cause:** Stack name in Komodo doesn't match Docker compose project name

**Check:**
```bash
docker compose ls  # Shows actual project names
```

**Fix:** Rename stack in Komodo to match project name

### "Remote Error" when accessing stack

**Cause:** Periphery can't access compose files

**Check:**
```bash
# From Komodo Core host
curl -k https://192.168.0.109:8120/

# From LXC
systemctl status periphery
journalctl -u periphery -f
```

**Fix:** Verify systemd periphery is running and paths are correct

### "Failed to read compose file contents"

**Cause:** Run Directory path incorrect

**Check:**
```bash
ls -la /srv/docker-compose/STACK_NAME/
```

**Fix:** Stack Config → Run Directory → correct path

### Periphery not connecting to Core

**Check connectivity from Core to Periphery:**
```bash
# From LXC 105 (Komodo Core)
pct exec 105 -- wget -qO- http://192.168.0.109:8120/health
```

**Check firewall on LXC 100:**
```bash
pct exec 100 -- ss -tuln | grep 8120
```

**Check logs:**
```bash
# Periphery logs
pct exec 100 -- journalctl -u periphery --no-pager -n 50

# Core logs
pct exec 105 -- docker logs komodo --tail 50
```

**Common issues:**
- Wrong passkey in Core or Periphery config
- IP whitelist blocking connection
- Firewall blocking port 8120
- LXC network bridge issues

---

## 9. Current Setup Summary

**Infrastructure:**
- Proxmox Host: 192.168.0.109
- **LXC 105:** Komodo Core (Alpine + MongoDB)
  - Access: http://192.168.0.105:9120
  - Installed via: Community Script
- **LXC 100:** docker-host
  - Periphery: systemd service on port 8120
  - Docker stacks: /srv/docker-compose/

**Stacks:** 33 stacks in Files on Server mode
- Location: `/srv/docker-compose/` on LXC 100
- Managed via: Komodo UI (LXC 105)
- Status: All visible and operational

**Network Flow:**
```
User → Komodo Core (LXC 105:9120)
     ↓
Komodo Core → Periphery (LXC 100:8120)
     ↓
Periphery → Docker (LXC 100)
```

**Authentication:**
- Komodo Core ↔ Periphery: HTTPS (self-signed) + passkey
- Periphery → Docker: Unix socket

**Next Steps:**
- [ ] Configure auto-updates for critical stacks
- [ ] Set up Resource Sync for config versioning
- [ ] Enable disk space alerts
- [ ] Plan migration to git-backed stacks (optional)
- [x] Disable/remove Dockge (no longer needed) ✅
- [x] Document LXC 105 IP for future reference ✅ (192.168.0.105)

---

## 10. Useful Commands

```bash
# Komodo Core (LXC 105)
pct status 105
pct enter 105
pct exec 105 -- docker logs komodo -f
pct exec 105 -- docker logs mongodb -f
pct exec 105 -- docker restart komodo

# Periphery (LXC 100)
pct exec 100 -- systemctl status periphery
pct exec 100 -- systemctl restart periphery
pct exec 100 -- journalctl -u periphery -f

# Docker stacks on LXC 100
pct exec 100 -- docker ps -a
pct exec 100 -- docker compose ls
pct exec 100 -- docker compose -f /srv/docker-compose/STACK/docker-compose.yml logs

# Disk space
pct exec 100 -- df -h
pct exec 100 -- du -sh /srv/docker-data/*
pct exec 105 -- df -h

# LXC management
pct list
pct config 105
pct config 100
```

---

## Resources

- [Komodo Documentation](https://komo.do/docs)
- [Komodo GitHub](https://github.com/moghtech/komodo)
- [Proxmox Community Scripts](https://community-scripts.github.io/ProxmoxVE/)
- [Komodo Community Script](https://community-scripts.github.io/ProxmoxVE/scripts?id=komodo)
- [FoxxMD Migration Guide](https://blog.foxxmd.dev/posts/migrating-to-komodo/)
- [FoxxMD Tips & Tricks](https://blog.foxxmd.dev/posts/komodo-tips-tricks/)
- [komodo-import tool](https://github.com/FoxxMD/komodo-import)
