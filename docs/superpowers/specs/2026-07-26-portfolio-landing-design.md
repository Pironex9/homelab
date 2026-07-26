# Homelab Portfolio Landing Page - Design

## Purpose

A standalone, visually striking landing page at the apex domain `homelabor.net`, built to catch a recruiter's/hiring manager's eye in the first 10 seconds - distinct from the existing technical documentation site. Motivated by active IT job hunting (career changer into DevOps/sysadmin roles, mid-process with Furbify as of 2026-07-26).

## Scope

In scope: a new one-page (scrolling) landing site - its content, visual design, live-status integration, and deployment.

Out of scope: the existing MkDocs documentation site (`docs.homelabor.net`) - stays completely unchanged, keeps serving detailed setup guides and host references. Out of scope: a CV/resume file (not ready yet; the contact section reserves a slot for a future "Download CV" link/button, added later without a design change).

## Relationship to the existing docs site

Two separate properties, explicitly not merged into one repo/deploy (GitHub Pages allows only one custom domain per repository - confirmed via research; an apex domain and a subdomain cannot both be served from the same repo's Pages site):

- `homelabor.net` (apex) - the new landing page, new repo.
- `docs.homelabor.net` (subdomain) - existing `homelab` repo, existing MkDocs site, untouched.

Cross-links: the landing page hero/footer links to `docs.homelabor.net` ("Full documentation"); `docs/index.md` on the existing site gets a small "Back to homelabor.net" link added at the top.

## Hosting

- New GitHub repository (e.g. `Pironex9/portfolio`), independent of the `homelab` repo.
- GitHub Pages, custom domain `homelabor.net` (apex). `CNAME` file with that content in the build output.
- DNS: `homelabor.net` is already managed in Cloudflare (per `docs/proxmox/20_MkDocs_Portfolio_Site_Setup.md`). At deploy time, add A records for the apex pointing at GitHub Pages' IPs (apex domains require A/ALIAS records, not CNAME - a subdomain-only technique doesn't apply here).
- Static output only - no server-side code, no database, no new attack surface, matches the rationale already used for the docs site.

## Tech stack

Astro (static site generator). Chosen over a plain hand-written HTML/CSS/JS page because component reuse (`Hero`, `StatusBadge`, `ProjectCard`, etc.) pays off if the site grows a second page later (e.g. a blog or more case studies); chosen over Next.js because there is no dynamic/interactive app-level state to justify a full React framework - Astro ships zero JS by default and only hydrates the small interactive pieces (counters, status widget).

## Content structure (one scrolling page)

1. **Hero** - name, short tagline (career changer -> DevOps/AI-driven developer), and the live-status hook: service count + uptime %, sourced from the embedded status widget (see below). CTA buttons: GitHub, LinkedIn, "Full documentation ->" (link to `docs.homelabor.net`).
2. **Tech stack** - icon grid (Proxmox, Docker, Komodo, MergerFS+SnapRAID, Restic, Pangolin, Caddy, Tailscale, AdGuard, monitoring tools), replacing the current markdown table on the docs site.
3. **Architecture** - reuse the existing `topology.png` asset (or a simplified redraw of it later); no new interactive diagramming tooling.
4. **Featured Projects** - the same four highlights currently in `docs/index.md` (Komodo GitOps Migration, Resilient Storage, Self-hosted Tunnel, Backup System), presented as cards, each linking to its corresponding page on `docs.homelabor.net`.
5. **Contact / footer** - LinkedIn, GitHub, and a reserved slot for a future "Download CV" button (hidden or omitted until a CV file exists - no placeholder link).

No other sections (no blog, no testimonials, no gimmick 3D/WebGPU demos) - out of scope for a first version; add later if/when there's actual content to justify them.

## Visual design direction

- Dark-based theme, consistent with the "live status hook" concept validated during brainstorming.
- Status indicators (bullet dots) get a subtle pulse animation; hero stats (service count, uptime %) count up on scroll-into-view.
- Featured Project cards: subtle lift/glow on hover, not overdone.
- Typography: a clean sans-serif for body copy (e.g. Inter/Geist) + a monospace face for numbers/status text (e.g. JetBrains Mono) - gives an engineering feel without a full terminal-emulator gimmick (that option was considered and explicitly rejected).
- Mobile: sections stack vertically; the tech-stack icon grid collapses to 2 columns.
- Actual implementation goes through the `design-taste-frontend` skill at build time, to avoid a generic/templated look.

## Live status integration

- Enable Uptime Kuma's built-in public status page (if not already enabled) covering the homelab's services.
- Expose it via Pangolin on its own public subdomain (e.g. `status.homelabor.net`) - no new backend, no API keys, no new attack surface; reuses infrastructure that already exists.
- The Hero section shows live service count and uptime % via a small client-side fetch against Uptime Kuma's public status-page JSON endpoint, styled to match the rest of the Hero (not an embedded iframe, which would show Kuma's own UI and break the visual design). Fall back to a plain iframe/link to the status page only if that endpoint turns out not to expose usable per-service data at implementation time.
- **Fallback**: if the status endpoint is unreachable (e.g. the homelab itself is powered off or the WAN link is down), the Hero falls back to a static value (e.g. a plain "27 self-hosted services" line) instead of showing an error or blank space. The landing page itself stays up regardless, since it's hosted on GitHub Pages independent of homelab uptime.
- No other embedded live widgets (GitHub contribution graph, last-commit timestamp, Netdata badges, Grafana public dashboards, WakaTime) - considered during brainstorming and explicitly deferred to keep the first version simple. Revisit later if desired.

## Deployment / CI

- GitHub Actions workflow in the new repo: `npm install` -> `astro build` -> `actions/deploy-pages`, mirroring the existing `homelab` repo's `deploy.yml` pattern (Astro build step instead of `mkdocs build`).
- Push to `main` -> auto-deploy, live within ~1-2 minutes, matching the UX already established for the docs site.
- Local dev via `npm run dev` (Astro dev server) for preview before pushing.

## Testing / quality checks

No automated test suite (unit/e2e) - not justified for a static one-page site with no backend logic. Before going live:

- Manual check of every section, desktop + mobile viewport.
- One-off Lighthouse/PageSpeed pass (performance, accessibility, basic SEO).
- Link check: every Featured Project card resolves to the correct `docs.homelabor.net` page.
- Status-widget fallback check: simulate the homelab/Uptime Kuma being unreachable and confirm the Hero degrades to the static fallback instead of breaking.
