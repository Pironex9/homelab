# PHP2Shell: Which of Our Services Run PHP

**Date:** 2026-10-21
**Hostname:** docker-host (LXC 100), plus every other host checked
**IP address:** 192.168.0.110

## Status: fixed

PHP shipped emergency releases on 2026-10-21 for two critical, unauthenticated RCE flaws, CVE-2026-109618 and CVE-2026-109619 ("PHP2Shell", CVSS 4.0 score 9.2). The fixed versions are 8.5.12, 8.4.27, 8.3.36 and 8.2.35. watchTowr reported active exploitation attempts the same day. Every PHP install that serves web requests is affected: PHP-FPM, Apache mod_php and FrankenPHP. The PHP team rates mod_php as the highest risk.

**Nothing public was exposed.** Exactly one service runs PHP, FreshRSS. It was on a vulnerable mod_php build, was reachable only from the LAN and the tailnet, and was moved to a patched image the same day.

## 1. What is public: read from Pangolin, not from the docs

The docs list public hostnames in several places, and that list is not guaranteed to be complete. The authoritative list is the Pangolin database on the VPS. The VPS has no `sqlite3` binary, so Python reads the database read-only:

```bash
ssh vps 'python3 - <<EOF
import sqlite3
c = sqlite3.connect("file:/opt/pangolin/config/db/db.sqlite?mode=ro", uri=True)
q = "select r.fullDomain, r.enabled, t.ip, t.port from resources r left join targets t on t.resourceId = r.resourceId"
for row in c.execute(q): print(row)
EOF'
```

| Public resource | Backend | PHP |
|---|---|---|
| landing page, randi | `caddy:alpine` on the VPS | no. The only `php_fastcgi` in the randi Caddyfile is the commented-out stock example |
| jellyfin, sign (DocuSeal), form, dawarich, pedikur | containers on LXC 100 | no |
| ha | HAOS (VM 101) | no |
| password manager (placeholder name) | Vaultwarden, LXC 103 | no |
| uptime | Uptime Kuma on the VPS | no |

Outside Pangolin: `docs.homelabor.net` is GitHub Pages, and Umami on the K3s cluster is `ghcr.io/umami-software/umami:3.3.1` (Node).

## 2. Where PHP actually runs

On LXC 100, every running container was checked for a PHP binary:

```bash
for c in $(docker ps --format '{{.Names}}'); do
  p=$(docker exec $c sh -c 'command -v php php-fpm frankenphp 2>/dev/null | head -1' 2>/dev/null)
  [ -n "$p" ] && echo "$c $p $(docker exec $c $p -v | head -1)"
done
```

It found one real hit, `freshrss` with `PHP 8.4.26`. The `garage` container also printed a line, but that was the OCI error text from a distroless image with no `sh`. A loop that prints anything non-empty will flag such images, so read the hits before believing them.

The same `command -v php` check came back empty on LXC 102, 103, 105, 106, 107, 109, 110 and 113, inside the Docker containers on those hosts, and on the VPS host and its containers. The K3s images are Forgejo (Go), Umami (Node), `postgres:17-alpine` and the kiwigrid sidecar, so none of them run PHP either.

## 3. FreshRSS

| | Before | After |
|---|---|---|
| Image | `freshrss/freshrss:latest` built 2026-10-20 | `latest` pushed 2026-10-21 14:39 UTC |
| `libapache2-mod-php8.4` | `8.4.26-1~deb13u1` | `8.4.27-1~deb13u1` |
| SAPI | Apache mod_php, the highest-risk setup | same |
| Exposure | `0.0.0.0:8083` and `freshrss.lan` in Caddy, so the LAN and the whole tailnet through subnet routing. No Pangolin resource | same |

The image is Debian 13 and uses Debian's PHP packages, so the fix to look for is the Debian one, `8.4.27-1~deb13u1` from DSA-6574-1, not the upstream version string. Check the new image before recreating anything:

```bash
docker pull -q freshrss/freshrss:latest
docker run --rm --entrypoint dpkg-query freshrss/freshrss:latest -W libapache2-mod-php8.4
```

Then recreate it from the Komodo stack directory, so that the `.env` Komodo keeps there is used:

```bash
cd /etc/komodo/repos/github/compose/proxmox-lxc-100/freshrss && docker compose up -d
```

There were a few seconds of downtime. Afterwards the container was running, `:8083` answered 302 (the login redirect), and the log had no errors. The old image (`sha256:a4a4a223...`) is still present locally if a rollback is needed. Komodo's 03:00 Global Auto Update pulls the same `latest`, so it will not undo this.

**Had the new image not existed yet,** `apt-get install --only-upgrade libapache2-mod-php8.4` inside the container would have worked, because Debian already had the candidate `8.4.27-1~deb13u1`. That fix only lasts until the container is next recreated.

## Sources

- [Qualys: PHP2Shell](https://blog.qualys.com/vulnerabilities-threat-research/2026/10/20/php-announces-critical-security-release-for-two-vulnerabilities)
- [Tenable FAQ](https://www.tenable.com/blog/php2shell-cve-2026-109618-cve-2026-109619-frequently-asked-questions-about-critical-php-remote)
- [Debian security tracker, CVE-2026-109618](https://security-tracker.debian.org/tracker/CVE-2026-109618)
