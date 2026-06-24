# Kan (Kanban Board)

**Date:** 2026-06-24
**Hostname:** docker-host (LXC 100)
**IP address:** 192.168.0.110

Self-hosted Trello alternative. Runs as a Docker Compose stack on LXC 100, managed via Komodo (GitOps).

## Overview

| Property | Value |
|----------|-------|
| Service | Kan ([kanbn/kan](https://github.com/kanbn/kan)) |
| Host | LXC 100 (docker-host) |
| Access | http://192.168.0.110:3006 |
| Image | `ghcr.io/kanbn/kan:latest` |
| Database | PostgreSQL 15 (`kan-db`, internal only) |
| Network | `arr_stack` (external) |

## Stack layout

Three containers (`compose/proxmox-lxc-100/kan/docker-compose.yml`):

- **kan** - Next.js web app, published on host port `3006`.
- **kan-db** - PostgreSQL 15, data bind-mounted to `${DOCKER_DATA}/kan/postgres`. Not exposed to the host.
- **kan-migrate** - one-shot DB migration; runs to completion before `kan` starts.

## Configuration

Secrets live in the Komodo Stack Environment (not git):

| Variable | Purpose |
|----------|---------|
| `KAN_POSTGRES_PASSWORD` | Postgres password (shared by all three services) |
| `KAN_AUTH_SECRET` | better-auth secret, 32+ chars (`openssl rand -base64 26 \| tr -dc 'a-zA-Z0-9' \| head -c 32`) |
| `KAN_BASE_URL` | Access URL, must match how you reach the app (`http://192.168.0.110:3006`) |

Email is disabled (`NEXT_PUBLIC_DISABLE_EMAIL=true`); enable SMTP vars from upstream if needed.

## First run

The first registered user becomes the admin. Set `NEXT_PUBLIC_DISABLE_SIGN_UP=true` after creating your account if you want to lock signups.

## Deployment

```bash
cd compose/proxmox-lxc-100/kan
docker compose up -d
```

Or via Komodo: Pull -> Deploy after committing changes.

## Komodo shows "unhealthy"

Normal. `kan-migrate` is a one-shot container - it runs the DB migrations, then exits `0`. Komodo counts any exited container as unhealthy even though this one is *meant* to exit. The app is fine as long as `kan` and `kan-db` are `Up`. Every Pull/Deploy re-runs (and re-creates) the migrate container, so the status returns; clear it with `docker rm kan-migrate` if the red status bothers you.
