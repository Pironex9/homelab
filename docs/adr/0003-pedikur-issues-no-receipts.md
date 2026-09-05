# Pedikur issues no receipts and no invoices

The pedicure app records what was charged, but it never produces the document
the client is handed. That looks like a missing feature and is a legal
boundary.

The practitioner works in Slovakia, where Act 384/2025 Z. z. on revenue
recording took effect on 2026-01-01, replacing 289/2008 Z. z. Pedicure,
manicure and cosmetic services are covered, and every cash payment has to pass
through eKasa - an online register, the free VRP2 from Financna sprava, or the
software register the new act recognises. Penalties start at EUR 330 per
failure and escalate. Nothing we write can stand in for a certified register.

## Considered options

Three ways to avoid typing the amount in two places were weighed:

- **Keep VRP2 and accept the overlap.** Chosen. VRP2 is free, has no monthly
  document limit, and is already open on her phone at every payment. The
  overlap with our record is one field, the amount: which client, which
  Treatment, which products and which notes exist only here.
- **Move to a software register with a REST API** and issue through it. It
  would collapse the two entries into one, but it costs monthly and it puts a
  certified cash register inside the dependency chain of a tool we maintain
  ourselves.
- **Import from the eKasa zone.** No documented free export interface for VRP2
  was found; the developer documentation that exists belongs to commercial
  integrators.

## Consequences

A future reader will find a business application with no invoicing module and
should not add one. The revenue figures in the dashboard are hers to type, and
they are management information rather than statutory records - which is also
why tax treatment, flat-rate expenses and the accountant's requirements are
absent from the design entirely.

One dated item to watch: Act 385/2025 Z. z. makes receiving e-invoices
compulsory for every taxable person, VAT-registered or not, from 2027-01-01.
Issuing stays out of scope, but supplier documents will start arriving as
Peppol XML rather than PDF, so the attachment intake must not assume PDF
forever.

Design it argues from: `docs/superpowers/specs/2026-09-05-pedikur-design.md`, whose section 0
lists the rest of the document set.
