# Leak Sensor Water Alert - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create two Home Assistant automations that send repeating push notifications when the leak sensor detects water, plus a "all clear" notification when it clears.

**Architecture:** Two independent automations communicating via a shared `notification_id`. Automation 1 uses `repeat: while:` to loop every 10 minutes while the sensor is wet. Automation 2 fires on dry state and dismisses the persistent notification. Both created via HA config API (not YAML file editing).

**Tech Stack:** Home Assistant MCP (`ha_config_set_automation`, `ha_config_get_automation`, `ha_get_automation_traces`, `ha_call_service`), HA companion app push notifications, HA persistent notifications.

---

## Task 1: Create "Vízérzékelő - Riasztás" automation

**HA entities touched:**
- Trigger: `binary_sensor.leak_sensor_water_leak`
- Actions: `persistent_notification.create`, `notify.mobile_app_norbi_telo`, `notify.mobile_app_ancsi_telo`
- Creates: `automation.vizerzekelo_riasztas` (or similar slug)

- [ ] **Step 1: Create the automation via ha_config_set_automation**

Call `ha_config_set_automation` with no `identifier` (fresh create) and the following config:

```python
config = {
    "alias": "Vízérzékelő - Riasztás",
    "mode": "single",
    "max_exceeded": "silent",
    "triggers": [
        {
            "trigger": "state",
            "entity_id": "binary_sensor.leak_sensor_water_leak",
            "to": "on"
        }
    ],
    "actions": [
        {
            "action": "persistent_notification.create",
            "data": {
                "title": "⚠️ Vízérzékelő riasztás",
                "message": "Víz észlelve! Ellenőrizd azonnal!",
                "notification_id": "leak_sensor_alert"
            }
        },
        {
            "repeat": {
                "while": [
                    {
                        "condition": "state",
                        "entity_id": "binary_sensor.leak_sensor_water_leak",
                        "state": "on"
                    }
                ],
                "sequence": [
                    {
                        "action": "notify.mobile_app_norbi_telo",
                        "data": {
                            "title": "⚠️ Vízérzékelő riasztás",
                            "message": "Víz észlelve! Ellenőrizd azonnal!",
                            "data": {
                                "tag": "leak_sensor_alert"
                            }
                        }
                    },
                    {
                        "action": "notify.mobile_app_ancsi_telo",
                        "data": {
                            "title": "⚠️ Vízérzékelő riasztás",
                            "message": "Víz észlelve! Ellenőrizd azonnal!",
                            "data": {
                                "tag": "leak_sensor_alert"
                            }
                        }
                    },
                    {
                        "delay": "00:10:00"
                    }
                ]
            }
        }
    ]
}
```

Expected result: tool returns `automation_id` like `automation.vizerzekelo_riasztas`. Note this entity_id for the next steps.

- [ ] **Step 2: Verify the automation was created correctly**

Call `ha_config_get_automation` with the returned `automation_id`.

Check:
- `alias` = "Vízérzékelő - Riasztás"
- `mode` = "single"
- `triggers[0].entity_id` = "binary_sensor.leak_sensor_water_leak"
- `triggers[0].to` = "on"
- `actions[0].action` = "persistent_notification.create"
- `actions[0].data.notification_id` = "leak_sensor_alert"
- `actions[1].repeat.while[0].entity_id` = "binary_sensor.leak_sensor_water_leak"
- `actions[1].repeat.sequence` has 3 items: norbi notify, ancsi notify, delay

If any field is wrong, call `ha_config_set_automation` again with `identifier` = the returned entity_id and the corrected config.

---

## Task 2: Create "Vízérzékelő - Helyreállt" automation

**HA entities touched:**
- Trigger: `binary_sensor.leak_sensor_water_leak`
- Actions: `notify.mobile_app_norbi_telo`, `notify.mobile_app_ancsi_telo`, `persistent_notification.dismiss`
- Creates: `automation.vizerzekelo_helyreállt` (or similar slug)

- [ ] **Step 1: Create the automation via ha_config_set_automation**

Call `ha_config_set_automation` with no `identifier` and the following config:

