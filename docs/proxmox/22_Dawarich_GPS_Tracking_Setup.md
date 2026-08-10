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
- **Both services must set `entrypoint:` as well as `command:`.** The image's own entrypoint is a bare `bundle exec`, so a compose file that sets only `command:` gets a working server that never migrates. The scripts to name are `web-entrypoint.sh` and `sidekiq-entrypoint.sh`, both shipped in the image at `/usr/local/bin/`; the web one creates the database if absent, waits for it, runs `db:migrate`, `rake data:migrate` and `db:seed`, then `exec bundle exec "$@"` - which is why `command:` stays `bin/rails server -p 3000 -b ::` and the sidekiq one is just `sidekiq`, with no `bundle exec` prefix of its own
- Because of that, **migrations run on every start** and must not be run by hand. `start_period` on the healthcheck is 180 s to cover them
- **The first deploy after restoring the entrypoint is not a free container recreate.** Twenty-four data migrations that had never run went off at once, and one of them backfilled a column across every point in the database. Expect a burst: all five sidekiq workers busy, five postgres backends alongside them, and a load average of 6.78 on a 6-core host for about ten minutes. It is one-off - the migrations are recorded as done afterwards - but pick the moment rather than discovering it

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

### 2. Check that the migrations ran themselves

Nothing to do here, but worth confirming once: the entrypoint migrates before Puma starts, so the startup log is where the evidence is.

```bash
docker logs dawarich_app 2>&1 | head -20        # "Running migrations for all databases..."
docker logs dawarich_app 2>&1 | grep -c "migrated ("
```

**Do not run `db:migrate` by hand in a running container.** It updates the database while the live Rails process keeps its boot-time schema cache, and the app then 500s on any page touching a changed model - see the troubleshooting table. If a migration is genuinely outstanding, restart the container and let the entrypoint do it.

`db:migrate:status` only covers schema migrations. The data migrations (`rake data:migrate`) are a separate track it does not report on at all, so a clean status there proves less than it looks.

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
| Norbi telefon | `device_tracker.norbi_telo` | account 1 | `192.168.0.110:3005` |
| Ancsi telefon | `device_tracker.ancsi_telo` | account 2 | `192.168.0.110:3005` |
| Enci telefon | `device_tracker.enci_telo` | account 3 | `192.168.0.110:3005` |
| Enci tablet | `device_tracker.enci_tablet` | account 3 | `dawarich.homelabor.net:443` |

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

**The settled configuration**, stated once, because the sections below arrive at it through several corrections and reversals:

| Where | Setting | Value |
|---|---|---|
| Home Assistant | one automation per device, `mode: queued` | `to: not_home` held **30 s** → `force_on`; `from: not_home` held **2 min** → `force_off`; plus a guard branch, see below |
| Home Assistant | every zone radius | **100 m** or more, and a zone for every place anyone lingers |
| Companion App | High accuracy mode (master toggle) | **off** - the automation owns it |
| Companion App | zone constraint, bluetooth constraint, trigger range | **all empty** |
| Companion App | high accuracy interval | 5 s - set by the automation on every departure, see below |
| Companion App | Location sent | Exact |
| Companion App | diagnostic sensors *High accuracy mode* and *High accuracy update interval* | enabled |
| Android | battery usage for Home Assistant | Unrestricted |

The tablet has the same automation as the phones, added after the fact. It was left out at first on the theory that a mostly-stationary device gains nothing from dense GPS, and that turned out to be the wrong reason to leave it out: **the omission is what let it sit in high accuracy at home indefinitely**, because nothing existed to switch the mode back off after it had been enabled by hand during setup. An automation that only ever turns the mode *on* is optional; the branch that turns it off is not.

**What the cycle costs, on a device that has a working data connection.** Three numbers to expect, none of them a fault:

| | |
|---|---|
| Delay before dense tracking starts | roughly a minute: geofence exit in seconds, plus the 30 s hold, plus push delivery. At 50 km/h that is about 700 m of sparse track at the start of a journey |
| Passing *through* another zone en route | the mode switches off on entry and back on 30 s after leaving, leaving a short sparse stretch. A direct consequence of "any zone turns it off", and not worth complicating the design to avoid |
| Battery while the mode is on | about 10 %/h. Measured once, as 4 % over 23 minutes, so treat it as an order of magnitude rather than a figure |

