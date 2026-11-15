# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

One family of three: two adults and their teenage child, each on their own
Android phone with the app installed from Chrome. All three record spending;
the adults also read the month, set limits and confirm recurring drafts. The
child manages a pocket money wallet. No other audience.

## Product Purpose

One shared ledger of household money: where it goes, and whether each
category stays inside its monthly limit. Success is that the family records
every expense without it feeling like a chore, and the monthly view is the
number they actually look at. What things cost elsewhere is a secondary
interest.

## Positioning

Capture-first and cash-aware: a purchase is recorded at the till by voice,
receipt photo (Slovak eKasa QR read exactly, other receipts by AI) or a
two-field form, with no bank sync. Hidden entries let a gift stay secret
while its amount still counts.

## Operating Context

- Recorded right after paying, in a shop or at the till, one-handed, often
  with bad signal; the capture form works offline and queues.
- Read at home in the evening: the month view, categories against limits,
  drafts waiting for confirmation.
- Shopping happens in Slovakia and Hungary (EUR and HUF), occasionally
  elsewhere. Reports are in EUR.
- Once a month the adults compare the month against the bank statement by eye.

## Capabilities and Constraints

- Phase 1: manual entry (also offline), categories with monthly EUR limits,
  income with recurring salary drafts, hidden entries, a child role with a
  pocket money wallet, monthly view. Photo and voice arrive in phase 2 and
  are visible but disabled ("hamarosan") in phase 1.
- Roles: adult and child. A child never sees household income, balance or
  limits.
- A hidden entry shows others only amount, category, date and author.
- Server-rendered pages (FastAPI + Jinja + htmx), no build step; the design
  lives in hand-written CSS.
- Interface language: Hungarian only, strings in `app/strings/hu.py`.
- Spec: `docs/superpowers/specs/2026-11-15-haztartas-design.md`.

## Brand Commitments

- Display name: **Háztartás** (confirmed 2026-11-15). Code, container and URL
  stay `haztartas`.
- Not the repo owner's `brand/` identity: this is the family's tool.

## Evidence on Hand

No real data yet. Screens are designed against invented sample entries; none
of them may be presented as the family's actual spending.

## Product Principles

1. Recording beats reading: capture must take seconds and never lose an item.
2. Every total tells the truth: hidden, child and draft rules are visible in
   how numbers are labelled, never silently bent.
3. Privacy inside the family is real: a secret stays secret on every screen.
4. One household, no ceremony: three known users, no onboarding, no settings
   anyone has to learn.

## Accessibility & Inclusion

No specific needs reported (confirmed 2026-11-15). Standard floor: WCAG AA
contrast, touch targets at least 44 px, works at 360 px width.
