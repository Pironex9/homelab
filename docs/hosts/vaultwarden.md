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
| OS | Alpine Linux 3.24.1 |
| CPU | 1 core |
| RAM | 512 MB |
| Disk | 1 GB (`local-lvm`) |
| Network | vmbr0, static 192.168.0.219/24 |
| Unprivileged | yes |
| `onboot` | yes |
| Installed from | Proxmox Community Scripts, Alpine variant |

Installed from the Alpine package repository and managed with `apk`; the
container was moved from Alpine 3.23.3 to 3.24.1 on 2026-08-28, and the section
on updating explains why the server version and the Alpine release had to move
together.

**The running version is deliberately not pinned on this page.** This is a public
site describing a password manager that is reachable from the internet, and a
maintained "here is exactly what runs right now" line is the one detail that
helps somebody targeting it and helps a reader not at all. To read it on the
machine:

```bash
pct exec 103 -- apk list -I vaultwarden
```

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
| `ADMIN_TOKEN` | empty | admin panel **disabled** - see below |
| `DOMAIN` | the public HTTPS URL | see below - not optional |

### The admin panel is off, and that is the setting

`ADMIN_TOKEN` is an empty string, which is not an unfinished setup: Vaultwarden
treats an empty token as "disabled" and `/admin` answers

```
The admin panel is disabled, please configure the 'ADMIN_TOKEN' variable to enable it
```

Verified by request, because a `curl` on `/admin` returns **200** either way -
the status code alone does not tell you whether the panel is live.

Everything the panel would do (user management, diagnostics, config) has to be
done from `/etc/conf.d/vaultwarden` plus a service restart instead. If it is ever
enabled, the token must be an Argon2 PHC hash (`vaultwarden hash`), not a plain
string: a plain token is compared on every request and is brute-forceable.

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

  This is not hypothetical. On 2026-08-28 the server was found on **1.37.0**
  while upstream **1.37.2** (2026-08-22) states plainly: *"This update is
  required for support with clients with version 2026.8.0+"*. Nothing was broken
  that day; it would have broken on whichever day a client auto-updated past
  2026.8.0, on a machine nobody looks at until they need it.

- **Pinning to the container's own Alpine release would have made this worse.**
  The obvious fix - point `/etc/apk/repositories` at the installed release so
  `apk upgrade` stays patch-level - fails here, because Alpine's stable branches
  do not carry vaultwarden version bumps:

  ```
  v3.23 (the release the container ran)   1.36.0-r0
  v3.24                                   1.37.2-r0
  edge                                    1.37.2-r0
  ```

  `v3.23` tops out **older than what was already installed**. So the recipe used
  for the Alpine komodo LXC - name a branch on the command line, leave
  `repositories` alone - does not transfer. The service only exists in a current
  version in the next release branch.

- **Why the release upgrade was the fix, not a workaround.** `repositories`
  pointed at `latest-stable`, which had moved on to 3.24 while the userland was
  still 3.23.3 - the container was already half-way across. `apk add --upgrade`
  scoped to the three vaultwarden packages did not avoid that: `--simulate`
  showed it dragging `musl 1.2.5-r21 -> 1.2.6-r2` along with it, which is the
  3.24 libc. There was no path that both updated the server and stayed on 3.23.

  Done on 2026-08-28, 113 packages, 3.23.3 -> 3.24.1, no errors. The version
  numbers below are the historical record of that day, not a claim about what is
  running now:

  ```bash
  # from pve, AFTER a fresh vzdump of 103
  pct exec 103 -- apk upgrade --available
  pct exec 103 -- rc-service vaultwarden restart
  ```

  **The restart is not optional.** `apk` swaps the binary on disk and leaves the
  running daemon on the old one; `supervise-daemon` will not notice. Confirm with
  `pct exec 103 -- /usr/bin/vaultwarden --version`, which must report the version
  you just installed rather than the one you replaced.

  `/etc/conf.d/vaultwarden` survived, because apk keeps a locally modified file
  and writes the packaged one beside it as `vaultwarden.apk-new`. Worth diffing
  once for new upstream options; nothing has to be merged for the service to run.

  Rollback if the restart fails or clients stop authenticating: stop the
  container, restore the `vzdump` tarball from `/mnt/storage/backup/proxmox/dump`
  over VMID 103, start it. 54 MB compressed, under a minute, and complete - the
  container holds 7.4 MB of data and nothing else depends on its state. Take that
  dump *before* the upgrade rather than relying on the 02:00 job, which may be up
  to 24 hours old.

- **`/api/config` does not report the server version.** Its `version` field is
  the Bitwarden server API version Vaultwarden advertises to clients - it read
  `2026.6.0` both before and after the 1.37.0 -> 1.37.2 upgrade, and it is not
  the web vault version either (that is `2026.7.0`, in
  `/usr/share/webapps/vaultwarden-web/vw-version.json`). Use `apk list -I` or
  `vaultwarden --version` to answer "what is running".

- **The version drift is now reported, not watched for.** `scripts/homelab-digest.sh`
  compares the installed packages against the repository every morning and warns
  only on a difference. Deliberately a notification, not an unattended upgrade:
  this is the one machine whose failure locks you out of every other credential,
  so an upgrade that goes wrong must go wrong while somebody is looking.

  It reports **two different things**, because the action differs:

  | Line | Meaning | What to do |
  |------|---------|------------|
  | `Vaultwarden frissítés vár` | ordinary package drift, the container and its repository are on the same Alpine release | plain `apk upgrade`, then restart |
  | `az Alpine latest-stable átbillent` | `alpine-release` is behind too: `latest-stable` has moved to the next Alpine release | the same command is now a **release jump** - fresh `vzdump` and a maintenance window first |

  The second line is the one that has to exist. `/etc/apk/repositories` points at
  `latest-stable`, which is a moving target: today it resolves to v3.24 and the
  container runs 3.24.1, so the two are aligned and an upgrade is patch-level.
  When Alpine 3.25 ships, `latest-stable` follows it and the identical command
  silently becomes a release jump again - which is exactly the state this
  container was found in on 2026-08-28, with nothing anywhere reporting it.

  Note also what the alignment buys: only the **current** stable branch receives
  version bumps. v3.24 moved 1.37.0 -> 1.37.2 while v3.23 stayed frozen at
  1.36.0. So while the container sits on the current release it tracks upstream
  normally; the moment a new Alpine ships, its branch stops moving and the next
  server update requires the jump.

- **The container is 1 GB.** It has room for a password database and little else;
  logs go to `/var/log/vaultwarden`. 25% used after the upgrade, 7.4 MB of data.
- `nesting=1,keyctl=1` are set on the container, which the community script
  requires on Alpine.

## Related

- [09 - Vaultwarden](../proxmox/09_Vaultwarden.md) - build guide and the full
  configuration reference
- [caddy (LXC 110)](caddy.md) - the LAN reverse proxy
- [VPS 02 - Security Configuration](../vps/02_Security_Configuration_Guide.md) -
  the public exposure posture
