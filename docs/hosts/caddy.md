# caddy LXC

## Overview

| Property | Value |
|----------|-------|
| Hostname | caddy |
| IP Address | 192.168.0.208 |
| VMID | 110 |
| OS | Alpine Linux 3.23 |
| CPU | 1 core |
| RAM | 256 MB |
| Disk | 3 GB (local-lvm) |
| Purpose | Reverse proxy for all .lan services (HTTP + HTTPS) |

## Running Services

| Service | Description |
|---------|-------------|
| `caddy` | Caddy web server / reverse proxy |

## Open Ports

| Port | Protocol | Service |
|------|----------|---------|
| 22 | TCP | SSH |
| 80 | TCP | HTTP - same handlers as HTTPS, for devices without the CA cert |
| 443 | TCP | HTTPS reverse proxy with TLS |

## Caddy

**Version:** v2.11.2 (installed via community-scripts Alpine LXC)
**Config:** `/etc/caddy/Caddyfile`
**Certs:** `/etc/caddy/certs/`

### TLS Certificates

Generated with mkcert using a local CA (CAROOT=/etc/caddy/certs):

| File | Description |
|------|-------------|
| `rootCA.pem` | Local CA root - must be imported into every browser/device |
| `rootCA-key.pem` | Local CA private key |
| `lan.pem` | Server cert (all .lan domains as explicit SANs) |
| `lan-key.pem` | Server cert private key (owner: root:caddy, mode: 640) |

**Cert expiry:** 2028-06-30

**Note:** Wildcard `*.lan` certs are rejected by Firefox (second-level wildcard). All .lan domains must be listed explicitly as SANs in the cert. To add a new domain, regenerate the cert with mkcert including the new domain name.

### Regenerating the cert

```bash
pct exec 110 -- sh -c 'CAROOT=/etc/caddy/certs /usr/local/bin/mkcert \
  -cert-file /etc/caddy/certs/lan.pem \
  -key-file /etc/caddy/certs/lan-key.pem \
  proxmox.lan adguard.lan komodo.lan karakeep.lan n8n.lan ollama.lan \
  jellyfin.lan homepage.lan immich.lan bentopdf.lan docuseal.lan \
  qbit.lan sonarr.lan form.lan syncthing.lan \
  suggestarr.lan notifiarr.lan calibre.lan seerr.lan radarr.lan \
  scrutiny.lan prowlarr.lan freshrss.lan \
  netdata.lan haos.lan vaultwarden.lan syncthing-nex.lan homelable.lan'
pct exec 110 -- chown root:caddy /etc/caddy/certs/lan-key.pem
pct exec 110 -- chmod 640 /etc/caddy/certs/lan-key.pem
pct exec 110 -- rc-service caddy restart
```

### Caddyfile structure

All service handlers are defined once in a `(lan_services)` snippet and imported by both the HTTPS and HTTP blocks. This avoids duplication:

```
(lan_services) {
    @service host service.lan
    handle @service { reverse_proxy ... }
    ...
    handle { respond 404 }
}

*.lan {
    tls /etc/caddy/certs/lan.pem /etc/caddy/certs/lan-key.pem
    import lan_services
}

http://*.lan {
    import lan_services
}
```

### Adding a new service

1. **AdGuard** - add DNS rewrite: `newservice.lan` → `192.168.0.208`

2. **Caddyfile** - add a new handler inside the `(lan_services)` snippet, before the final `handle { respond 404 }`:
```bash
ssh root@192.168.0.109 "pct exec 110 -- vi /etc/caddy/Caddyfile"
# Add before the final "handle { respond 404 }" line:
#
#     @newservice host newservice.lan
#     handle @newservice {
#         reverse_proxy 192.168.0.110:PORT
#     }
#
pct exec 110 -- rc-service caddy reload
```

3. **Cert** - regenerate with the new domain added to the list (see "Regenerating the cert" above)

4. **DNS cache** - flush on the client:
```bash
resolvectl flush-caches
```

### Installing the root CA on a new device

```bash
# Pull rootCA.pem from the LXC via Proxmox
ssh root@192.168.0.109 "pct pull 110 /etc/caddy/certs/rootCA.pem /tmp/rootCA.pem"
scp root@192.168.0.109:/tmp/rootCA.pem ~/mkcert-rootCA.pem
```

