#!/bin/bash
# Trim the memsearch SessionStart "Recent Memory" injection.
#
# The plugin injects a recap of recent daily journals into every session start.
# Stock settings (2 files x 40 lines, uncapped line length) cost ~12 KB, roughly
# 3000 tokens, every single session. This cuts it to 1 file x 20 lines with
# lines clipped at 200 chars: ~3 KB, and it is the *recent* end of the journal
# because 0.4.17 extracts with tail. Detailed lookups still work through the
# pull-based /memory-recall skill.
#
# The plugin cache path is version-pinned, so a `claude plugin update` installs
# a fresh unpatched copy. Re-run this script after every plugin update.
# Idempotent: running it twice is a no-op.
#
# Usage: ./memsearch-trim-recap.sh [--check]

set -uo pipefail

CACHE=/root/.claude/plugins/cache/memsearch-plugins/memsearch
CHECK_ONLY=0
[ "${1:-}" = "--check" ] && CHECK_ONLY=1

# Highest version directory present, so the script follows plugin upgrades.
VERSION=$(ls -1 "$CACHE" 2>/dev/null | sort -V | tail -1)
if [ -z "$VERSION" ]; then
    echo "Error: no memsearch plugin found under $CACHE" >&2
    exit 1
fi
HOOK="$CACHE/$VERSION/hooks/session-start.sh"
if [ ! -f "$HOOK" ]; then
    echo "Error: $HOOK not found" >&2
    exit 1
fi

echo "memsearch plugin version: $VERSION"

CHECK_ONLY=$CHECK_ONLY python3 - "$HOOK" <<'PY'
import os, sys

path = sys.argv[1]
check_only = os.environ.get("CHECK_ONLY") == "1"
src = open(path).read()

edits = [
    ('| tail -n "$max_lines" || true',
     '| tail -n "$max_lines" | cut -c1-200 || true'),
    ('-print 2>/dev/null | sort -r | head -2',
     '-print 2>/dev/null | sort -r | head -1'),
    ('content=$(_recent_memory_preview "$f" 40)',
     'content=$(_recent_memory_preview "$f" 20)'),
]

applied, todo = [], []
for old, new in edits:
    if new in src:
        applied.append(new)
    elif src.count(old) == 1:
        todo.append((old, new))
    else:
        # Neither form present: upstream changed the code this patch targets.
        print(f"MISMATCH: anchor not found and not already applied:\n  {old}")
        sys.exit(2)

if not todo:
    print(f"already patched ({len(applied)}/{len(edits)} edits present)")
    sys.exit(0)
if check_only:
    print(f"NOT patched: {len(todo)} edit(s) missing")
    sys.exit(1)

for old, new in todo:
    src = src.replace(old, new)
open(path, "w").write(src)
print(f"patched: {len(todo)} edit(s) applied")
PY
rc=$?

if [ "$rc" -eq 2 ]; then
    echo "The upstream hook changed shape. Re-check the injection block by hand:" >&2
    echo "  $HOOK" >&2
    exit 2
fi

if [ "$rc" -eq 0 ] && [ "$CHECK_ONLY" -eq 0 ]; then
    bash -n "$HOOK" || { echo "Error: patched hook has a syntax error" >&2; exit 1; }
    echo "syntax OK - restart Claude Code for the hook change to take effect"
fi

exit $rc
