# homepage

Self-hosted dashboard served by `ghcr.io/gethomepage/homepage` on port 3002.

## GitOps config

Homepage application config is versioned in `config/` and mounted into the
container as `/app/config`.

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
