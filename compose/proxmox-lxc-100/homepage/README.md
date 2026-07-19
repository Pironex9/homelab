# homepage

Self-hosted dashboard served by `ghcr.io/gethomepage/homepage` on port 3002.

## GitOps config

Homepage application config is versioned in `config/` and mounted into the
container as `/app/config`.

The `homepage` stack is already registered in Komodo with:

- branch: `main`
- run directory: `compose/proxmox-lxc-100/homepage/`
- compose file: `docker-compose.yml`
- environment file path: `stack.env`

Komodo deploy flow:

```bash
git commit
# git push only when requested
# Komodo: Pull -> Deploy the homepage stack
```

Secrets must stay in Komodo Stack Environment / `stack.env`, never in git. Use
Homepage variable placeholders in YAML, for example:

```yaml
key: {{HOMEPAGE_VAR_EXAMPLE_KEY}}
```

Runtime-only files stay on the host:

- `/srv/docker-data/homepage/images` -> `/app/public/images`
- `/srv/docker-data/homepage/logs` -> `/app/config/logs`
- `/srv/docker-data/homepage/.env` / `stack.env` for secrets

## Current live state

On 2026-07-19, the live stack was deployed through Komodo after moving config
into git. The running container mounts:

- `/etc/komodo/repos/github/compose/proxmox-lxc-100/homepage/config` -> `/app/config`
- `/srv/docker-data/homepage/logs` -> `/app/config/logs`
- `/srv/docker-data/homepage/images` -> `/app/public/images`

The old `/srv/docker-data/homepage/*.yaml` files are no longer the source of
truth. If a live edit is made there, it will not affect the container after the
GitOps deployment because `/app/config` now points at the Komodo repo checkout.

To change dashboard links or widgets:

1. Edit files under `config/`.
2. Commit and push the repo.
3. In Komodo, run `Pull` and then `Deploy` on the `homepage` stack.

## Security notes

Do not commit `.env`, `stack.env`, API keys, token values, or passwords.
Homepage YAML files should reference secrets only through
`{{HOMEPAGE_VAR_*}}` placeholders.

The Komodo repo checkout on LXC 100 currently uses a tokenized HTTPS Git remote.
This works, but the token should be treated as a secret. Long term, prefer a
GitHub deploy key or SSH remote and rotate the old personal access token after
the migration.
