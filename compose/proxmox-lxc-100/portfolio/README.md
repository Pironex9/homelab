# Portfolio site build

Static art portfolio for Enci's school admission. No backend, no database.

## Content lives outside git, on purpose

The real drawings are photos of a minor's schoolwork - they must never be committed or
pushed to GitHub. `content/` is gitignored. On the docker host (LXC 100), the real
content lives at `/srv/docker-data/portfolio/content/` instead, completely outside this
git checkout, so no `git pull` / `reset` / `clean` can ever touch it. The repo only ships
the build tooling and a placeholder sample under `content/` for local dev/tests.

## Adding a new drawing

1. Photograph/scan the drawing (not covered by this tool).
2. Copy the image into `/srv/docker-data/portfolio/content/<category>/` on LXC 100
   (or `content/<category>/` locally for dev), e.g. `.../csendelet/03-hegyek.jpg`.
   New categories are just new folders - no code changes needed.
   Keep folder names accent-free (they become file paths); set the accented
   display name in `bio.yml` under `categories:`, e.g. `tajkep: "Tájkép"`.
3. Optionally add a sidecar YAML file next to it with the same base name, e.g. `03-hegyek.yml`:

   ```yaml
   title: "Hegyi tajkep"
   technique: "akvarell"
   date: "2026-09-01"
   featured: true      # optional, see below
   ```

   If you skip this file, the title is derived from the filename.

   **Put the date in.** It is optional to the build and load-bearing to the page: the
   whole site argues that this is a collection built up over years, and an undated work
   cannot sit on the year rail, sorts to the end of the register, and gets an accession
   number with no year. The build prints a warning listing every undated file.

   **Quote any title containing an apostrophe or a quote mark.** A stray `"` inside a
   double-quoted YAML string aborts the build. The error names the file, but the
   underlying message comes from the YAML parser and reads like nonsense; if you see
   `bad indentation of a mapping entry`, look for a quote in the title.

   `featured: true` marks a work for the three large slots at the top of the page.
   With nothing marked, the build stands in three works spread evenly from the oldest
   to the newest, so the opening view always shows the collection's whole span. That
   fallback is honest about being a spread, not a claim about which drawings are best -
   mark the good ones and yours win.
4. Build (no npm on the host - run it in a throwaway Node container, bind-mounting the
   real content dir over the git-tracked one):

   ```bash
   cd /etc/komodo/repos/github/compose/proxmox-lxc-100/portfolio
   docker run --rm -v "$(pwd)":/app -v /srv/docker-data/portfolio/content:/app/content \
     -w /app node:20 sh -c 'npm run build'
   ```
5. Recreate the container so its `dist/` bind mount isn't stale (a plain `restart` is not
   enough - the build deletes and recreates `dist/`, which breaks the existing mount):

   ```bash
   docker rm -f portfolio && docker compose up -d
   ```

## The two faces are self-hosted, on purpose

`assets/fonts.css` and `assets/fonts/` hold Archivo Narrow and Courier Prime as woff2,
and `build.js` copies the whole `assets/` directory into `dist/` so the built page makes
**no third-party request**. Regenerate them with `scratchpad/fetch-fonts.py` if a weight
is ever added.

Both the `latin` and `latin-ext` subsets are shipped, and dropping `latin-ext` to save
30 KB would be a silent bug rather than an optimisation: Hungarian needs U+0151 (ő) and
U+0171 (ű), which live only in the extended subset. The failure mode is a page that
looks fine in English and falls back to a different font mid-word on `Csendélet`.

## Editing the bio

Edit `bio.yml` (name, age, intro, category display names), then rebuild.

## Running tests

`npm test`
