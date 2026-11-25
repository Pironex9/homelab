# Stuck PIR Sensor: Hallway Lights On for Hours, and an MQTT Watchdog

**Date:** 2026-11-25
**Hostname:** haos (VM 101, Home Assistant OS, Zigbee2MQTT 2.14.3)
**IP address:** 192.168.0.202

## Status: fixed

The two hallway lights came on at 04:23 with nobody in the hallway, and all three hallway automations failed to turn them off. A Tuya `ZMS-102` PIR sensor had stopped reporting with its occupancy still `true`. Z2M has no software timeout option for this model, so the fix is a Home Assistant automation. After 5 minutes of continuous `on`, it publishes a fake `occupancy:false` on the device's Z2M topic.

## The setup

| Entity | Device | Model |
|---|---|---|
| `binary_sensor.szenzor_folyoso_fent_occupancy` | Szenzor_Folyoso_Fent | Tuya `TS0202_1` |
| `binary_sensor.szenzor_folyoso_kozep_occupancy` | Szenzor_Folyoso_Kozep | Tuya `ZMS-102` |
| `binary_sensor.szenzor_folyoso_lent_occupancy` | Szenzor_Folyoso_Lent | Tuya `TS0202_1` |

Three automations drive `light.folyoso_fenti_lampa` and `light.folyoso_lenti_lampa`:

- **Folyoso Lampa vezerles** turns the lights on when any sensor is `on`, and off 5 s after all three are `off`.
- **Fenti ajto 5mp** and **Bejarati ajto 10mp** turn the lights on when a door opens, wait, and turn them off only if all three sensors are `off`.

Every turn-off path checks all three sensors are `off`. One sensor that stays `on` keeps the lights on indefinitely, whatever triggered them.

## What happened

From the logbook, in local time:

| Time | Event |
|---|---|
| 04:23:36 | `kozep` goes `on`, and `vezerles` turns the lights on |
| 04:25 - 04:27 | All three automations run by hand. Each one stops at its "all sensors off" condition |
| 04:29:26 | Lights turned off by a manual `light.turn_off` |
| 06:21:27 | The upper door opens, and the lights come on and stay on, because `kozep` is still `on` |
| 06:44:04 | Someone walks past the middle sensor, it reports `false`, and the lights go off 5 s later |

This was not the first time. The 30-day history has a 5 h 08 min stuck period on 2026-11-24 from 07:11. It also has the shorter phantom triggers the household had noticed before: short `on` periods at night with the doors closed, which cleared within a minute or two as designed.

## Diagnosis: the sensor was alive, it just never sent false

HA does not rewrite an MQTT entity's state when the value does not change. `last_changed` and `last_reported` therefore cannot tell a silent device from an idle one. The MQTT debug info shows the raw messages a device sent, over the HA websocket:

```json
{"id": 1, "type": "mqtt/device/debug_info", "device_id": "<device id>"}
```

The last three payloads on `zigbee2mqtt/Szenzor_Folyoso_Kozep`:

```
03:24:36 UTC  {"occupancy":true,  "linkquality":220, "battery":92, "keep_time":60, ...}
05:43:56 UTC  {"occupancy":true,  "linkquality":216, ...}
05:44:04 UTC  {"occupancy":false, "linkquality":216, ...}
```

The first `true` arrived at 03:23:36 UTC. The sensor then sent `true` **again** exactly 60 s later, which is its `keep_time`, and after that nothing for 2 h 19 min. Link quality 220 and a 92% battery rule out a weak connection and a dying battery. The one community report of a Tuya PIR stuck on "detected" blames batteries under 35%, which does not apply here. The `ZMS-102` is also the only one of the three sensors with this behaviour. The two `TS0202_1` units have never done it.

## Why the fix is not in Zigbee2MQTT

Some Tuya PIRs (e.g. `TS0202_1`) have a Z2M `occupancy_timeout` option that clears occupancy in software. The [ZMS-102 device page](https://www.zigbee2mqtt.io/devices/ZMS-102.html) lists no device-specific options at all. It exposes only `sensitivity` (low/medium/high) and `keep_time` (30/60/120), which are sensor-side settings and not a software timeout.

Changing the three lighting automations would also work, but each of them would need its own staleness logic. A single fix at the sensor's MQTT topic covers every consumer at once.

## The watchdog

`automation.folyoso_kozep_szenzor_watchdog`:

```yaml
alias: Folyoso Kozep szenzor watchdog
triggers:
  - trigger: state
    entity_id: binary_sensor.szenzor_folyoso_kozep_occupancy
    to: "on"
    for: "00:05:00"
actions:
  - action: mqtt.publish
    data:
      topic: zigbee2mqtt/Szenzor_Folyoso_Kozep
      retain: false
      payload: >-
        {{ {'occupancy': false,
            'battery': states('sensor.szenzor_folyoso_kozep_battery')|int(0),
            'voltage': states('sensor.szenzor_folyoso_kozep_voltage')|int(0),
            'battery_low': is_state('binary_sensor.szenzor_folyoso_kozep_battery_low','on'),
            'keep_time': states('select.szenzor_folyoso_kozep_keep_time'),
            'sensitivity': states('select.szenzor_folyoso_kozep_sensitivity')} | to_json }}
  - action: logbook.log
    data:
      name: Folyoso Kozep szenzor
      message: stuck occupancy cleared by watchdog
      entity_id: binary_sensor.szenzor_folyoso_kozep_occupancy
mode: single
```

Design notes:

- **The full payload, not only `occupancy`.** The device's battery, voltage, keep_time and sensitivity entities read the same topic with `value_json.<field>` templates. A bare `{"occupancy": false}` would leave them without their field. The payload copies the current values back.
- **`retain: false`**, matching what Z2M publishes for devices. Z2M subscribes to `/set` and `/get`, not to the state topic, so it ignores the fake message.
- **5 minutes.** The sensor's own hold is at most 120 s. A real walker in a hallway does not keep it on for 5 minutes, and if someone does, the next real `true` turns the lights back on.
- **The logbook line** leaves a record each time the watchdog fires. Without it, a fired watchdog is indistinguishable from the sensor's own `false`.

Verification: firing the automation by hand while the sensor was already `off` published the payload, and all six of the device's entities parsed it without error. The actual stuck `on` to `off` path has not fired live yet. Its first occurrence will show up as the logbook line above.

## Known limits

- A Z2M restart replays the cached device state, which may still be `true`. The watchdog clears it again 5 minutes later.
- Z2M's own cached state keeps saying `true` until the sensor sends something real. Only Home Assistant sees the fake `false`.
- The short phantom triggers at night still happen, and still clear on their own. Lowering `sensitivity` from `high` to `medium` is the next step for those, at the risk of missing a fast walk past the sensor. That trade-off is still open.

## Rollback

Delete the automation (Settings > Automations > "Folyoso Kozep szenzor watchdog" > Delete). Nothing else was changed.
