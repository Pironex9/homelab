**Date:** 2026-07-27
**Purpose:** Public one-page landing site at the apex domain, self-hosted on the VPS
**Hostname:** Hetzner VPS
**Container:** `landing` at `172.18.0.10` on the `pangolin` network
**Public URL:** https://homelabor.net
**Stack:** `compose/vps/landing/`

---

## Why a Second Site

`docs.homelabor.net` serves a reader who already cares and wants the details. It is a poor first impression: a wall of setup guides with no argument in it.

The landing page exists to make a hiring audience take the infrastructure seriously in the first ten seconds, and then hand them off to the documentation. The two are split by role: the landing page argues, the documentation site holds the reference material. Every fact has exactly one home, which is why the Tech Stack, Architecture, Dashboard and Featured Projects sections were **moved** out of `docs/index.md` rather than copied.

## Why Self-Hosted Rather Than GitHub Pages

The documentation site runs on GitHub Pages, so the obvious move was to put this there too. It is instead a container on the VPS. The reasoning is recorded in `docs/adr/0001-landing-page-hosted-on-vps.md`; in short, GitHub Pages allows one custom domain per repository, and a page whose pitch is "I run this infrastructure" is more credible served from that infrastructure.

The homelab itself was rejected as the host. That would have tied the page's availability to the homelab's, which has documented recurring failure modes, and the usual mitigation is unavailable here: this setup mandates gray-cloud DNS throughout, because orange cloud breaks Traefik's Let's Encrypt challenge.

The VPS avoids the trade entirely, and produces the honest failure mode: when the homelab goes down, the landing page stays up and correctly reports it as down.

## Architecture

```
Browser
   |
Cloudflare DNS (homelabor.net -> VPS IP, gray cloud, A record)
   |
Hetzner VPS
   |
gerbil:443 -> Traefik -> 172.18.0.10:80   (Pangolin resource, no auth)
                |
          caddy:alpine  (container "landing")
                |
                +-- static files from dist/
                |     /            landing page
                |     /topology/   interactive topology map
                |
                +-- /api/badge/*                        --> 172.17.0.1:3001
                +-- /api/status-page/statuspage1        --> 172.17.0.1:3001
                +-- /api/status-page/heartbeat/...      --> 172.17.0.1:3001
                                                             (Uptime Kuma, same host)
```

Three properties are load-bearing and look cosmetic:

- **The container joins the existing `pangolin` network at a static address** and publishes no host port. UFW permits port 3001 only from `172.18.0.0/16`, so a container on its own network could not reach Uptime Kuma at all. The address is static because Pangolin addresses resource targets by IP, and a container that picks up a new address on recreate silently breaks the public route.
- **Kuma is reached at `172.17.0.1:3001`**, which is the address Pangolin's own resource target uses. The architecture diagram in `03_Uptime_Kuma_VPS_Migration.md` says `172.18.0.1`; that is wrong.
- **The status-page routes are pinned to one slug**, not wildcarded. `/api/status-page/*` on a public auth-free hostname would publish every status page Kuma ever hosts, including one created later for private use.

Because Kuma runs on this same host, the widget is same-origin. That matters: Kuma's status-page JSON sends no CORS headers, so a page served from anywhere else could not read it.

## The Build

A single POSIX shell script, `build.sh`. No Node, no npm, no framework, no lockfile.

It derives the Compose Stack count from the repository, substitutes it into `index.html`, and writes `dist/`. Three guards fail the build rather than shipping something wrong:

1. A count of zero refuses to build.
2. Any file in `src/` matching a dotfile, `*.bak`, `*~`, `*.swp`, `*.orig` or `*.env` refuses to build. `dist/` becomes a public web root and the copy is wholesale, so a stray `.env` would be fetchable by path.
3. Any surviving `{{TOKEN}}` anywhere in `dist/` refuses to build. Shipping a literal `{{STACK_COUNT}}` to a hiring audience is the failure worth guarding against.

`test-build.sh` asserts the substitution works and that an unsubstituted placeholder is caught. Its negative case dirties the real source file, so the restore runs from a `trap` with an `mktemp` backup: without it, an interrupt would leave a corrupted source, and the next run would back up the corruption and restore it.

### The counting rule

A Compose Stack is a directory under `compose/<host>/<name>/` containing `docker-compose.yml`, `compose.yml` or `compose.yaml`. **Not** simply a directory:

```bash
find compose -mindepth 3 -maxdepth 3 \
  \( -name docker-compose.yml -o -name compose.yml -o -name compose.yaml \) \
  | sed 's|/[^/]*$||' | sort -u | wc -l
```

