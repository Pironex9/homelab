# Pedikur stores health data unencrypted at rest, deliberately

The pedicure app holds client foot conditions, which are GDPR Article 9 health
data. The SQLite file and the photographs sit unencrypted on LXC 100's disk.
This will look like an oversight in any later review, so it is written down as
a decision.

Encrypting the database with SQLCipher would put the key in the Komodo Stack
Environment - on the same host as the data it protects. Anyone who reaches the
host reaches both. At-rest encryption defends against a stolen disk and against
a backup that escapes; it does not defend against the compromise of the machine
running the application, which is the realistic threat here. The cost side is
concrete: `sqlite3` on the command line stops working, and with it `.backup`,
`PRAGMA integrity_check`, the restore test and every ordinary diagnostic.

The two risks encryption would actually address are already covered elsewhere.
Off-host backups go through restic, which encrypts by definition. Host access
is controlled at the Proxmox and network layer, and full-disk encryption for
the guest is a hypervisor decision affecting all its stacks, not something this
application should reach for on its own.

## Consequences

A compromise of LXC 100 is a health-data breach, and should be treated as one
rather than as a service outage. That is the accepted risk, stated rather than
discovered.

Two related boundaries follow from the same reasoning. Erasure cannot reach the
seven nightly database copies or the restic snapshots; they age out on their
own schedule and are never restored selectively, so restoring an old backup
means running the erasure again. And the app's own login demands a password
even behind Pangolin SSO, because a single proxy misconfiguration must not be
the only thing between the internet and this data.

Design it argues from: `docs/superpowers/specs/2026-09-05-pedikur-design.md`, whose section 0
lists the rest of the document set.
