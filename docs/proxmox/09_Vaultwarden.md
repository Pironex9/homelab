**Date:** 2026-04-13
**System:** Proxmox VE 9.1
**LXC ID:** 103
**IP:** 192.168.0.219

---

## Overview

Vaultwarden is a self-hosted Bitwarden-compatible password manager running on Alpine Linux LXC 103. It serves as the primary password manager for the homelab, accessible both on the local network and publicly via Pangolin.

---

## Installation

Installed via Proxmox Community Scripts (Alpine variant):

```bash
bash -c "$(wget -qO - https://raw.githubusercontent.com/community-scripts/ProxmoxVE/main/ct/vaultwarden.sh)"
```

The separate `alpine-vaultwarden.sh` this container was originally built from no
longer exists; the script above replaced it and now prompts for the OS
("Choose the container OS: debian / alpine"). Pick **alpine** to get what is
running here. The old URL 404s, so a copy-paste of the original command fails
outright rather than quietly installing the Debian variant.

## LXC Specifications

- **Platform:** Alpine Linux LXC (Unprivileged)
- **CPU:** 1 core
- **RAM:** 256MB
- **Disk:** 1GB
- **Network:** vmbr0, static IP 192.168.0.219

---

## Access

| URL | Context |
|-----|---------|
| `https://vaultwarden.lan` | LAN access via Caddy reverse proxy (LXC 110) |
| `https://your-vaultwarden.yourdomain.com` | Public access via Pangolin (Hetzner VPS) |

---

## Configuration

Config file: `/etc/conf.d/vaultwarden`

```bash
# Enter LXC to edit
pct enter 103
vi /etc/conf.d/vaultwarden
rc-service vaultwarden restart
```

### Key settings

```bash
export DATA_FOLDER=/var/lib/vaultwarden
export WEB_VAULT_ENABLED=true
export WEB_VAULT_FOLDER=/usr/share/webapps/vaultwarden-web
export ADMIN_TOKEN=''        # empty = admin panel disabled
export ROCKET_ADDRESS=0.0.0.0
export SIGNUPS_ALLOWED=false
export DOMAIN=https://your-vaultwarden.yourdomain.com
```

### DOMAIN is required for browser extension / mobile clients

`DOMAIN` was missing until 2026-07-16 (no `.env` file ever existed, only `.env.template`). Without it, Vaultwarden's `/api/config` endpoint reports `http://localhost` as the API/identity/notifications base URL. The web vault (static page, relative paths) still worked fine, but the Bitwarden browser extension and mobile apps fetch `/api/config` first and then call the returned URLs literally - so they tried to reach `http://localhost` on the *client's own machine* and failed with a generic "An error has occurred" / "Network error when attempting to fetch resource".

**Symptom:** web vault login works, browser extension/mobile app login fails with a generic error.
**Fix:** set `DOMAIN` to the exact externally-reachable HTTPS URL and restart. Verify with:
```bash
curl -s https://your-vaultwarden.yourdomain.com/api/config | grep -A5 environment
```
should show your real domain in the URLs, not `localhost`.

### Important: no ROCKET_TLS

Vaultwarden runs HTTP-only internally (port 8000). TLS is terminated by:
- Caddy (LXC 110) for `vaultwarden.lan`
- Pangolin (Hetzner VPS) for `your-vaultwarden.yourdomain.com`

The built-in Rocket TLS is intentionally disabled - it is not production-ready and causes issues with mobile clients.

---

## Security

