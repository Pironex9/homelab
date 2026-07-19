# Portfolio site build

Static art portfolio for Enci's school admission. No backend, no database.

## Adding a new drawing

1. Photograph/scan the drawing (not covered by this tool).
2. Copy the image into `content/<category>/`, e.g. `content/tajkep/03-hegyek.jpg`.
   New categories are just new folders under `content/` - no code changes needed.
   Keep folder names accent-free (they become file paths); set the accented
   display name in `bio.yml` under `categories:`, e.g. `tajkep: "Tájkép"`.
3. Optionally add a sidecar YAML file next to it with the same base name, e.g. `content/tajkep/03-hegyek.yml`:

   ```yaml
   title: "Hegyi tajkep"
   technique: "akvarell"
   date: "2026-09-01"
   ```

   If you skip this file, the title is derived from the filename.
4. Run `npm run build`.
5. Redeploy the stack (see repo root `compose/CLAUDE.md` for the Komodo GitOps flow, or `docker compose up -d` locally as a manual fallback).

## Editing the bio

Edit `bio.yml` (name, age, intro, category display names), then rebuild.

## Running tests

`npm test`
