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

### One entry per device, and the duplicate check that gets in the way

Each person gets their own config entry with their own API key and their own `device_tracker`. Four are live:

| Entry | Device tracker | Dawarich account | Host |
|---|---|---|---|
| Norbi telefon | `device_tracker.norbi_telo` | `xnex88@` | `192.168.0.110:3005` |
| Ancsi telefon | `device_tracker.ancsi_telo` | `bertalananiko@` | `192.168.0.110:3005` |
| Enci telefon | `device_tracker.enci_telo` | `henczeniko@` | `192.168.0.110:3005` |
| Enci tablet | `device_tracker.enci_tablet` | `henczeniko@` | `dawarich.homelabor.net:443` |

The first three were confirmed sending, per account rather than in aggregate - points arriving under the right user with the right `device_id`. **The tablet has not forwarded anything yet**: its entry loads and reads the server fine, but the tablet itself stopped producing location updates, so there is nothing to relay. See the last row of the troubleshooting table.

The last row is not a mistake. **The integration rejects a new entry when host *and* API key both match an existing one** (`_async_abort_entries_match` on `CONF_HOST` + `CONF_API_KEY`), so a second device belonging to the same Dawarich user aborts with `already_configured`. The fix is to reach the same server by a different address: the public URL works, needs no infrastructure change, and costs only that the tablet's points travel out to the VPS and back. `dawarich.lan` is not an option here - **Home Assistant cannot resolve `.lan` at all** (`NXDOMAIN` from its Supervisor DNS), even though every LXC can.

Which account belongs to which person is worth pinning down before configuring, not after: Dawarich leaves `first_name`/`last_name` `nil`, the family record carries no member names, and older points have no `device_id`, so the database cannot tell you. Sending one person's live location into another person's account is not something to guess at.

### How often each device actually reports

The Companion App reports for zone presence, so the rate varies enormously by device. Measured over 12 hours, counting attribute-only updates (which is what the integration forwards on - plain state history hides them, since the *state* only changes when a zone boundary is crossed):

| Device | Updates / 12 h |
|---|---|
| `norbi_telo` | 494 |
| `enci_telo` | 360 |
| `enci_tablet` | 54 |

A phone produces roughly one point every 1.5-2 minutes averaged over a day, but the rate is bursty rather than steady - an awake phone was measured reporting every 9-11 seconds for minutes at a time, with nothing in between. That is the concrete shape of the "sparser than a dedicated tracker" trade-off, and it is also why a mostly-stationary tablet writing into the same account as its owner's phone is tolerable rather than ruinous. If the stationary clusters ever become annoying, they can be deleted by `device_id`.

**Do not read the tablet's 54 as "one every 13 minutes."** That average hides long silences: on the day of setup the tablet last updated at 05:47 and had still produced nothing 1.5 hours later, ignoring a `request_location_update` in between. A daily average is the wrong statistic for a device that reports in bursts and then sleeps.

To count these properly, ask the history API **without** `minimal_response`:

```
GET /api/history/period/<iso8601>?filter_entity_id=device_tracker.<device>
```

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

### Updating the integration

HACS notices a new tag on its own and flips `update.dawarich_update` to `on`; the update surfaces under Settings > Updates or in HACS itself. The entity supports `INSTALL`, `SPECIFIC_VERSION`, `PROGRESS` and `RELEASE_NOTES` - but **not** `BACKUP`, so nothing is snapshotted before the files are replaced.

```yaml
service: update.install
target: {entity_id: update.dawarich_update}
# data: {version: "1.0.0-beta7"}   # a specific tag, also used to roll back

# a custom integration is not live-reloaded - the restart is mandatory
service: homeassistant.restart
```

**Read the version before installing every single time.** Pre-release is switched on for this repository (it has to be - there is no stable tag at all), and the consequence is that *every* new tag is offered, `-debug` builds included. The rule is simply: anything ending in `-debug` gets skipped.

```yaml
service: update.skip
target: {entity_id: update.dawarich_update}
```

