# Brand values are duplicated across surfaces; font files are not

The brand's colours and type stack appear verbatim in four places:
`compose/vps/landing/src/style.css`, `compose/vps/landing/og.html`,
`compose/proxmox-lxc-100/topology/build.js` and
`docs/stylesheets/extra.css`. `brand/tokens.css` is the source of truth as a
document that each of them copies from, not as a file any of them imports.

This looks like something to fix and is not. `build.sh` is dependency-free
POSIX shell by design and its spec commits to that; `og.html` carries a comment
stating it is self-contained on purpose, so the share card keeps rendering
identically even if `style.css` moves on; and the topology map is a separate
stack on a separate host with its own npm build and no access to the VPS
checkout. Any shared-import scheme would have to add a CSS build step to at
least two of the three, which costs more than the drift it prevents at this
number of consumers.

## The font files are the exception

The rule above stops at text. A stale hex value is visible in a diff; a stale
`.woff2` is not, so "caught in review" is not a control that exists for
binaries.

The font files therefore have exactly one committed copy, in `brand/`, and the
consumers reach it rather than duplicate it. `build.sh` already resolves the
repository root to count Compose Stacks, so copying from `brand/` costs it one
line and no dependency. `build.js` runs under Node and reads the same files to
embed them. Only the Documentation Site needs its own copy, because MkDocs
cannot pull a file from outside `docs_dir` without a plugin - and that copy is
guarded by a checksum check rather than by review.

## Consequences

Colour drift is caught in review rather than at build time. The `#0b1120` vs
`#0b0e13` and `#e8a04c` vs `#e8933f` split that prompted this work is exactly
the failure mode being accepted - so when a brand value changes, all four sites
change in the same commit, and a change touching only one of them should not
pass review.

Font drift is caught by a check, and in two of the three consumers it is
structurally impossible.
