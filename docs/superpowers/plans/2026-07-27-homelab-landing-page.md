# Homelab Landing Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a public one-page site at `homelabor.net`, self-hosted on the Hetzner VPS, whose hero carries a derived Compose Stack count and a live thirty-day uptime figure.

**Architecture:** A `caddy:alpine` container in a new Compose Stack at `compose/vps/landing/`, attached to the existing `pangolin` bridge network at a static address so Traefik can reach it inbound and it can reach Uptime Kuma outbound through the existing UFW rule. Static HTML built by a dependency-free POSIX shell script that substitutes one derived count. The uptime figure is fetched at runtime, same-origin, through a narrow Caddy reverse proxy to Kuma on the same host.

**Tech Stack:** Caddy, Docker Compose, POSIX shell, vanilla JavaScript, Uptime Kuma badge API, Pangolin/Traefik, Komodo GitOps.

**Reference spec:** `docs/superpowers/specs/2026-07-26-portfolio-landing-design.md`

## Global Constraints

- No dependencies of any kind. No Node, no npm, no framework, no lockfile. The build is POSIX shell.
- The container publishes **no host port** and adds **no UFW rule**.
- Container network: existing external bridge `pangolin`, static address `172.18.0.10`.
- Uptime Kuma is reached at `172.17.0.1:3001`. Not `172.18.0.1` - the VPS docs diagram says that and is wrong.
- Uptime Kuma status page slug is `statuspage1`. It already exists and is already published.
- Apex DNS must be **gray cloud (DNS only)**. Orange cloud breaks Traefik's Let's Encrypt challenge.
- Stack directory name is `landing`. `portfolio` is taken by the daughter's art site.
- Hero figures: Compose Stack count and thirty-day uptime. No Proxmox guest count - it cannot be derived reliably.
- The hero must never render a fabricated number. If Kuma does not answer, the figures are omitted.
- No em dashes anywhere in output or docs (project rule, `CLAUDE.md`).
- Never `git push` unless explicitly asked. Commit locally freely.
- Private LAN IPs (192.168.0.x) and container IPs are never redacted in this repo's docs.

## File Structure

| Path | Responsibility |
|---|---|
| `compose/vps/landing/docker-compose.yml` | Container definition, network attachment, static IP |
| `compose/vps/landing/Caddyfile` | Static file serving, compression, and three narrow reverse-proxy routes to Kuma |
| `compose/vps/landing/build.sh` | Derives the Compose Stack count, substitutes it, writes `dist/`, self-checks |
| `compose/vps/landing/test-build.sh` | Asserts the build substitutes correctly and fails loudly when it cannot |
| `compose/vps/landing/src/index.html` | Page markup, with `{{STACK_COUNT}}` placeholder |
| `compose/vps/landing/src/style.css` | All styling |
| `compose/vps/landing/src/status.js` | Live status widget: uptime average and per-service dots |
| `compose/vps/landing/src/topology.png` | Architecture diagram, copied from `docs/assets/` after regeneration |
| `compose/vps/landing/.gitignore` | Excludes `dist/` |
| `compose/vps/landing/README.md` | Build and deploy instructions for this stack |
| `docs/index.md` | Stripped to a navigation index (modified) |
| `docs/README.md` | GitHub-facing index; gains a link to the new public site (modified) |
| `docs/hosts/vps.md` | Records the new stack and the apex route (modified) |
| `compose/CLAUDE.md` | Gains the rebuild reminder for the baked-in count (modified) |
| `docs/assets/topology.png` | Stale export, regenerated before use (modified) |

`dist/` is a build artifact and is never committed.

---

### Task 1: Curate the public status page

Remediation of a live exposure. `https://uptime.homelabor.net/status/statuspage1` is published without authentication and discloses all 37 monitor names, including the media-acquisition stack. This runs first because the uptime average in Task 4 reads whichever monitors remain public, and because the exposure should not wait on the rest of the project.

This task is done through the Uptime Kuma web UI, not by editing its database. Direct SQLite edits bypass Kuma's in-memory caches and will not take effect until a restart.

**Files:**
- No repo files. Configuration change on the VPS, verified from the command line.

**Interfaces:**
- Consumes: nothing.
- Produces: a public status page at slug `statuspage1` whose `publicGroupList` contains exactly the thirteen monitors below. Task 4 reads monitor IDs from this page and depends on nothing else.

**Monitors that stay public** (id, name):

| 9 | AdGuard Home | 10 | Scrutiny | 11 | Home Assistant |
|---|---|---|---|---|---|
| 16 | Jellyfin | 35 | Immich | 38 | NetData |
| 40 | DocuSeal | 42 | Pangolin | 47 | Uptime Kuma (public) |
| 48 | SnapRAID Daemon | 53 | code-server | 54 | FreshRSS |
| 57 | Kan | | | | |

**Monitors that come off:** qBittorrent, Radarr, Sonarr, Prowlarr, Seerr, SuggestArr, Calibre Web Automated, Syncthing, Dawarich, Notifiarr, BentoPDF, ntfy, Homepage, Topology, Portfolio, Odysseus, Hermes, Homelable, Homelable MCP, Form, and the four duplicate "(public)" tunnel self-tests other than Uptime Kuma's.

- [ ] **Step 1: Record the current state so the change is reversible**

```bash
curl -s https://uptime.homelabor.net/api/status-page/statuspage1 \
  | grep -oE '"id":[0-9]+,"name":"[^"]+"' \
  > /tmp/statuspage1-before.txt
wc -l /tmp/statuspage1-before.txt
```

Expected: a non-empty list. Keep this file until Step 4 passes.

- [ ] **Step 2: Edit the status page in the Uptime Kuma UI**

Open `https://uptime.homelabor.net`, log in, open the status page titled "Running services", click Edit.

In the "Services" group, remove every monitor **except** the thirteen listed above. Save.

- [ ] **Step 3: Verify the public API no longer discloses the removed monitors**

```bash
curl -s https://uptime.homelabor.net/api/status-page/statuspage1 \
  | grep -oE '"name":"[^"]+"' | sed 's/"name":"//;s/"//' | sort
```

Expected: thirteen monitor names plus the group name "Services". Specifically absent: `qBittorrent`, `Radarr`, `Sonarr`, `Prowlarr`, `Seerr`, `SuggestArr`, `Syncthing`, `Dawarich`.