That battery cost is the argument for zones, not against high accuracy: adding a zone for the place someone actually spends the day cut one person's out-of-zone time from 302 to 82 minutes, which is what makes the whole thing cheap.

**The full outbound cycle has still not been observed in the field.** The guard branch and the switch-off path are verified; what is not is that the mode reliably comes *on* shortly after a real departure. The one run on record predates every part of this design and measured the untouched baseline: 19 points over 56 minutes. On the next trip outside a zone, read `binary_sensor.<device>_high_accuracy_mode` for the moment it flipped and compare it against the departure - that single number is the one piece of evidence still missing, and it can only be guessed at from point density otherwise.

The command is Android-only, and its default interval is 5 seconds - which would mean about 720 points per hour per device landing in Dawarich. The interval was set to 60 s on each phone first, and only then were the automations created:

```yaml
action: notify.mobile_app_<device>
data:
  message: "command_high_accuracy_mode"
  data:
    command: "high_accuracy_set_update_interval"
    high_accuracy_update_interval: 60      # minimum 5
```

Each automation has state triggers on that device's `device_tracker` - `to: not_home` turns it on, `from: not_home` turns it off - and `mode: queued`, because rapid zone flapping must be processed in order rather than dropped. **`not_home` is exactly the right condition and not a rough approximation:** any named zone means parked somewhere, where dense tracking would burn battery to draw a dot.

**Both triggers are held, and neither hold was there originally.** `to: not_home` for **30 s**, `from: not_home` for **2 min**, and the away trigger carries no `not_from` filter. All three are corrections made in the field, each after a journey that behaved wrongly: see *The arrival flush replays the whole trip's zone history* and *Driving through a zone switched the mode back off* below. An unheld trigger on a `device_tracker` is the recurring mistake in this design - a tracker reports transitions that are real for a second and meaningless for the journey.

Verified by reading the automation trace rather than trusting that it triggered - "triggered" does not prove the intended branch ran:

```
07:47:49  trigger id=away  home -> not_home   steps: … choose/0/sequence/0   (on)
07:47:52  trigger/1                            steps: … choose/1/sequence/0   (off)
```

The commands sent are `force_on` / `force_off` rather than `turn_on` / `turn_off`. With no constraint configured the two are identical; the forced form is kept because if a constraint is ever added back, the plain form would obey it and refuse to switch on far from home - precisely where the dense track is wanted.

Two things to know about this design:

