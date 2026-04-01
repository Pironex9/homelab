
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
Firefox
   |
Cloudflare DNS (uptime.homelabor.net → VPS IP, gray cloud)
   |
Hetzner VPS
   |
gerbil:443 → Traefik → 172.18.0.1:3001 (pangolin bridge gateway → VPS host)
                |
          Pangolin Badger auth (login required)
                |
          uptime-kuma (host network)
                |
          Tailscale → pve subnet router → 192.168.0.0/24 (homelab LAN)
```

Key networking decisions:
- Uptime Kuma runs with `network_mode: host` so it can use the VPS host's Tailscale routes to reach 192.168.0.x
- Traefik reaches Uptime Kuma via the Docker bridge gateway IP (`172.18.0.1:3001`) - not by container name
- VPS has `--accept-routes` enabled on Tailscale, accepting the `192.168.0.0/24` subnet route advertised by `pve`

---

## 1. Pre-Migration: Backup Data from LXC 100

Stop Uptime Kuma in Komodo first (http://192.168.0.105:9120), then on LXC 100:

```bash
tar -czf /tmp/uptime-kuma-backup.tar.gz -C /srv/docker-data uptime-kuma
ls -lh /tmp/uptime-kuma-backup.tar.gz
```

Copy to VPS. If there is no direct SSH key from LXC 100 to the VPS, route through an intermediate machine (e.g. Nobara):

```bash
# Step 1 - LXC 100 to Nobara
scp /tmp/uptime-kuma-backup.tar.gz nex@192.168.0.100:/tmp/

# Step 2 - Nobara to VPS (using the correct key name if non-default)
scp -i ~/.ssh/YOUR_KEY /tmp/uptime-kuma-backup.tar.gz root@YOUR_VPS_IP:/tmp/
```

---

## 2. DNS Record (Cloudflare)

Add a new A record **before** deploying - this avoids Let's Encrypt getting a NXDOMAIN and AdGuard caching it:

```
Type:          A
Name:          uptime
IPv4 address:  YOUR_VPS_IP
Proxy status:  DNS only (Gray cloud) ← required for Pangolin/Traefik TLS
TTL:           Auto
```

> **Note:** If you add the DNS record after Uptime Kuma is already running and someone queries the domain, AdGuard will cache the NXDOMAIN. You'll need to clear the AdGuard DNS cache manually (Settings → DNS settings → Clear DNS cache).

---

## 3. Tailscale Accept Routes

The VPS needs to accept the `192.168.0.0/24` subnet route that `pve` advertises. Without this, Uptime Kuma cannot reach homelab services.

```bash
tailscale set --accept-routes

# Verify: LAN should now be reachable
ping -c 2 192.168.0.110
```

---

## 4. Restore Data on VPS

```bash
mkdir -p /opt/uptime-kuma
tar -xzf /tmp/uptime-kuma-backup.tar.gz -C /opt/
ls -la /opt/uptime-kuma/
```

---

## 5. Deploy via Komodo

In Komodo (http://192.168.0.105:9120) → **Stacks** → **New Stack**:

- **Name:** `uptime-kuma`
- **Server:** `vps`
- **Repo:** `Pironex9/homelab`
- **Branch:** `main`
- **Compose File Path:** `compose/vps/uptime-kuma/docker-compose.yml`

Deploy. The data at `/opt/uptime-kuma` is already in place.

---

## 6. UFW Rule for Traefik Access

Uptime Kuma runs on host networking and listens on port 3001. UFW blocks Docker bridge → host traffic by default. Add a scoped rule so only Traefik (on the pangolin bridge) can reach it:

```bash
ufw allow from 172.18.0.0/16 to any port 3001 proto tcp comment 'Uptime Kuma - Traefik internal'
ufw status | grep 3001
```

> `172.18.0.0/16` is the pangolin Docker bridge subnet. Port 3001 remains closed to the internet.

---

## 7. Pangolin Resource Configuration

### 7a. Create a Local Site

Uptime Kuma runs on the VPS itself - not behind a Newt tunnel. In Pangolin UI, create a **local** site (no Newt client needed). Do not add it under the homelab tunnel site - Pangolin would try to route the request through the tunnel to a container that does not exist there.

### 7b. Add Resource

1. Open Pangolin dashboard (https://pangolin.homelabor.net)
2. Under the local site → **Resources** → **New Resource**
3. Fill in:
   - **Name:** Uptime Kuma
   - **Subdomain:** `uptime`
   - **Target:** `http://172.18.0.1:3001`
   - **Resource Type:** HTTP