Counting directories returns one more, because `compose/proxmox-lxc-100/uptime-kuma/` still exists holding only a `.env` after Kuma moved to the VPS. This number is published on a public page, so the derivation follows the definition in `CONTEXT.md` rather than the directory listing.

## The Live Status Widget

`src/status.js`, vanilla JavaScript, no dependencies.

It reads the public monitors from the status page itself rather than a hardcoded list, so curating the page is the single source of truth. For each, it fetches Kuma's badge endpoint at a thirty-day window and averages the results; per-service dots come from one heartbeat call.

Four details exist because of specific failures found in review:

- **`Promise.allSettled` throughout, never `Promise.all`.** One badge returning 404 must not hide the figure when twelve others answered.
- **An `AbortController` timeout on every request.** `allSettled` waits forever on a promise that never settles, so a hung Kuma would otherwise leave the block hidden permanently.
- **The badge regex takes the last match.** The SVG draws its value twice, a shadow then the visible fill.
- **The uptime block ships with `hidden` and an empty figure.** Revealing it is the only thing successful JavaScript does, so no JavaScript, or any API failure, shows no number at all. The fallback is structural, not runtime logic.

### Why thirty days and not the live figure

Kuma's status-page JSON exposes only twenty-four hour uptime; `uptimeList[\`${monitorID}_24\`]` is hardcoded in its `status-page-router.js`. The thirty-day window is reachable only through the badge endpoint.

Thirty days is also the right window for a public page. A single overnight outage moves a thirty-day average by a fraction of a percent but sends a twenty-four hour figure toward zero, and the reader arrives at a moment of their choosing.

### Compression

The heartbeat payload is large and repetitive: 242 KB for 37 monitors. Kuma's `showOnlyLastHeartbeat` option does **not** help, because the heartbeat route hardcodes `LIMIT 100` and never reads that flag. The fix is one `encode zstd gzip` directive in the Caddyfile, measured at 242 KB down to 18 KB.

## The Two Status Pages

| Slug | Contents | Audience |
|---|---|---|
| `statuspage1` | 13 public-facing services | Anyone. This is what the landing page reads. |
| `ops-…` (unguessable) | All 38 monitors, including the landing page | The Homepage dashboard widget |

`statuspage1` was curated down from 37. It had been published without authentication and disclosed every monitor name, including the media-acquisition stack, and the landing page renders each name into a dot's `title` attribute for accessibility. Keeping it uncurated would have published all 37 names on the portfolio page itself.

Only names and up or down state were ever exposed: `sendUrl` is 0, so no URLs, ports or credentials. The curation was about what the page says, not about closing a hole.

The second page exists because the dashboard lost its overview. It is published, because Kuma serves status-page data over the API only for published pages, but under a slug that cannot be guessed. Verified: Kuma exposes no public endpoint that enumerates status pages, so the obscurity holds.

**Consequence, accepted knowingly:** with every monitor public via the second page, the landing site's wildcard `/api/badge/*` proxy returns real uptime for any monitor id. No name, type or URL leaks; the badge label is only `Uptime (720h)`. Narrowing the route would mean hardcoding ids that break on the next curation.

## Deployment

Komodo GitOps, same as every other VPS stack.

The stack is registered with **`auto_update` and `poll_for_updates` off**, deliberately and unlike its neighbours. An automatic deploy would run `docker compose up` without running `build.sh`, and since `dist/` is gitignored the container would silently serve the previous build.

```bash
# first run, and after any content change
ssh vps 'cd /etc/komodo/repos/github/compose/vps/landing && sh build.sh && docker compose up -d'

# any later rebuild: recreate, do not restart
ssh vps 'cd /etc/komodo/repos/github/compose/vps/landing && sh build.sh && docker rm -f landing && docker compose up -d'
```

Recreating rather than restarting is required because the build deletes and recreates `dist/`, which breaks an existing bind mount.

### Maintenance contract

The stack count is baked in at build time and nothing rebuilds it on a schedule. **After adding or removing any compose stack anywhere in this repository, rebuild this one**, or the published number silently goes stale. The reminder lives in `AGENTS.md` under Codex Workflow, which is the file actually read when a stack is added. The uptime figure needs none of this; it is fetched live and cannot drift.

## Going Live: Two Pangolin Behaviours

Both cost real debugging time and will recur on the next resource.

**Resources are created with Platform SSO enabled by default.** The apex answered `302` to the Pangolin auth wall until SSO was disabled on that specific resource. Disabling it affects only that resource; every other one keeps its own setting.

