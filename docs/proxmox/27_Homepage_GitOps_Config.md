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

## 2026-08-28: the K3s cluster's four web UIs

Argo CD, Longhorn, Grafana and Forgejo were added as their own `K3s` group -
that is every GUI the cluster has. They went in as **services, not bookmarks**:
Quick Links is for third-party sites and carries no `siteMonitor`, and for a
cluster that is only reachable over Tailscale the status dot is the point. If
the remote site loses power, that is what you want the dashboard to tell you.

Two things had to be measured, because neither is visible from the config.

### `argocd.png` does not exist

The icon is `argo-cd.png`. Both `argocd.png` and `argocd` return **404** from
dashboard-icons *and* from the selfhst set. Homepage does not report a missing
icon - it renders an empty tile and logs nothing, so the name has to be checked
rather than guessed:

```bash
curl -s -o /dev/null -w '%{http_code}\n' \
  https://cdn.jsdelivr.net/gh/homarr-labs/dashboard-icons/png/argo-cd.png
```

### A Tailscale Ingress needs the hostname, not the IP

LXC 100 cannot resolve `*.tailc6abe2.ts.net`: `tailscaled` runs there with
`accept-dns=false` on purpose, so there is no MagicDNS. The obvious workaround -
point `siteMonitor` at the raw tailnet IP, the way the Code Server card does -
**does not work here**, and it fails in a way that reads as an outage:

```
tailscale ping 100.87.160.51                              pong
TCP connect to 100.87.160.51:443                          succeeds
curl https://100.87.160.51/                               000
curl --resolve argocd...:443:100.87.160.51 https://argocd...   200
```

The Tailscale Ingress selects the backend by **SNI**. A request addressed to the
bare IP completes the TCP handshake and then dies in TLS, so the card would sit
on a red dot with a perfectly healthy service behind it.

The fix is four `extra_hosts` entries on the `homepage` service in
`docker-compose.yml`. That resolves the names inside this one container and does
not touch host DNS, which is what makes it safe on a machine running 24 stacks:

```yaml
extra_hosts:
  - "argocd.tailc6abe2.ts.net:100.87.160.51"
  - "longhorn.tailc6abe2.ts.net:100.127.135.123"
  - "grafana.tailc6abe2.ts.net:100.73.118.70"
  - "forgejo.tailc6abe2.ts.net:100.99.251.110"
```

**These IPs are not stable forever.** Each Ingress consumes its own tailnet
device, created by the Tailscale Kubernetes operator; if an Ingress is deleted
and recreated, its address changes and the card goes red while the service is
fine. `tailscale status | grep -E 'argocd|longhorn|grafana|forgejo'` is the
check.

`extra_hosts` also only takes effect on a container **recreate**, so this needs
Komodo `Deploy`, not `Restart` - and therefore the `/api/revalidate` call from
the section above.

Validation performed after deploy:

- container recreated, `HostConfig.ExtraHosts` carries all four entries
- `docker exec homepage cat /etc/hosts` shows the four names
- from inside the container: argocd 200, longhorn 200, grafana 302, forgejo 200
- `/api/revalidate` returned `{"revalidated":true}`
- screenshot confirms four cards with icons and green dots

The `href` stays the tailnet name, so the cards only open from a device on the
tailnet. That is deliberate: these UIs have no LAN path, and the Longhorn one has
no authentication at all.

## Credential hygiene

The Komodo repo checkout on LXC 100 currently uses a tokenized HTTPS Git remote. Treat that token as a secret and do not copy it into docs or logs. Long term, migrate the checkout to a GitHub deploy key or SSH remote, then rotate the old personal access token.
