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
| `compose/vps/landing/Caddyfile` | Static file serving plus two narrow reverse-proxy routes to Kuma |
| `compose/vps/landing/build.sh` | Derives the Compose Stack count, substitutes it, writes `dist/`, self-checks |
| `compose/vps/landing/test-build.sh` | Asserts the build substitutes correctly and fails loudly when it cannot |
| `compose/vps/landing/src/index.html` | Page markup, with `{{STACK_COUNT}}` placeholder |
| `compose/vps/landing/src/style.css` | All styling |
| `compose/vps/landing/src/status.js` | Live status widget: uptime average and per-service dots |
| `compose/vps/landing/src/topology.png` | Architecture diagram, copied from `docs/assets/` |
| `compose/vps/landing/.gitignore` | Excludes `dist/` |
| `compose/vps/landing/README.md` | Build and deploy instructions for this stack |
| `docs/index.md` | Stripped to a navigation index (modified) |
| `docs/hosts/vps.md` | Records the new stack and the apex route (modified) |

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
curl -s "https://uptime.homelabor.net/api/badge/9/uptime/720h" | grep -oE '>[0-9.]+%<'
```

Expected: a percentage such as `>99.93%<`. If this returns `N/A`, monitor 9 lost its public group membership and Step 2 was applied incorrectly.

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
cp "$DIR/src/index.html" "$DIR/src/index.html.bak"
printf '<!-- {{UNKNOWN_TOKEN}} -->\n' >> "$DIR/src/index.html"
if sh "$DIR/build.sh" >/dev/null 2>&1; then
    mv "$DIR/src/index.html.bak" "$DIR/src/index.html"
    fail "build.sh accepted an unsubstituted placeholder"
fi
mv "$DIR/src/index.html.bak" "$DIR/src/index.html"

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

stack_count=$(find "$REPO_ROOT/compose" -mindepth 2 -maxdepth 2 -type d | wc -l | tr -d ' ')

[ "$stack_count" -gt 0 ] || {
    echo "build: derived a stack count of zero, refusing to build" >&2
    exit 1
}

rm -rf "$DIST"
mkdir -p "$DIST"
cp -R "$SRC"/. "$DIST"/

sed -i "s/{{STACK_COUNT}}/$stack_count/g" "$DIST/index.html"

if grep -q '{{[A-Z_]*}}' "$DIST/index.html"; then
    echo "build: an unsubstituted placeholder is still in dist/index.html" >&2
    grep -o '{{[A-Z_]*}}' "$DIST/index.html" >&2
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
find compose -mindepth 2 -maxdepth 2 -type d | wc -l
grep -o 'id="stack-count">[0-9]*' compose/vps/landing/dist/index.html
```

Expected: both report 29 at the time of writing. They must agree with each other whatever the value is.

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
  - `#stack-count` - already substituted at build time, no JavaScript touches it
  - `#uptime-figure` - text content set to a string like `99.93%`
  - `#uptime-block` - the container whose `hidden` attribute is removed once a figure is available
  - `#service-dots` - a container that receives one `<span class="dot" data-status="up|down">` per public monitor

- [ ] **Step 1: Invoke the design skill**

This page exists to be looked at. Use the `design-taste-frontend` skill before writing markup, and follow its output for layout, type scale, spacing and colour. The spec's direction is the input to that skill, not a substitute for it:

- Dark theme.
- Sans-serif body copy, monospace for figures and status text.
- Indicator dots pulse subtly; hero figures count up when scrolled into view.
- Project cards lift slightly on hover.
- Mobile: sections stack, icon grid drops to two columns.

- [ ] **Step 2: Copy the architecture diagram into the stack**

```bash
cp docs/assets/topology.png compose/vps/landing/src/topology.png
ls -l compose/vps/landing/src/topology.png
```

Expected: about 218 KB. It is copied rather than referenced because the container serves only its own directory.

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
- Produces: two same-origin routes that must exist for the widget to work: `/api/badge/*` and `/api/status-page/*`, both proxied to `172.17.0.1:3001`.

The monitor list is **not** hardcoded. `status.js` reads the public monitors from the status page itself, so Task 1's curation is the single source of truth and a later change there needs no code edit.

- [ ] **Step 1: Write the Caddyfile**

Create `compose/vps/landing/Caddyfile`:

