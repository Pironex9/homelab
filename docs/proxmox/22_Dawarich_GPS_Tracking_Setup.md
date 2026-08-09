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
- `APPLICATION_HOSTS` must include **every** hostname used to reach the app, the internal ones too - LAN IP, localhost, the public domain (`dawarich.homelabor.net`) and the Caddy name (`dawarich.lan`). A missing entry does not fail at startup; Rails host authorization rejects the request at runtime with `Blocked hosts: <name>`, so it looks like a proxy fault rather than a config one. Adding a `.lan` name to the Caddyfile is only half the job - the app has to be told about it as well
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

## Location Source

### Current: Home Assistant relays the Companion App (2026-08-09)

No dedicated tracker app runs on any phone. The HA Companion App - already installed for zone automations - is the only GPS source, and a custom integration on Home Assistant forwards each of its updates to Dawarich.

**Why the change.** Colota was the recommendation here and it did not survive contact with the family: it froze or crashed on their phones and silently stopped sending, which is the worst failure mode a tracker has. Every dedicated tracker shares that risk, because it is one more background app that has to stay alive on someone else's phone. The Companion App is the app they already keep alive for other reasons.

**The other half of the argument is retention.** Home Assistant's recorder defaults to `purge_keep_days: 10`, so HA is structurally incapable of being the location archive - it deletes the history. HA answers "where is everyone now", Dawarich answers "where was I in March". Both are needed; only one of them needs an app on the phone.

**Trade-offs, stated plainly:**

| | |
|---|---|
| Two hops | phone → HA → Dawarich. Points produced while HA is down are lost; a dedicated app would queue them. The nightly `qm reboot 101` at 04:10 is a gap in principle, at an hour when nobody moves |
| Track shape | the Companion App reports for zone presence, not for drawing a line. Points are sparser than a dedicated tracker's. "High accuracy mode" in the Companion App improves it at the cost of battery |
| Maturity | the integration is a community project, explicitly labelled experimental, unaffiliated with Dawarich. Not a load-bearing dependency |

Measured after cutover: points arriving with 7-19 m accuracy, several per minute while the phone was awake.

### Installing the integration

[AlbinLind/dawarich-home-assistant](https://github.com/AlbinLind/dawarich-home-assistant), installed through HACS so it stays updatable. Two things about it are not obvious:

- **It has no stable release.** Every tag is a pre-release (`1.0.0-beta6` at the time of writing), so HACS will not offer it until *Show beta versions* is enabled for the repository - otherwise the download silently has nothing to fetch.
- **The newest tag is not the one you want.** `1.0.0-beta6-debug` is a debug build, and HACS offers it as an update. Skip that version on the `update.dawarich_update` entity, otherwise the nag stays and someone eventually installs a debug build.

Note that the shipped `manifest.json` still says `1.0.0-beta2` regardless of the tag installed - the author does not bump it. Trust the HACS `installed_version`, not the manifest.

Configuration (Settings > Devices & Services > Add Integration > Dawarich):

| Field | Value | Why |
|---|---|---|
| Host / Port | `192.168.0.110` / `3005` | straight to the container. Going through `dawarich.homelabor.net` would send LAN traffic out to the VPS and back; `dawarich.lan` would drag in the mkcert CA |
| SSL / Verify SSL | off / on | plain HTTP on the LAN, so neither matters |
| Name | the person, e.g. `Norbi telefon` | **this becomes `device_id` on every point in Dawarich.** Left at the default, every family member's points arrive labelled `Dawarich`. The account statistics are per-API-key anyway, so naming the entry after the person is correct on both counts |
| Device tracker | `device_tracker.norbi_telo` | must be a GPS-source tracker; the integration logs a warning and sends nothing for router- or bluetooth-source trackers |
| API key | that person's own key | Dawarich > Settings > API Keys |

The API key is asked for on a **second** step, after the host is contacted - the first form has no key field at all, which reads like a bug and is not one.

Adding a family member later means a second config entry with their own API key and their own `device_tracker`, not a change to this one.

**Verifying it actually sends**, without waiting for someone to drive somewhere:

```bash
# ask the phone for a fresh fix
POST /api/services/notify/mobile_app_<device>  {"message": "request_location_update"}
```

Then `sensor.dawarich_tracker` should read `success`, and on the Dawarich side the newest point should carry the right label:

```ruby
Point.order(timestamp: :desc).first.raw_data.dig("properties", "device_id")
```

`sensor.dawarich_tracker` reads `unknown` until the first forward after every reload - that is the initial state, not an error.

### Other supported apps

Still available if the HA path is ever dropped: the official Dawarich apps for [Android](https://play.google.com/store/apps/details?id=app.dawarich.Dawarich) and iOS, a community Android client, OwnTracks, Overland, GPSLogger and PhoneTrack. Note the official Android app was rewritten and republished under a new package - the old one is now listed as **Dawarich (old)** and should not be installed.

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
| Map V2 blank in all browsers | `/maps_maplibre/styles/light.json` returns 404 - static style files in the Docker image are shadowed by the `/var/app/public` volume mount | Copy style files from the image to the host volume: `docker run --rm -v /srv/docker-data/dawarich-public:/target freikin/dawarich:latest sh -c "cp -r /var/app/public/maps_maplibre /target/"` - files persist across updates |
| `dawarich.lan` unreachable, `dawarich.homelabor.net` worked | LAN Caddyfile on LXC 110 never had a `dawarich.lan` block, and `APPLICATION_HOSTS` didn't include it either | Add `@dawarich host dawarich.lan { reverse_proxy 192.168.0.110:3005 }` to the Caddyfile, and append `,dawarich.lan` to `APPLICATION_HOSTS` |
| `/map/v2` 500s with `PG::UndefinedTable: relation "posters" does not exist` | Stack hadn't been redeployed in months (blocked by the LXC 105 DNS issue), so `freikin/dawarich:latest` jumped ~18 migrations ahead of the DB schema on the next pull | `docker exec dawarich_app bin/rails db:migrate` - all 18 pending migrations ran clean, no data loss |
| Family members' phones stop sending, silently | Colota froze or crashed and nothing reports that a tracker went quiet | Dropped the dedicated tracker app entirely; the HA Companion App is now the source, see Location Source above |
| HACS shows the integration but offers nothing to download | The repository has no stable release, only pre-release tags | Enable *Show beta versions* on the repository, then download the newest non-`-debug` tag |
| Points in Dawarich all labelled `device_id: Dawarich` | The config entry's **Name** field is sent as `device_id`, and its default is `Dawarich` | Reconfigure the entry with the person's name. The reconfigure form does not prefill the device tracker or API key - re-enter both or they are cleared |
