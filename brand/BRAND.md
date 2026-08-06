# Brand

One identity across the Landing Page, the topology map, the Documentation Site,
the GitHub profile and the CV. It is the person, not the infrastructure: both
site titles carry the name, and the Landing Page exists to answer a question
about a specific person.

Values live in `tokens.css`. Terms are defined in `CONTEXT.md` - Mark,
Portrait, Brand Tokens, Framed Artifact, Display Face, Self-Hosted End to End.

## Typefaces

| Role | Face | Where |
|---|---|---|
| Body | IBM Plex Sans (variable) | all properties |
| Code, figures | IBM Plex Mono (400, 500) | all properties |
| Display | Big Shoulders Display (variable) | the topology map only |

All SIL OFL. Self-hosted, same-origin, subset to Latin plus Latin Extended-A so
Hungarian survives. `brand/` holds the only committed copy; run
`python3 brand/check-fonts.py` after any re-subset.

IBM Plex Mono has no variable cut in the Google Fonts repository, so the mono
role ships as two static instances. Every mono weight in use is standard, so
nothing is lost.

## The three deliberate exceptions

Written down because each one looks like a defect and is not.

**The topology map keeps its own palette.** `#0b1120` with its own panel, line
and wire tints, plus the node colours. On that one surface colour is functional
- the legend keys node type to colour - and the Landing Page already frames the
map in a bordered plate rather than bleeding it into the page. It is a Framed
Artifact. Retinting it would flatten a distinction the design already makes.

**The topology map keeps its own display face.** Big Shoulders Display is
condensed, and the Landing Page's headings are tracked negatively for a
normal-width face. Adopting it site-wide would mean re-tuning heading CSS that
was deliberately dialled in, and it costs scannability in long documentation.

**The Mark's hypervisor is `#e8933f`, the map's is `#e8a04c`.** The Mark is a
translation of the map into the Landing Page's own tokens, not a copy of it.
Its own comment has said so since it was drawn. Do not "fix" this.

## The Documentation Site takes only part of this

Header, accent and Mark. Not the reading surfaces: the Landing Page is
dark-only by design, the Documentation Site ships a light and dark toggle that
serves long-form reading, and there is no light palette anywhere in this repo
to base one on.

## What is not here

No spacing scale. `style.css` has none and never has; a scale invented here
would be a new system presented as a consolidation. If one is wanted it is its
own piece of work, on its own evidence.