```
:80 {
	# Uptime Kuma runs on this same host with network_mode: host.
	# 172.17.0.1 is the address Pangolin's own resource target uses; the
	# architecture diagram in docs/vps/03 says 172.18.0.1 and is wrong.
	# Only these two prefixes are proxied, not all of Kuma's API.
	handle /api/badge/* {
		reverse_proxy 172.17.0.1:3001
	}

	handle /api/status-page/* {
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

  function getJSON(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error(url + " returned " + r.status);
      return r.json();
    });
  }

  // Kuma's badge endpoint returns SVG, not JSON. The value is text content,
  // e.g. ...textLength="430">99.93%</text>
  function getBadgeUptime(id) {
    return fetch("/api/badge/" + id + "/uptime/" + WINDOW_HOURS)
      .then(function (r) {
        if (!r.ok) throw new Error("badge " + id + " returned " + r.status);
        return r.text();
      })
      .then(function (svg) {
        var m = svg.match(/>([\d.]+)%</);
        return m ? parseFloat(m[1]) : null;
      });
  }

  function publicMonitorIds(page) {
    var ids = [];
    (page.publicGroupList || []).forEach(function (group) {
      (group.monitorList || []).forEach(function (m) {
        ids.push(m.id);
      });
    });
    return ids;
  }

  function renderDots(ids, heartbeats) {
    var container = document.getElementById("service-dots");
    if (!container) return;
    container.textContent = "";
    ids.forEach(function (id) {
      var beats = heartbeats[id] || [];
      var last = beats[beats.length - 1];
      var dot = document.createElement("span");
      dot.className = "dot";
      // Kuma status: 1 = up, 3 = maintenance. Anything else is not up.
      dot.dataset.status = last && (last.status === 1 || last.status === 3) ? "up" : "down";
      container.appendChild(dot);
    });
  }

  getJSON("/api/status-page/" + SLUG)
    .then(function (page) {
      var ids = publicMonitorIds(page);
      if (!ids.length) throw new Error("status page lists no public monitors");

      return Promise.all([
        Promise.all(ids.map(getBadgeUptime)),
        getJSON("/api/status-page/heartbeat/" + SLUG)
      ]).then(function (results) {
        var values = results[0].filter(function (v) {
          return typeof v === "number" && !isNaN(v);
        });
        if (!values.length) throw new Error("no badge returned a usable value");

        var mean =
          values.reduce(function (a, b) {
            return a + b;
          }, 0) / values.length;

        document.getElementById("uptime-figure").textContent = mean.toFixed(2) + "%";
        renderDots(ids, (results[1] || {}).heartbeatList || {});
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

- [ ] **Step 4: Verify the build still passes**

Run: `sh compose/vps/landing/test-build.sh`
Expected: `PASS`. `build.sh` copies `src/` wholesale, so the new files need no build change. If this fails, `build.sh` was modified when it should not have been.

- [ ] **Step 5: Commit**

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

Create `compose/vps/landing/README.md` documenting: what the stack is, that `dist/` is a build artifact, the exact build and redeploy commands from Step 5 below, why the container joins the `pangolin` network, why Kuma is at `172.17.0.1:3001`, and that the stack is stateless so `scripts/backup.sh` has nothing to cover. Mirror the tone and level of detail of `compose/proxmox-lxc-100/portfolio/README.md`.

- [ ] **Step 3: Commit and let Komodo pull**

```bash
git add compose/vps/landing/docker-compose.yml compose/vps/landing/README.md
git commit -m "feat(landing): compose stack for the VPS"
```

Then in the Komodo UI at `http://192.168.0.105:9120`, create a stack for `compose/vps/landing` on server **VPS** (uppercase - a lowercase name creates a duplicate server entry, see `docs/hosts/vps.md`), and Pull.

Pushing is required for Komodo to see the commit. Ask the user before pushing; do not push unprompted.

- [ ] **Step 4: Confirm the network is joinable before starting anything**

```bash
ssh vps 'docker network inspect pangolin --format "{{range .IPAM.Config}}{{.Subnet}} {{.Gateway}}{{end}}"'
ssh vps 'docker network inspect pangolin --format "{{range .Containers}}{{.IPv4Address}} {{end}}"'
```

Expected: subnet `172.18.0.0/16`, gateway `172.18.0.1`, and `172.18.0.10` **not** among the addresses in use. If it is taken, pick the next free address and update both the compose file and Task 6's target.

- [ ] **Step 5: Build and start**

```bash
ssh vps 'cd /etc/komodo/repos/github/compose/vps/landing && sh build.sh && docker compose up -d'
```

Expected: `build: ok, 29 compose stacks` followed by the container starting.

The build must run before `up -d`, because `dist/` is a bind mount that does not exist until the build creates it.

On every later rebuild, recreate rather than restart. The build deletes and recreates `dist/`, which breaks an existing bind mount:

```bash
ssh vps 'cd /etc/komodo/repos/github/compose/vps/landing && sh build.sh && docker rm -f landing && docker compose up -d'
```

- [ ] **Step 6: Verify the page is served**

```bash
ssh vps 'curl -s -o /dev/null -w "%{http_code}\n" http://172.18.0.10/'
ssh vps 'curl -s http://172.18.0.10/ | grep -o "id=\"stack-count\">[0-9]*"'
```

Expected: `200`, and a stack count matching `find compose -mindepth 2 -maxdepth 2 -type d | wc -l`.

- [ ] **Step 7: Verify the Kuma proxy works from inside the container's network**

```bash
ssh vps 'curl -s "http://172.18.0.10/api/badge/9/uptime/720h" | grep -oE ">[0-9.]+%<"'
ssh vps 'curl -s "http://172.18.0.10/api/status-page/statuspage1" | grep -oE "\"name\":\"[^\"]+\"" | wc -l'
```

Expected: a percentage such as `>99.93%<`, and fourteen names (thirteen monitors plus the group).

If the badge request hangs or returns a 502, the container is not in the UFW-permitted source range. Confirm with `ssh vps 'docker inspect landing --format "{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}"'` - it must report `172.18.0.10`.

- [ ] **Step 8: Review the rendered page visually**

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

Add near the top, under the `# Homelab Infrastructure` heading:

```markdown
This is the technical documentation. For the overview, see [homelabor.net](https://homelabor.net/).
```

The four Featured Project descriptions now live on the Landing Page. They are moved, not copied: duplicated facts drift, which is the same reason the stack count is derived rather than typed.

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
git add docs/index.md docs/hosts/vps.md
git commit -m "docs: point the docs homepage at homelabor.net and record the landing stack"
```

---

## Post-implementation follow-ups

Not part of this plan. Recorded so they are not lost:

- `AGENTS.md` and `CLAUDE.md` both claim 22 Docker stacks on LXC 100; there are 23.
- `docs/vps/03_Uptime_Kuma_VPS_Migration.md` shows Traefik reaching Kuma at `172.18.0.1:3001`; the configured target is `172.17.0.1:3001`.
- `pangolin` and `traefik` on the VPS run floating `latest` tags. This matters more now that an apex route depends on Pangolin's behaviour.
