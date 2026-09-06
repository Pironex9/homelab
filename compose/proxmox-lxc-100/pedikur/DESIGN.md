# Pedikur design direction

**Purpose:** A working tool held in one hand between clients, and read on a
laptop in the evening. Speed of reading beats richness.

**Tone:** Calm and clinical without being cold. It sits in a treatment room,
so it must look clean rather than playful.

**Constraints:** Thumb-reachable primary actions. Legible at arm's length on a
phone. One accent colour, used only for the primary action and today's column.
Red is reserved for the client alert and nothing else, or it stops meaning
anything.

**Differentiation:** This is not the brand of `brand/BRAND.md`. That brand is
the repo owner's public identity, dark and portfolio-tuned; this is someone
else's daily tool and gets its own light, quiet palette.

## Decisions derived from the above

**Light, and warm.** Picked from the use scene, not the category: a treatment
room is brightly lit and the phone is often held in daylight. The ground is
`#f7f6f4`, a warm off-white rather than a blue-grey, because blue-grey is what
makes software look like a hospital chart. There is no dark theme; a single
committed palette beats two half-tuned ones.

**One accent, deep pine `#2f6f62`.** Far enough from red that the two never
read as a pair, dark enough to carry white text at 5.9:1, and quiet enough to
be used on every screen without shouting. It marks exactly two things: the
primary action and today.

**Red is a reserved word.** `--danger` appears on the client health alert and
on form errors, and nowhere else. No red for delete buttons, no red for
counts. The alert is a tinted surface with a hairline border and a filled dot,
not a thick coloured bar: a 4px stripe is the generic "callout" costume and
would train the eye to ignore it.

**Numbers are tabular.** Times and prices are the spine of a calendar, so
every element that shows one gets `font-variant-numeric: tabular-nums`. A
09:00 that shifts a pixel against a 10:00 is a column that cannot be scanned.

**System type, tuned rather than replaced.** This is a tool, not a display
page, and a self-hosted face would buy character the practitioner will never
look at while it costs a render-blocking request on a phone in a treatment
room. What it does get: an explicit fallback stack that renders Hungarian
accents natively, a scale with obvious steps, and tight line lengths.

**Text labels, no icon set.** Four tabs in Hungarian read faster than four
glyphs someone has to learn, and an invented icon set would be four drawings
carrying no more information than the four words.

**Contrast measured, not assumed.** Every text pair on this palette:
ink on bg 16.1, ink-muted on bg 5.1, accent on bg 5.4, white on accent 5.9,
danger on surface 6.5, ok on surface 6.1. The floor is 4.5.