- [ ] **Step 4: Verify the badge endpoint still answers for a monitor that stayed**

```bash
curl -s "https://uptime.homelabor.net/api/badge/9/uptime/720h" | grep -oE '>[0-9.]+%<' | head -1
```

Expected: one line, a percentage such as `>99.93%<`. The `head -1` is not cosmetic: the badge SVG draws the value twice, once as a shadow and once as visible fill, so without it this prints two identical lines.

If this returns nothing and the badge body contains `N/A`, monitor 9 lost its public group membership and Step 2 was applied incorrectly.

- [ ] **Step 5: Verify a removed monitor now returns N/A**

```bash
curl -s "https://uptime.homelabor.net/api/badge/7/uptime/720h" | grep -oE 'N/A|>[0-9.]+%<'
```

Expected: `N/A`. Monitor 7 is qBittorrent. This confirms the removal took effect on the badge API and not only in the page's rendering.

- [ ] **Step 6: Record the change**

No repo files changed, so there is nothing to commit. Note in `private/todo.md` that the status page was curated on this date, so the reason is recoverable later.

---

### Task 2: Build script and its self-check

The only logic in the project. Everything else is markup, styling and configuration.

**Files:**
- Create: `compose/vps/landing/build.sh`
- Create: `compose/vps/landing/test-build.sh`
- Create: `compose/vps/landing/src/index.html`
- Create: `compose/vps/landing/.gitignore`

**Interfaces:**
- Consumes: nothing.
- Produces: `build.sh`, run with no arguments from any working directory, writes `dist/index.html` with `{{STACK_COUNT}}` replaced by a decimal integer. Exits 0 on success, non-zero with a message on stderr otherwise. Task 3 adds files to `src/`; `build.sh` copies the whole directory, so it needs no change when they appear.

- [ ] **Step 1: Write the failing test**

Create `compose/vps/landing/test-build.sh`:

```sh
#!/bin/sh
# Self-check for build.sh. Run: sh test-build.sh
set -eu

DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
fail() { echo "FAIL: $1" >&2; exit 1; }

# 1. A normal build succeeds and substitutes the placeholder.
sh "$DIR/build.sh" >/dev/null || fail "build.sh exited non-zero on a good source tree"
[ -f "$DIR/dist/index.html" ] || fail "build.sh did not produce dist/index.html"
grep -q '{{STACK_COUNT}}' "$DIR/dist/index.html" && fail "placeholder survived into dist/index.html"
# Loose on attributes on purpose: Task 3 restyles this element, and the test
# must survive a class or data attribute being added to it.
grep -qE 'id="stack-count"[^>]*>[0-9]+' "$DIR/dist/index.html" \
    || fail "stack count was not substituted with a number"

# 2. An unsubstituted placeholder is caught rather than shipped.
#
# This case has to dirty the real src/index.html, so the restore runs from a
# trap rather than from the happy path. Without it, a Ctrl-C between the
# mutation and the restore leaves a corrupted source file in the repo, and
# the next run would then back up the already-corrupted file and "restore"
# it. mktemp also keeps concurrent runs from sharing one backup path.
backup=$(mktemp)
cp "$DIR/src/index.html" "$backup"
trap 'cp "$backup" "$DIR/src/index.html" 2>/dev/null || true; rm -f "$backup"' EXIT INT TERM HUP

printf '<!-- {{UNKNOWN_TOKEN}} -->\n' >> "$DIR/src/index.html"
if sh "$DIR/build.sh" >/dev/null 2>&1; then
    fail "build.sh accepted an unsubstituted placeholder"
fi
cp "$backup" "$DIR/src/index.html"

# Leave a good build behind.
sh "$DIR/build.sh" >/dev/null || fail "rebuild after the negative case failed"

echo "PASS: build.sh substitutes counts and rejects leftover placeholders"
```

- [ ] **Step 2: Create the minimal source page the test needs**

Create `compose/vps/landing/src/index.html`. This is a skeleton; Task 3 replaces its content entirely, but the placeholder and the `stack-count` element id are contracts the test and `status.js` both rely on.

```html
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Norbert Csicsay - Homelab</title>
</head>
<body>
<p><span id="stack-count">{{STACK_COUNT}}</span> Docker Compose stacks</p>
</body>
</html>
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `sh compose/vps/landing/test-build.sh`
Expected: FAIL, because `build.sh` does not exist yet. The shell reports `build.sh: No such file or directory` and the test exits non-zero at the first assertion.

- [ ] **Step 4: Write the build script**

Create `compose/vps/landing/build.sh`:

```sh
#!/bin/sh
# Builds dist/ from src/, substituting counts derived from the repo.
# No dependencies: POSIX shell only, by design. See the design spec.
set -eu

DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$DIR/../../.." && pwd)
SRC="$DIR/src"
DIST="$DIR/dist"

[ -d "$REPO_ROOT/compose" ] || {
    echo "build: no compose/ directory under $REPO_ROOT" >&2
    exit 1
}

# Count directories that actually contain a compose file, not every
# second-level directory. CONTEXT.md defines a Compose Stack as a directory
# holding a docker-compose.yml, and the repo currently has one directory
# that does not: compose/proxmox-lxc-100/uptime-kuma is a leftover holding
# only .env after Kuma moved to the VPS. Counting directories would put a
# number on a public page that the repo cannot back up.
# Both spellings are in use here: seerr and bentopdf use compose.yaml.
# sed rather than find -printf, which is GNU-only.
stack_count=$(find "$REPO_ROOT/compose" -mindepth 3 -maxdepth 3 \
    \( -name docker-compose.yml -o -name compose.yml -o -name compose.yaml \) \
    | sed 's|/[^/]*$||' | sort -u | wc -l | tr -d ' ')

[ "$stack_count" -gt 0 ] || {
    echo "build: derived a stack count of zero, refusing to build" >&2
    exit 1
}

# dist/ becomes a public web root, and the copy below is wholesale. Anything
# that lands in src/ is served by path even with directory listing off, so a
# stray .env, editor swap file or *.bak would be fetchable at
# https://homelabor.net/<name>. Refuse rather than silently drop them, so the
# engineer finds out here instead of never.
risky=$(find "$SRC" \( -name '.*' -o -name '*.bak' -o -name '*~' \
    -o -name '*.swp' -o -name '*.orig' -o -name '*.env' \) -print)