```python
config = {
    "alias": "Vízérzékelő - Helyreállt",
    "mode": "single",
    "triggers": [
        {
            "trigger": "state",
            "entity_id": "binary_sensor.leak_sensor_water_leak",
            "from": "on",
            "to": "off"
        }
    ],
    "actions": [
        {
            "action": "notify.mobile_app_norbi_telo",
            "data": {
                "title": "✅ Vízérzékelő - OK",
                "message": "A vízérzékelő normál állapotba tért vissza.",
                "data": {
                    "tag": "leak_sensor_alert"
                }
            }
        },
        {
            "action": "notify.mobile_app_ancsi_telo",
            "data": {
                "title": "✅ Vízérzékelő - OK",
                "message": "A vízérzékelő normál állapotba tért vissza.",
                "data": {
                    "tag": "leak_sensor_alert"
                }
            }
        },
        {
            "action": "persistent_notification.dismiss",
            "data": {
                "notification_id": "leak_sensor_alert"
            }
        }
    ]
}
```

Expected result: tool returns `automation_id` like `automation.vizerzekelo_helyreállt`.

- [ ] **Step 2: Verify the automation was created correctly**

Call `ha_config_get_automation` with the returned `automation_id`.

Check:
- `alias` = "Vízérzékelő - Helyreállt"
- `triggers[0].from` = "on" and `triggers[0].to` = "off"
- `actions[0].action` = "notify.mobile_app_norbi_telo"
- `actions[0].data.data.tag` = "leak_sensor_alert"
- `actions[2].action` = "persistent_notification.dismiss"
- `actions[2].data.notification_id` = "leak_sensor_alert"

---

## Task 3: Smoke test - Automation 1 (persistent notification path)

The sensor is currently dry (`off`), so a manual trigger will:
- Execute `persistent_notification.create` ✓
- Enter the repeat loop → check `while` condition → sensor is `off` → loop exits immediately (no push sent — this is correct behavior)

This verifies the persistent notification path without needing the sensor wet.

- [ ] **Step 1: Manually trigger Automation 1**

Call `ha_call_service`:
- domain: `automation`
- service: `trigger`
- entity_id: the `automation_id` from Task 1 (e.g. `automation.vizerzekelo_riasztas`)

- [ ] **Step 2: Verify persistent notification was created**

Call `ha_call_service`:
- domain: `persistent_notification`
- service: `get` (or search entities for `persistent_notification.leak_sensor_alert`)

If the persistent notification entity exists with the expected title ("⚠️ Vízérzékelő riasztás"), the step passed.

Alternatively: call `ha_search_entities` with query "leak_sensor_alert" — the persistent notification should appear.

- [ ] **Step 3: Check automation trace**

Call `ha_get_automation_traces` with the `automation_id` from Task 1.

Expected in the most recent trace:
- Trigger shows manual trigger (context)
- `persistent_notification.create` action completed
- `repeat` block entered, `while` condition evaluated as `false` (sensor off), loop did not execute sequence

If trace shows an error in any action, fix the config and re-run.

---

## Task 4: Smoke test - Automation 2 (all clear path)

The persistent notification from Task 3 should still be visible. This step verifies it gets dismissed.

- [ ] **Step 1: Manually trigger Automation 2**

Call `ha_call_service`:
- domain: `automation`
- service: `trigger`
- entity_id: the `automation_id` from Task 2 (e.g. `automation.vizerzekelo_helyreállt`)

- [ ] **Step 2: Verify persistent notification was dismissed**

Call `ha_search_entities` with query "leak_sensor_alert".

Expected: entity no longer present (or state = `dismissed` depending on HA version).

- [ ] **Step 3: Check automation trace**

Call `ha_get_automation_traces` with the `automation_id` from Task 2.

Expected in the most recent trace:
- All 3 actions completed successfully
- No errors

If `persistent_notification.dismiss` failed (e.g. notification ID mismatch), verify that the `notification_id` in automation 2 exactly matches what was created in automation 1: `"leak_sensor_alert"`.

---

## End-to-end test note (physical sensor)

To verify the push notification loop (the `repeat: while:` path), physically trigger the sensor:
1. Get the sensor wet → automation 1 triggers → push notification arrives on Norbi + Ancsi phone
2. Wait or dry the sensor → automation 2 triggers → "OK" notification replaces the alert on both phones + HA dashboard clears

The `tag: "leak_sensor_alert"` on mobile ensures repeated alerts update the existing notification rather than stacking duplicates.
