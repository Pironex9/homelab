# Landing page

Static landing page for the homelab, served by Caddy on the Hetzner VPS. No backend,
no database.

## Maintenance contract: the stack count is baked in, not live

The Compose Stack count on the landing page is baked in at build time. Nothing rebuilds
it on a schedule; that was a deliberate design choice. So **after adding or removing
any Compose Stack anywhere in this repo**, rebuild and recreate this one, or the public
number silently goes stale:

```bash
ssh vps 'cd /etc/komodo/repos/github/compose/vps/landing && sh build.sh && docker rm -f landing && docker compose up -d'
```

The uptime figure needs none of this: it is fetched live from Uptime Kuma by the
browser and cannot drift.

## The share card and the topology diagram move together

`src/og.png` is the Open Graph card, the image LinkedIn and Slack show when the link
is shared. It is generated from `og.html` in this directory, which is kept out of
`src/` on purpose: `build.sh` copies `src/` wholesale into a public web root, so the
generator would otherwise be served at `https://homelabor.net/og.html`.

The card prints two figures, **14 nodes** and **2 sites**. Both come from the same
`compose/proxmox-lxc-100/topology/nodes.yml` that generates `src/topology.png`, and
the figcaption under the diagram on the page repeats them in words. Adding or removing
a host therefore moves five things, and they must move in one go:

1. edit `nodes.yml` and `npm run build` in `compose/proxmox-lxc-100/topology/`
2. re-export `src/topology.png` (and `docs/assets/topology.png`, which is the same
   file byte for byte). Serve `compose/proxmox-lxc-100/topology/dist/` on port 8899
   and screenshot it at the size the page is already laid out for:

   ```bash
   google-chrome --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
     --run-all-compositor-stages-before-draw \
     --screenshot=compose/vps/landing/src/topology.png \
     --window-size=1280,1360 --virtual-time-budget=9000 http://127.0.0.1:8899/
   ```

   1360 is the page's own height with the node-detail panel open on `pve`, which is
   the state it loads in. A taller window pads the bottom with background.

   Then re-encode the WebP from the PNG you just wrote. `src/index.html` serves the
   diagram through a `<picture>` element with WebP first and the PNG as the fallback,
   so a stale `topology.webp` means almost every visitor sees the **old** map while
   the PNG next to it is correct - and nothing anywhere reports the mismatch:

   ```bash
   ffmpeg -y -i compose/vps/landing/src/topology.png \
     -c:v libwebp -lossless 0 -quality 92 compose/vps/landing/src/topology.webp
   ```

   Quality 92 was compared against the PNG at 2.6x magnification on the node-detail
   panel, the densest small text in the image, with no visible difference. It cuts
   268 KB to 87 KB. Lossless WebP only reaches 200 KB, which is not worth the extra
   113 KB on a diagram the page already downscales.
3. copy the interactive page across:

   ```bash
   cp compose/proxmox-lxc-100/topology/dist/index.html \
      compose/vps/landing/src/topology/index.html
   ```

   `src/topology/index.html` is the only committed build artifact in `src/`, and it
   exists because `topology/dist/` is gitignored and therefore absent from the VPS
   checkout that `build.sh` runs against. Do not edit it: it is byte-for-byte the
   output of `topology/build.js`, and any hand edit is lost on the next copy.

4. re-render the card. It must be served over HTTP, not opened from `file://`:
   `og.html` now carries `@font-face` rules, and Chrome restricts font loads
   under `file://`. The failure is silent - the card renders in a fallback face
   and looks fine. From the repo root:

   ```bash
   python3 -m http.server 8901 &
   sleep 2
   google-chrome --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
     --run-all-compositor-stages-before-draw \
     --screenshot=compose/vps/landing/src/og.png \
     --window-size=1200,630 --virtual-time-budget=9000 \
     http://127.0.0.1:8901/compose/vps/landing/og.html
   pkill -f "http.server 8901"
   ```

   The server must run from the repository root, because the font paths in
   `og.html` reach up into `brand/`.

5. update the prose counts in `src/index.html`. There are **three** of them, not
   one, and nothing links them: the `og:image:alt` meta near the top, the
   `<img alt>` on the diagram itself, and the figcaption under it. The removal of
   LXC 111 on 2026-08-23 caught the first two and missed the `alt`, which then
   told screen readers "ten LXC containers" under a map showing nine. Grep the
   file for the spelled-out number before calling it done.

`src/favicon.svg` needs none of this, but it no longer stands alone: `og.html`
inlines the same drawing, and `brand/mark-large.svg` is the header-size variant.
Change one and change all three, or the share card advertises a mark the site no
longer uses. Note when editing any of them that an XML comment may not contain two
consecutive hyphens: an invalid SVG still copies into `dist/` happily and only shows
up as a missing tab icon.

## The Content-Security-Policy forbids inline script and inline style