**Firefox (desktop):** Settings → Privacy & Security → View Certificates → Authorities → Import → select `mkcert-rootCA.pem` → check "Trust this CA to identify websites"

**Android (system cert):** Copy the .pem file to the device → Settings → Security → Install certificate → CA certificate. This enables HTTPS in Chrome and regular Firefox, but **not** Firefox Nightly (which ignores user certs).

**Firefox Nightly on Android:** Nightly does not trust Android user-installed CA certs. Use `http://service.lan` (port 80) instead - the HTTP listener serves identical content without TLS. The Tailscale mesh provides transport encryption so plain HTTP is acceptable over Tailscale.

### Proxied Services

All .lan domains resolve to 192.168.0.208 (Caddy) via AdGuard DNS rewrites.

| Domain | Backend |
|--------|---------|
| proxmox.lan | https://192.168.0.109:8006 (tls_insecure_skip_verify) |
| adguard.lan | http://192.168.0.111:80 |
| komodo.lan | http://192.168.0.105:9120 |
| karakeep.lan | http://192.168.0.128:3000 |
| n8n.lan | http://192.168.0.112:5678 |
| ollama.lan | http://192.168.0.231:11434 |
| jellyfin.lan | http://192.168.0.110:8096 |
| homepage.lan | http://192.168.0.110:3002 |
| immich.lan | http://192.168.0.110:2283 |
| bentopdf.lan | http://192.168.0.110:3000 |
| docuseal.lan | http://192.168.0.110:3003 |
| qbit.lan | http://192.168.0.110:8080 (X-Forwarded-Proto: https) |
| sonarr.lan | http://192.168.0.110:8989 |
| form.lan | http://192.168.0.110:3004 |
| syncthing.lan | http://192.168.0.110:8384 |
| suggestarr.lan | http://192.168.0.110:5000 |
| notifiarr.lan | http://192.168.0.110:5454 |
| calibre.lan | http://192.168.0.110:8085 |
| seerr.lan | http://192.168.0.110:5055 |
| radarr.lan | http://192.168.0.110:7878 |
| scrutiny.lan | http://192.168.0.110:8082 |
| prowlarr.lan | http://192.168.0.110:9696 |
| freshrss.lan | http://192.168.0.110:8083 |
| netdata.lan | http://192.168.0.109:19999 |
| haos.lan | http://192.168.0.202:8123 |
| vaultwarden.lan | https://192.168.0.219:8000 (tls_insecure_skip_verify) |
| syncthing-nex.lan | http://192.168.0.100:8384 |
| homelable.lan | http://192.168.0.110:3001 |

**Note on qbit.lan:** qBittorrent 5.1+ reads `X-Forwarded-Proto: https` from trusted proxies to automatically set the `Secure` flag on its session cookie. The Caddy block explicitly sets this header even on HTTP requests so the behavior is consistent.

## Lessons Learned

- **Wildcard `*.lan` rejected by Firefox:** Firefox does not accept second-level wildcard certs (e.g. `*.lan`). All domains must be listed explicitly as SANs. mkcert warns about this during generation.
- **Key file permissions:** Caddy runs as the `caddy` user. The private key must be `chown root:caddy` and `chmod 640`, otherwise Caddy fails to start with "permission denied".
- **DNS cache on Linux clients:** After adding new AdGuard rewrites, Linux clients may need `resolvectl flush-caches` before the new domain resolves.
- **mkcert not in Alpine apk:** mkcert is not available in Alpine's package repos. Install the binary directly from GitHub releases.
- **Installation:** Deployed via community-scripts Alpine LXC script (successor to tteck/Proxmox scripts).
- **HTTP + HTTPS in one Caddyfile:** Caddy does not allow a `tls` directive in a block that matches both HTTP and HTTPS. Solution: define handlers once in a named snippet `(lan_services)` and `import` it from both the `*.lan` (HTTPS) and `http://*.lan` (HTTP) blocks.
- **Firefox Nightly Android cannot trust user CAs:** Android user-installed CA certificates are ignored by Firefox Nightly regardless of `security.enterprise_roots.enabled`. The workaround is HTTP access on port 80.