if [ -n "$risky" ]; then
    echo "build: src/ contains files that must not be published:" >&2
    echo "$risky" >&2
    exit 1
fi

rm -rf "$DIST"
mkdir -p "$DIST"
cp -R "$SRC"/. "$DIST"/

sed -i "s/{{STACK_COUNT}}/$stack_count/g" "$DIST/index.html"

# Scan the whole output, not just index.html. Tasks 3 and 4 add style.css
# and status.js to src/, which are copied verbatim; a stray placeholder in
# either would otherwise ship silently. -I skips binaries so topology.png
# cannot produce a false match.
if grep -rIq '{{[A-Z_]*}}' "$DIST"; then
    echo "build: unsubstituted placeholders remain in dist/" >&2
    grep -rIo '{{[A-Z_]*}}' "$DIST" >&2
    exit 1
fi

echo "build: ok, $stack_count compose stacks"
```

- [ ] **Step 5: Create the gitignore**

Create `compose/vps/landing/.gitignore`:

```
dist/
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `sh compose/vps/landing/test-build.sh`
Expected: `PASS: build.sh substitutes counts and rejects leftover placeholders`

Then confirm the derived number matches reality:

```bash
find compose -mindepth 3 -maxdepth 3 \
  \( -name docker-compose.yml -o -name compose.yml -o -name compose.yaml \) \
  | sed 's|/[^/]*$||' | sort -u | wc -l
grep -o 'id="stack-count">[0-9]*' compose/vps/landing/dist/index.html
```

Expected: both report **28** at this point, and **29** once Task 5 adds `compose/vps/landing/docker-compose.yml`. They must agree with each other whatever the value is.

Note that a plain `find -mindepth 2 -maxdepth 2 -type d` reports 29 and 30 respectively. That extra directory is `compose/proxmox-lxc-100/uptime-kuma`, which holds only a `.env` left behind when Uptime Kuma moved to the VPS. It is not a Compose Stack under this repo's own definition, and this number goes on a public page, so the count follows the definition rather than the directory listing.

- [ ] **Step 7: Commit**

```bash
git add compose/vps/landing/build.sh compose/vps/landing/test-build.sh \
        compose/vps/landing/src/index.html compose/vps/landing/.gitignore
git commit -m "feat(landing): dependency-free build script with self-check"
```

---

### Task 3: Page content and visual design

**Files:**
- Modify: `compose/vps/landing/src/index.html` (replaces the skeleton from Task 2)
- Create: `compose/vps/landing/src/style.css`
- Create: `compose/vps/landing/src/topology.png` (copied from `docs/assets/topology.png`)

**Interfaces:**
- Consumes: `build.sh` from Task 2, and the `{{STACK_COUNT}}` placeholder contract.
- Produces: DOM element ids that Task 4's `status.js` binds to, and which must not be renamed:
  - `#stack-count` - already substituted at build time, no JavaScript touches it. **Its opening tag must be immediately followed by `{{STACK_COUNT}}` on the same line, with no nested element and no whitespace between them**, like `<span id="stack-count">{{STACK_COUNT}}</span>`. Task 2's test asserts the pattern `id="stack-count"[^>]*>[0-9]+`, so wrapping the number in an inner element or breaking the line is valid HTML that still renders correctly but fails the build check in Task 5, long after the cause. Attributes may be added freely; only the position of the number is fixed.
  - `#uptime-figure` - text content set to a string like `99.93%`
  - `#uptime-block` - the container whose `hidden` attribute is removed once a figure is available
  - `#service-dots` - a container that receives a `<ul class="dots">` holding one `<li class="dot" data-status="up|down">` per public monitor, each carrying a `title` and a visually hidden label like `AdGuard Home: up`. The stylesheet needs a `.visually-hidden` rule (clipped, not `display:none`, which would hide it from screen readers too) and must style `.dots` as an unstyled list.

- [ ] **Step 1: Invoke the design skill**

This page exists to be looked at. Use the `design-taste-frontend` skill before writing markup, and follow its output for layout, type scale, spacing and colour. The spec's direction is the input to that skill, not a substitute for it:

- Dark theme.
- Sans-serif body copy, monospace for figures and status text.
- Indicator dots pulse subtly; hero figures count up when scrolled into view.
- Project cards lift slightly on hover.
- Mobile: sections stack, icon grid drops to two columns.

- [ ] **Step 2: Regenerate the architecture diagram, then copy it**

**Do not copy `docs/assets/topology.png` as it stands.** It is a stale export and it becomes the architecture centrepiece of a page written to be examined by hiring managers. Verified against the live hypervisor:

- It shows `Ollama (LXC 108)` at 192.168.0.231. `pct list` on pve returns no LXC 108; that container is gone.
- It omits LXC 111 (`uzlet`) and LXC 113 (`agentos`), both of which exist and are documented in `AGENTS.md`.

The good news is that only the image is stale. The source of truth, `compose/proxmox-lxc-100/topology/nodes.yml`, is already correct: it contains 111 and 113 and no 108. So this is a re-export, not a data fix.

Confirm that before regenerating, so a fix is not applied to the wrong layer:

```bash
grep -c "LXC 108" compose/proxmox-lxc-100/topology/nodes.yml
grep -c "LXC 111\|LXC 113" compose/proxmox-lxc-100/topology/nodes.yml
ssh root@192.168.0.109 'pct list'
```

Expected: `0` for LXC 108, `2` for 111 and 113, and a `pct list` that agrees with `nodes.yml`. If `nodes.yml` disagrees with `pct list`, fix `nodes.yml` first and note it, because that stack renders the diagram used in two places.

Then rebuild the topology stack, capture the rendered page as a PNG, and put the fresh export in both places:

```bash
cp <fresh-export>.png docs/assets/topology.png
cp docs/assets/topology.png compose/vps/landing/src/topology.png
ls -l compose/vps/landing/src/topology.png
```

The Documentation Site's copy is refreshed too, since it carries the same staleness and the same diagram. Copying rather than referencing is required because the container serves only its own directory.

- [ ] **Step 3: Write the page**