The moment the author ships a real stable release, turn `switch.dawarich_pre_release` off. HACS then only offers stable tags and this whole hazard disappears.

If an update misbehaves, `update.install` with an explicit older `version` rolls back, and VM 101 is in the nightly vzdump set as a second line of defence.

### High accuracy mode, driven by zone (2026-08-09)

The Companion App reports too sparsely to draw a clean line while travelling, and its high accuracy mode is the fix - but running it permanently is not, because it holds GPS open continuously and shows a **permanent notification the user cannot dismiss** (an Android system requirement, not an app choice). So it is switched on only outside every zone, by one automation per phone: `automation.high_accuracy_<person>_zonan_kivul`.

The command is Android-only, and its default interval is 5 seconds - which would mean about 720 points per hour per device landing in Dawarich. The interval was set to 60 s on each phone first, and only then were the automations created:

```yaml
action: notify.mobile_app_<device>
data:
  message: "command_high_accuracy_mode"
  data:
    command: "high_accuracy_set_update_interval"
    high_accuracy_update_interval: 60      # minimum 5
```

Each automation has two state triggers on the person's `device_tracker` - `to: not_home` turns it on, `from: not_home` turns it off - with `not_from`/`not_to` excluding `unknown` and `unavailable`, so a phone dropping off the network is not mistaken for a journey. `mode: queued`, because rapid zone flapping must be processed in order rather than dropped. **`not_home` is exactly the right condition and not a rough approximation:** any named zone (`Apa`, `Suli`, `Uzlet`, …) means parked somewhere, where dense tracking would burn battery to draw a dot.

Verified by reading the automation trace rather than trusting that it triggered - "triggered" does not prove the intended branch ran:

```
07:47:49  trigger id=away  home -> not_home   steps: … choose/0/sequence/0   (on)
07:47:52  trigger/1                            steps: … choose/1/sequence/0   (off)
```

The commands sent are `force_on` / `force_off` rather than `turn_on` / `turn_off`. With no zone or bluetooth constraint configured in the app the two are identical, but if a constraint is ever added, the plain form obeys it and would refuse to switch on far from home - which is precisely where the dense track is wanted.

Two things to know about this design:

