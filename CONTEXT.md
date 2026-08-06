# Context Glossary

Domain terms for the homelab repo. Implementation details belong in specs/plans, not here.

## Homelab Landing Page

The public one-page site at the apex domain, distinct from both the documentation site and from the daughter's art portfolio. "Service" was previously used for three different things; each now has its own term and exactly one source of truth.

### Language

**Landing Page**:
The public one-page site at `homelabor.net`, whose purpose is to make a hiring audience take the infrastructure seriously.
_Avoid_: Portfolio (that name is taken by the art site), homepage (that is the internal dashboard)

**Documentation Site**:
The MkDocs site at `docs.homelabor.net` holding setup guides and host references.
_Avoid_: Docs site, wiki

**Compose Stack**:
One directory under `compose/<host>/<name>/` containing a compose file, in any of its three accepted spellings: `docker-compose.yml`, `compose.yml` or `compose.yaml`. Both `compose.yaml` spellings are in use here, so a definition naming only `docker-compose.yml` undercounts by two. A directory holding no compose file is not a Compose Stack, however it is named. This is the unit the repo version-controls, and therefore the only service count that can be derived rather than asserted.
_Avoid_: Container, app, service

**Proxmox Guest**:
One LXC container or VM on the hypervisor. Includes things that are not Compose Stacks at all, such as AdGuard, Vaultwarden and n8n.
_Avoid_: VM, node, machine

**Monitored Service**:
One Uptime Kuma monitor. Not one-to-one with either count above: some services carry two monitors (an internal check plus a public tunnel check), and some Compose Stacks have none.
_Avoid_: Check, probe

**Publicly Monitored Service**:
The curated subset of Monitored Services shown on the public status page. Deliberately smaller than the full set, because every name on that page is a public statement about what the infrastructure is for.
_Avoid_: Public service, exposed service

**Self-Hosted End to End**:
The claim that every part of the public path is operated by the owner, including the tunnel onto it - no third-party provider, no forwarded ports, and no third-party origin fetched by the browser. It is a claim a visitor can check, so anything the pages load from someone else's domain contradicts it directly rather than merely falling short of it.
_Avoid_: Self-hosted (unqualified - the whole point is the "end to end")

**Uptime**:
The thirty-day availability figure. The twenty-four hour figure exists in Uptime Kuma but is never shown publicly, because a single outage distorts it past usefulness.
_Avoid_: Availability, SLA

## Brand

The visual identity shared by the owner's public properties. There is one brand and it is the person, not the infrastructure: the Landing Page title, its hero kicker and the Documentation Site name all read "Norbert Csicsay", and the Landing Page exists to answer a question about a specific person rather than to sell a product.

### Language

**Mark**:
The single monogram identifying Norbert Csicsay wherever his properties appear - favicon, Documentation Site header, GitHub avatar, CV. There is exactly one; the infrastructure has no separate mark of its own.
_Avoid_: Logo (implies a company or product mark, which is the confusion this term exists to prevent), brandmark, icon

**Brand Tokens**:
The values the properties hold in common: accent colour, type pairing and spacing scale. Background and surface colours are deliberately not among them - the Landing Page is dark-only by design, and the Documentation Site keeps its own light and dark reading surfaces.
_Avoid_: Theme, palette (both imply a full surface treatment, which this deliberately is not)

## Daughter's Art Portfolio Site

- **Category** — a grouping of drawings shown as a filterable tab in the gallery (e.g. "Csendelet", "Anime karakterek"). Backed by a folder under `content/`. Has two distinct names:
  - **name** — the folder name on disk (e.g. `csendelet`, `anime-karakter`). Technical identifier: used for file paths and as the internal filter key. Not shown to the user.
  - **label** — the human-readable, properly accented/capitalized text shown on the tab (e.g. "Csendelet", "Anime karakterek"). Never derived automatically from `name` — always explicit, so Hungarian accents and casing are correct.