Replace `compose/vps/landing/src/index.html` with the five sections below. Write the real copy; there is no placeholder text in this project.

1. **Hero** - name; one line stating what is run; `{{STACK_COUNT}}` Docker Compose stacks; the uptime block; buttons to GitHub, LinkedIn, and `https://docs.homelabor.net/`. Do not use the phrase "career changer" or any equivalent. State what the infrastructure is, not what the author is transitioning from.
2. **Tech stack** - icon grid: Proxmox, Docker, Komodo, MergerFS + SnapRAID, Restic, Pangolin, Caddy, Tailscale, AdGuard, Uptime Kuma.
3. **Architecture** - `topology.png` with a short caption.
4. **Featured Projects** - four cards. Titles and hrefs exactly as below; all four were verified to return HTTP 200:
   - Komodo GitOps Migration -> `https://docs.homelabor.net/proxmox/16_Komodo_complete_setup/`
   - Resilient Storage -> `https://docs.homelabor.net/proxmox/01_Proxmox_VE_9.1_MergerFS_SnapRAID_Installation_Documentation/`
   - Self-hosted Tunnel -> `https://docs.homelabor.net/vps/01_Hetzner_VPS_Pangolin_Jellyfin_Setup/`
   - Backup System -> `https://docs.homelabor.net/proxmox/15_Proxmox_Backup_System_Documentation/`
   - Card body text: adapt the four descriptions currently in `docs/index.md` lines 64 to 85. They are removed from there in Task 6, so read them before that task runs.
5. **Contact / footer** - LinkedIn, GitHub. No CV link. The slot is reserved in the markup as an HTML comment naming what goes there, so a future edit needs no design decision.

The uptime block starts hidden and carries the ids from the Interfaces section:

```html
<div id="uptime-block" hidden>
  <span id="uptime-figure"></span>
  <span class="label">30-day uptime</span>
  <div id="service-dots"></div>
</div>
```

`hidden` is the default state on purpose. If `status.js` never runs or Kuma never answers, the page shows no uptime claim at all rather than a zero, a dash or a spinner.

- [ ] **Step 4: Write the stylesheet**

Create `compose/vps/landing/src/style.css` following the design skill's output. It must cover: the dark palette, the two type families, the responsive grid collapse at a mobile breakpoint, the `.dot` states (`[data-status="up"]` and `[data-status="down"]`), the dot pulse animation, and the card hover lift.

Respect `prefers-reduced-motion: reduce` by disabling the pulse and the count-up. Motion that cannot be turned off is an accessibility defect, and the Lighthouse pass in Task 6 will not catch it.

- [ ] **Step 5: Build and review locally**

```bash
sh compose/vps/landing/test-build.sh
python3 -m http.server 8099 --directory compose/vps/landing/dist
```

Open `http://localhost:8099`. The uptime block is expected to be invisible at this point: `status.js` does not exist yet, and even once it does, the Kuma proxy only exists on the VPS. Check the other four sections at a desktop width and at 375 px.

- [ ] **Step 6: Commit**

```bash
git add compose/vps/landing/src/
git commit -m "feat(landing): page content, styling and architecture diagram"
```

---

### Task 4: Live status widget and the Kuma proxy

**Files:**
- Create: `compose/vps/landing/src/status.js`
- Create: `compose/vps/landing/Caddyfile`
- Modify: `compose/vps/landing/src/index.html` (add the script tag)

**Interfaces:**
- Consumes: the DOM ids from Task 3; the curated status page from Task 1.
- Produces: three same-origin routes that must exist for the widget to work, all proxied to `172.17.0.1:3001`: `/api/badge/*`, and the two exact paths `/api/status-page/statuspage1` and `/api/status-page/heartbeat/statuspage1`. Adding a status page later means adding its routes here deliberately, which is the point.

**Honest boundary:** this task can prove the Caddyfile is *valid* and that it serves the static site, but it cannot prove the proxy routes reach Kuma. The upstream is `172.17.0.1:3001` on the VPS, which does not exist on a development machine. Proxy acceptance genuinely belongs to Task 5 Step 9, and is called out there rather than pretended here.

The monitor list is **not** hardcoded. `status.js` reads the public monitors from the status page itself, so Task 1's curation is the single source of truth and a later change there needs no code edit.

- [ ] **Step 1: Write the Caddyfile**

Create `compose/vps/landing/Caddyfile`:

```
:80 {
	# The heartbeat payload is large and highly repetitive: 242 KB for 37
	# monitors, and still around 85 KB for the curated 13. It compresses
	# 13x (measured: 242 KB -> 18 KB gzipped), so this one line is the
	# fix rather than trying to shrink the payload at the Kuma end.
	# Kuma's showOnlyLastHeartbeat option does NOT help - the heartbeat
	# route hardcodes `LIMIT 100` and never reads that flag.
	encode zstd gzip

	# Uptime Kuma runs on this same host with network_mode: host.
	# 172.17.0.1 is the address Pangolin's own resource target uses; the
	# architecture diagram in docs/vps/03 says 172.18.0.1 and is wrong.
	# Only these two prefixes are proxied, not all of Kuma's API.
	# Badges stay a wildcard because the monitor ids follow whatever Task 1
	# curates, and Kuma gates them itself: isMonitorPublic() makes a badge
	# for a non-public monitor render "N/A" rather than leak a figure.
	handle /api/badge/* {
		reverse_proxy 172.17.0.1:3001
	}

	# Status-page routes are pinned to this one slug, NOT /api/status-page/*.
	# A wildcard would publish every status page Kuma ever hosts through the
	# apex, including a future one created for private use. This route is on
	# an auth-free public hostname, so it grants exactly what the widget
	# needs and nothing else.
	handle /api/status-page/statuspage1 {
		reverse_proxy 172.17.0.1:3001
	}

	handle /api/status-page/heartbeat/statuspage1 {
		reverse_proxy 172.17.0.1:3001
	}

	handle {
		root * /usr/share/caddy
		file_server
	}
}
```

- [ ] **Step 2: Write the status widget**

Create `compose/vps/landing/src/status.js`:

