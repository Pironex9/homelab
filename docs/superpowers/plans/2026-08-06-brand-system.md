# Brand System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Self-host the brand's typefaces on all three public surfaces so no page fetches a font from a third party, bring the Documentation Site into the brand, and write the brand down in `brand/BRAND.md`.

**Architecture:** A new top-level `brand/` directory holds the only committed copy of each subsetted font, plus the Mark and the written brand. The Landing Page's `build.sh` copies fonts from it, the topology generator reads and base64-embeds them, and the Documentation Site keeps a checksum-verified copy because MkDocs cannot read outside `docs_dir`. No new build tooling, no npm package, no CSS pipeline.

**Tech Stack:** POSIX shell (`build.sh`), Node (topology `build.js`, `node --test`), MkDocs Material `<10`, Caddy, `fonttools` + `brotli` (developer machine only, never at build time).

## Global Constraints

- Never use em dashes; use plain hyphens.
- Private LAN IPs (192.168.0.x) are never redacted. API keys are placeholders.
- **`build.sh` must gain no dependency.** It is dependency-free POSIX shell by design.
- **`src/index.html` must gain no `<script>` block and no `style=` attribute.** The CSP refuses them silently in production.
- **`compose/vps/landing/src/topology/index.html` stays exactly one file** and is never hand-edited. It is byte-for-byte the output of `topology/build.js`.
- **Text-bearing assets are never generated.** They render locally from HTML with headless Chrome.
- Fonts subset to Latin plus Latin Extended-A. Hungarian `ő` and `ű` must survive.
- Do not `git push`. Commit locally only.
- Spec: `docs/superpowers/specs/2026-08-06-brand-system-design.md`. Glossary: `CONTEXT.md`. See `docs/adr/0002-brand-values-are-duplicated-not-shared.md`.

---

## File Structure

**Created**

| Path | Responsibility |
|---|---|
| `brand/BRAND.md` | The written brand: tokens, the three deliberate exceptions, and why each exists |
| `brand/tokens.css` | The colour and typeface values, as a document to copy from |
| `brand/check-fonts.py` | Fails if a subset dropped a character the properties need |
| `brand/mark.svg` | The Mark at 16px fidelity - the current `src/favicon.svg`, unchanged |
| `brand/mark-large.svg` | The Mark redrawn for header and CV sizes |
| `brand/ibm-plex-sans-var.woff2` | Body face, variable |
| `brand/ibm-plex-mono-400.woff2` | Mono face, regular |
| `brand/ibm-plex-mono-500.woff2` | Mono face, medium |
| `brand/big-shoulders-var.woff2` | Topology map display face, variable |
| `docs/assets/fonts/*.woff2` | The Documentation Site's checksum-verified copies |
| `docs/assets/mark.svg` | The Mark for `theme.logo` and `theme.favicon` |

**Modified**

| Path | Change |
|---|---|
| `compose/vps/landing/build.sh` | One `cp` of `brand/*.woff2` into `dist/fonts/` |
| `compose/vps/landing/test-build.sh` | Assert the fonts reached `dist/fonts/` |
| `compose/vps/landing/src/style.css` | `@font-face` blocks; `--sans` and `--mono` point at Plex |
| `compose/vps/landing/Caddyfile` | `font-src 'self'` in the CSP; `*.woff2` in `@diagram` |
| `compose/vps/landing/og.html` | `@font-face`; the two stacks become the brand faces |
| `compose/vps/landing/README.md` | The `og.png` render command moves from `file://` to HTTP |
| `compose/vps/landing/src/og.png` | Re-rendered |
| `compose/vps/landing/src/topology/index.html` | Re-copied from the topology build |
| `compose/vps/landing/src/topology.png`, `.webp` | Re-exported |
| `compose/proxmox-lxc-100/topology/build.js` | Google Fonts `<link>`s become embedded `@font-face` |
| `compose/proxmox-lxc-100/topology/test/build.test.js` | Assert no third-party font origin in the output |
| `mkdocs.yml` | `primary`/`accent` custom, `font: false`, `logo`, `favicon` |
| `docs/stylesheets/extra.css` | `@font-face`, font variables, colour variables for both schemes |
| `.github/workflows/deploy.yml` | `cmp` the docs font copies against `brand/` before building |
| `CLAUDE.md`, `AGENTS.md` | A line for `brand/` |

---

### Task 1: The `brand/` directory

**Files:**
- Create: `brand/check-fonts.py`, `brand/tokens.css`, `brand/BRAND.md`, `brand/mark.svg`, `brand/mark-large.svg`, `brand/ibm-plex-sans-var.woff2`, `brand/ibm-plex-mono-400.woff2`, `brand/ibm-plex-mono-500.woff2`, `brand/big-shoulders-var.woff2`
- Modify: `CLAUDE.md`, `AGENTS.md`

**Interfaces:**
- Consumes: nothing.
- Produces: four `.woff2` files at the exact names above, consumed by Tasks 2, 4 and 5. `brand/mark.svg` and `brand/mark-large.svg`, consumed by Task 5. `brand/check-fonts.py`, run again in Task 7.

- [ ] **Step 1: Write the check before the fonts exist**

Create `brand/check-fonts.py`:

