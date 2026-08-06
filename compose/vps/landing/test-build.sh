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

# 3. The brand fonts reach dist/. src/ does not contain them - build.sh copies
# them from brand/, which is the only committed copy. A missing font does not
# fail the build or the page; it silently falls back to a system face, so the
# only way to notice is to assert it here.
for f in ibm-plex-sans-var ibm-plex-mono-400 ibm-plex-mono-500; do
    [ -s "$DIR/dist/fonts/$f.woff2" ] || fail "build.sh did not copy $f.woff2 into dist/fonts/"
done

# Scope the font-src checks to their own handle block rather than grepping
# the whole file. A file-scoped grep cannot tell the two CSP blocks apart: if
# the landing and /topology/* directives were ever swapped, both strings
# would still be present somewhere in the file and a bare grep would still
# pass while both surfaces actually render in a fallback face. Extract each
# block with awk (no dependency added, same as build.sh's own tool budget)
# and grep only inside it.
landing_block=$(awk '/^\thandle \{$/,/^\t\}$/' "$DIR/Caddyfile")
topology_block=$(awk '/^\thandle \/topology\/\* \{$/,/^\t\}$/' "$DIR/Caddyfile")
[ -n "$landing_block" ] || fail "could not find the bare 'handle {' block in Caddyfile"
[ -n "$topology_block" ] || fail "could not find the 'handle /topology/*' block in Caddyfile"

# The CSP has default-src 'none', so a missing font-src blocks every font the
# page loads - including its own. This is silent in production: the page
# renders in a fallback face and looks fine.
echo "$landing_block" | grep -q "font-src 'self'" \
    || fail "landing CSP has no font-src 'self', fonts will be blocked"

# The /topology/ route has its own weaker CSP. The map's fonts are data: URIs
# embedded by topology/build.js, so that policy needs font-src data: - and
# must no longer name Google, which nothing requests any more. npm test in the
# topology stack cannot catch this: it reads the HTML, not the policy serving
# it.
echo "$topology_block" | grep -q "font-src data:" \
    || fail "topology CSP has no font-src data:, the embedded fonts will be blocked"
grep -q "fonts.gstatic.com\|fonts.googleapis.com" "$DIR/Caddyfile" && fail "Caddyfile still allows Google Fonts"

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