`Caddyfile` sends a strict CSP for everything except `/topology/`: no inline script,
no inline style, no third-party origin of any kind. The landing page can afford that
because it has none - the counter that used to sit in a `<script>` block at the
bottom of `src/index.html` was moved into `src/ui.js` for exactly this reason.

So: **do not put a `<script>` block or a `style=` attribute into `src/index.html`.**
It will build fine, pass the tests, look correct in your editor, and then be refused
by the browser in production with nothing but a console error to show for it. Add the
code to `src/ui.js` and the styling to `src/style.css` instead.

`/topology/` gets its own, weaker policy. That page is generator output copied in
wholesale, and it carries an inline `<style>`, an inline `<script>` and inline style
attributes. None of it can be fixed from this directory, so it is scoped off rather
than allowed to weaken the whole site.

It no longer fetches anything from a third party. It used to pull two faces from
Google, which was a genuine wart on a site whose whole argument is that it is
self-hosted end to end. They are now base64 `data:` URIs embedded by that stack's
`build.js` from `brand/`, so this policy's `font-src` is `data:` and nothing else.
If a future topology build goes back to linking a font, this policy blocks it, and
`test-build.sh` fails before it gets that far.

## Why HTML, CSS, JS and the diagram carry `Cache-Control: no-cache`

`no-cache` does not mean "do not cache". It means "keep a copy, but revalidate before
using it", which costs one 304 per visit and guarantees a deploy actually arrives.

The header is load-bearing, not belt-and-braces. With no `Cache-Control` at all a
browser invents its own freshness window from `Last-Modified` - commonly a tenth of
the file's age. An `index.html` that had been untouched for nine days was therefore
treated as fresh for most of a day, and a visitor who had loaded the page before the
deploy kept seeing the old one without a single request reaching the server. An
`ETag` does not save you there: it only helps once the browser decides to ask.

Fonts and `favicon.svg` are the exception and are cached hard, for 24 hours with a
7-day `stale-while-revalidate` window. They move only on a deliberate re-subset or a
mark redraw.

`topology.png` and `topology.webp` used to sit in that rule too, and it was the wrong
call. `max-age` means the browser does not contact the server **at all** for the whole
window, so the `ETag` never gets a chance to work, and `stale-while-revalidate` then
allows one further stale render after the window closes. A topology change was
invisible to a returning visitor for 24 hours guaranteed, plus one more page load any
time inside 8 days. That is exactly what happened on 2026-08-23 after LXC 111 was
removed: `/topology/` was correct immediately because it is HTML, while the diagram on
the landing page still showed the old map.

The measurement that settled it, taken the same day against the live origin on a warm
connection, is the honest cost of the fix: a conditional GET returning 304 with no body
takes **33 ms and zero bytes**, against 142 ms and 84 KB for the full WebP. One extra
round trip per visit, for a map that is the most visible element on the page and only
ever changes because the homelab changed.

## `dist/` is a build artifact

`dist/` is generated by `build.sh` from `src/` and is gitignored. It does not exist
until the first build, and the compose file bind-mounts it read-only into the
container. Never edit it by hand; edit `src/` and rebuild.

## Build and redeploy

First run on a fresh checkout (`dist/` does not exist yet, so `up -d` alone would fail
the bind mount):

```bash
cd /etc/komodo/repos/github/compose/vps/landing
sh build.sh
docker compose up -d
```

Every later rebuild must recreate rather than restart. `build.sh` deletes and
recreates `dist/`, which breaks an already-running container's bind mount:

```bash
cd /etc/komodo/repos/github/compose/vps/landing
sh build.sh
docker rm -f landing && docker compose up -d
```

## Why the container joins the `pangolin` network

`landing` joins the existing external `pangolin` bridge network at the static address
`172.18.0.10`, and publishes no host port. This is load-bearing, not cosmetic:

- UFW on the VPS permits port 3001 (Uptime Kuma) only from `172.18.0.0/16`. A container
  on its own default bridge network would get a different subnet and could not reach
  Kuma at all.
- No host port needs publishing because Pangolin fronts the site itself; the container
  only needs to be reachable from the `pangolin` network, not from the public internet
  directly.
- The address is static (`ipv4_address: 172.18.0.10`) because Pangolin addresses
  resource targets by IP. A container that picked up a new address on recreate would
  silently break the route with no obvious error on either side.

Do not "simplify" this into a plain bridge network - it will build and start fine, and
the uptime widget will silently stop working.

## Why Kuma is proxied at `172.17.0.1:3001`

Uptime Kuma runs on this same VPS host with `network_mode: host`, so from any container
on the `pangolin` bridge it is reached via the Docker bridge gateway,
`172.17.0.1:3001`, not via `172.18.0.1`. The Caddyfile documents this same point; the
architecture diagram in `docs/vps/03` gets it wrong and should not be trusted over the
Caddyfile.

## Backups

This stack is stateless: `src/`, `Caddyfile`, and `docker-compose.yml` are all in git,
and `dist/` is disposable and rebuilt on demand. There is nothing here for a backup
to cover.

## Running tests

```bash
sh test-build.sh
```
