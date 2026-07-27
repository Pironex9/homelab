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