> `172.18.0.1` is the pangolin Docker bridge gateway - the host IP as seen from Traefik's network namespace.

### 7c. Enable Pangolin Authentication

On the resource settings, enable **Authentication**. This requires users to log in to Pangolin (Badger) before accessing Uptime Kuma.

---

## 8. Verify

```bash
# From VPS - should return HTTP 401 (Badger auth working)
curl -s https://uptime.homelabor.net

# From VPS - verify container reaches LAN
docker exec uptime-kuma curl -s --connect-timeout 3 http://192.168.0.110:3000 | head -1
```

Open https://uptime.homelabor.net in a browser:
1. Pangolin login prompt
2. After login, Uptime Kuma dashboard loads with all monitors intact

---

## 9. Post-Migration: Remove from LXC 100

In Komodo (http://192.168.0.105:9120):
1. Find the `uptime-kuma` stack (LXC 100 server)
2. **Stop** → **Delete**

Clean up data on LXC 100 (optional, after verifying VPS is stable):

```bash
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
    network_mode: host
    restart: unless-stopped
```

Key differences from LXC 100 version:
- `network_mode: host` - container uses the VPS host network stack, including Tailscale routes
- Volume path: `/opt/uptime-kuma` (VPS convention, vs `/srv/docker-data/` on LXC 100)
- `docker.sock` read-only - allows monitoring VPS Docker containers (Pangolin stack)
- No `networks:` section - host networking does not use Docker bridges
- No exposed ports - Traefik reaches it via `172.18.0.1:3001` (bridge gateway)

---

## Monitor Configuration

After migration, update monitors to use reachable addresses from the VPS:

| Service | Old target (LAN) | New target |
|---------|-----------------|------------|
| Jellyfin | 192.168.0.110:8096 | https://jellyfin.homelabor.net or 192.168.0.110:8096 |
| Home Assistant | 192.168.0.202:8123 | https://ha.homelabor.net or 192.168.0.202:8123 |
| DocuSeal | 192.168.0.110:... | https://sign.homelabor.net or LAN IP |
| Internal services | 192.168.0.110:port | Same - VPS can reach LAN via Tailscale |

Both LAN IPs and public URLs work. Using public URLs tests the full Pangolin stack end-to-end.

---

## Troubleshooting

**504 Gateway Timeout:**
- UFW is blocking Docker bridge → host on port 3001
- Fix: `ufw allow from 172.18.0.0/16 to any port 3001 proto tcp`
- Verify from VPS: `docker exec gerbil wget -qO- http://172.18.0.1:3001`

**"no available server" from Pangolin:**
- Resource was added under the homelab tunnel site instead of a local site
- Create a new local site in Pangolin and move the resource there

**DNS not resolving (AdGuard):**
- AdGuard cached NXDOMAIN before the DNS record was created
- Fix: AdGuard UI → Settings → DNS settings → Clear DNS cache

**Monitors show DOWN for LAN services:**
- VPS cannot reach 192.168.0.x
- Check: `ping 192.168.0.110` from VPS
- Fix: `tailscale set --accept-routes` and verify pve is advertising the subnet

**Let's Encrypt cert not issued (NXDOMAIN error in Traefik logs):**
- DNS was not propagated when Traefik first tried
- Fix: delete `/opt/pangolin/config/letsencrypt/acme.json` and restart Traefik
- Trigger cert issuance: `curl -k https://uptime.homelabor.net`
