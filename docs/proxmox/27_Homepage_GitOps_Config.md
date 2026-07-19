# Homepage GitOps Configuration

**Date:** 2026-07-19
**Hostname:** docker-host (LXC 100)
**IP address:** 192.168.0.110

Homepage is the LAN service dashboard at `homepage.lan`, served by the `homepage` Docker stack on port 3002. The stack is managed by Komodo and now uses the homelab repo as the source of truth for the Homepage application config, not the old live YAML files under `/srv/docker-data/homepage`.

## Source of truth

The versioned config lives here:

```text
compose/proxmox-lxc-100/homepage/config/
```

Komodo deploys the stack from its checkout on LXC 100:

```text
/etc/komodo/repos/github/compose/proxmox-lxc-100/homepage/
```

The running container mounts:

```text
/etc/komodo/repos/github/compose/proxmox-lxc-100/homepage/config -> /app/config
/srv/docker-data/homepage/logs -> /app/config/logs
/srv/docker-data/homepage/images -> /app/public/images
```

The old live files such as `/srv/docker-data/homepage/services.yaml` are no longer the source of truth after the GitOps deploy. Edit the repo copy instead.

## Komodo stack settings

The existing `homepage` stack is registered in Komodo with these relevant settings:

| Setting | Value |
|---|---|
| Branch | `main` |
| Run directory | `compose/proxmox-lxc-100/homepage/` |
| Compose file | `docker-compose.yml` |
| Environment file path | `stack.env` |
| Stack environment | Komodo writes this during deploy |

The compose file reads the generated environment file:

```yaml
env_file:
  - stack.env
```

## Secret handling

Do not commit `.env`, `stack.env`, API keys, token values or passwords. Homepage YAML files must reference secrets through placeholders:

```yaml
key: {{HOMEPAGE_VAR_EXAMPLE_KEY}}
```

The actual `HOMEPAGE_VAR_*` values live in Komodo Stack Environment and are written to `stack.env` during deploy. No extra environment variable is required for the GitOps config mount.

## Change workflow

To change dashboard links, widgets, layout or service monitors:

1. Edit files under `compose/proxmox-lxc-100/homepage/config/`.
2. Commit and push the repo.
3. In Komodo, run `Pull` and then `Deploy` on the `homepage` stack.
4. Verify the container is healthy and `homepage.lan` loads.

Example verification from LXC 100:

```bash
docker ps --filter name=homepage
curl -I -H 'Host: homepage.lan' http://127.0.0.1:3002/
```

## 2026-07-19 migration

The live config was copied from `/srv/docker-data/homepage`, sanitized, committed to git, pushed, then deployed through Komodo. The `topology.lan` dashboard card is now in the versioned `services.yaml` and no longer exists only as live config drift.

Validation performed after deploy:

- Komodo `PullStack` completed successfully
- Komodo `DeployStack` completed successfully
- `homepage` container restarted and reported healthy
- `/app/config` points to the Komodo repo checkout
- Homepage API returned the `Topology` card with `http://topology.lan` and monitor `http://192.168.0.110:3009`

## Credential hygiene

The Komodo repo checkout on LXC 100 currently uses a tokenized HTTPS Git remote. Treat that token as a secret and do not copy it into docs or logs. Long term, migrate the checkout to a GitHub deploy key or SSH remote, then rotate the old personal access token.