- **Signups disabled:** `SIGNUPS_ALLOWED=false`
- **Admin panel disabled:** `ADMIN_TOKEN` is empty
- **2FA:** enabled on the account (TOTP via Google Authenticator)
- **Rate limiting:** built-in, no configuration needed
- **HTTPS:** enforced at reverse proxy level (Let's Encrypt via Pangolin for public access)

---

## Caddy Configuration (LXC 110)

```caddy
@vaultwarden host vaultwarden.lan
handle @vaultwarden {
    reverse_proxy http://192.168.0.219:8000
}
```

---

## Updating

Vaultwarden comes from the Alpine package manager, and the naive command below
does **not** work here. It is kept because it is the one everybody reaches for
first:

```bash
# looks right, is not enough - see why
apk update && apk upgrade vaultwarden
```

### Alpine's stable branches do not carry Vaultwarden version bumps

This is the fact that decides the whole update strategy. Measured on 2026-08-28
against the branch indexes:

```
v3.23 (the release the container was running)   1.36.0-r0
v3.24                                           1.37.2-r0
edge                                            1.37.2-r0
installed at the time                           1.37.0-r0
```

The container's own release branch tops out **older than what was already
installed**. So the usual hardening advice - pin `/etc/apk/repositories` to the
installed release so `apk upgrade` stays patch-level - would freeze this service
permanently behind. The recipe used for the Alpine Komodo container (name a
branch on the command line, leave `repositories` untouched) does not transfer
either, for the same reason.

Scoping the upgrade to the three packages does not avoid it. `--simulate` first,
always, and read what comes along:

```
(1/7) Upgrading musl (1.2.5-r21 -> 1.2.6-r2)     <- this is already the 3.24 libc
...
(5/7) Upgrading vaultwarden (1.37.0-r0 -> 1.37.2-r0)
```

There is no path that updates the server and stays on the old release.

### The procedure that works

`/etc/apk/repositories` points at `latest-stable`, so the release upgrade is the
plain `apk upgrade --available`. Do it deliberately, in a window, with a fresh
backup - not as a reflex:

```bash
# 1. rollback point FIRST - the 02:00 job may be up to 24 hours old
vzdump 103 --storage backup-hdd --mode snapshot --compress zstd \
       --notes-template "pre-upgrade"

# 2. the upgrade itself
pct exec 103 -- apk upgrade --available

# 3. mandatory - see below
pct exec 103 -- rc-service vaultwarden restart

# 4. verify what is actually running
pct exec 103 -- /usr/bin/vaultwarden --version
```

Done on 2026-08-28: 113 packages, Alpine 3.23.3 -> 3.24.1, vaultwarden
1.37.0 -> 1.37.2, no errors, empty `error.log`.

**Step 3 is not optional and is easy to skip.** `apk` replaces the binary on
disk while `supervise-daemon` keeps running the old one, and `rc-service
vaultwarden status` reports `started` either way. Only `vaultwarden --version`
answers the question.

**`/etc/conf.d/vaultwarden` survives.** apk keeps a locally modified file and
writes the packaged one beside it as `vaultwarden.apk-new`. Worth diffing once
for new upstream options; nothing has to be merged for the service to start.

**Rollback**, if the restart fails or clients stop authenticating: stop the
container, restore the `vzdump` tarball from `/mnt/storage/backup/proxmox/dump`
over VMID 103, start it. Under a minute, and complete - the container holds about
7 MB of data and nothing else depends on its state.

```bash
pct stop 103
pct restore 103 /mnt/storage/backup/proxmox/dump/vzdump-lxc-103-<timestamp>.tar.zst \
    --force 1 --storage local-lvm
pct start 103
```

### 2026-09-27: a patch-level upgrade, and a cheaper rollback point

The opposite case to the release jump above, and it needs a different reflex. The digest
had been reporting `alpine-release-3.24.1-r0 < 3.24.2-r0` for ten days: 45 packages inside
the 3.24 branch, no `vaultwarden` among them. The server stayed at 1.37.2-r0 before and
after. What moved was the base system - `apk-tools` 3.0.7 -> 3.0.8, `util-linux` 2.42.1 ->
2.42.3, `libcurl` 8.21.0 -> 8.22.0, `ca-certificates-bundle` 20260611 -> 20260909.

**The rollback point was a snapshot, not a fresh `vzdump`.** Step 1 of the procedure above
exists because the nightly job can be up to 24 hours old, and re-running `vzdump` fixes
that at the cost of several minutes and a write into the backup pool. A thin-LVM snapshot
buys the same guarantee in under a second:

```bash
pct snapshot 103 pre-apk-20260927 --description "before Alpine 3.24.1 -> 3.24.2 apk upgrade"
pct exec 103 -- apk upgrade
pct exec 103 -- rc-service vaultwarden restart
# verify, then:
pct delsnapshot 103 pre-apk-20260927
```

It cost 0.08 percentage points of the thin pool while it existed (66.89% -> 66.97%), and
`pct rollback 103 pre-apk-20260927` returns the vault to the exact pre-upgrade state -
including credentials added since the last nightly, which a `pct restore` of the 02:07
tarball would silently drop.

Two limits keep this from replacing the backup. A snapshot lives in the same thin pool as
the origin, so it survives a bad upgrade and not a bad disk; and it grows as the origin
diverges, which is why it gets deleted as soon as a real login has been verified rather
than left lying around. It replaces the *extra* pre-upgrade `vzdump`, never the nightly one.

`apk` reported `OK: 207.4 MiB in 114 packages`, the restart was clean, and afterwards:

```
$ pct exec 103 -- /usr/bin/vaultwarden --version
Vaultwarden 1.37.2-r0
$ pct exec 103 -- apk list -u | wc -l
0
```

The restart is still mandatory even when the server package itself did not change, because
`libcurl` was replaced underneath a running process.

**Do not verify this container over HTTPS on its own address.** It answers nothing there:

```
$ curl -sk -o /dev/null -w '%{http_code}\n' https://192.168.0.219/
000
```

That is the documented `no ROCKET_TLS` design, not a broken upgrade - TLS terminates at
Caddy on LXC 110. The two checks that mean something are the backend directly and the
proxied hostname:

```bash
curl -s -o /dev/null -w '%{http_code}\n' http://192.168.0.219:8000/          # 200
curl -sk --resolve vaultwarden.lan:443:192.168.0.208 https://vaultwarden.lan/api/config
```

One inconsistency found while checking versions: `vaultwarden --version` prints `Web-Vault
Version file missing` even though `/usr/share/webapps/vaultwarden-web/vw-version.json`
exists and reads `2026.7.0`. The binary looks for it somewhere else than Alpine puts it, so
read the file, not the binary, for the web vault version.

### Do not automate the upgrade; automate the noticing

The failure on 2026-08-28 was not that the server was out of date. It was that
nobody knew. `scripts/homelab-digest.sh` now compares the installed packages
against the repository every morning and warns only on a difference.

An unattended `apk upgrade` on this container is the wrong trade: it is the one
machine whose breakage locks you out of every other credential in the homelab, so
an upgrade that goes wrong has to go wrong while somebody is watching.

### `/api/config` does not tell you the server version

Its `version` field read `2026.6.0` both before and after the 1.37.0 -> 1.37.2
upgrade - it is the Bitwarden server API version Vaultwarden advertises to
clients. It is not the web vault version either; that lives in
`/usr/share/webapps/vaultwarden-web/vw-version.json` (build `2026.7.0` as of
2026-08-28). Use `apk list -I vaultwarden` or `vaultwarden --version`.

### Known issue: browser extension login breaks after Bitwarden frontend updates

Bitwarden's browser extension frontend occasionally adds new API routes before the Vaultwarden server implements them. Seen 2026-07-16: extension called `POST /identity/accounts/prelogin/password` (a newer "unified login" route), server returned `404` (running 1.35.4-r0, which predates the route), causing "An error has occurred" on extension login while the web vault kept working normally.

**Diagnose:** check `/var/log/vaultwarden/access.log` for `404` responses to `/identity/accounts/...` around the time of the failed login.
**Fix:** update the server by the procedure above, not by a bare `apk upgrade vaultwarden` - the server-side fix aliases the new route to the existing `/identity/accounts/prelogin` handler (upstream PR [#7156](https://github.com/dani-garcia/vaultwarden/pull/7156)). Back up first.

The same class of breakage was live again on 2026-08-28 and caught before it bit: 1.37.2's release notes state that the update is *required* for clients from version 2026.8.0 onward, while the server was still on 1.37.0. Nothing was failing yet - it would have started failing on whichever day a client auto-updated past that line.

---

## Operations

```bash
# Status
pct exec 103 -- rc-service vaultwarden status

# Logs
pct exec 103 -- tail -f /var/log/vaultwarden/access.log
pct exec 103 -- tail -f /var/log/vaultwarden/error.log

# Restart
pct exec 103 -- rc-service vaultwarden restart

# Backup data (before upgrades)
pct exec 103 -- tar czf /root/vaultwarden-backup-$(date +%Y%m%d-%H%M).tar.gz -C /var/lib/vaultwarden .
```

---

## Notes

- SSH access is not available - use `pct enter 103` or `pct exec 103` from PVE
- Data stored in `/var/lib/vaultwarden`
- No `.env` file - configuration is in `/etc/conf.d/vaultwarden` (Alpine OpenRC style)

---

## Further Documentation

- [Vaultwarden Wiki](https://github.com/dani-garcia/vaultwarden/wiki)
- [Proxy examples](https://github.com/dani-garcia/vaultwarden/wiki/Proxy-examples)
- [Proxmox Helper Scripts](https://community-scripts.github.io/ProxmoxVE/)
