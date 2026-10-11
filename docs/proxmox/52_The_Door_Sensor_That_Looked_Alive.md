**Date:** 2026-10-11
**Host:** VM 101 haos (192.168.0.202), Zigbee2MQTT add-on, SONOFF Dongle Plus (`adapter: ember`)
**Device:** `Ajto_Szenzor_Bejarati`, Aqara MCCGQ11LM door/window sensor (`0x00158d008b5a229d`)

---

# The Door Sensor That Looked Alive for Two Months

The entrance door sensor kept "dropping off" Home Assistant: no Activity entries, no
automation triggers. The device page still showed `Closed`, battery 100%, 34.0 °C and
3035 mV, so at first glance it looked like it was working.

**Outcome:** the sensor had not sent a single frame since **2026-08-14 23:52**. It was
re-paired with its parent pinned to a SONOFF plug, and Zigbee2MQTT availability was turned on
so that a silent battery device now goes `unavailable` instead of looking healthy.

---

## Why a dead sensor looked healthy

Zigbee2MQTT keeps the last known state of every device in `state.json` and republishes it
on every start. Home Assistant receives a normal-looking payload and has no way to tell it
apart from fresh data. Without availability tracking, nothing ever marks the device offline.

Three checks showed the payload was stale, not live:

| Check | Healthy sensor (`Ajto_Szenzor_Fent`) | Dead sensor (`Ajto_Szenzor_Bejarati`) |
|---|---|---|
| `lastSeen` in `/config/zigbee2mqtt/database.db` | minutes ago | 2026-08-14 23:52 |
| Payload contents across logs | `linkquality` and `contact` vary | byte-identical in every log since September (`linkquality:200`, `power_outage_count:565`) |
| When the payload is published | on every open/close | only in the second after each Z2M start |
| Listed in `zigbee2mqtt/bridge/health` → `devices` | yes, message counter rising | absent: zero messages since the last start |

The last row is the quickest check. `bridge/health` only counts messages actually received
since the process started, so a device missing from it has been silent the whole time.

---

## Finding the parent

An Aqara end device has exactly one parent, and it is known to drop off parents it does
not get along with. Once dropped, it does not look for a new parent by itself. The raw
network map shows the parent: `rel=1` marks a child link.

```bash
# on the HAOS SSH add-on; the broker credentials are the `mqtt:` block of configuration.yaml
mosquitto_sub -h 192.168.0.202 -u addons -P '<mqtt_password>' \
  -t zigbee2mqtt/bridge/response/networkmap -C 1 -W 150 > /tmp/nm.json &
mosquitto_pub -h 192.168.0.202 -u addons -P '<mqtt_password>' \
  -t zigbee2mqtt/bridge/request/networkmap -m '{"type":"raw","routes":false}'
```

After the first plain re-pair, the sensor ended up under `Folyoso_Fenti_Lampa`, a Philips
Hue bulb (`lqi=174`). The working twin sensor was a direct child of the coordinator
(`lqi=195`).

Whether Hue is incompatible with Aqara is **not** established. The Zigbee2MQTT device page
for MCCGQ11LM lists Centralite, GE, Iris, Ledvance, Legrand, OSRAM, Sylvania, SmartThings
and Securifi as routers known to drop Xiaomi devices, and Hue is not on that list. The
stronger argument against a bulb as a parent is simpler: a bulb on a wall switch takes its
children down every time it is switched off. During the same session `Balkon_Lampa`, another
Hue bulb, was offline with `lqi=0` on every link.

---

## Pinning the parent

`permit_join` accepts a `device` field, so only that router accepts the join. That makes it
possible to choose the parent instead of leaving it to the sensor:

```bash
mosquitto_pub -h 192.168.0.202 -u addons -P '<mqtt_password>' \
  -t zigbee2mqtt/bridge/request/permit_join -m '{"time":254,"device":"Stekker_Balkon"}'
```

Then hold the sensor's button for about 5 s until the LED blinks blue, and keep short-pressing
it about once a second until the interview finishes. The IEEE address does not change, so the
friendly name, the HA entities and the automations survive a re-pair untouched.

| Attempt | Join result | After the join |
|---|---|---|
| `"device":"Coordinator"` | interviewed successfully at 17:15:53 | **no frame at all**, many door openings went unseen; no router listed it as a child |
| `"device":"Stekker_Balkon"` (SONOFF S60ZBTPF) | interviewed successfully at 17:23:37 | 20 open/close events within two minutes; network map shows `Ajto_Szenzor_Bejarati -> Stekker_Balkon lqi=102 rel=1` |

The coordinator attempt is the useful lesson. A successful interview does not prove the
link will hold. From the entrance, the signal was enough to complete the join and then not
enough for anything after it. Whether a parent works can only be judged from what the device
sends afterwards.

One trap during pairing: a long press after the interview resets the sensor and starts the
join again (`left the network` → `joined` in the log). Once the interview has finished, stop
pressing the button and use the door instead.

---

## Making the next outage visible

```bash
mosquitto_pub -h 192.168.0.202 -u addons -P '<mqtt_password>' \
  -t zigbee2mqtt/bridge/request/options -m '{"options":{"availability":{"enabled":true}}}'
# response: {"data":{"restart_required":true},"status":"ok"}
mosquitto_pub -h 192.168.0.202 -u addons -P '<mqtt_password>' \
  -t zigbee2mqtt/bridge/request/restart -m ''
```

The `options` request writes `availability: enabled: true` into `configuration.yaml`; a
backup was taken first. After the restart, every device gets a
`zigbee2mqtt/<name>/availability` topic. The Home Assistant discovery config references that
topic, so a battery device that stays silent past the default 25-hour passive timeout shows up
as `unavailable` in HA. The sensor would have been flagged on 2026-08-16, not discovered by
accident on 2026-10-11.

---

## If it drops again

1. Check `bridge/health` first. If the device is missing from `devices`, it is silent, no
   matter what HA shows.
2. Pull the raw network map and read its `rel=1` link to see which router it is attached to.
3. `Stekker_Balkon` is now load-bearing for this sensor: it must stay plugged in and powered.
   The next candidate parent is `Stekker_Konyha`, the other SONOFF S60ZBTPF.
