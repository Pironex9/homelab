# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

**Delegated, and the answer is: keep the existing build.** The owner left the stack
choice open on 2026-08-05 ("nem kell ide se statikus weboldal ha lehet mas, jobb"), so
it was reconsidered from scratch rather than assumed.

What exists is a Node 20 ESM build (`build.js` plus `lib/scan.js`, `lib/metadata.js`,
`lib/resize.js`, `lib/render.js`) that turns a folder of photographs into one
self-contained `dist/index.html` with the gallery data embedded as JSON, plus `sharp`
image variants, served by `caddy:alpine`. It has 15 tests under `test/` and it fails
loudly: a missing variant, a category absent from the HTML, or two files colliding on
one output basename all abort the build instead of shipping a broken page.

A framework was considered and rejected. Astro or Next would buy routing and components
that a single growing gallery does not need, and would cost a `node_modules` tree on the
deploy path and a second build system to keep working two years from now. The one thing
the current setup does not do is multiple pages, and nothing in the product needs them.

**Upgrade trigger, so this decision can be revisited on evidence rather than taste:**
move to a framework when the site genuinely needs more than one route (a per-drawing
permalink the committee can be sent directly, a separate written statement page), or
when the embedded JSON plus inline CSS in one HTML file crosses the point where the
first paint suffers. Neither is true at 6 images and neither is obviously true at 50.
A new stack must keep the two hard constraints below: the content directory stays
outside git, and adding a drawing stays a folder drop.

## Users

**Primary: the admissions panel of a Hungarian secondary art school**, roughly two years
from now. Enci is 13 and there are about two years until the secondary-school
application ("meg ket ev van a kozepiskolaig"), so nothing here is deadline work. They
are reviewing many applicants, they are looking at a screen, and they are judging both
the current level and whether the applicant has been drawing seriously or assembled a
folder in a fortnight.

**Secondary: Enci herself.** Over two years this is the only place her work is collected
in order. Seeing the early drawings next to the recent ones is part of what the site is
for, not a side effect.

**Also: family and teachers** who are handed the link. They are not the design target,
but they are why the URL has to be openable without an account or an app.

## Product Purpose

A public, growing record of one 13-year-old's drawing, kept from now until the
secondary-school application.

Success is not "the gallery looks nice". Success is that someone who opens the link
two years from now can see, without being told, that this is a continuous body of work
that got better - and can look closely enough at any single drawing to judge the actual
hand behind it.

## Positioning

**Two years of dated work, in order, in one place.** The obvious alternatives cannot
truthfully offer that: an Instagram or Behance profile is feed-ordered, mixed with
things that are not drawings, and shows no development arc; a folder of photographs
attached to an email shows a snapshot. A collection that starts two years before it is
needed is the one thing that cannot be produced retroactively, and it is the whole
point of starting now.

## Operating Context

Publishing a drawing is a folder drop, and that is deliberate:

1. photograph or scan the drawing
2. copy it into `/srv/docker-data/portfolio/content/<category>/` on LXC 100
   (192.168.0.110). A new folder is a new category, no code change
3. optionally add a sidecar `.yml` beside it with `title`, `technique`, `date`
4. rebuild in a throwaway Node container with the real content directory bind-mounted
   over the git-tracked one, then recreate the container so its `dist/` mount is not
   stale (a plain restart is not enough)

The full commands are in `README.md`. Two facts about that flow are load-bearing:
there is no npm on the docker host, and the build deletes and recreates `dist/`.

Category folder names are accent-free ASCII because they become file paths; the accented
display names live in `bio.yml` under `categories:`.

## Capabilities and Constraints

- **The real drawings never enter git.** They are photographs of a minor's schoolwork.
  `content/` is gitignored and the real content lives at
  `/srv/docker-data/portfolio/content/` on LXC 100, entirely outside the git checkout,
  so no `git pull`, `reset` or `clean` can reach it. The repo carries only the build
  tooling and placeholder samples. Any future change that would put a drawing into the
  repository is wrong, whatever else it buys.