- **It originally only ever reacted to a zone transition,** so it could not correct a wrong starting state: high accuracy left on while the phone sat in a zone stayed on until a full leave-and-return cycle. That hole is now closed by the guard branch described below, which makes the design self-correcting rather than dependent on a manual `force_off` after any fiddling. (An earlier version of this document claimed the mode's state could not be observed from Home Assistant at all. That was wrong - the Companion App does expose it, see the settings table below.)
- **A dense burst of points does not mean high accuracy is stuck on.** An awake phone reports every 9-11 seconds on its own. Distinguish them by where the burst starts and when it stops, not by its density: check the spacing of the newest points against the time now.

**The zone exit is detected as late as the reporting is sparse - which is the point of the whole exercise, and it bites here too.** A run on 2026-08-09 started at 08:30 and the tracker only went `not_home` at **08:40**, despite a `home` zone radius of just 40 m. The phone had physically left within seconds; Home Assistant simply had no update saying so. So high accuracy engages roughly ten minutes into a run that starts from home, and the first stretch stays sparse.

#### The app-side zone constraint was tried, and removed

The obvious-looking fix is `High accuracy mode only when entering zone` plus `High accuracy mode trigger range for zone (meters)`, under **Settings > Companion App > Manage Sensors > Location Sensors > Background Location**. It was configured, measured, and taken back out. Three reasons, in order of importance:

**1. It is the inverse of what is wanted.** The constraint restricts high accuracy to a band *around* the selected zones. The goal here is dense tracking *away* from every zone. The Android app has no setting for that - there is an open [feature request](https://community.home-assistant.io/t/feature-request-high-accuracy-mode-when-not-in-zones/559845) asking for exactly it. So the Home Assistant automation is not a workaround for a missing configuration; it is the only mechanism that exists.

**2. It can revoke the automation's own command.** From the notification-commands documentation, `force_on` holds "until either `force_off` is sent, **or the constraints go from active to inactive**." That produces a failure which gets *more* likely as the setup gets better:

1. The phone leaves the 40 m home zone but is still inside the 500 m band, so the constraint switches high accuracy on by itself.
2. Reporting every 60 s, Home Assistant sees `not_home` within a minute rather than ten - and the automation sends `force_on`.
3. Minutes later the phone crosses 500 m. The constraint goes active → inactive, and that transition cancels the `force_on`. High accuracy is off again for the rest of the journey.

Without the constraint this cannot happen: `force_on` arrives with no constraint to transition. The trigger range speeds up detection, and the faster detection is exactly what lands the command inside the dangerous window. (Inferred from the quoted sentence, not reproduced deliberately.)

**3. It burns GPS where it is least wanted.** A 500 m band around every selected zone - the school, the shop, a relative's house - is precisely the stationary ground the whole design is trying to avoid. Each constrained zone also creates two geofences instead of one.

Removing it collapsed the automation back to two triggers and one command per branch. A five-minute delay with a re-assert, and `mode: restart` to stop an arrival queueing behind that delay, existed only to survive point 2 and went with it.

**The one thing the constraint was buying - fast exit detection - has a better root fix.** The `Location zone` sensor uses geofences, which report an exit in seconds regardless of how sparsely the phone is otherwise reporting. A ten-minute delay is not the design working as intended; it points at Android battery management throttling the app's background callbacks. Check that Home Assistant is set to **Unrestricted** battery usage and is not in the device's sleeping-apps list, rather than papering over it with a constraint.

#### The interval command is silently ignored unless the mode is on

Setting the interval from Home Assistant looks like it works and often does not:

```yaml
action: notify.mobile_app_<device>
data:
  message: "command_high_accuracy_mode"
  data:
    command: "high_accuracy_set_update_interval"
    high_accuracy_update_interval: 60
```

The service call returns HTTP 200, the phone receives it, and the value does not change. **The app only applies this command while high accuracy mode is actually running** - which mirrors its own UI, where the interval field is greyed out until the master toggle is on. Sent with the mode off, it is accepted and dropped without a word.

One phone ended up on 60 s and another stayed on the 5 s default from the same batch of commands, and the difference went unnoticed until the diagnostic sensor was enabled and read them back. The working sequence:

```
force_on  →  high_accuracy_set_update_interval  →  force_off
```

The interval survives the mode being switched off again, so this is a one-off per phone. Verify with `sensor.<device>_high_accuracy_update_interval`; if the reading looks stale, `command_update_sensors` forces the app to report immediately.

**HTTP 200 on a notify command means Home Assistant handed it to the push service - nothing more.** It is not evidence the phone acted on it, and for a fire-and-forget command there is no error path back. The only proof is a sensor that reads the value back, which is the argument for enabling those two diagnostic sensors on every phone rather than just one. `command_update_sensors` is the cheap liveness check: if the battery sensor's timestamp jumps immediately afterwards, the phone is receiving commands and any failure is the command's own, not delivery.

**So the automation sets it, rather than a person doing it once per phone.** The away branch sends `force_on`, waits five seconds, then sends the interval - at which point the mode is running, so the command lands. That also solves the delivery problem, because a phone that is leaving a zone is by definition awake and reporting, whereas one sitting on a table at midday may ignore commands entirely. During this work one phone stopped acknowledging anything for twenty minutes: `command_update_sensors` did not move its battery timestamp, so the commands were not being delivered at all, and no amount of retrying would have helped.

The manual `force_on → set → force_off` sequence is still the way to fix a phone immediately, but it only works while that phone is awake.

#### Choosing the interval, and why zones decide it

The interval is **5 s** - the app's minimum, and the densest track it can produce. Getting there was not a matter of taste; it needed the zone list fixed first.

The battery argument that originally pushed this to 60 s does not hold. The documentation describes high accuracy mode as "permanent usage of GPS", so the radio is held open for as long as the mode is on, however rarely it reports. The interval buys track detail and costs disk. Metres between consecutive points:

| | **5 s** | 10 s | 30 s | 60 s |
|---|---|---|---|---|
| walking, 5 km/h | **6 m** | 14 m | 41 m | 83 m |
| running, 11 km/h | **15 m** | 30 m | 91 m | 183 m |
| city driving, 50 km/h | **69 m** | 139 m | 416 m | 833 m |
| motorway, 130 km/h | **180 m** | 361 m | 1083 m | 2166 m |

The cost is real and was measured rather than assumed: the `points` table holds 74 291 rows in 116 MB, about 1.6 kB each including indexes and the raw JSON. LXC 100's root has 12 GB free, on the LVM thin pool that has run short before.

**What decided it was measuring how long anyone is actually outside a zone**, from `device_tracker` history rather than from anyone's impression of it:

| | before zones were fixed | after |
|---|---|---|
| Ancsi | 410 min/day | **99** |
| Norbi | 348 min/day | **82** |
| Enci | 61 min/day | **54** |
| **total** | **13.7 h/day** | **3.9 h/day** |
| cost at 5 s | 5.9 GB/year | **1.68 GB/year** |

The intuition being tested was "we are rarely outside a zone". The measurement said otherwise - nearly seven hours a day each for two people - and the reason was that the places they spend those hours had no zones. One was a few hundred metres from home; another was a single out-of-town location holding **67 % of that person's remaining away time**. Adding zones for them cut the total by 72 %, which is worth far more than any interval tuning: it stops the GPS running for hours while somebody sits still, keeps stationary clusters out of the tracks, *and* is what makes 5 s affordable.

Find them with a time-weighted count over `device_tracker` history - not a sample count, which is biased towards moving periods and pointed at the wrong places here:

```python
# for each not_home interval, if its coordinates fall in no zone,
# add its duration to a bucket keyed on the rounded position
buckets[(round(lat, 3), round(lon, 3))] += (next_ts - ts).total_seconds()
```

Two details worth copying: derive each zone's centre from the **mean of the samples near it**, since coordinates rounded to three decimals are only accurate to about 100 m and would put the circle off centre; and size the radius from the observed spread of those samples, not from a default - two of the new ones needed 150 m and 200 m, while 100 m was right for the rest.

#### Every zone was below Android's minimum geofence radius (2026-08-09)

The ten-minute delay was chased through sparse reporting and battery management before the actual cause turned up: **all six zones were far below the radius Android needs for reliable geofencing.**

| Zone | Was | Now |
|---|---|---|
| home | 40 m | 100 m |
| five others | 25-83 m | 100 m |

[Android's geofencing guidance](https://developer.android.com/develop/sensors-and-location/location/geofencing) puts the minimum at **100-150 m**, "to account for the location accuracy of typical Wi-Fi networks, and also to reduce device power consumption". Home Assistant's own default for the home zone is 100 m. Below that, exit events are delayed or missed outright - which is exactly what a 40 m home zone produced.

This matters more now than it did before. When the only consequence was a late `not_home` on the map, ten minutes was cosmetic. Now that the same transition is what switches high accuracy on, those ten minutes are missing from the track.

Checked first, and worth checking before any similar change: **nothing else referenced the zones.** `grep` over `automations.yaml` found only this document's own three automations (`to: not_home` / `from: not_home`), and no script or scene mentioned a zone at all. Enlarging them therefore could not break a light or a presence automation.

The home zone is not an ordinary zone - its radius lives in core config, so it takes `config/core/update` over the websocket API rather than `zone/update`:

```python
await call({"type": "zone/list"})                                    # the other five
await call({"type": "zone/update", "zone_id": z["id"], "radius": 100})
await call({"type": "config/core/update", "radius": 100})            # home
```

No device changed zone as a result, so the enlargement produced no spurious enter/exit events. The phones re-register their geofences when they next sync the zone list; opening the app once on each is the quick way to be sure.

**Turning the app's own `High accuracy mode` toggle on is not the answer either.** It is the master switch, so with no constraint it means permanently on: GPS held open at home, a permanent notification, and a point every 60 s into Dawarich while sitting still. That toggle is the automation's to own, and its resting value is off. It was found on once during this work - `binary_sensor.<device>_high_accuracy_mode` reading `on` while the tracker said `home` is what caught it.

#### The arrival flush replays the whole trip's zone history in seconds (2026-08-09)

A phone that has been offline hands its entire backlog to Home Assistant the moment it reconnects. Home Assistant recomputes the zone for every point in that backlog, so **the zone history of the whole journey is replayed at upload speed**, in the wrong order. One arrival produced five states in four seconds:

```
20:34:21.809  not_home
20:34:25.331  <a zone 1.4 km away>
20:34:25.540  not_home
20:34:25.792  home
```

The automation, correctly set to `mode: queued`, dutifully processed all of it: `force_on`, `force_off`, `force_on`, `force_off` inside four seconds. The device received them roughly ten minutes later and **applied `force_on` last** - `binary_sensor.<device>_high_accuracy_mode` read `on` while the tracker read `home`. That is the whole failure: the server's ordering is not the device's ordering, and four commands four seconds apart is an invitation to find out.

Three changes, in the order they matter:

**1. Hold the away trigger for 30 s.** A replay never keeps `not_home` continuously for half a minute, so the flapping stops producing commands at all. The cost is 30 s of sparse track at the start of a real journey, against 100 m zones that already take longer than that to exit.

```yaml
triggers:
  - trigger: state
    entity_id: device_tracker.<device>
    to: not_home
    for: {seconds: 30}
    id: away
```

**2. Drop `not_from: [unknown, unavailable]` from the away trigger.** It was there to stop a phone dropping off the network being mistaken for a journey, and it silenced the exact transition where the command is most needed: an app restarting *while away* goes `unavailable` → `not_home`, and the filter threw that away, leaving the rest of the trip sparse. The filter is unnecessary anyway once the trigger is held for 30 s, and it cannot misfire at home, because a phone reconnecting at home transitions to `home`, not to `not_home`. (`not_to` on the *back* trigger stays: turning the mode off on a dropout is harmless.)

**3. Add a guard branch that switches the mode off whenever it is on inside a zone.** This is the one that makes the design self-correcting, and it catches every cause at once - a late or reordered push, a manually flipped toggle, an app restart:

```yaml
  - trigger: state
    entity_id: binary_sensor.<device>_high_accuracy_mode
    to: "on"
    for: {minutes: 2}
    id: stuck
# and, in the choose:
  - conditions:
      - {condition: trigger, id: stuck}
      - condition: not                       # i.e. the device is in some zone
        conditions:
          - condition: state
            entity_id: device_tracker.<device>
            state: [not_home, unknown, unavailable]
    sequence: [ … force_off … ]
```

Verified live rather than assumed: `force_on` sent deliberately to a phone sitting at home at 21:11:08, the sensor confirmed `on` at 21:11:23, and the guard switched it off at 21:13:23.

#### A device with no data connection cannot be commanded (2026-08-09)

The whole design rests on a push command reaching the device. One family phone had exhausted its mobile data allowance, and for the 23 minutes it was away it **sent nothing and received nothing**. The independent proof is the battery sensor, which reports about every 15 minutes: it skipped both of its slots inside that window and resumed in the same second as the location backlog, so the outage was the entire app-to-server channel and not the location subsystem.

Two consequences, and only one of them is fixable here:

- **High accuracy never engages during the trip,** because the `force_on` cannot be delivered. It is delivered on arrival instead, which is what strands the mode on at home. The guard branch above is the answer to that half.
- **The timestamps of the whole trip collapse.** The Companion App hands queued points to Home Assistant with no fix time, so they are stored at receipt time. Confirmed in Dawarich's own database, not just in the Home Assistant recorder: about 200 points covering a 23-minute walk all carry timestamps inside a three-second window, out of order. **The route survives, the clock does not.** Nothing on the server can repair this; `mobile_app`'s device tracker has no timestamp field to carry a fix time.

If real times matter more than the Home Assistant integration does, a logger that posts straight to Dawarich keeps them, because the payload carries the timestamp from the device: GPSLogger to `/api/v1/owntracks/points` with `"tst": "%TIMESTAMP"`, and its *Send on Wi-Fi only* toggle suits a device that has no mobile data at all.

**A wifi-only device is the permanent version of this, and it fails more quietly.** Its tracker never even reaches `not_home` while away, because no update arrives to say it left, so the away branch never fires and there is nothing in the logs to look at. Expect presence plus a coarse, time-collapsed track from such a device, and let a phone travelling alongside it carry the real one.

#### Driving through a zone switched the mode back off (2026-08-10)

The first journey after the guard branch went in looked, from the phone, like the mode simply never started. The history says otherwise: it started twice, and was switched off twice, both times by the automation itself.

```
05:18:42  not_home                 departure finally registers
05:20:05  high accuracy  on        30 s hold plus push, as designed
05:22:10  -> a 100 m zone          driven through, in it for about 20 s
05:24:54  high accuracy  off       the back trigger, delivered late

05:33:49  not_home
05:34:21  high accuracy  on        2 s after the trigger this time
05:37:27  -> a 150 m zone          driven through
05:37:28  high accuracy  off
```

**The away trigger was given a 30 s hold and the back trigger was not, and only half the problem was fixed.** `from: not_home` fires the instant the tracker reports any named zone, and a car crossing a 150 m circle is inside it for a few seconds. Every zone on a route is therefore a switch that turns dense tracking off for the rest of the journey, and the further the route runs past known places, the worse it gets.

The fix is the same instrument, applied symmetrically:

```yaml
  - trigger: state
    entity_id: device_tracker.<device>
    from: not_home
    not_to: [unknown, unavailable]
    for: {minutes: 2}
    id: back
```

Two minutes because that is what already separates *arrived* from *passed through* elsewhere in this design: it matches the guard branch's own hold. A pass-through never satisfies it, the trigger is cancelled when the tracker leaves the zone again, and a genuine arrival pays two extra minutes of dense tracking, which is nothing against a journey.

One narrow hole is left deliberately. If the guard branch's own trigger comes due at the exact moment the device is mid-pass-through, its condition sees a zone and switches the mode off. That window is a couple of seconds wide, opens at most once per journey, and closes itself on the next `not_home`, which is 30 s later. Widening the guard to exclude it would cost more than it saves.

#### The departure is invisible until something makes the phone report (2026-08-10)

Under the trace above sits a second, independent fault, and it is the one that is actually felt: **the phone left home at 05:12 and Home Assistant did not know until 05:18:42, when the app was opened by hand.** The command path was never the problem. The second departure that morning switched the mode on 2 s after its trigger, with nothing touched. Opening the app did not deliver a command, it delivered the *departure*, and until that arrived the automation had nothing to fire on.

The cause is one sentence in *Every zone was below Android's minimum geofence radius*, written the day before and never acted on: the phones re-register their geofences when they next sync the zone list. The zones were enlarged from 40 m to 100 m on 2026-08-09; until an app is opened, that device is still watching the old circle, at the radius Android was documented as unreliable at. **Enlarging a zone server-side is half a change. The other half happens on each device, and nothing reports that it is outstanding.**

So after any zone edit, open the Companion App once on every tracked device, and check that Home Assistant's battery usage is **Unrestricted** while there.

What would have settled this in one glance is a sensor that is off by default: **Last update trigger**, in *Manage Sensors > Location*. It labels each update with its cause, so `Geofence Exit` against `Manual` distinguishes a working geofence from a user opening the app, which is exactly the ambiguity that cost the morning. Enable it alongside the two high accuracy diagnostics.

#### The rest of the location settings, and what each one costs

Verified on the running phone:

| Setting | Value | Verdict |
|---|---|---|
| Single accurate location | enabled, *Get location on sensor update* on, min time 60000 ms | correct - this is what `request_location_update` uses, throttled to once a minute |
| Location zone | enabled | correct - this drives the automation's triggers |
| Background location | enabled | correct - the main feed into Dawarich |
| High accuracy mode (app toggle) | **off** | the automation owns it. On means permanently on |
| High accuracy interval | 60 s | confirmed by `sensor.<device>_high_accuracy_update_interval` |
| Bluetooth constraint | none, and the "zone **and** bluetooth" toggle off | correct - requiring both would rarely be satisfied |
| Zone constraint | **none selected** | deliberately empty - see above, it is the inverse of this goal |
| Location sent | *Exact* | required, a coarse fix would ruin the track |
| **Minimum accuracy** | **80 m** | fixes worse than this are dropped and never reach Home Assistant at all. The run's points ranged 5-72 m so they passed, but anything filtered is invisible - it looks like a gap, not like a rejection. The documentation's own advice is to raise the number when reports appear to be skipped |

Enable the two diagnostic sensors, **High accuracy mode** and **High accuracy update interval**, in *Manage Sensors > Location*. They are off by default and they are what turns "I sent the command" into "the mode is on at 60 s" - `binary_sensor.<device>_high_accuracy_mode` and `sensor.<device>_high_accuracy_update_interval`. Without them the only evidence is the density of incoming points, which is ambiguous.

### Open: points are not getting a country assigned

After the backfill above finished, roughly a thousand points still had `country_id` null, and **the number keeps climbing as new points arrive** - so this is not leftover work from the migration, it is that incoming points are not being assigned a country at all:

```
2026-04-01     976    the initial import
2024-08-03      16
2026-08-09     126    and rising, today's live points
```

`sensor.dawarich_total_reverse_geocoded_points` also sits at 0, which points at reverse geocoding never having been configured as the common cause. Cosmetic - it affects country statistics only, not the tracks or the map - and untouched so far.

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
| White page on sign in | Migrations not run | Restart the app container and let `web-entrypoint.sh` migrate. Historically this was fixed with a manual `docker exec dawarich_app bin/rails db:migrate`, which is what later caused the stale-schema-cache fault two rows down |
| No default login | No demo user exists | Create user via `rails runner` command above |
| Colota 404 on test connection | Base URL entered instead of full endpoint | Use full `/api/v1/owntracks/points?api_key=...` URL |
| `dawarich.homelabor.net` returns 503 / no available server | `APPLICATION_PROTOCOL: https` causes Rails force_ssl redirect loop through Pangolin | Set `APPLICATION_PROTOCOL: http` - Pangolin handles TLS |
| Map V2 blank in all browsers | `/maps_maplibre/styles/light.json` returns 404 - static style files in the Docker image are shadowed by the `/var/app/public` volume mount | Copy style files from the image to the host volume: `docker run --rm -v /srv/docker-data/dawarich-public:/target freikin/dawarich:latest sh -c "cp -r /var/app/public/maps_maplibre /target/"` - files persist across updates |
| `dawarich.lan` unreachable, `dawarich.homelabor.net` worked | LAN Caddyfile on LXC 110 never had a `dawarich.lan` block, and `APPLICATION_HOSTS` didn't include it either | Add `@dawarich host dawarich.lan { reverse_proxy 192.168.0.110:3005 }` to the Caddyfile, and append `,dawarich.lan` to `APPLICATION_HOSTS` |
| `/map/v2` 500s with `PG::UndefinedTable: relation "posters" does not exist` | **The compose never set `entrypoint:`**, so the image's default `bundle exec` ran and the shipped `web-entrypoint.sh` - which migrates before starting Rails - was skipped. Migrations therefore only ever ran by hand, and 18 of them piled up unnoticed | Root fix: `entrypoint: web-entrypoint.sh` on `dawarich_app` and `entrypoint: sidekiq-entrypoint.sh` on `dawarich_sidekiq`, matching upstream. Every start now runs `db:migrate`, `data:migrate` and `db:seed` before Puma boots, so the image can never be ahead of the schema. **`rake data:migrate` is a separate track and `db:migrate:status` says nothing about it** - 24 data migrations were still pending here while schema migrations reported zero outstanding, and they only ran once the entrypoint was restored |
| Proxmox CPU at 60-70 % and load near 7 for several minutes, starting right after a Dawarich deploy | `DataMigrations::SetPointsCountryIdsJob` backfilling `country_id` over the whole points table - about 40 000 jobs in three minutes here, against 79 865 points. It is a data migration that had never run before, released by restoring the entrypoint | Nothing. Wait it out and confirm it is finishing: `select count(*) from points where country_id is null;` should fall steadily, and `docker stats dawarich_sidekiq` drops from ~66 % to under 1 % when it is done. It cannot repeat - the migration is marked as run |
| Every page works except the map, which 500s with `Undeclared attribute type for enum ... Enums must be backed by a database column` | **Rails caches the schema at boot.** Migrations run with `docker exec` inside an *already running* container update the database but not the live Puma process, so models keep their old attribute set. The column exists, `db:migrate:status` shows nothing pending, and a fresh `bin/rails runner` sees the enum fine - only the long-lived web process is wrong | Restart the app container. Better, do not migrate by hand at all: with the entrypoint above, migrations always run before the server starts and this state cannot arise |
| Family members' phones stop sending, silently | Colota froze or crashed and nothing reports that a tracker went quiet | Dropped the dedicated tracker app entirely; the HA Companion App is now the source, see Location Source above |
| HACS shows the integration but offers nothing to download | The repository has no stable release, only pre-release tags | Enable *Show beta versions* on the repository, then download the newest non-`-debug` tag |
| Points in Dawarich all labelled `device_id: Dawarich` | The config entry's **Name** field is sent as `device_id`, and its default is `Dawarich` | Reconfigure the entry with the person's name. The reconfigure form does not prefill the device tracker or API key - re-enter both or they are cleared |
| Second device for the same person aborts with `already_configured` | The integration treats host + API key as the uniqueness key | Point that entry at the same server by another address - `dawarich.homelabor.net:443` with SSL on. `dawarich.lan` will not work, HA cannot resolve `.lan` |
| A tracker sensor sits at `unknown` and never sends | No state-change event has fired for that `device_tracker` since the entry was created | `notify.mobile_app_<device>` with `request_location_update`, then wait. `unknown` is the initial state, not an error - it says nothing has been forwarded yet, not that anything is broken |
| High accuracy mode runs while the device is sitting in a zone | Either no automation exists for that device, or a `force_on` from an earlier zone transition was delivered late and out of order, or the app's master toggle was switched on by hand | The guard branch on `binary_sensor.<device>_high_accuracy_mode` now clears all three within 2 minutes. Every tracked device needs the automation, including ones that never travel |
| The mode never switches on during a whole journey | The away trigger was filtered with `not_from: [unknown, unavailable]` and the app restarted while away, or the device has no data connection and the push was never delivered | Remove the filter. If the device has no mobile data, the command cannot arrive at all - see *A device with no data connection cannot be commanded* |
| The mode switches on at departure, then goes off partway through the journey and stays off | The route passed through a named zone. Without a hold, `from: not_home` fires on a few seconds inside a 150 m circle | Hold the back trigger for 2 minutes. Confirm with the `device_tracker` history: a zone name appearing for one or two samples, followed by `force_off` |
| The mode only starts after the Companion App is opened by hand | Home Assistant did not know the device had left. The phone is still watching a stale geofence, typically because the zones were edited server-side and that device has not synced since | Open the app once on every tracked device after any zone edit, and set the app's battery usage to Unrestricted. Enable the **Last update trigger** sensor to tell `Geofence Exit` from `Manual` next time |
| An entire journey appears in Dawarich at one timestamp, points out of order | The device was offline and flushed its backlog on arrival; Home Assistant stores queued points at receipt time because `mobile_app` carries no fix time | Not repairable server-side. Use a logger that posts to Dawarich directly with `"tst": "%TIMESTAMP"` if the times matter |
| That sensor is *still* `unknown` after hours, and `request_location_update` gets no response | The device is not producing location updates at all. Check `last_updated` on the `device_tracker` itself: if it is hours old, the problem is on the phone, not in the integration | In the Companion App: background location permission (Android 13+ needs "Allow all the time" as a separate grant), **Manage sensors > Location** toggles, and whether battery optimisation is killing the app. `device_tracker.enci_tablet` was in this state on 2026-08-09, last updated 05:47 with nothing an hour and a half later |