```js
// Live status for the hero. Same-origin: Caddy proxies /api/* to Uptime
// Kuma on this host. Kuma's status-page JSON sends no CORS headers, which
// is why this page is served from the same host rather than from a CDN.
(function () {
  "use strict";

  var SLUG = "statuspage1";
  var WINDOW_HOURS = "720h"; // 30 days. The status-page JSON only exposes 24h.
  var TIMEOUT_MS = 4000;

  // allSettled waits for every promise to settle, and a stalled fetch never
  // does. Without a deadline, one hung request from Kuma leaves the block
  // hidden forever even though the other values already arrived. Every
  // request therefore carries its own abort timer.
  function fetchWithTimeout(url) {
    var controller = new AbortController();
    var timer = setTimeout(function () {
      controller.abort();
    }, TIMEOUT_MS);
    return fetch(url, { signal: controller.signal }).then(
      function (r) {
        clearTimeout(timer);
        return r;
      },
      function (err) {
        clearTimeout(timer);
        throw err;
      }
    );
  }

  function getJSON(url) {
    return fetchWithTimeout(url).then(function (r) {
      if (!r.ok) throw new Error(url + " returned " + r.status);
      return r.json();
    });
  }

  // Kuma's badge endpoint returns SVG, not JSON. The value is text content,
  // e.g. ...textLength="430">99.93%</text>
  function getBadgeUptime(id) {
    return fetchWithTimeout("/api/badge/" + id + "/uptime/" + WINDOW_HOURS)
      .then(function (r) {
        if (!r.ok) throw new Error("badge " + id + " returned " + r.status);
        return r.text();
      })
      .then(function (svg) {
        // The badge draws the value twice: a dark shadow text, then the
        // visible fill text. Take the last match, which is the visible one.
        // A monitor that is not on the public status page renders "N/A"
        // instead of a percentage, and falls through to null.
        var matches = svg.match(/>([\d.]+)%</g);
        if (!matches || !matches.length) return null;
        var last = matches[matches.length - 1];
        return parseFloat(last.slice(1, -2));
      });
  }

  // Names are kept, not just ids. A row of coloured dots with no text is
  // meaningless to a screen reader and ambiguous to everyone else: nothing
  // says which dot is which service.
  function publicMonitors(page) {
    var monitors = [];
    (page.publicGroupList || []).forEach(function (group) {
      (group.monitorList || []).forEach(function (m) {
        monitors.push({ id: m.id, name: m.name });
      });
    });
    return monitors;
  }

  function renderDots(monitors, heartbeats) {
    var container = document.getElementById("service-dots");
    if (!container) return;
    container.textContent = "";

    var list = document.createElement("ul");
    list.className = "dots";

    monitors.forEach(function (m) {
      var beats = heartbeats[m.id] || [];
      var last = beats[beats.length - 1];
      // Kuma status: 1 = up, 3 = maintenance. Anything else is not up.
      var up = !!last && (last.status === 1 || last.status === 3);

      var item = document.createElement("li");
      item.className = "dot";
      item.dataset.status = up ? "up" : "down";
      // Carries the meaning in text, not only in colour. Read aloud by
      // screen readers, shown on hover, and survives a CSS failure.
      item.title = m.name + ": " + (up ? "up" : "down");

      var label = document.createElement("span");
      label.className = "visually-hidden";
      label.textContent = item.title;
      item.appendChild(label);

      list.appendChild(item);
    });

    container.appendChild(list);
  }

  getJSON("/api/status-page/" + SLUG)
    .then(function (page) {
      var monitors = publicMonitors(page);
      if (!monitors.length) throw new Error("status page lists no public monitors");

      var ids = monitors.map(function (m) {
        return m.id;
      });

      // allSettled throughout, never all. One badge returning 404 must not
      // cost the whole figure when twelve others answered, and losing the
      // heartbeat call must not cost the figure either. Only a total absence
      // of usable values hides the block.
      return Promise.allSettled([
        Promise.allSettled(ids.map(getBadgeUptime)),
        getJSON("/api/status-page/heartbeat/" + SLUG)
      ]).then(function (outer) {
        var values = (outer[0].value || [])
          .filter(function (r) {
            return (
              r.status === "fulfilled" &&
              typeof r.value === "number" &&
              !isNaN(r.value)
            );
          })
          .map(function (r) {
            return r.value;
          });

        if (!values.length) throw new Error("no badge returned a usable value");

        var mean =
          values.reduce(function (a, b) {
            return a + b;
          }, 0) / values.length;

        document.getElementById("uptime-figure").textContent = mean.toFixed(2) + "%";

        if (outer[1].status === "fulfilled") {
          renderDots(monitors, (outer[1].value || {}).heartbeatList || {});
        } else {
          console.warn("service dots unavailable:", outer[1].reason.message);
        }

        document.getElementById("uptime-block").removeAttribute("hidden");
      });
    })
    .catch(function (err) {
      // Deliberate: the block stays hidden. A portfolio page must never
      // show a fabricated or broken availability figure.
      console.warn("live status unavailable:", err.message);
    });
})();
```

- [ ] **Step 3: Add the script tag**

In `compose/vps/landing/src/index.html`, immediately before `</body>`:

```html
<script src="status.js" defer></script>
```

- [ ] **Step 4: Verify the build still passes, and that the guard reaches the new files**

Run: `sh compose/vps/landing/test-build.sh`
Expected: `PASS`. `build.sh` copies `src/` wholesale, so the new files need no build change.

The placeholder guard scans all of `dist/`, not only `index.html`. `status.js` and `style.css` are copied verbatim and never substituted, so a stray `{{TOKEN}}` in either would ship to a public page unless the guard reaches them. Confirm it does, now that there is a second file to test against:

Probe with a **new throwaway file** rather than by appending to `status.js`. Editing a real source file and undoing the edit is the pattern Task 2 had to fix with a trap; an interrupted `sed -i '$d'` deletes a real line of code, and if the file lacks a trailing newline the appended comment merges into the last statement:

```bash
cd compose/vps/landing
printf '// {{LEFTOVER}}\n' > src/_guard-probe.js
sh build.sh; echo "exit=$?"
rm -f src/_guard-probe.js
sh build.sh >/dev/null && echo "guard verified, no source file was touched"
```

Expected: the first build exits non-zero reporting `{{LEFTOVER}}`; after the probe is removed, the build succeeds. If the first build exits 0, the guard is still scanning only `index.html` and Task 2's build script was not updated.

