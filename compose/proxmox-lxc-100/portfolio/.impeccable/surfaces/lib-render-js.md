---
version: 1
slug: "lib-render-js"
primary_target: "lib/render.js"
related_targets: ["build.js"]
---

# Surface: the portfolio gallery (single page, three views)

**Scope:** the whole public site. One HTML page rendered by `lib/render.js`, three
views inside it. **Visitor mode: Experience** - the visitor is inside the work itself,
so the drawings lead from the first viewport and the interface recedes.

**Audience and job:** a Hungarian art-secondary admission panel, about two years out,
deciding whether this applicant has been drawing seriously. Second audience: Enci, who
adds her own work and who has to defend this portfolio out loud at the oral exam.

**Action:** read the collection as one continuous, dated body of work, then look closely
at any single drawing.

**Proof/content:** the drawings, their dates, and the count. Nothing else exists and
nothing else may be invented (see PRODUCT.md, Evidence on Hand).

## Chosen direction

**Gyarapodási napló** - museum accession register, catalogue-card cabinet, conservation
board. Seed key `d52c906f`, roll from the human-approved catalog. The collection is an
accession list that grows, not a gallery wall: every work has a number and a date, and
the number goes up.

Approved comps in `.impeccable/mocks/`:

| Comp | Role | File |
|---|---|---|
| C | hero / opening view | `comp-c-fiok.png` (carries `approved: true`) |
| B | second view, the ledger; also the print source | `comp-b-leltarkonyv.png` |
| A | detail view for one work | `comp-a-kiemelt-tetel.png` |

**Memorable moment:** the violet date stamp. It is the only saturated violet on the
page and it appears on nothing except dates, so the thing the product is arguing
(chronology) is the thing the eye lands on.

## Design system read from the approved comps

- **Corner language:** 2px. Cards, rails and images are near-square; nothing is pill
  shaped and nothing is circular except the brass tab holders.
- **Line weights:** 1px hairlines in brass for table rules and card edges; a 3px oxblood
  rail marks the active region. No 2px+ neutral borders anywhere.
- **Elevation:** one shadow recipe, low and wide, cast onto the dark ground. Drawings
  cast it; chrome does not.
- **Type ramp:** condensed grotesque capitals with wide tracking for labels and
  navigation; monospaced typewriter for every number, accession code and date; the
  drawing titles sit between them in the same condensed face at sentence case.
- **Ground:** dark throughout. The drawings are light-on-white paper, so a dark cabinet
  ground is what makes them read as objects rather than as page background.

## Implementation inventory

| Region | Medium | Note |
|---|---|---|
| page ground, rails, spine | CSS | flat colour fields, no texture claim |
| catalogue cards, ledger rows, tabs | semantic HTML + CSS | real table markup in the ledger view |
| brass tab holders, hairline rules | CSS + inline SVG | countable flat shapes, vector territory |
| violet date stamp | CSS (transform + colour) on real text | must stay selectable text, never rastered |
| the drawings | existing project asset | `sharp` variants from `content/`; never generated |
| buckram / board texture | **accepted omission** | flat colour instead; revisit only with a real tiling asset, not a CSS gradient pretending to be cloth |
| year rail / scrubber | semantic HTML input + CSS | keyboard operable, not a canvas widget |
| print sheets (A/3, PDF) | `@media print` on the ledger view | the ledger *is* the print form; no second renderer |

## Constraints carried from PRODUCT.md

- First name only. No surname, school, town or contact details.
- No invented titles, techniques, dates, institutions or attributions.
- Adding a drawing stays a folder drop.
- Hungarian throughout, with correct accents in UI text and `alt` attributes.
- Keyboard navigation and `prefers-reduced-motion` handling survive the redesign.

## Unresolved

- **How "selected" works are chosen.** The hero shows three. Nothing in the content model
  marks a work as selected yet; it needs a `featured: true` sidecar flag or an ordered
  list in `bio.yml`.
- **`date` is optional today** and the whole composition leans on it.
- **`age: 13` is hardcoded** in `bio.yml` and goes stale within a year.
- **Public hostname and whether `robots.txt` keeps disallowing indexing.**
