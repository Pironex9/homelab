# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

The primary visitor is someone who already has the owner's name and is looking him up: a
hiring manager or technical interviewer checking a claim, a colleague or acquaintance
following a reference, a fellow self-hoster arriving from the documentation or GitHub.
They arrive with a question about a specific person, not with a problem they want a
product to solve, and they are evaluating rather than shopping.

The site is no longer an active job-search asset. The owner accepted a position on
2026-07-27; the surface has since become a durable professional calling card with no
campaign behind it and no conversion deadline.

## Product Purpose

homelabor.net is the public front door to a self-hosted homelab that is run with
production discipline. Its job is to let a visitor establish, quickly and without taking
anything on trust, that the infrastructure behind it is real, current, and operated
rather than merely assembled.

Two outcomes both count as success, and neither outranks the other:

1. the visitor goes on to read the documentation at docs.homelabor.net;
2. the visitor gets in touch.

## Positioning

The differentiator is verifiability, not scale. Competing homelab pages describe a setup;
this one exposes the machinery that would expose a lie: the topology map is generated
from the same `nodes.yml` the infrastructure is described by, the uptime figure is
fetched live from the owner's own Uptime Kuma instance, the stack count is baked from the
actual repository, and the full build history is published as documentation. A page that
merely claimed the same things could not truthfully copy any of it.

The second, quieter claim is that the whole thing is self-hosted end to end, including
the public path onto it: no third-party tunnel provider, no forwarded ports on the home
router.

## Operating Context

The visitor is on a desktop or phone, usually for well under a minute, often in the
middle of checking several sources about the same person. They may arrive from LinkedIn,
from a GitHub profile, from a search on the owner's name, or from a shared link whose
preview card is the first thing they see. Nothing about the visit is a workflow; there is
no return visit to design for and no state to carry.

The surrounding properties are part of the picture and predate this page: the
documentation site, the public GitHub repository, and the LinkedIn profile.

## Capabilities and Constraints

- Static site. No backend, no database, no session, no forms. Served by Caddy on a
  Hetzner VPS, behind Pangolin, from a `dist/` directory generated out of `src/` by
  `build.sh`.
- The Docker Compose stack count is baked in at build time on purpose, and goes stale
  until someone rebuilds. It is not fetched live and must not be presented as if it were.
- The 30-day uptime figure is fetched by the browser from Uptime Kuma at request time.
  When that fetch fails the figure stays hidden entirely; showing a zero, a dash, or a
  spinner in its place is a defect, not a fallback.
- The topology diagram exists twice: a PNG exported at 1280x1360 for the page, and an
  interactive version at `/topology/`. Both derive from
  `compose/proxmox-lxc-100/topology/nodes.yml`. The PNG, the Open Graph card, and the
  figcaption wording all repeat the same node and site counts and must move together.
- The container's network placement (`pangolin` bridge, static `172.18.0.10`) is
  load-bearing for the uptime widget and is not a cosmetic detail.

**Open, deliberately undecided:** there is currently no contact channel on the page other
than the LinkedIn and GitHub links, though "get in touch" is a named success outcome. A
CV download link is reserved in the markup as a comment but has not been committed to as
a product fact, and no email address has been established as public.

## Brand Commitments

- The name **Norbert Csicsay** and the domain **homelabor.net** are fixed.
- The LinkedIn profile link stays on the page. The owner has stopped posting there, but
  the profile remains a wanted destination.
- Voice, as established by the incumbent copy: plain, declarative, specific, and free of
  superlatives. Sentences state what exists and what it cost. Where something is a
  limitation it is said out loud, as in the figcaption admitting the map is only as
  current as the last rebuild. That candour is the credibility mechanism and is not
  negotiable.

## Evidence on Hand

Real, and already wired in:

- `src/topology.png` and `src/topology/index.html`, both generated from `nodes.yml`
- live 30-day uptime and per-service status from Uptime Kuma, via `src/status.js`
- the build-time Docker Compose stack count
- four project write-ups on docs.homelabor.net, linked from the Featured Projects cards
- the public GitHub repository, and `src/og.png` as the share card

Explicitly absent, and never to be fabricated to fill a layout: testimonials, client or
employer logos, user counts, adoption or "trusted by" claims, benchmarks, pricing, and
any figure that is not measured somewhere in this repository. This was confirmed as a
hard constraint.

## Product Principles

1. **Every number must be traceable.** A figure on this page is either fetched live or
   baked from a file in this repository. If it cannot be traced, it does not appear.
2. **Absence beats approximation.** When real data is unavailable, hide the element.
   Placeholders, zeros, and spinners all read as decoration and cost more credibility
   than the missing figure would have earned.
3. **Name the limits.** Staleness, manual steps, and things deliberately left out are
   stated on the page rather than hidden. The willingness to say so is the proof.
4. **The documentation is the product; this is the door.** The page never restates what
   docs.homelabor.net covers better. It establishes that the docs are worth opening.
5. **The visitor arrives evaluating a person, not a service.** No funnel language, no
   urgency, no manufactured calls to action.

## Accessibility & Inclusion

No external standard was set as a requirement, but the incumbent implementation carries
deliberate accessibility work that later work must preserve rather than rediscover: a
skip link, an `aria-label` on the sideways-scrollable topology plate and on the link
inside it, a full descriptive `alt` paragraph on the diagram, keyboard focus on the
scroll container, and a `prefers-reduced-motion` guard that disables the counting
animation. The page also declares `color-scheme: dark`.