An interruption here leaves behind a stray `_guard-probe.js` rather than a damaged source file, and the next build refuses to run until it is gone, so the failure announces itself.

- [ ] **Step 5: Validate the Caddyfile and confirm static serving**

A syntax error or a mistyped path matcher in the Caddyfile would otherwise surface only in Task 5, on the VPS, mixed in with network and firewall variables. Separate it out now:

```bash
cd compose/vps/landing
docker run --rm -v "$PWD/Caddyfile:/etc/caddy/Caddyfile:ro" caddy:alpine \
  caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile
```

Expected: `Valid configuration`. This checks the whole file including the three `handle` blocks and the `encode` directive.

Then confirm the static half actually serves, and that the API paths are routed rather than falling through to the file server:

```bash
docker run --rm -d --name landing-probe -p 8099:80 \
  -v "$PWD/Caddyfile:/etc/caddy/Caddyfile:ro" \
  -v "$PWD/dist:/usr/share/caddy:ro" caddy:alpine
sleep 2
curl -s -o /dev/null -w "index: %{http_code}\n" http://localhost:8099/
curl -s -o /dev/null -w "status.js: %{http_code}\n" http://localhost:8099/status.js
curl -s -o /dev/null -w "api: %{http_code}\n" http://localhost:8099/api/status-page/statuspage1
curl -s -o /dev/null -w "unrouted api: %{http_code}\n" http://localhost:8099/api/status-page/other
docker rm -f landing-probe
```

Expected: `200` for the first two. The third returns `502` - Caddy matched the route and tried to reach `172.17.0.1:3001`, which is not there locally; that failure is the proof the route matched. The fourth must return `404`, from the file server, proving the narrowed matcher does **not** pass arbitrary status page slugs. A `502` on the fourth means the route was left as a wildcard.

- [ ] **Step 6: Commit**

```bash
git add compose/vps/landing/Caddyfile compose/vps/landing/src/status.js \
        compose/vps/landing/src/index.html
git commit -m "feat(landing): same-origin live status widget and Kuma proxy"
```

---

### Task 5: Deploy the stack to the VPS

At the end of this task the site runs on the VPS and is reachable from the VPS only. It is not public yet; that is Task 6.

**Files:**
- Create: `compose/vps/landing/docker-compose.yml`
- Create: `compose/vps/landing/README.md`

**Interfaces:**
- Consumes: everything from Tasks 2 to 4.
- Produces: a running container named `landing` at `172.18.0.10:80` on the `pangolin` network. Task 6's Pangolin resource targets exactly that address and port.

- [ ] **Step 1: Write the compose file**

Create `compose/vps/landing/docker-compose.yml`:

```yaml
services:
  landing:
    image: caddy:alpine
    container_name: landing
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - ./dist:/usr/share/caddy:ro
    networks:
      pangolin:
        ipv4_address: 172.18.0.10
    restart: unless-stopped

# Joining the existing pangolin network is load-bearing, not cosmetic.
# UFW on this host permits port 3001 only from 172.18.0.0/16, so a container
# on its own network could not reach Uptime Kuma. It also means no host port
# is published on the public gateway. The address is static because Pangolin
# addresses resource targets by IP.
networks:
  pangolin:
    external: true
```

- [ ] **Step 2: Write the stack README**

Create `compose/vps/landing/README.md` documenting: what the stack is, that `dist/` is a build artifact, the exact build and redeploy commands from Step 7 below, why the container joins the `pangolin` network, why Kuma is at `172.17.0.1:3001`, and that the stack is stateless so `scripts/backup.sh` has nothing to cover. Mirror the tone and level of detail of `compose/proxmox-lxc-100/portfolio/README.md`.

It must also carry the **maintenance contract**, prominently, because nothing else enforces it:

> The Compose Stack count on the landing page is baked in at build time. Nothing rebuilds it on a schedule; that was a deliberate design choice. So **after adding or removing any Compose Stack anywhere in this repo**, rebuild and recreate this one, or the public number silently goes stale:
>
> ```bash
> ssh vps 'cd /etc/komodo/repos/github/compose/vps/landing && sh build.sh && docker rm -f landing && docker compose up -d'
> ```

Add the same one-line reminder to `compose/CLAUDE.md`, next to the existing "After editing a compose file" instruction. That file is the one actually read when a stack is added, so it is where the reminder has a chance of being seen.

The uptime figure needs none of this: it is fetched live and cannot drift.

- [ ] **Step 3: Commit locally**

```bash
git add compose/vps/landing/docker-compose.yml compose/vps/landing/README.md
git commit -m "feat(landing): compose stack for the VPS"
```

- [ ] **Step 4: Stop and ask for push authorization**

Komodo deploys from the **remote**, so it cannot see this stack until the commit is pushed. The project rule in `AGENTS.md` is never to push unless explicitly asked, so this is a hard stop, not a formality.

Ask the user for permission to push. Do not continue past this step without an explicit yes.

If permission is refused, deployment is blocked. Stop here and report that; do not attempt to work around it by copying files onto the VPS by hand, which would leave the running stack diverged from git and defeat the point of the GitOps flow.

If permission is granted:

```bash
git push
```

- [ ] **Step 5: Register the stack in Komodo and pull**

In the Komodo UI at `http://192.168.0.105:9120`, create a stack for `compose/vps/landing` on server **VPS** (uppercase - a lowercase name creates a duplicate server entry, see `docs/hosts/vps.md`), then Pull.

Verify the pull actually landed before going further:

```bash
ssh vps 'ls /etc/komodo/repos/github/compose/vps/landing/'
```

Expected: `Caddyfile`, `README.md`, `build.sh`, `docker-compose.yml`, `src/`, `test-build.sh`. If `src/` is missing, the pull predates the content commit and Komodo needs another Pull.

- [ ] **Step 6: Confirm the network is joinable before starting anything**

```bash
ssh vps 'docker network inspect pangolin --format "{{range .IPAM.Config}}{{.Subnet}} {{.Gateway}}{{end}}"'
ssh vps 'docker network inspect pangolin --format "{{range .Containers}}{{.IPv4Address}} {{end}}"'
```

Expected: subnet `172.18.0.0/16`, gateway `172.18.0.1`, and `172.18.0.10` **not** among the addresses in use. If it is taken, pick the next free address and update both the compose file and Task 6's target.

