# Leak Sensor Water Alert - Automation Design

**Date:** 2026-05-29
**Status:** Approved

## Overview

Two Home Assistant automations that alert when the leak sensor detects water. Repeating push notifications every 10 minutes until the sensor clears, plus a persistent dashboard notification. An "all clear" notification is sent when the sensor returns to dry state.

## Entities

| Entity | Purpose |
|---|---|
| `binary_sensor.leak_sensor_water_leak` | Trigger sensor (`on` = wet, `off` = dry) |
| `notify.mobile_app_norbi_telo` | Push target - Norbi |
| `notify.mobile_app_ancsi_telo` | Push target - Ancsi |
| Persistent notification ID: `leak_sensor_alert` | Dashboard alert, fixed ID for dismissal |

## Automations

### Automation 1: Vízérzékelő - Riasztás

**Trigger:** `binary_sensor.leak_sensor_water_leak` → `on`

**Mode:** `single` + `max_exceeded: silent`
- Only one loop runs at a time
- If sensor somehow re-triggers while loop is running, the new trigger is silently ignored (loop already running and watching the sensor)

**Actions:**
1. Create persistent notification (`notification_id: leak_sensor_alert`) - stays on HA dashboard until manually dismissed or automation #2 clears it
2. `repeat: while: sensor = on`
   - Send push to `norbi_telo` with `tag: leak_sensor_alert`
   - Send push to `ancsi_telo` with `tag: leak_sensor_alert`
   - Delay 10 minutes

The `tag` on mobile notifications means each repeat updates the existing notification rather than stacking new ones.

The repeat fires immediately on first iteration (no leading delay), then waits 10 minutes before each subsequent send. Loop exits automatically when the sensor returns to `off`.

### Automation 2: Vízérzékelő - Helyreállt

**Trigger:** `binary_sensor.leak_sensor_water_leak` from `on` → `off`

**Mode:** `single`

**Actions:**
1. Send "OK" push to `norbi_telo` with `tag: leak_sensor_alert` - replaces the alert notification on the phone
2. Send "OK" push to `ancsi_telo` with same tag
3. `persistent_notification.dismiss` with `notification_id: leak_sensor_alert`

## Notification Content

| Event | Title | Message |
|---|---|---|
| Water detected | ⚠️ Vízérzékelő riasztás | Víz észlelve! Ellenőrizd azonnal! |
| Sensor cleared | ✅ Vízérzékelő - OK | A vízérzékelő normál állapotba tért vissza. |

## Implementation Notes

- Automations are created via the HA config API (not YAML file editing), so they appear in the UI editor and validate on save
- Both automations use `entity_id` (not `device_id`) for resilience against device re-pairing
- The `tag` field is nested under a second `data:` key in the notify service call (HA companion app convention)
- No time conditions - the alert fires any time of day or night, as water damage is always urgent
