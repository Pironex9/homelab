# Pedikur has a hand-written backend rather than a headless CMS

The pedicure app is thirteen tables behind a FastAPI service written for the
purpose. The obvious alternative - point Directus or a similar platform at a
database and get REST, GraphQL, an admin UI, roles, file storage and an MCP
server without writing any of them - was recommended first and rejected.

Directus would have fitted. The free tier caps at 3 user seats, 25 collections
and 5 flows, and this project needs 2, 13 and 0; the Open Innovation Grant
lifts those caps for anyone under USD 5M revenue and 50 employees. The reason
for not taking it is not the caps but their arrival: Directus moved to the BSL
in 2023 and to the MSCL with v12 on 2026-05-26, adding enforcement where there
had been an honour system. Two licence changes in three years is a poor
foundation for a tool meant to run unattended for years for someone who cannot
debug it.

PocketBase was the other candidate and failed differently: MIT and a single Go
binary, but v0.39.10 (2026-07-29) is still pre-1.0, and upstream states plainly
that it is not recommended for production-critical applications unless you
accept occasional manual migration steps.

## Consequences

Roughly two weeks of work that a platform would have given away: session auth,
the `is_admin` check, file upload, the admin screens and the MCP server. There
is also no usable interface on day one - a platform's admin UI would have
allowed data entry before the front end existed - so the build order puts
clients and Visits first, and the practitioner starts using it at the end of
phase 1 rather than at the start.

What is bought is that nothing in the stack can change its licence, its API or
its enforcement underneath a tool that someone depends on daily. If that trade
ever looks wrong, the data model is small and plain enough to lift into a
platform later; the reverse migration is the hard direction.

Design it argues from: `docs/superpowers/specs/2026-09-05-pedikur-design.md`, whose section 0
lists the rest of the document set.