- [ ] **Step 7: Build and start**

```bash
ssh vps 'cd /etc/komodo/repos/github/compose/vps/landing && sh build.sh && docker compose up -d'
```

Expected: `build: ok, 29 compose stacks` followed by the container starting.

The build must run before `up -d`, because `dist/` is a bind mount that does not exist until the build creates it.

On every later rebuild, recreate rather than restart. The build deletes and recreates `dist/`, which breaks an existing bind mount:

```bash
ssh vps 'cd /etc/komodo/repos/github/compose/vps/landing && sh build.sh && docker rm -f landing && docker compose up -d'
```

- [ ] **Step 8: Verify the page is served**

```bash
ssh vps 'curl -s -o /dev/null -w "%{http_code}\n" http://172.18.0.10/'
ssh vps 'curl -s http://172.18.0.10/ | grep -o "id=\"stack-count\">[0-9]*"'
```

Expected: `200`, and a stack count of **29** - the 28 from Task 2 plus this stack's own `docker-compose.yml`, which is now committed and counted. If it still reads 28, `build.sh` ran before the compose file existed and needs re-running.

- [ ] **Step 9: Verify the Kuma proxy works from inside the container's network**

```bash
ssh vps 'curl -s "http://172.18.0.10/api/badge/9/uptime/720h" | grep -oE ">[0-9.]+%<" | head -1'
ssh vps 'curl -s "http://172.18.0.10/api/status-page/statuspage1" | grep -oE "\"name\":\"[^\"]+\"" | wc -l'
ssh vps 'curl -s -H "Accept-Encoding: gzip" -o /dev/null -w "%{size_download} bytes\n" "http://172.18.0.10/api/status-page/heartbeat/statuspage1"'
```

Expected: one percentage such as `>99.93%<`; fourteen names (thirteen monitors plus the group); and a compressed heartbeat body in the region of 6 KB. If that third figure comes back near 85 KB, `encode` is missing from the Caddyfile and the page is shipping fourteen times more bytes than it needs.

If the badge request hangs or returns a 502, the container is not in the UFW-permitted source range. Confirm with `ssh vps 'docker inspect landing --format "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}"'` - it must report `172.18.0.10`.

- [ ] **Step 10: Review the rendered page visually**

```bash
ssh -L 8099:172.18.0.10:80 vps -N
```

Open `http://localhost:8099`. The uptime block should now be **visible**, showing a figure near 99.9% and thirteen dots. This is the first point at which the widget can work, because it is the first time the page and Kuma share an origin.

---

### Task 6: Go public, and strip the docs homepage

**Files:**
- Modify: `docs/index.md`
- Modify: `docs/hosts/vps.md`

**Interfaces:**
- Consumes: the running container from Task 5.
- Produces: `https://homelabor.net` serving the Landing Page over TLS with no authentication.

- [ ] **Step 1: Add the apex DNS record**

In Cloudflare, for `homelabor.net`, add an **A** record:

- Name: `@`
- Value: the VPS address, `46.224.206.74`
- Proxy status: **DNS only (gray cloud)**

Gray cloud is mandatory. Orange cloud breaks Traefik's Let's Encrypt challenge, per `docs/vps/01_Hetzner_VPS_Pangolin_Jellyfin_Setup.md`. This also means there is no CDN and no stale-on-error cache; that trade was made knowingly in `docs/adr/0001-landing-page-hosted-on-vps.md`.

Verify:

```bash
dig +short homelabor.net A
```

Expected: `46.224.206.74`.

- [ ] **Step 2: Create the Pangolin resource**

In the Pangolin UI at `https://pangolin.homelabor.net`:

- New HTTP resource, name `Landing`.
- Domain: `homelabor.net`, subdomain field left **blank** (this is how an apex resource is expressed; `subdomain` is nullable and all ten existing resources happen to use one, so there is no local precedent).
- Target: `172.18.0.10`, port `80`, method `http`.
- SSL: on.
- Authentication: **off**. This is the one resource that must be reachable with no session. Jellyfin is the existing precedent for a public auth-free resource.