- **It only ever reacts to a zone transition,** so it cannot correct a wrong starting state. If high accuracy is somehow left on while the phone sits in a zone, nothing turns it off until a full leave-and-return cycle. A one-off `force_off` to each phone establishes the baseline the automation assumes; do that after any manual fiddling. (An earlier version of this document claimed the mode's state could not be observed from Home Assistant at all. That was wrong - the Companion App does expose it, see the settings table below.)
- **A dense burst of points does not mean high accuracy is stuck on.** An awake phone reports every 9-11 seconds on its own. Distinguish them by where the burst starts and when it stops, not by its density: check the spacing of the newest points against the time now.

**The zone exit is detected as late as the reporting is sparse - which is the point of the whole exercise, and it bites here too.** A run on 2026-08-09 started at 08:30 and the tracker only went `not_home` at **08:40**, despite a `home` zone radius of just 40 m. The phone had physically left within seconds; Home Assistant simply had no update saying so. So high accuracy engages roughly ten minutes into a run that starts from home, and the first stretch stays sparse.

The app-side fix is `High accuracy mode only when entering zone` = *Home* plus `High accuracy mode trigger range for zone (meters)` = ~500, under **Settings > Companion App > Manage Sensors > Location Sensors > Background Location**. Note what that setting actually does, because the name suggests otherwise: it draws an *expanded* boundary around the zone and runs high accuracy between that boundary and the zone edge, deactivating on entry. It is designed for precise **arrival** detection. It happens to cover departure too, since the band is the same on the way out - but do not reach for it expecting a "switch on before leaving" feature, because that is not what it is.

Worth measuring before configuring: the automation alone already covered 46 of that run's 56 minutes. The trigger range buys the remaining ten, at the cost of per-phone setup and GPS running whenever anyone is within 500 m of home. It is worth it only on a phone that actually goes running.

#### The zone constraint can cancel the automation's own command

Once a zone constraint exists, the notification command changes meaning. From the notification-commands documentation: `force_on` "will make high accuracy mode active until either `force_off` is sent, **or the constraints go from active to inactive**."

That sets up a failure that gets *more* likely as the setup gets better:

1. The phone leaves the 40 m home zone but is still inside the 500 m band, so the constraint switches high accuracy on by itself.
2. Reporting every 60 s, Home Assistant now sees `not_home` within a minute instead of ten - and the automation sends `force_on`.
3. A few minutes later the phone crosses 500 m. The constraint goes active → inactive, and that transition **cancels the `force_on`**. High accuracy switches off for the rest of the run.

Without the constraint this cannot happen, because `force_on` arrives roughly ten minutes in, already outside every band, with no transition left to cancel it. The trigger range speeds up detection, and the faster detection is exactly what lands the command inside the dangerous window.

The automation therefore sends `force_on`, waits five minutes, re-checks that the phone is still `not_home`, and sends `force_on` again - by then it is well beyond every band, so no transition remains that could revoke it. Its mode is `restart` rather than `queued` for the same reason: arriving home must cancel a run that is still sleeping in that delay, instead of queueing the `force_off` behind it.

This behaviour is inferred from the sentence quoted above rather than observed - the documentation says nothing more about constraints during a forced state, and the transition has not been reproduced deliberately. Treat the re-assert as cheap insurance, not as a fix for a confirmed bug.

#### The rest of the location settings, and what each one costs

Verified on the running phone:

| Setting | Value | Verdict |
|---|---|---|
| Single accurate location | enabled, *Get location on sensor update* on, min time 60000 ms | correct - this is what `request_location_update` uses, throttled to once a minute |
| Location zone | enabled | correct - this drives the automation's triggers |
| Background location | enabled | correct - the main feed into Dawarich |
| High accuracy mode (app toggle) | **off** | correct - the automation owns it |
| High accuracy interval | 60 s | confirmed by `sensor.<device>_high_accuracy_update_interval` |
| Bluetooth constraint | none, and the "zone **and** bluetooth" toggle off | correct - requiring both would rarely be satisfied |
| Zone constraint | all six zones | works, but a 500 m band around the shop and the school costs battery for nothing. Narrowing it to `zone.home` is the tidier choice |
| Location sent | *Exact* | required, a coarse fix would ruin the track |
| **Minimum accuracy** | **80 m** | fixes worse than this are dropped and never reach Home Assistant at all. The run's points ranged 5-72 m so they passed, but anything filtered is invisible - it looks like a gap, not like a rejection. The documentation's own advice is to raise the number when reports appear to be skipped |

Enable the two diagnostic sensors, **High accuracy mode** and **High accuracy update interval**, in *Manage Sensors > Location*. They are off by default and they are what turns "I sent the command" into "the mode is on at 60 s" - `binary_sensor.<device>_high_accuracy_mode` and `sensor.<device>_high_accuracy_update_interval`. Without them the only evidence is the density of incoming points, which is ambiguous.

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
| Second device for the same person aborts with `already_configured` | The integration treats host + API key as the uniqueness key | Point that entry at the same server by another address - `dawarich.homelabor.net:443` with SSL on. `dawarich.lan` will not work, HA cannot resolve `.lan` |
| A tracker sensor sits at `unknown` and never sends | No state-change event has fired for that `device_tracker` since the entry was created | `notify.mobile_app_<device>` with `request_location_update`, then wait. `unknown` is the initial state, not an error - it says nothing has been forwarded yet, not that anything is broken |
| That sensor is *still* `unknown` after hours, and `request_location_update` gets no response | The device is not producing location updates at all. Check `last_updated` on the `device_tracker` itself: if it is hours old, the problem is on the phone, not in the integration | In the Companion App: background location permission (Android 13+ needs "Allow all the time" as a separate grant), **Manage sensors > Location** toggles, and whether battery optimisation is killing the app. `device_tracker.enci_tablet` was in this state on 2026-08-09, last updated 05:47 with nothing an hour and a half later |
