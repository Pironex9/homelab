# Brand values are duplicated across surfaces, not shared through a build step

The brand's colours, type stack and font files appear verbatim in four places:
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

## Consequences

Drift is caught in review rather than at build time. The `#0b1120` vs `#0b0e13`
and `#e8a04c` vs `#e8933f` split this spec fixes is exactly the failure mode
being accepted - so when a brand value changes, all four sites change in the
same commit, and a change that touches only one of them should not pass review.