**If the installed version refuses a blank subdomain** (fosrl/pangolin issue #2645 covers this), fall back to a Traefik file-provider router. Add to `/opt/pangolin/config/traefik/dynamic_config.yml` under `http.routers`:

```yaml
    landing-router:
      rule: "Host(`homelabor.net`)"
      service: landing-service
      entryPoints:
        - websecure
      tls:
        certResolver: letsencrypt
```

and under `http.services`:

```yaml
    landing-service:
      loadBalancer:
        servers:
          - url: "http://172.18.0.10:80"
```

Back the file up first (`cp dynamic_config.yml dynamic_config.yml.bak-$(date +%Y%m%d)`, matching the existing convention in that directory), and record the hand-edit in `docs/hosts/vps.md` as something to re-apply after a Pangolin upgrade. Note that `pangolin` and `traefik` both run floating `latest` tags on this host, so an upgrade can arrive unannounced.

**Rollback, before running Step 3.** Steps 1 and 2 are the first externally visible changes in this plan. If verification fails, `homelabor.net` is publicly resolving to a broken route, a login page or a TLS error, and it stays that way until undone. Read this before verifying, not after:

The order depends on which path Step 2 took, because the two failure modes have different blast radii.

**If the Step 2 fallback was used, or any existing subdomain has stopped working, start here.** `dynamic_config.yml` is the live Traefik file provider for the whole gateway, not just the apex, so a bad edit there can take down `jellyfin.homelabor.net`, `uptime.homelabor.net` and everything else. Deleting the apex DNS record does nothing for those. Restore first, verify the other resources, then unwind the apex:

```bash
ssh vps 'cd /opt/pangolin/config/traefik && cp dynamic_config.yml.bak-YYYYMMDD dynamic_config.yml'
ssh vps 'docker restart traefik'
ssh vps 'docker logs --tail 30 traefik'
curl -s -o /dev/null -w "uptime: %{http_code}\n" https://uptime.homelabor.net/
curl -s -o /dev/null -w "pangolin: %{http_code}\n" https://pangolin.homelabor.net/
```

Traefik picks up file-provider changes on write, but restarting removes the doubt. Check the logs for certificate errors, and confirm those two unrelated hostnames answer, before concluding the restore worked.

**Then, or as the whole rollback if the Pangolin resource path was used:**

1. **Pangolin:** delete the `Landing` resource, or toggle it disabled. No other resource shares the apex, so this is contained.
2. **Cloudflare:** delete the apex `A` record, or pause it. The name stops resolving, which is strictly better than resolving to something broken. Note this does not revoke an already-issued certificate; it only stops future public resolution.

None of Tasks 1 to 5 need reverting: the container is not public on its own, and the status page curation is a fix that stands regardless.

- [ ] **Step 3: Verify the apex is public and correctly certificated**

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://homelabor.net/
curl -sI https://homelabor.net/ | head -1
echo | openssl s_client -connect homelabor.net:443 -servername homelabor.net 2>/dev/null \
  | openssl x509 -noout -subject -dates
```

Expected: `200` with no redirect to a Pangolin login page, and a certificate whose subject covers `homelabor.net` with a valid date range.

Then confirm from a session-free client, since a logged-in browser would mask an auth misconfiguration:

```bash
curl -s https://homelabor.net/ | grep -c "stack-count"
```

Expected: `1`.

- [ ] **Step 4: Strip the docs homepage**

In `docs/index.md`, remove the `## Tech Stack`, `## Architecture`, `## Docker Services (LXC 100)`, `## Dashboard` and `## Featured Projects` sections (lines 11 to 85 at the time of writing). Keep `## Navigation` and `## Contact`.

Then **replace** the intro sentence under the `# Homelab Infrastructure` heading. It currently reads:

```markdown
Self-hosted infrastructure running 28 services on Proxmox VE. Built from scratch to learn Linux, networking, and DevOps practices.
```

That "28 services" is a hand-typed count, of exactly the kind this whole plan exists to stop publishing. Removing lines 11 to 85 does not touch it, so it must be replaced explicitly:

```markdown
This is the technical documentation. For the infrastructure overview and live status, see [homelabor.net](https://homelabor.net/).
```

Do not substitute a corrected number here. The Documentation Site has no build step that can derive one, so any figure written here starts drifting the moment a stack is added. The count belongs on the Landing Page, where it is derived.

The four Featured Project descriptions now live on the Landing Page. They are moved, not copied: duplicated facts drift, which is the same reason the stack count is derived rather than typed.

Then handle the GitHub-facing index. `AGENTS.md` requires MkDocs navigation and `docs/README.md` to stay in sync with docs changes, and `docs/CLAUDE.md` records that `docs/index.md` and `docs/README.md` coexist, the latter being what GitHub renders.

This task adds and removes no documentation *files*, so `README.md`'s directory listing stays accurate and `mkdocs.yml`'s `nav:` needs no change. Confirm that rather than assuming it:

```bash
grep -c '\.md)' docs/README.md
ls docs/proxmox/*.md docs/vps/*.md docs/hosts/*.md | wc -l
```

Both counts must be unchanged from before this task. What *is* now missing from `README.md` is the site itself: it is the GitHub-facing entry point and the repo has just acquired a public landing page. Add one line to its `## External Resources` section:

```markdown
- [homelabor.net](https://homelabor.net/) - infrastructure overview
```

`docs/CNAME` stays exactly as it is, containing `docs.homelabor.net`. The documentation site keeps its subdomain; only the apex is new.

- [ ] **Step 5: Verify the docs site still builds and its links resolve**

```bash
mkdocs build --strict
```

Expected: a clean build. `--strict` turns broken internal links into errors, which is what catches a section removed while something still links to it.

- [ ] **Step 6: Document the new stack**

In `docs/hosts/vps.md`, add `landing` to the list of Komodo-managed stacks, and record: the static address `172.18.0.10` on the `pangolin` network, that no host port is published, that the apex route has no authentication by design, and the Traefik hand-edit if Step 2's fallback was used.

- [ ] **Step 7: Run the quality checks**

- Lighthouse on `https://homelabor.net/`: performance, accessibility, best practices, SEO. Fix anything that lands in the red.
- Check every section at a desktop width and at 375 px.
- Click all four Featured Project cards and confirm each loads its documentation page.
- Confirm the reserved CV slot renders nothing visible.

- [ ] **Step 8: Verify the failure path**

The uptime block must disappear rather than break when Kuma is unreachable. Do not stop Kuma to test this - it is monitoring production. Block the requests at the client instead.

Open `https://homelabor.net/` with devtools, add a network request-blocking pattern for `*/api/*`, and reload.

Expected: the hero renders with no uptime figure, no empty box, no zero, no dash and no error text. The console carries a single `live status unavailable:` warning. Every other section is unaffected.

Then remove the block, reload, and confirm the figure returns. A fallback that never un-falls-back is the same defect in the other direction.

- [ ] **Step 9: Monitor the Landing Page itself**

In the Uptime Kuma UI, add an HTTP monitor:

- Name: `Landing`
- URL: `https://homelabor.net/`
- Expected status: 200

Do **not** add it to the `statuspage1` group. A page that reports its own availability proves nothing, and the figure it reports would include itself.

Verify it stays off the public page:

```bash
curl -s https://uptime.homelabor.net/api/status-page/statuspage1 | grep -c '"name":"Landing"'
```

Expected: `0`.

- [ ] **Step 10: Commit**

```bash
git add docs/index.md docs/README.md docs/hosts/vps.md
git commit -m "docs: point the docs homepage at homelabor.net and record the landing stack"
```

---

## Post-implementation follow-ups

Not part of this plan. Recorded so they are not lost:

- `AGENTS.md` and `CLAUDE.md` both claim 22 Docker stacks on LXC 100; there are 23.
- `docs/vps/03_Uptime_Kuma_VPS_Migration.md` shows Traefik reaching Kuma at `172.18.0.1:3001`; the configured target is `172.17.0.1:3001`.
- `pangolin` and `traefik` on the VPS run floating `latest` tags. This matters more now that an apex route depends on Pangolin's behaviour.
- `compose/proxmox-lxc-100/uptime-kuma/` holds only a `.env`, left behind when Uptime Kuma moved to the VPS. It is not a Compose Stack and is the reason the count in Task 2 is derived from compose files rather than directories. Worth deleting, but deliberately not in this plan: removing it would change a publicly displayed number in the same change that ships the page.