- **The site becomes publicly reachable.** Decided 2026-08-05: the panel must be able
  to open a link, so a laptop shown in person is not enough. Today it is LAN-only
  (`portfolio.lan` through the LAN Caddy proxy, `192.168.0.110:3008`) and
  `dist/robots.txt` says `Disallow: /`. The public route is not built yet; Pangolin on
  the Hetzner VPS is the existing pattern in this homelab. **Open:** the hostname, and
  whether `robots.txt` keeps disallowing indexing once the site is public. Public and
  unindexed is a coherent position and is probably the right one for a minor's work.

- **The collection grows.** Confirmed as a continuously expanding collection rather than
  a fixed application packet, so 50+ images over two years is the case to design for,
  not 10. Ordering, filtering and some sense of chronology are product requirements, not
  polish. Today the only ordering is filename sort inside a category, and the only
  filter is the category tabs.

- **Every drawing carries an optional date; it should not stay optional.** `date` in the
  sidecar is currently one of three free-text fields and is shown only in the lightbox
  caption. If progression is the argument, the date is the load-bearing field.

- **`bio.yml` hardcodes `age: 13`.** That is wrong within a year and nothing reports it.
  A birth year, or dropping the age in favour of the drawing dates, is the fix.

- **All six images on the host today are placeholders.** Their sidecars say so in the
  technique field ("ideiglenes helyettesito kep"). No real drawing has been photographed
  yet.

## Brand Commitments

- **Hungarian, throughout.** UI text, category names and captions are Hungarian, with
  correct accents. The audience is a Hungarian school panel.

- **First name only, and nothing else identifying.** The site says "Enci". No surname,
  no school, no town, no contact details, no email, no social links. This is not an
  oversight to be helpfully corrected later: the site is public and the artist is a
  minor. Age is the single identifying fact that is published on purpose, because the
  panel's judgement of the work depends on knowing it.

- **The intro line in `bio.yml` is Enci's own wording** ("Szeretek rajzolni, kulonosen
  anime-stilusu karaktereket."). Rewriting it into marketing copy would replace the one
  authentic voice on the page.

## Evidence on Hand

- Six placeholder photographs in three categories (`csendelet`, `tajkep`,
  `anime-karakter`) with sidecar metadata that labels them as placeholders. **No real
  work exists on the site yet.**
- `bio.yml`: name, age, intro, and the accented category display names.
- Nothing else. There are **no** teacher quotes, awards, competition results,
  exhibition history, testimonials or press. Future work must not invent any of these,
  must not present a placeholder as real work, and must not invent a title, technique
  or date for a drawing that came without a sidecar.

## Product Principles

1. **Progression is the argument.** The single thing this site can show that no
   hastily-assembled folder can is two years of dated work getting better. Design
   decisions that make chronology visible beat decisions that make any one image
   prettier.

2. **The drawing leads; the interface recedes.** Every pixel of chrome competes with a
   pencil drawing for the same attention. Interface elements earn their place by helping
   someone look at the work more closely, or they go.

3. **A minor's safety outranks completeness.** The public site publishes a first name,
   an age and the drawings. Anything that would narrow that down to a findable person
   is out, no matter how conventional it is on a portfolio site.

4. **Never show what is not there.** No placeholder tiles, no empty categories, no
   invented metadata, no "coming soon". A gallery of six drawings that says nothing
   about being small is more honest than one padded to look full.

5. **Adding a drawing stays a folder drop.** If a change means publishing new work
   requires editing code, or that a photograph has to pass through a person who knows
   the build, it is the wrong change. Enci has to be able to add her own drawings.

## Accessibility & Inclusion

- Hungarian text with correct accents, including in `alt` attributes, which are
  currently derived from the drawing titles.
- Keyboard navigation through the lightbox already exists (Escape, arrows) and must
  survive any redesign; so must the `prefers-reduced-motion` handling on the reveal
  animation.
- The panel may be considerably older than the artist. Legibility, contrast and
  comfortable target sizes outrank fashionable typography.
