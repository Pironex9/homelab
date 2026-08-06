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
