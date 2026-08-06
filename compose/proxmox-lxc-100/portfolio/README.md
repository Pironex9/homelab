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
   ```

   If you skip this file, the title is derived from the filename.
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

## Editing the bio

Edit `bio.yml` (name, age, intro, category display names), then rebuild.

## Running tests

`npm test`
