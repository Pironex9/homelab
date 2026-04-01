**Date:** 2026-04-01
**Hostname:** docker-host
**IP address:** 192.168.0.110

# Dawarich GPS Location Tracking Setup

## Overview

Dawarich is a self-hosted GPS location history and family tracking platform. It replaces cloud-based location tracking apps (e.g. Locator 24) with a fully private, self-hosted solution. It stores location history, shows maps, supports family sharing, and accepts data from multiple mobile apps.

- **URL (LAN):** http://192.168.0.110:3005
- **URL (public):** https://dawarich.homelabor.net (via Pangolin)
- **Stack location:** `compose/proxmox-lxc-100/dawarich/`
- **Managed via:** Komodo (Stack: `dawarich`, LXC 100)

## Architecture

4 containers on an internal `dawarich` bridge network:

| Container | Image | Role |
|-----------|-------|------|
| `dawarich_app` | `freikin/dawarich:latest` | Rails web application (port 3005) |
| `dawarich_sidekiq` | `freikin/dawarich:latest` | Background job worker |
| `dawarich_db` | `postgis/postgis:17-3.5-alpine` | PostgreSQL with PostGIS extension |
| `dawarich_redis` | `redis:7.4-alpine` | Job queue and cache |

## Environment Variables

Set in Komodo Stack Environment:

| Variable | Description |
|----------|-------------|
| `DOCKER_DATA` | `/srv/docker-data` - bind mount root |
| `TZ` | `Europe/Budapest` |
| `DAWARICH_DB_PASSWORD` | PostgreSQL password for the `dawarich` database |
| `DAWARICH_SECRET_KEY_BASE` | 64-character random secret for Rails session encryption |
| `DAWARICH_SMTP_PASSWORD` | Resend API key (used as SMTP password) |
| `DAWARICH_SMTP_FROM` | From address for invitation emails (e.g. `noreply@yourdomain.com`) |

Generate `SECRET_KEY_BASE` with: `openssl rand -hex 64`

## Key Configuration Notes

- Dawarich uses `DATABASE_HOST` / `DATABASE_USERNAME` / `DATABASE_NAME` env vars - NOT `POSTGRES_HOST` or `DATABASE_URL`
- `APPLICATION_HOSTS` must include all hostnames used to access the app - LAN IP, localhost, and any public domain (e.g. `dawarich.homelabor.net`)
- `APPLICATION_PROTOCOL` must be `http` - Pangolin handles TLS termination. Setting `https` causes Rails to force-redirect HTTP to HTTPS, creating a redirect loop through the Pangolin tunnel.
- The `bin/rails server` command must be specified explicitly - the image has no default entrypoint command for the app service
- Migrations do NOT run automatically on startup - run manually after first deploy (see below)

## SMTP Setup (Family Invitations)

Dawarich uses SMTP to send family invitation emails. Configured with Resend:

| Variable | Value |
|----------|-------|
| `SMTP_SERVER` | `smtp.resend.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USERNAME` | `resend` |
| `SMTP_PASSWORD` | Resend API key (set in Komodo env) |
| `SMTP_STARTTLS` | `true` |
| `SMTP_FROM` | From address configured in Resend |

To invite family members:
1. Settings - Users - Invite User (or use the Family Group feature)
2. The invited user receives an email with a registration link

## First-Time Setup

### 1. Deploy via Komodo

Add Stack Environment in Komodo, then deploy. After the stack is running:

### 2. Run database migrations

```bash
docker exec dawarich_app bin/rails db:migrate
```

Verify with:

```bash
docker exec dawarich_app bin/rails db:migrate:status
```

### 3. Create admin user

```bash
docker exec dawarich_app bin/rails runner 'User.create!(email: "your@email.com", password: "your_password", password_confirmation: "your_password", admin: true)'
```

Note: Use single quotes around the Ruby code to avoid bash `!` interpretation issues.

There is no default demo user - the account must be created manually.

## Mobile App Setup

### Recommended: Colota (Android)

[Colota](https://colota.app) is the recommended GPS tracking client for Android. It sends location data directly to Dawarich with smart battery profiles and GPS accuracy filtering.

**Why Colota over alternatives:**
- Intelligent tracking profiles - faster updates when moving/in car, slower when stationary
- GPS accuracy filtering - discards bad GPS points automatically
- Offline queue - stores points when offline, syncs later
- Open source (AGPL), no telemetry

**Setup:**
1. Install Colota from Google Play or IzzyOnDroid
2. In Dawarich: Settings - API Keys - copy your API key
3. In Colota: Settings - API Settings - select **Dawarich** template
4. Enter the full endpoint URL:
   ```
   https://dawarich.homelabor.net/api/v1/owntracks/points?api_key=YOUR_API_KEY
   ```
5. Tap Test Connection to verify

**Note:** The full endpoint path `/api/v1/owntracks/points?api_key=...` is required - the base URL alone returns 404.

### Home Assistant Companion App

Use the HA Companion App alongside Colota for zone-based presence detection (home/away automations). These serve different purposes and run simultaneously without conflict:

| App | Purpose |
|-----|---------|
| Colota | Continuous GPS history in Dawarich |
| HA Companion App | Zone entry/exit detection for HA automations |

### Other Supported Apps

Dawarich also supports OwnTracks, Overland, GPSLogger, and Traccar Client via these endpoints:

- OwnTracks / Colota: `https://dawarich.homelabor.net/api/v1/owntracks/points?api_key=KEY`
- Overland: `https://dawarich.homelabor.net/api/v1/overland/batches?api_key=KEY`

## Deployment Troubleshooting

Issues encountered during setup and their fixes:

| Problem | Cause | Fix |
|---------|-------|-----|
| Port conflict on 3004 | `form` container already uses 3004 | Changed to port 3005 |
| `bundler: exec needs a command to run` | Missing `command:` in compose | Added `bin/rails server -p 3000 -b ::` |
| YAML parse error on `::` | Unquoted `::` is invalid YAML | Quoted the command string |
| `Blocked hosts: 192.168.0.110` | Rails host authorization | Added `APPLICATION_HOSTS` with LAN IP |
| `Blocked hosts: dawarich.homelabor.net` | Public domain not in allowed hosts | Added domain to `APPLICATION_HOSTS` |
| Socket connection instead of TCP | Wrong env var names | Use `DATABASE_HOST`/`USERNAME`/`NAME`, not `POSTGRES_*` |
| App crashes on startup | `DATABASE_URL` not supported | Use individual `DATABASE_*` vars instead |
| White page on sign in | Migrations not run | Run `docker exec dawarich_app bin/rails db:migrate` |
| No default login | No demo user exists | Create user via `rails runner` command above |
| Colota 404 on test connection | Base URL entered instead of full endpoint | Use full `/api/v1/owntracks/points?api_key=...` URL |
| `dawarich.homelabor.net` returns 503 / no available server | `APPLICATION_PROTOCOL: https` causes Rails force_ssl redirect loop through Pangolin | Set `APPLICATION_PROTOCOL: http` - Pangolin handles TLS |