**A target defaults to the tunnel site, not the local one.** There are two sites: `HomeLabor` (type `newt`, the tunnel to the homelab) and `VPS` (type `local`). The Landing target landed on `HomeLabor`, so Traefik was handed `http://100.89.128.4:<port>` for a container running on the VPS itself, and every request hung for 25 seconds. Moving the target to the `VPS` site fixed it. Uptime Kuma is the only other resource on the local site; everything else legitimately goes through the tunnel.

A third thing looks like a cause and is not: **the `badger` middleware sits on every resource**, including the ones that are publicly reachable. Its presence is not the auth wall - Badger asks Pangolin per resource. Do not chase it.

The apex resource itself worked on the first attempt with a blank subdomain field, so the Traefik file-provider fallback was never needed. The Let's Encrypt certificate issued normally over the gray-cloud A record.

## Verification

Run from a machine with no session, since a logged-in browser masks an auth misconfiguration.

```bash
# reachable, no redirect to a login page
curl -s -o /dev/null -w "%{http_code} %{redirect_url}\n" https://homelabor.net/

# certificate covers the apex
echo | openssl s_client -connect homelabor.net:443 -servername homelabor.net 2>/dev/null \
  | openssl x509 -noout -subject -dates

# nothing served that should not be
for p in Caddyfile build.sh docker-compose.yml og.html .git/config "..%2f..%2fetc%2fpasswd"; do
  curl -s -o /dev/null -w "$p %{http_code}\n" "https://homelabor.net/$p"
done

# the proxy is as narrow as it claims: only two status-page routes pass
curl -s -o /dev/null -w "other slug: %{http_code}\n" https://homelabor.net/api/status-page/other
curl -s -o /dev/null -w "entry-page: %{http_code}\n" https://homelabor.net/api/entry-page
```

Expected: `200` with no redirect; a valid certificate for `homelabor.net`; `404` for every file probe and traversal; `404` for both narrowing probes.

Current state at the time of writing: Lighthouse scores 100 for performance, accessibility, best practices and SEO. Page weight is 10 KB of HTML (3.6 KB gzipped), 12.6 KB CSS, 5.8 KB JavaScript.

### Attack surface

Measured, not assumed:

- UFW is unchanged by any of this. Inbound remains 80, 443, 22, WireGuard and gerbil only, plus 3001 from `172.18.0.0/16`.
- The container is unprivileged with no added capabilities.
- It reaches Uptime Kuma by design, and reaches **neither the Pangolin application nor the homelab LAN**.
- The web root holds only static files. No upload path, no backend, no execution.

Two hardening options remain available and were not taken: `read_only: true` on the container, and a non-root `user:`.

## Files

| Path | Responsibility |
|---|---|
| `compose/vps/landing/docker-compose.yml` | Container, network attachment, static IP |
| `compose/vps/landing/Caddyfile` | Static serving, compression, three narrow proxy routes |
| `compose/vps/landing/build.sh` | Derives the count, substitutes, guards, writes `dist/` |
| `compose/vps/landing/test-build.sh` | Asserts the build fails when it should |
| `compose/vps/landing/src/` | `index.html`, `style.css`, `status.js`, `topology.png`, `og.png`, `favicon.svg` |
| `compose/vps/landing/src/topology/index.html` | The interactive map, copied from another stack's build output |
| `compose/vps/landing/og.html` | Generator for the Open Graph card, deliberately outside `src/` |
| `compose/vps/landing/README.md` | Build and redeploy commands, maintenance contract |

`dist/` is a build artifact and is never committed.

`src/topology/index.html` is the one exception to that rule, and it is a committed build artifact on purpose. It comes from `compose/proxmox-lxc-100/topology/`, whose own `dist/` is gitignored and therefore missing from the VPS checkout `build.sh` runs against - there is nothing to copy from at build time. Never edit it: it is byte-for-byte the output of that stack's `build.js`, and a hand edit is lost on the next copy. See `26_Network_Topology_Map.md` for what has to move with it.

## Related

- `docs/adr/0001-landing-page-hosted-on-vps.md` - why the VPS and not GitHub Pages
- `docs/superpowers/specs/2026-07-26-portfolio-landing-design.md` - the design
- `docs/superpowers/plans/2026-07-27-homelab-landing-page.md` - the implementation plan
- `docs/hosts/vps.md` - host reference
- `03_Uptime_Kuma_VPS_Migration.md` - the Kuma instance this reads from
