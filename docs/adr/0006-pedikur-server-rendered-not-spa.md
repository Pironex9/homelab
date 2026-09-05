# Pedikur renders on the server with htmx rather than shipping an SPA

The pedicure app is Jinja templates and htmx 2.x. There is no npm, no bundler
and no client-side state. In 2026 the default assumption is the opposite, so
the reasoning is recorded here rather than left to be inferred.

The app is a single-user CRUD tool over thirteen tables, used on a phone in a
treatment room and on a laptop in the evening. Its screens are lists and forms.
The one screen that genuinely wants JavaScript is the week calendar, and the
design already gives that up: v1 creates and edits by click, not by dragging,
because a Visit is moved about once a day. What an SPA would add here is a
build step, a dependency tree that needs updating, and a second copy of the
domain state that can disagree with the server's.

Building the interface ourselves was a requirement from the start, and this
does not compromise it: the design lives in HTML and CSS either way.

htmx is pinned to 2.x rather than 4.x. Version 4.0.0 shipped 2026-08-28, but
2.x stays `latest` on npm until early 2027, is feature-complete and is
supported indefinitely; 4.0 swapped XHR for the Fetch API and renamed
attributes, which buys nothing here.

## Consequences

The front end cannot be handed to a component library or a design system that
assumes React. Rich interactions - dragging appointments, an offline-capable
form queue - would each need hand-written JavaScript or a rewrite, and the
rewrite is the expensive direction.

The offline question is settled by the working conditions rather than by the
architecture: fixed premises, reliable wifi, and a service worker that caches
the Today screen read-only. If the practitioner ever starts visiting clients at
home, that assumption fails and this decision should be revisited alongside it.
