
**Date:** 2026-04-01
**Purpose:** Migrate Uptime Kuma from LXC 100 (docker-host) to Hetzner VPS for external monitoring
**From:** LXC 100 (192.168.0.110) - `/srv/docker-data/uptime-kuma`
**To:** Hetzner VPS - `/opt/uptime-kuma`
**Public URL:** https://uptime.homelabor.net

---

## Why Move to VPS?

Running Uptime Kuma on LXC 100 means it monitors services from inside the homelab network. If the Proxmox host or the network goes down, Uptime Kuma goes down with it and can no longer send alerts.

On the VPS, Uptime Kuma runs independently. It monitors homelab services from outside - if the homelab is unreachable, the VPS still runs and can alert.

---

## Architecture

```
Internet
   |
Cloudflare DNS (uptime.homelabor.net → VPS IP, gray cloud)
   |
Hetzner VPS
   |
gerbil:443 → traefik → uptime-kuma:3001 (pangolin Docker network)
   |
Pangolin auth (login required before accessing Uptime Kuma)
```

Uptime Kuma is on the `pangolin` Docker network. Traefik (which shares gerbil's network namespace) can reach it by container name. Pangolin manages the Traefik dynamic config via its UI.

---

## 1. Pre-Migration: Backup Data from LXC 100

On LXC 100 (192.168.0.110):

```bash
# Stop Uptime Kuma first for a clean backup
cd /opt/stacks/uptime-kuma   # or wherever Komodo keeps it
docker compose down

# Create a tarball of the data
tar -czf /tmp/uptime-kuma-backup.tar.gz -C /srv/docker-data uptime-kuma

# Verify
ls -lh /tmp/uptime-kuma-backup.tar.gz
```

Copy to VPS:

```bash
# From LXC 109 or any machine with SSH access to VPS
scp root@192.168.0.110:/tmp/uptime-kuma-backup.tar.gz root@YOUR_VPS_IP:/tmp/
```

---

## 2. DNS Record (Cloudflare)

Add a new A record:

```
Type:          A
Name:          uptime
IPv4 address:  YOUR_VPS_IP
Proxy status:  DNS only (Gray cloud) ← required for Pangolin/Traefik TLS
TTL:           Auto
```

---

## 3. Deploy on VPS

SSH into the VPS:

```bash
ssh root@YOUR_VPS_IP
```

Create data directory and restore backup:

```bash
mkdir -p /opt/uptime-kuma

# Restore data from backup
tar -xzf /tmp/uptime-kuma-backup.tar.gz -C /opt/
# This extracts to /opt/uptime-kuma/

# Verify
ls /opt/uptime-kuma/
```

Deploy the compose stack:

```bash
mkdir -p /opt/stacks/uptime-kuma
# Copy or clone the compose file from the repo
# compose/vps/uptime-kuma/docker-compose.yml

cd /opt/stacks/uptime-kuma
docker compose up -d

# Verify container is running
docker ps | grep uptime-kuma

# Check logs
docker logs uptime-kuma
```

---

## 4. Pangolin Resource Configuration

### 4a. Add Resource in Pangolin UI

1. Open Pangolin dashboard (https://pangolin.homelabor.net)
2. Navigate to the site/org → **Resources**
3. Click **New Resource**
4. Fill in:
   - **Name:** Uptime Kuma
   - **Subdomain:** `uptime`
   - **Target:** `http://uptime-kuma:3001`
   - **Resource Type:** HTTP

> `uptime-kuma` resolves by container name because both containers are on the `pangolin` Docker network.

### 4b. Enable Pangolin Authentication

On the resource settings:

1. Enable **Authentication** (toggle on)
2. This requires users to log in to Pangolin before the request is forwarded to Uptime Kuma
3. Choose which users/roles can access it

This adds a second auth layer on top of Uptime Kuma's own login.

---

## 5. Verify

```bash
# Test that the container responds locally on VPS
docker exec uptime-kuma curl -s http://localhost:3001

# Check logs for errors
docker logs uptime-kuma --tail 50
```

Open https://uptime.homelabor.net in a browser:
- Should prompt for Pangolin login first
- After login, redirects to Uptime Kuma login
- All monitors and history should be intact (from restored backup)

---

## 6. Post-Migration: Remove from LXC 100

### Remove from Komodo

1. Open Komodo (http://192.168.0.105:9120)
2. Find the `uptime-kuma` stack
3. **Stop** the stack
4. **Delete** the stack from Komodo (removes management, not the data)

### Clean up data on LXC 100 (optional, after verifying VPS works)

```bash
# On LXC 100
rm -rf /srv/docker-data/uptime-kuma
```

---

## Compose File Reference

`compose/vps/uptime-kuma/docker-compose.yml`:

```yaml
services:
  uptime-kuma:
    image: louislam/uptime-kuma:2
    container_name: uptime-kuma
    environment:
      - TZ=Europe/Budapest
    volumes:
      - /opt/uptime-kuma:/app/data
      - /var/run/docker.sock:/var/run/docker.sock:ro
    networks:
      - pangolin
    restart: unless-stopped

networks:
  pangolin:
    external: true
    name: pangolin
```

Key differences from LXC 100 version:
- `network_mode: host` removed - uses `pangolin` bridge network instead
- Volume path changed from `/srv/docker-data/uptime-kuma` to `/opt/uptime-kuma`
- `docker.sock` kept read-only - monitors VPS containers (Pangolin stack)
- No exposed ports - Traefik handles routing via the pangolin network

---

## Troubleshooting

**Uptime Kuma not reachable after Pangolin resource setup:**
- Verify the container is on the `pangolin` network: `docker inspect uptime-kuma | grep -A 20 Networks`
- Check Pangolin logs: `docker logs pangolin`
- Ensure target is `http://uptime-kuma:3001` (not localhost or IP)

**Data not restored correctly:**
- Check permissions: `ls -la /opt/uptime-kuma/`
- Uptime Kuma runs as UID 1000 inside the container, but the data directory needs to be writable
- Fix: `chown -R 1000:1000 /opt/uptime-kuma`

**Docker socket monitoring not working:**
- The `docker.sock` mount allows Uptime Kuma to use the Docker monitor type
- Verify: `docker exec uptime-kuma ls -la /var/run/docker.sock`