```python
#!/usr/bin/env python3
"""Fails if a subsetted font in brand/ dropped a character the properties need.

Run: python3 brand/check-fonts.py

The subsetting command lives in the plan and in BRAND.md, and it is easy to
run with a narrower --unicodes range than intended. The failure mode is
silent: the page renders, and only the affected glyph falls back to a system
face. This check turns that into an error.
"""
import pathlib
import sys

from fontTools.ttLib import TTFont

BRAND = pathlib.Path(__file__).resolve().parent

# Latin, digits, the punctuation the three surfaces actually set, and the
# Hungarian accented letters. Hungarian is the reason the subset range goes
# past Latin-1: o-double-acute and u-double-acute live in Latin Extended-A.
REQUIRED = "ABCXYZabcxyz0123456789.,:;/-()[]&%+'\"áéíóöúüőű"

EXPECTED = [
    "ibm-plex-sans-var.woff2",
    "ibm-plex-mono-400.woff2",
    "ibm-plex-mono-500.woff2",
    "big-shoulders-var.woff2",
]


def main():
    failed = False
    for name in EXPECTED:
        path = BRAND / name
        if not path.exists():
            print(f"MISSING: {name}")
            failed = True
            continue
        cmap = TTFont(path).getBestCmap()
        missing = [c for c in REQUIRED if ord(c) not in cmap]
        if missing:
            print(f"{name}: subset dropped {''.join(missing)}")
            failed = True
        else:
            print(f"ok: {name}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Install the subsetting tools and run the check to watch it fail**

```bash
python3 -m pip install --break-system-packages fonttools brotli
python3 brand/check-fonts.py
```

Expected: exit code 1, four `MISSING:` lines. `brotli` is what lets fontTools read and write `.woff2`.

These tools are for the developer machine only. Nothing in `build.sh`, `build.js` or `deploy.yml` may call them.

- [ ] **Step 3: Download the four source fonts**

```bash
mkdir -p /tmp/brandsrc && cd /tmp/brandsrc
base=https://raw.githubusercontent.com/google/fonts/main/ofl
curl -fsSL -o sans.ttf   "$base/ibmplexsans/IBMPlexSans%5Bwdth%2Cwght%5D.ttf"
curl -fsSL -o mono400.ttf "$base/ibmplexmono/IBMPlexMono-Regular.ttf"
curl -fsSL -o mono500.ttf "$base/ibmplexmono/IBMPlexMono-Medium.ttf"
curl -fsSL -o display.ttf "$base/bigshouldersdisplay/BigShouldersDisplay%5Bwght%5D.ttf"
ls -l
```

Expected: four non-empty files. All are SIL OFL. IBM Plex Mono has no variable cut in this repository, which is why 400 and 500 are fetched separately.

- [ ] **Step 4: Subset all four to woff2**

```bash
cd /root/homelab
U="U+0000-024F,U+2000-206F,U+20A0-20BF,U+2122,U+2190-2193,U+2212"
for pair in "sans:ibm-plex-sans-var" "mono400:ibm-plex-mono-400" \
            "mono500:ibm-plex-mono-500" "display:big-shoulders-var"; do
    src=${pair%%:*}; out=${pair##*:}
    pyftsubset "/tmp/brandsrc/$src.ttf" \
        --output-file="brand/$out.woff2" \
        --flavor=woff2 \
        --layout-features='kern,liga,calt,tnum,ccmp,mark,mkmk' \
        --unicodes="$U"
done
ls -l brand/*.woff2
```

`U+0100-017F` inside the `U+0000-024F` range is Latin Extended-A, which carries `ő` and `ű`. `ccmp`, `mark` and `mkmk` keep accent composition working. Variable axes are retained by default; do not pass `--instancer`.

- [ ] **Step 5: Run the check to verify it passes**

```bash
python3 brand/check-fonts.py
```

Expected: exit code 0 and four `ok:` lines.

- [ ] **Step 6: Place the Mark**

```bash
cp compose/vps/landing/src/favicon.svg brand/mark.svg
```

Then create `brand/mark-large.svg`. The 16px drawing reduces the map to three shapes for legibility at favicon size; at header and CV size it can carry more of the diagram. Draw it on a `0 0 64 64` viewBox, keeping the same four colours and the same reading - one hypervisor above, two guests below, connected:

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="homelabor.net">
  <!-- The Mark at header and CV size. brand/mark.svg is the 16px reduction of
       the same drawing and stays three shapes; this one can afford the ports
       and the second guest row. Colours are the Landing Page's own bg, accent,
       ink-2 and line-hover-card tokens, per brand/BRAND.md - deliberately not
       the topology map's node colours. Note for future edits: an XML comment
       may not contain two hyphens in a row, so the CSS custom property names
       cannot be written out here. -->
  <rect width="64" height="64" rx="12" fill="#0b0e13"/>
  <path d="M32 25v11M17 36v-5h30v5" fill="none" stroke="#3a4351" stroke-width="2.4" stroke-linecap="square"/>
  <rect x="19" y="10" width="26" height="15" rx="3" fill="#e8933f"/>
  <rect x="8" y="38" width="18" height="16" rx="3" fill="#a2adbb"/>
  <rect x="38" y="38" width="18" height="16" rx="3" fill="#a2adbb"/>
</svg>
```

- [ ] **Step 7: Write `brand/tokens.css`**

```css
/* The brand's shared values, as a document to copy from - not a file any
   surface imports. See docs/adr/0002-brand-values-are-duplicated-not-shared.md
   for why, and brand/BRAND.md for what is deliberately NOT shared.

   The font files are the exception to that ADR: brand/ holds the only
   committed copy, because a stale .woff2 is invisible in a diff. */

:root {
  /* Surfaces. The Landing Page is dark-only; the Documentation Site keeps its
     own light and dark reading surfaces and takes only the accent and header
     from here. */
  --bg:        #0b0e13;
  --surface:   #12161d;
  --surface-2: #161b23;
  --line:      #232a35;
  --line-soft: #1a2028;

  --ink:   #e9edf2;
  --ink-2: #a2adbb;
  --ink-3: #7d8898;

  --accent:      #e8933f;
  --accent-soft: #f2b273;
  --on-accent:   #14181f;

  --up:   #56c98a;
  --down: #e05a52;

  /* Typefaces. Self-hosted, same-origin, no third-party request. */
  --sans: "IBM Plex Sans", system-ui, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, monospace;
}

/* Node colours. These key node type to colour in the topology map's legend,
   so they carry information rather than decoration. They belong to that map
   and are recorded here only so nobody re-picks them. */
:root {
  --node-hypervisor: #e8a04c;
  --node-lxc:        #5cc8ff;
  --node-vm:         #b18aff;
  --node-k3s:        #6ee7a0;
}

/* There is deliberately no spacing scale. style.css writes spacing inline and
   has never had one; inventing a scale here would be adding a system, not
   recording one. */
```

- [ ] **Step 8: Write `brand/BRAND.md`**

```markdown
# Brand

One identity across the Landing Page, the topology map, the Documentation Site,
the GitHub profile and the CV. It is the person, not the infrastructure: both
site titles carry the name, and the Landing Page exists to answer a question
about a specific person.

Values live in `tokens.css`. Terms are defined in `CONTEXT.md` - Mark,
Portrait, Brand Tokens, Framed Artifact, Display Face, Self-Hosted End to End.

## Typefaces

| Role | Face | Where |
|---|---|---|
| Body | IBM Plex Sans (variable) | all properties |
| Code, figures | IBM Plex Mono (400, 500) | all properties |
| Display | Big Shoulders Display (variable) | the topology map only |

All SIL OFL. Self-hosted, same-origin, subset to Latin plus Latin Extended-A so
Hungarian survives. `brand/` holds the only committed copy; run
`python3 brand/check-fonts.py` after any re-subset.

IBM Plex Mono has no variable cut in the Google Fonts repository, so the mono
role ships as two static instances. Every mono weight in use is standard, so
nothing is lost.

## The three deliberate exceptions

Written down because each one looks like a defect and is not.

**The topology map keeps its own palette.** `#0b1120` with its own panel, line
and wire tints, plus the node colours. On that one surface colour is functional
- the legend keys node type to colour - and the Landing Page already frames the
map in a bordered plate rather than bleeding it into the page. It is a Framed
Artifact. Retinting it would flatten a distinction the design already makes.

**The topology map keeps its own display face.** Big Shoulders Display is
condensed, and the Landing Page's headings are tracked negatively for a
normal-width face. Adopting it site-wide would mean re-tuning heading CSS that
was deliberately dialled in, and it costs scannability in long documentation.

**The Mark's hypervisor is `#e8933f`, the map's is `#e8a04c`.** The Mark is a
translation of the map into the Landing Page's own tokens, not a copy of it.
Its own comment has said so since it was drawn. Do not "fix" this.

## The Documentation Site takes only part of this

Header, accent and Mark. Not the reading surfaces: the Landing Page is
dark-only by design, the Documentation Site ships a light and dark toggle that
serves long-form reading, and there is no light palette anywhere in this repo
to base one on.

## What is not here

No spacing scale. `style.css` has none and never has; a scale invented here
would be a new system presented as a consolidation. If one is wanted it is its
own piece of work, on its own evidence.
```

- [ ] **Step 9: Add `brand/` to both agent files**

In `CLAUDE.md`, under `## Key Directories`, after the `docs/` line:

```markdown
- `brand/` - the written brand: tokens, the Mark, and the only committed copy of the self-hosted fonts (`brand/BRAND.md`)
```

Add the same line to the equivalent section of `AGENTS.md`. These two are kept in sync deliberately; a new key directory in one and not the other is exactly the drift they exist to prevent.

- [ ] **Step 10: Commit**

```bash
git add brand CLAUDE.md AGENTS.md
git commit -m "feat(brand): add brand/ with the written brand, the Mark and the self-hosted fonts

Four subsetted faces, Latin plus Latin Extended-A so Hungarian survives.
brand/ holds the only committed copy: a stale woff2 is invisible in a diff,
so the copy-don't-import rule in ADR 0002 stops at text.

BRAND.md records the three deliberate exceptions - the topology map's palette
and display face, and the Mark translating the map into landing tokens - so
the next reader does not fix them."
```

---

### Task 2: The Landing Page serves the fonts

**Files:**
- Modify: `compose/vps/landing/build.sh`, `compose/vps/landing/test-build.sh`, `compose/vps/landing/src/style.css`, `compose/vps/landing/Caddyfile`

**Interfaces:**
- Consumes: `brand/*.woff2` from Task 1.
- Produces: `dist/fonts/*.woff2` served same-origin, and `--sans`/`--mono` in `style.css` resolving to the brand faces. Task 3 mirrors the same `@font-face` block into `og.html`.

- [ ] **Step 1: Write the failing test**

In `compose/vps/landing/test-build.sh`, after the existing check 1 block and before the `backup=$(mktemp)` line of check 2, insert:

```sh
# 3. The brand fonts reach dist/. src/ does not contain them - build.sh copies
# them from brand/, which is the only committed copy. A missing font does not
# fail the build or the page; it silently falls back to a system face, so the
# only way to notice is to assert it here.
for f in ibm-plex-sans-var ibm-plex-mono-400 ibm-plex-mono-500; do
    [ -s "$DIR/dist/fonts/$f.woff2" ] || fail "build.sh did not copy $f.woff2 into dist/fonts/"
done

# The CSP has default-src 'none', so a missing font-src blocks every font the
# page loads - including its own. This is silent in production: the page
# renders in a fallback face and looks fine.
grep -q "font-src 'self'" "$DIR/Caddyfile" || fail "Caddyfile CSP has no font-src, fonts will be blocked"
```

- [ ] **Step 2: Run it to watch it fail**

```bash
sh compose/vps/landing/test-build.sh
```

Expected: `FAIL: build.sh did not copy ibm-plex-sans-var.woff2 into dist/fonts/`

- [ ] **Step 3: Teach `build.sh` to copy the fonts**

In `compose/vps/landing/build.sh`, immediately after the `cp -R "$SRC"/. "$DIST"/` line:

```sh
# The brand fonts are not in src/, because brand/ holds the only committed
# copy of each - see docs/adr/0002-brand-values-are-duplicated-not-shared.md.
# REPO_ROOT is already resolved above to count Compose Stacks, so this costs
# no dependency. Big Shoulders is not copied: it belongs to the topology map,
# which embeds its own.
mkdir -p "$DIST/fonts"
for f in ibm-plex-sans-var ibm-plex-mono-400 ibm-plex-mono-500; do
    [ -f "$REPO_ROOT/brand/$f.woff2" ] || {
        echo "build: brand/$f.woff2 is missing" >&2
        exit 1
    }
    cp "$REPO_ROOT/brand/$f.woff2" "$DIST/fonts/"
done
```

- [ ] **Step 4: Add `font-src` and the woff2 cache rule to the Caddyfile**

In `compose/vps/landing/Caddyfile`, in the `handle { }` block, replace the CSP header line with:

```
		header Content-Security-Policy "default-src 'none'; img-src 'self'; style-src 'self'; script-src 'self'; font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'"
```

and replace the `@diagram` matcher line with:

```
		# Fonts join the diagram rule rather than the revalidate one: they
		# change only on a deliberate re-subset, and without a rule they would
		# ship with no Cache-Control at all - the failure the comment below
		# describes.
		@diagram path *.png *.webp *.svg *.woff2
```

- [ ] **Step 5: Declare the faces in `style.css`**

At the top of `compose/vps/landing/src/style.css`, before the `:root` block:

```css
/* Self-hosted, same-origin. The CSP is default-src 'none' with font-src
   'self', so a third-party font would be refused - which is the point: this
   site's argument is that it is self-hosted end to end.

   Values copied from brand/tokens.css; see brand/BRAND.md. The files are
   placed into dist/fonts/ by build.sh from brand/, which holds the only
   committed copy. */
@font-face {
  font-family: "IBM Plex Sans";
  src: url("fonts/ibm-plex-sans-var.woff2") format("woff2-variations");
  font-weight: 100 700;
  font-display: swap;
}
@font-face {
  font-family: "IBM Plex Mono";
  src: url("fonts/ibm-plex-mono-400.woff2") format("woff2");
  font-weight: 400;
  font-display: swap;
}
@font-face {
  font-family: "IBM Plex Mono";
  src: url("fonts/ibm-plex-mono-500.woff2") format("woff2");
  font-weight: 500;
  font-display: swap;
}
```

Then replace the `--sans` and `--mono` declarations inside `:root` (currently at lines 52 and 54) with:

```css
  --sans: "IBM Plex Sans", system-ui, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, monospace;
```

The `font-weight: 100 700` range on the variable face is what makes `font-weight: 620`, `570` and `550` elsewhere in this file resolve exactly rather than snapping. They previously resolved only on macOS and Windows, whose system faces are variable, and snapped on Linux.

- [ ] **Step 6: Run the test to verify it passes**

```bash
sh compose/vps/landing/test-build.sh
```

Expected: exits 0, no `FAIL:` line.

- [ ] **Step 7: Look at the result before believing it**

```bash
cd /root/homelab && python3 -m http.server 8899 --directory compose/vps/landing/dist &
sleep 1
google-chrome --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
  --run-all-compositor-stages-before-draw \
  --screenshot=/tmp/landing-after.png \
  --window-size=1280,1600 --virtual-time-budget=9000 http://127.0.0.1:8899/
kill %1
```

Open `/tmp/landing-after.png` and confirm the page is set in IBM Plex Sans, that headings do not look broken at the odd weights, and that nothing has reflowed badly. The typeface changes on every platform, so this is a real visual change and not a formality.

- [ ] **Step 8: Commit**

```bash
git add compose/vps/landing/build.sh compose/vps/landing/test-build.sh \
        compose/vps/landing/src/style.css compose/vps/landing/Caddyfile
git commit -m "feat(landing): self-host IBM Plex Sans and Mono

build.sh copies the faces from brand/, which holds the only committed copy.
The CSP had default-src 'none' and no font-src, so it would have blocked the
page's own fonts; test-build.sh now asserts both the copy and the directive,
because either failing is silent - the page just renders in a fallback face.

woff2 joins the @diagram cache rule rather than @revalidate: a font changes
only on a deliberate re-subset, and matching neither rule would have shipped
it with no Cache-Control at all."
```

---

### Task 3: The share card renders over HTTP

**Files:**
- Modify: `compose/vps/landing/og.html`, `compose/vps/landing/README.md`
- Regenerate: `compose/vps/landing/src/og.png`

**Interfaces:**
- Consumes: `brand/*.woff2` from Task 1, at the relative path `../../../brand/`.
- Produces: a regenerated `src/og.png` set in the brand faces.

- [ ] **Step 1: Declare the faces in `og.html`**

In `compose/vps/landing/og.html`, inside the existing `<style>` block and above the `:root` rule, add:

```css
    /* Rendered over HTTP, not file:// - see the command in README.md. Chrome
       restricts font loads under file://, and the failure is silent: the card
       renders in a fallback face and looks perfectly fine while being wrong.
       This file had no subresource at all before these three rules, which is
       why the old command needed no server.

       Paths are relative to the repository root, which is what the render
       command serves. */
    @font-face {
      font-family: "IBM Plex Sans";
      src: url("../../../brand/ibm-plex-sans-var.woff2") format("woff2-variations");
      font-weight: 100 700;
    }
    @font-face {
      font-family: "IBM Plex Mono";
      src: url("../../../brand/ibm-plex-mono-400.woff2") format("woff2");
      font-weight: 400;
    }
    @font-face {
      font-family: "IBM Plex Mono";
      src: url("../../../brand/ibm-plex-mono-500.woff2") format("woff2");
      font-weight: 500;
    }
```

Then replace the `--sans` and `--mono` declarations (currently lines 37 and 38) with:

```css
    --sans: "IBM Plex Sans", system-ui, sans-serif;
    --mono: "IBM Plex Mono", ui-monospace, monospace;
```

The old stack put `"Liberation Sans"` and `"DejaVu Sans Mono"` first on purpose, so this Linux render machine produced a deterministic card. Self-hosting the faces makes that unnecessary and, for the first time, sets the card in the same typeface as the page it advertises.

- [ ] **Step 2: Re-render the card over HTTP**

```bash
cd /root/homelab
python3 -m http.server 8901 &
sleep 1
google-chrome --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
  --run-all-compositor-stages-before-draw \
  --screenshot=compose/vps/landing/src/og.png \
  --window-size=1200,630 --virtual-time-budget=9000 \
  http://127.0.0.1:8901/compose/vps/landing/og.html
kill %1
```

- [ ] **Step 3: Verify the card actually picked up the face**

Open `compose/vps/landing/src/og.png` and compare it against the previous version in git:

```bash
git stash && cp compose/vps/landing/src/og.png /tmp/og-old.png && git stash pop
```

Expected: the two differ visibly in typeface. If they look identical, the font did not load and the render silently fell back - check that the server was still running and that the relative path resolves.

- [ ] **Step 4: Update the documented procedure in `README.md`**

In `compose/vps/landing/README.md`, replace the `og.png` render command in step 4 with:

````markdown
4. re-render the card. It must be served over HTTP, not opened from `file://`:
   `og.html` now carries `@font-face` rules, and Chrome restricts font loads
   under `file://`. The failure is silent - the card renders in a fallback face
   and looks fine. From the repo root:

   ```bash
   python3 -m http.server 8901 &
   google-chrome --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
     --run-all-compositor-stages-before-draw \
     --screenshot=compose/vps/landing/src/og.png \
     --window-size=1200,630 --virtual-time-budget=9000 \
     http://127.0.0.1:8901/compose/vps/landing/og.html
   kill %1
   ```

   The server must run from the repository root, because the font paths in
   `og.html` reach up into `brand/`.
````

Also update the comment block at the top of `og.html` itself, which repeats the old `file://` command, so the two do not disagree.

- [ ] **Step 5: Commit**

```bash
git add compose/vps/landing/og.html compose/vps/landing/README.md \
        compose/vps/landing/src/og.png
git commit -m "feat(landing): set the share card in the brand faces

og.html had no subresource at all, which is why it screenshotted straight
from file:// with no flags. An @font-face is its first, and Chrome restricts
font loads under file:// - silently, so the card would have rendered in a
fallback face and looked fine. The documented command now serves the repo
root over HTTP.

The old Liberation Sans / DejaVu stack was deliberate: it made this Linux
render machine deterministic. Self-hosted faces make it unnecessary, and the
card and the page are now the same typeface for the first time."
```

---

### Task 4: The topology map embeds its fonts

**Files:**
- Modify: `compose/proxmox-lxc-100/topology/build.js`, `compose/proxmox-lxc-100/topology/test/build.test.js`
- Regenerate: `compose/vps/landing/src/topology/index.html`, `compose/vps/landing/src/topology.png`, `compose/vps/landing/src/topology.webp`

**Interfaces:**
- Consumes: `brand/big-shoulders-var.woff2`, `brand/ibm-plex-mono-400.woff2`, `brand/ibm-plex-mono-500.woff2` from Task 1.
- Produces: a `dist/index.html` with no third-party origin, still a single self-contained file.

- [ ] **Step 1: Write the failing test**

In `compose/proxmox-lxc-100/topology/test/build.test.js`, add:

```javascript
test('the generated page fetches nothing from a third party', () => {
  const distDir = fs.mkdtempSync(path.join(os.tmpdir(), 'topology-'));
  build({ distDir });
  const html = fs.readFileSync(path.join(distDir, 'index.html'), 'utf8');

  // The landing page's whole argument is that it is self-hosted end to end,
  // and this map is served under that domain. A Google Fonts link here hands
  // the visitor to a third party on the one page that claims otherwise.
  assert.ok(!html.includes('fonts.googleapis.com'), 'output links to Google Fonts');
  assert.ok(!html.includes('fonts.gstatic.com'), 'output preconnects to Google Fonts');
  assert.match(html, /data:font\/woff2;base64,/, 'output has no embedded font');

  fs.rmSync(distDir, { recursive: true, force: true });
});
```

This follows the file's existing pattern: it builds into a temp directory via
the exported `build({ distDir })` rather than reading the committed `dist/`.
`test`, `assert`, `fs`, `os`, `path` and `build` are all already imported at
the top of the file; add no new import lines.

- [ ] **Step 2: Run it to watch it fail**

```bash
cd compose/proxmox-lxc-100/topology && npm test
```

Expected: FAIL, `output links to Google Fonts`.

- [ ] **Step 3: Embed the fonts in `build.js`**

`build.js` is an ES module and already imports `fs`, `path` and
`fileURLToPath`, and defines `__dirname` at line 6. Add no import lines. After
the existing `DEFAULT_DIST_DIR` declaration, insert:

```javascript
// brand/ holds the only committed copy of each face. Embedding them as data:
// URIs rather than shipping files next to the HTML is deliberate and load
// bearing twice over:
//
//   1. compose/vps/landing/README.md defines the transfer of this page as a
//      single file copy, and states that src/topology/index.html is the only
//      committed build artifact in src/. Font files beside it would make that
//      a directory copy and commit binaries into a public web root.
//   2. dist/ is also served standalone on port 3009, and that is what
//      topology.png is screenshotted from. A font that resolved on the live
//      page but not there would render the screenshot in a different face
//      than the page, with nothing reporting the mismatch.
//
// The cost is roughly 130 KB of base64 in this file. That is the price of
// staying one file.
const BRAND = path.join(__dirname, '..', '..', '..', 'brand');

function embed(file) {
  const b64 = fs.readFileSync(path.join(BRAND, file)).toString('base64');
  return `data:font/woff2;base64,${b64}`;
}

const FONT_FACES = `
@font-face {
  font-family: "Big Shoulders Display";
  src: url(${embed('big-shoulders-var.woff2')}) format("woff2-variations");
  font-weight: 100 900;
}
@font-face {
  font-family: "IBM Plex Mono";
  src: url(${embed('ibm-plex-mono-400.woff2')}) format("woff2");
  font-weight: 400;
}
@font-face {
  font-family: "IBM Plex Mono";
  src: url(${embed('ibm-plex-mono-500.woff2')}) format("woff2");
  font-weight: 500;
}
`;
```

Then delete the three Google Fonts lines from the template (currently lines 79-81):

```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@500;700;800&family=IBM+Plex+Mono:wght@400;500;600&display=swap" rel="stylesheet">
```

and insert `${FONT_FACES}` as the first thing inside the existing `<style>` block.

The old request asked Google for IBM Plex Mono 600, which this page never uses - only 400 and 500 appear in its CSS - so 600 is not embedded.

- [ ] **Step 4: Build and run the test to verify it passes**

```bash
cd compose/proxmox-lxc-100/topology && npm run build && npm test
```

Expected: PASS. Then confirm the size is what was predicted:

```bash
ls -l dist/index.html
```

Expected: roughly 130-170 KB, up from about 19 KB.

- [ ] **Step 5: Copy the page across and re-export the images**

```bash
cd /root/homelab
cp compose/proxmox-lxc-100/topology/dist/index.html \
   compose/vps/landing/src/topology/index.html

python3 -m http.server 8899 --directory compose/proxmox-lxc-100/topology/dist &
sleep 1
google-chrome --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
  --run-all-compositor-stages-before-draw \
  --screenshot=compose/vps/landing/src/topology.png \
  --window-size=1280,1360 --virtual-time-budget=9000 http://127.0.0.1:8899/
kill %1

ffmpeg -y -i compose/vps/landing/src/topology.png \
  -c:v libwebp -lossless 0 -quality 92 compose/vps/landing/src/topology.webp

cp compose/vps/landing/src/topology.png docs/assets/topology.png
```

`docs/assets/topology.png` is the same file byte for byte and must move with it, per the README. Confirm the screenshot is set in Big Shoulders and IBM Plex Mono, not a fallback - this is exactly the mismatch the embedding exists to prevent.

- [ ] **Step 6: Verify the copy stayed one file**

```bash
find compose/vps/landing/src/topology -type f
```

Expected: exactly one line, `compose/vps/landing/src/topology/index.html`.

- [ ] **Step 7: Commit**

```bash
git add compose/proxmox-lxc-100/topology/build.js \
        compose/proxmox-lxc-100/topology/test/build.test.js \
        compose/vps/landing/src/topology/index.html \
        compose/vps/landing/src/topology.png \
        compose/vps/landing/src/topology.webp \
        docs/assets/topology.png
git commit -m "feat(topology): embed the fonts, drop the Google Fonts requests

The README already called these requests a wart against the self-hosted
end-to-end claim. They are now data: URIs read from brand/ at build time.

Embedding rather than shipping files keeps the two invariants the README
documents: the transfer stays a one-line cp with src/topology/index.html as
the only committed build artifact in src/, and the port-3009 standalone
render that topology.png comes from resolves the same faces as the live
page. The file grows to about 150 KB, which is the price of staying one file.

Plex Mono 600 was requested from Google and never used, so it is not embedded."
```

---

### Task 5: The Documentation Site joins the brand

**Files:**
- Create: `docs/assets/fonts/ibm-plex-sans-var.woff2`, `docs/assets/fonts/ibm-plex-mono-400.woff2`, `docs/assets/fonts/ibm-plex-mono-500.woff2`, `docs/assets/mark.svg`
- Modify: `mkdocs.yml`, `docs/stylesheets/extra.css`, `.github/workflows/deploy.yml`

**Interfaces:**
- Consumes: `brand/*.woff2` and `brand/mark-large.svg` from Task 1.
- Produces: a Documentation Site that fetches nothing from Google and carries the Mark.

- [ ] **Step 1: Write the failing check**

In `.github/workflows/deploy.yml`, in the `build` job, between the `Install MkDocs + Material` step and the `Build site` step:

```yaml
      # brand/ holds the only committed copy of each font, but MkDocs cannot
      # read outside docs_dir without a plugin, so this one copy has to exist.
      # A stale .woff2 is invisible in a diff, so review is not a control here
      # - this is. See docs/adr/0002-brand-values-are-duplicated-not-shared.md
      - name: Verify the docs font copies match brand/
        run: |
          for f in ibm-plex-sans-var ibm-plex-mono-400 ibm-plex-mono-500; do
            cmp "brand/$f.woff2" "docs/assets/fonts/$f.woff2" \
              || { echo "docs/assets/fonts/$f.woff2 differs from brand/$f.woff2"; exit 1; }
          done
```

- [ ] **Step 2: Run the same comparison locally to watch it fail**

```bash
cd /root/homelab
for f in ibm-plex-sans-var ibm-plex-mono-400 ibm-plex-mono-500; do
  cmp "brand/$f.woff2" "docs/assets/fonts/$f.woff2" \
    || echo "MISMATCH OR MISSING: $f"
done
```

Expected: three `MISMATCH OR MISSING` lines, because `docs/assets/fonts/` does not exist yet.

- [ ] **Step 3: Place the fonts and the Mark**

```bash
cd /root/homelab
mkdir -p docs/assets/fonts
for f in ibm-plex-sans-var ibm-plex-mono-400 ibm-plex-mono-500; do
  cp "brand/$f.woff2" "docs/assets/fonts/$f.woff2"
done
cp brand/mark-large.svg docs/assets/mark.svg
```

Big Shoulders is not copied. It belongs to the topology map, which embeds its own.

- [ ] **Step 4: Run the comparison again to verify it passes**

```bash
cd /root/homelab
for f in ibm-plex-sans-var ibm-plex-mono-400 ibm-plex-mono-500; do
  cmp "brand/$f.woff2" "docs/assets/fonts/$f.woff2" && echo "ok: $f"
done
```

Expected: three `ok:` lines and no output from `cmp`.

- [ ] **Step 5: Point the theme at custom colours, the Mark, and no Google Fonts**

In `mkdocs.yml`, replace the `theme:` block's `palette:` section and add three keys:

```yaml
theme:
  name: material
  logo: assets/mark.svg
  favicon: assets/mark.svg
  # Stops Material fetching Roboto from Google Fonts. The faces are then set
  # through --md-text-font and --md-code-font in stylesheets/extra.css. This
  # site links from a landing page whose argument is that it is self-hosted
  # end to end; a Google Fonts request here contradicts it directly.
  font: false
  palette:
    - scheme: default
      primary: custom
      accent: custom
      toggle:
        icon: material/weather-night
        name: Switch to dark mode
    - scheme: slate
      primary: custom
      accent: custom
      toggle:
        icon: material/weather-sunny
        name: Switch to light mode
```

Leave `features:`, `icon:` and everything below unchanged.

- [ ] **Step 6: Set the faces and colours in `extra.css`**

Append to `docs/stylesheets/extra.css`, keeping the existing five-line code-block fix at the top:

```css
/* Brand faces, self-hosted. Values copied from brand/tokens.css; see
   brand/BRAND.md. The files in assets/fonts/ are checksum-verified against
   brand/ by .github/workflows/deploy.yml.

   Material requires the faces be set through its own variables rather than
   font-family, which would disable its system fallback. */
@font-face {
  font-family: "IBM Plex Sans";
  src: url("../assets/fonts/ibm-plex-sans-var.woff2") format("woff2-variations");
  font-weight: 100 700;
  font-display: swap;
}
@font-face {
  font-family: "IBM Plex Mono";
  src: url("../assets/fonts/ibm-plex-mono-400.woff2") format("woff2");
  font-weight: 400;
  font-display: swap;
}
@font-face {
  font-family: "IBM Plex Mono";
  src: url("../assets/fonts/ibm-plex-mono-500.woff2") format("woff2");
  font-weight: 500;
  font-display: swap;
}

:root {
  --md-text-font: "IBM Plex Sans";
  --md-code-font: "IBM Plex Mono";
}

/* The brand reaches the header and the accent only. The reading surfaces stay
   Material's own, in both schemes: this site is built for long-form reading,
   the landing page is dark-only by design, and there is no light palette in
   this repo to base one on. See brand/BRAND.md. */
[data-md-color-scheme="default"] {
  --md-primary-fg-color:        #0b0e13;
  --md-primary-fg-color--light: #12161d;
  --md-primary-fg-color--dark:  #05070a;
  --md-accent-fg-color:         #b96a1d;
}

[data-md-color-scheme="slate"] {
  --md-primary-fg-color:        #0b0e13;
  --md-primary-fg-color--light: #12161d;
  --md-primary-fg-color--dark:  #05070a;
  --md-accent-fg-color:         #e8933f;
}
```

The light scheme uses a darker accent than `#e8933f`, because the brand orange is tuned for a near-black background and does not reach 4.5:1 against white for link text. The header bar stays the brand's dark surface in both schemes, which is where the two sites visibly become one.

- [ ] **Step 7: Build and check the result**

```bash
cd /root/homelab
python3 -m pip install --break-system-packages "mkdocs-material<10"
mkdocs build
grep -r "fonts.googleapis.com\|fonts.gstatic.com" site/ && echo "STILL FETCHING GOOGLE FONTS" || echo "ok: no Google Fonts"
```

Expected: `ok: no Google Fonts`, and a clean build with no warnings about the missing `assets/mark.svg`.

- [ ] **Step 8: Look at both schemes**

```bash
cd /root/homelab && python3 -m http.server 8902 --directory site &
sleep 1
google-chrome --headless=new --disable-gpu --no-sandbox --hide-scrollbars \
  --run-all-compositor-stages-before-draw \
  --screenshot=/tmp/docs-light.png \
  --window-size=1280,1400 --virtual-time-budget=9000 http://127.0.0.1:8902/
kill %1
```

Open `/tmp/docs-light.png`. Confirm the header is the brand's dark surface, the Mark is in it, body text is IBM Plex Sans and comfortable to read, and links are legible against white. Then toggle to dark mode in a real browser and check the same.

- [ ] **Step 9: Commit**

```bash
git add mkdocs.yml docs/stylesheets/extra.css docs/assets/fonts docs/assets/mark.svg \
        .github/workflows/deploy.yml
git commit -m "feat(docs): bring the documentation site into the brand

theme.font was never set, so Material was fetching Roboto from Google Fonts -
the same defect the landing README calls a wart about the topology map, on
the site the landing links to first. font: false plus self-hosted faces.

The brand takes the header, the accent and the Mark; the reading surfaces
stay Material's own in both schemes, because this site is built for long-form
reading and there is no light palette in the repo to base one on. The light
scheme darkens the accent, which does not reach 4.5:1 against white.

deploy.yml now cmp's the font copies against brand/ before building: this is
the one surface that needs its own copy, and a stale woff2 is invisible in a
diff."
```

---

### Task 6: The Portrait

**Files:**
- Create: `brand/portrait-cv.png`, `brand/portrait-avatar.png`, `brand/portrait-docs.png`

**Interfaces:**
- Consumes: `brand/tokens.css` from Task 1 for the background colour.
- Produces: three crops, used outside this repository (CV, GitHub profile) and on the Documentation Site.

This is the only task that spends a credit.

- [ ] **Step 1: Choose the source photograph**

Pick one real photograph: face clearly visible, in focus, no heavy shadow across the features. It does not need a clean background - that is what the next step removes. Save it as `/tmp/portrait-src.jpg`.

No face is generated. What varies across the CV header, the GitHub avatar and the Documentation Site is background and crop, not the face, and a generated face on an identity document always needs explaining.

- [ ] **Step 2: Check the cost before spending it**

```bash
higgsfield account status
```

Note the balance. `image_background_remover` takes no prompt, so `generate cost` cannot price it without an upload; expect roughly one credit.

- [ ] **Step 3: Remove the background**

```bash
cd /tmp
higgsfield generate create image_background_remover --image ./portrait-src.jpg --wait --json
```

Download the returned URL to `/tmp/portrait-cut.png`. Then confirm the spend was what was expected:

```bash
higgsfield account status
```

- [ ] **Step 4: Composite the three crops locally**

```bash
cd /root/homelab
# 1:1 avatar, 512px, for GitHub and the docs authorship slot.
ffmpeg -y -i /tmp/portrait-cut.png -vf "scale=512:-1,pad=512:512:(ow-iw)/2:(oh-ih)/2:color=0x0b0e13" \
  brand/portrait-avatar.png
cp brand/portrait-avatar.png brand/portrait-docs.png
# 4:5 portrait for a CV header.
ffmpeg -y -i /tmp/portrait-cut.png -vf "scale=640:-1,pad=640:800:(ow-iw)/2:(oh-ih)/2:color=0x0b0e13" \
  brand/portrait-cv.png
```

`0x0b0e13` is `--bg` from `brand/tokens.css`. Open all three and adjust the `scale` and `pad` offsets until the crop sits well - the framing is a judgement call, not a formula.

- [ ] **Step 5: Commit**

```bash
git add brand/portrait-cv.png brand/portrait-avatar.png brand/portrait-docs.png
git commit -m "feat(brand): add the portrait in three crops

A real photograph with its background removed and the brand background
composited behind it. What differs between the CV header, the GitHub avatar
and the docs authorship slot is background and crop, not the face, so no face
is generated - which is also the defensible choice on a CV.

The one credit spent in this whole piece of work."
```

---

### Task 7: Verify the claim across all three properties

**Files:**
- None modified. This task proves the work or finds what is left.

**Interfaces:**
- Consumes: everything from Tasks 1-5.
- Produces: nothing. It is the gate.

- [ ] **Step 1: Re-run every check**

```bash
cd /root/homelab
python3 brand/check-fonts.py
sh compose/vps/landing/test-build.sh
( cd compose/proxmox-lxc-100/topology && npm test )
mkdocs build
for f in ibm-plex-sans-var ibm-plex-mono-400 ibm-plex-mono-500; do
  cmp "brand/$f.woff2" "docs/assets/fonts/$f.woff2" || echo "MISMATCH: $f"
done
```

Expected: all pass, no `MISMATCH` line.

- [ ] **Step 2: Prove no page fetches a font from a third party**

```bash
cd /root/homelab
grep -rn "fonts.googleapis.com\|fonts.gstatic.com" \
  compose/vps/landing/src compose/vps/landing/og.html \
  compose/proxmox-lxc-100/topology/build.js \
  compose/proxmox-lxc-100/topology/dist site \
  && echo "FOUND A THIRD-PARTY FONT REQUEST" || echo "ok: none"
```

Expected: `ok: none`.

Then confirm it in a browser, which is the only check that covers what a
visitor actually experiences. Load `https://homelabor.net/`,
`https://homelabor.net/topology/` and `https://docs.homelabor.net/` with the
network panel open, filtered to third-party requests. Expected: nothing from
`fonts.googleapis.com` or `fonts.gstatic.com` on any of the three.

- [ ] **Step 3: Confirm every asset carries a Cache-Control header**

```bash
curl -sI https://homelabor.net/fonts/ibm-plex-sans-var.woff2 | grep -i cache-control
```

Expected: `cache-control: public, max-age=86400, stale-while-revalidate=604800`. An empty result means `.woff2` did not reach the `@diagram` matcher and the font ships with no freshness policy at all.

- [ ] **Step 4: Compare the Landing Page against its previous appearance**

Put the screenshot taken in Task 2 Step 7 beside the live site at
`https://homelabor.net/`, which is still serving the pre-change build until
someone pushes. For the card, recover the previous version by its own commit
rather than by counting back from `HEAD`:

```bash
git show "$(git log -1 --format=%H --skip=1 -- compose/vps/landing/src/og.png)":compose/vps/landing/src/og.png \
  > /tmp/og-before.png
```

The typeface changed on every platform, so confirm the result is wanted rather
than merely different. If a heading now looks too light, the fix is the weight
value in `style.css`, not the font.

- [ ] **Step 5: Commit anything the verification changed**

If nothing changed, there is nothing to commit and the work is done. If a weight or a crop was adjusted:

```bash
git add -A
git commit -m "fix(brand): adjust after the cross-property verification pass"
```

---

## What this plan does not do

- **No spacing scale.** `style.css` has none; inventing one here would add a system rather than record one. Its own piece of work, on its own evidence.
- **No repalette of the topology map.** Its colours key node type in a legend, and the Landing Page frames it as a separate artifact. See `brand/BRAND.md`.
- **No new Mark.** The existing `favicon.svg` is hand-drawn, documented, and reads at 16px. Only a larger variant is added.
- **No change to Enci's art portfolio.** That site is hers.
- **No `git push`.** Deploying the Documentation Site is a push to `main`, so that is the owner's call, not this plan's.
