# Rails Learning Lab

**Date:** 2026-08-01
**Hostname:** docker-host
**IP address:** 192.168.0.110
**Location:** `/opt/rails-lab`
**URL:** http://192.168.0.110:3300

A disposable Ruby on Rails 8 + PostgreSQL sandbox used for learning. Not a
production service: no reverse proxy, no backups, no Komodo management. The
point is a real app to poke at - `rails console`, migrations, request tracing.

## Stack

| Container | Image | Port | Role |
|-----------|-------|------|------|
| `rails-lab-web` | built from `ruby:3.4-slim` | 3300 -> 3000 | Rails 8.1.3.1 dev server |
| `rails-lab-db` | `postgres:17-alpine` | internal 5432 | Development database |

Named volumes: `rails-lab_pgdata` (database), `rails-lab_bundle` (gems).
The generated Rails app lives in `/opt/rails-lab/app`, bind-mounted into the
container at `/app`.

## Why port 3300

Port 3000 is taken by BentoPDF, and 3001-3006 plus 3008-3009 are taken by
Homelable, Homepage, DocuSeal, Form, Dawarich, Kan, Portfolio and Topology.
The first deploy failed with `Bind for 0.0.0.0:3000 failed: port is already
allocated`, so the lab moved to 3300.

## Rails 8 host authorization

Rails blocks non-localhost requests in development mode. The compose file sets:

```yaml
RAILS_DEVELOPMENT_HOSTS: "192.168.0.110,.local,.lan,.ts.net"
```

Without this, browsing to the LAN IP returns "Blocked hosts" instead of the app.

## Source of truth

The compose file, Dockerfile and bootstrap script are **not** in this repo.
They live in the learning workspace on LXC 109:

```
/root/learning/rails/lab/
  Dockerfile
  compose.yaml
  bootstrap.sh
  README.md
```

Deployed with `scp -r` to `/opt/rails-lab`. Kept out of `compose/` because it
is throwaway learning infrastructure, not a homelab service - same reasoning as
Odysseus being a `files_on_host` stack outside the repo.

## First-time setup

```bash
scp -i ~/.ssh/id_ed25519 -r /root/learning/rails/lab root@192.168.0.110:/opt/rails-lab
ssh docker-host
cd /opt/rails-lab
./bootstrap.sh      # builds image, runs `rails new`, creates the database
docker compose up -d
```

`bootstrap.sh` is idempotent - it exits early if `app/Gemfile` already exists.

## Daily commands

```bash
cd /opt/rails-lab
docker compose up -d
docker compose logs -f web
docker compose exec web bin/rails console
docker compose exec web bin/rails routes
docker compose exec web bin/rails db:migrate
docker compose exec web irb          # plain Ruby REPL, no Rails
docker compose down -v               # stop and wipe the database
```

## Editing from VS Code

VS Code on the Nobara desktop connects over Remote-SSH:

1. `Ctrl+Shift+P` -> *Remote-SSH: Connect to Host* -> `docker`
2. Open folder `/opt/rails-lab/app`

The `docker` alias already existed in Nobara's `~/.ssh/config`. On 2026-08-01
Nobara's public key was appended to `/root/.ssh/authorized_keys` on
docker-host - before that, Remote-SSH failed with
`Permission denied (publickey)`.

Rails reloads changed code automatically in development mode, so saving in
VS Code is enough - no container restart.

## Notes

- The stack has `restart: unless-stopped`, so it survives host reboots
- Gems install at runtime into a named volume rather than at image build time.
  Slower first boot, but no rebuild needed when the Gemfile changes
- To start over completely: `docker compose down -v && rm -rf /opt/rails-lab/app`
