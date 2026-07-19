# Context Glossary

Domain terms for the homelab repo. Implementation details belong in specs/plans, not here.

## Daughter's Art Portfolio Site

- **Category** — a grouping of drawings shown as a filterable tab in the gallery (e.g. "Csendelet", "Anime karakterek"). Backed by a folder under `content/`. Has two distinct names:
  - **name** — the folder name on disk (e.g. `csendelet`, `anime-karakter`). Technical identifier: used for file paths and as the internal filter key. Not shown to the user.
  - **label** — the human-readable, properly accented/capitalized text shown on the tab (e.g. "Csendelet", "Anime karakterek"). Never derived automatically from `name` — always explicit, so Hungarian accents and casing are correct.
