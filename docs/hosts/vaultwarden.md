**Date:** 2026-08-28
**Hostname:** alpine-vaultwarden (LXC 103)
**IP address:** 192.168.0.219

---

# vaultwarden LXC

**Status:** Production. The primary password manager for the entire homelab.

## Overview

| Property | Value |
|----------|-------|
| VMID | 103 |
| OS | Alpine Linux 3.23.3 |
| CPU | 1 core |
| RAM | 512 MB |
| Disk | 1 GB (`local-lvm`) |
| Network | vmbr0, static 192.168.0.219/24 |
| Unprivileged | yes |
| `onboot` | yes |
| Installed from | Proxmox Community Scripts, Alpine variant |

Versions: `vaultwarden 1.37.0-r0`, `vaultwarden-web-vault 1.35.4-r0`, both from
the Alpine package repository, managed with `apk`.

Full build guide: [09 - Vaultwarden](../proxmox/09_Vaultwarden.md).

## Access

**No SSH.** This is a deliberate exception, not an oversight - it is the one
container holding every other credential in the homelab, so it is excluded from
every automated tool that has a key anywhere else. Administration goes through
the hypervisor:

```bash
# from pve (192.168.0.109)
pct exec 103 -- sh
```

Alpine, so `apk` and `rc-service`, never `apt` and `systemctl`:

```bash
pct exec 103 -- rc-service vaultwarden status
pct exec 103 -- rc-service vaultwarden restart
```

| URL | Path |
|-----|------|
| `https://vaultwarden.lan` | LAN, via Caddy on LXC 110 |
| `https://your-vaultwarden.yourdomain.com` | public, via Pangolin on the Hetzner VPS |

The real public hostname is deliberately not written down here. This site is
public, and naming the exact login page of the homelab's password manager adds
attack surface for no documentation value.

Caddy on LXC 110 proxies it plainly, with TLS terminated at the proxy:

```
@vaultwarden host vaultwarden.lan
handle @vaultwarden {
    reverse_proxy http://192.168.0.219:8000
}
```

## Configuration

Config lives in `/etc/conf.d/vaultwarden`, exported as environment variables by
the OpenRC service - not in a `.env` file next to a compose file, because this
container is not Docker.

| Variable | Value | Why |
|----------|-------|-----|
| `DATA_FOLDER` | `/var/lib/vaultwarden` | SQLite database and attachments |
| `WEB_VAULT_ENABLED` | `true` | serves the web UI |
| `WEB_VAULT_FOLDER` | `/usr/share/webapps/vaultwarden-web` | separate `apk` package |
| `ROCKET_ADDRESS` | `0.0.0.0` | so Caddy on another host can reach it |
| `SIGNUPS_ALLOWED` | `false` | single-user instance, closed after setup |
| `ADMIN_TOKEN` | (in the password manager) | admin panel |
| `DOMAIN` | the public HTTPS URL | see below - not optional |

### `DOMAIN` is load-bearing for clients, invisible in a browser

Set it to the exact externally reachable HTTPS URL. Missing, Vaultwarden's
`/api/config` reports `http://localhost` as the API, identity and notifications
base URL. The web vault keeps working, because it is a static page using relative
paths - so a browser test passes and nothing looks wrong.

The browser extension and the mobile apps fetch `/api/config` first and then call
the returned URLs literally, so they try to reach `http://localhost` on the
*client's own machine* and fail with a generic "An error has occurred". This was
the state until 2026-07-16, when it turned out no `.env` had ever existed, only
`.env.template`.

Verify after any change:

```bash
curl -s https://your-vaultwarden.yourdomain.com/api/config | grep -A5 environment
```

The URLs in the response must be the real domain, not `localhost`.

## Backups

Covered by the nightly Proxmox `vzdump` job at 02:00 (`mode snapshot`, zstd,
storage `backup-hdd` at `/mnt/storage/backup/proxmox`), which includes VMIDs
100, 101, 102, **103**, 105, 106, 107, 109, 110 and 113. Retention is
`keep-daily=7, keep-last=7, keep-weekly=4, keep-monthly=3`. The 2026-08-28 dump
is 54 MB.

**It is not in the Restic job**, and that is a property of where the disk lives,
not an omission: `backup-proxmox-restic.sh` backs up `/` on the hypervisor, while
this container's rootfs is an LVM thin volume (`local-lvm:vm-103-disk-0`) that
never appears in the host filesystem. Anything similar applies to every other
LXC - the container backups come from `vzdump`, the host configuration from
Restic, and neither one substitutes for the other.

Full layout: [15 - Backup System](../proxmox/15_Proxmox_Backup_System_Documentation.md).

## Notes

- **Version-tied client breakage.** The Bitwarden clients and Vaultwarden move
  independently, and a client update can start calling an API shape the running
  server does not have yet. The symptom is a login that fails at the prelogin
  step while the web vault still works. Check the installed version against the
  client's expectations before assuming the container is broken.
- **The container is 1 GB.** It has room for a password database and little else;
  logs go to `/var/log/vaultwarden`.
- `nesting=1,keyctl=1` are set on the container, which the community script
  requires on Alpine.

## Related

- [09 - Vaultwarden](../proxmox/09_Vaultwarden.md) - build guide and the full
  configuration reference
- [caddy (LXC 110)](caddy.md) - the LAN reverse proxy
- [VPS 02 - Security Configuration](../vps/02_Security_Configuration_Guide.md) -
  the public exposure posture
