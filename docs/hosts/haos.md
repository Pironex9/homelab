# Home Assistant OS (HAOS) VM

## Overview

| Property     | Value                               |
|--------------|-------------------------------------|
| Hostname     | haos                                |
| IP Address   | 192.168.0.202                       |
| VMID         | 101                                 |
| Type         | KVM Virtual Machine (not LXC)       |
| OS           | Alpine Linux 3.23.3 (add-on sandbox)|
| Kernel       | 6.12.67-haos                        |
| Purpose      | Home automation platform            |
| Web UI       | http://192.168.0.202:8123           |
| HA Version   | 2026.4.2                            |

> **Note:** HAOS is a full KVM VM, not an LXC container. It is listed here for consistency. The SSH shell runs inside the Advanced SSH & Web Terminal add-on sandbox (Alpine Linux), not on the host HAOS system directly.

## Architecture

HAOS uses a layered architecture:

```
KVM VM (VMID 101)
└── Home Assistant OS (haos kernel 6.12.67)
    └── Supervisor (Docker-based)
        ├── Home Assistant Core (2026.2.3)
        ├── Mosquitto broker add-on
        ├── Zigbee2MQTT add-on
        ├── go2rtc add-on
        └── Advanced SSH & Web Terminal add-on  ← SSH lands here
```

## Resources

| Resource | Value                |
|----------|----------------------|
| RAM      | 6144 MB (allocated in Proxmox) |
| Swap     | none                |
| Disk     | 32 GB (local-lvm, LVM thin)  |

## Installed Add-ons

| Add-on                      | Notes                                  |
|-----------------------------|----------------------------------------|
| Advanced SSH & Web Terminal | SSH access, user=hassio, port=22       |
| Mosquitto broker            | MQTT broker, ports 1883/1884/8883/8884 |
| Zigbee2MQTT                 | Zigbee coordinator via Sonoff USB dongle, v2.8.0 |
| go2rtc                      | RTSP/WebRTC camera stream proxy        |

## Integrations

| Domain          | Description                         |
|-----------------|-------------------------------------|
| zha             | Sonoff Zigbee 3.0 USB Dongle Plus V2 |
| mqtt            | Mosquitto broker                    |
| go2rtc          | go2rtc camera proxy                 |
| cast            | Google Cast                         |
| dlna_dmr        | DLNA media renderer (TV)            |
| dlna_dms        | DLNA media server                   |
| upnp            | Router UPnP                         |
| met             | Home weather (Met.no)               |
| google_translate | Text-to-speech                     |
| radio_browser   | Radio Browser                       |

## Open Ports

| Port        | Protocol | Service                                  |
|-------------|----------|------------------------------------------|
| 22          | TCP      | SSH (Advanced SSH & Web Terminal add-on) |
| 8123        | TCP      | Home Assistant web UI + REST API         |
| 1883        | TCP      | MQTT (unencrypted)                       |
| 1884        | TCP      | MQTT (WebSocket)                         |
| 8883        | TCP      | MQTT TLS                                 |
| 8884        | TCP      | MQTT TLS WebSocket                       |
| 4357        | TCP      | Zigbee2MQTT frontend                     |
| 8485        | TCP      | go2rtc web UI                            |
| 18554/18555 | TCP      | go2rtc RTSP                              |

## Key Config Files

| File                                          | Description                   |
|-----------------------------------------------|-------------------------------|
| `/homeassistant/configuration.yaml`           | Main HA configuration         |
| `/homeassistant/automations.yaml`             | Automation rules              |
| `/homeassistant/secrets.yaml`                 | Sensitive values              |
| `/homeassistant/home-assistant_v2.db`         | SQLite history database       |
| `/homeassistant/.storage/core.config`         | Instance config               |
| `/homeassistant/.storage/core.config_entries` | Installed integrations        |
| `/addon_configs/45df7312_zigbee2mqtt/`        | Zigbee2MQTT config            |

## SSH Access

SSH is provided by the **Advanced SSH & Web Terminal** add-on. The shell runs inside an Alpine Linux sandbox - not on the HAOS host directly.

| Setting        | Value                        |
|----------------|------------------------------|
| Username       | `hassio`                     |
| Port           | `22`                         |
| Auth           | Key-based only               |
| Protection mode | enabled                     |

```bash
# Direct
ssh hassio@192.168.0.202
```

**What SSH can access:**

| Accessible                                  | Not accessible               |
|---------------------------------------------|------------------------------|
| `/homeassistant/` (config, DB, automations) | Docker daemon                |
| `/addon_configs/`, `/share/`, `/backup/`    | Supervisor API               |
| Network info (`netstat`, `ping`)            | Host OS filesystem           |
| System stats (`df`, `free`, `uptime`)       | `ha` CLI commands            |

## REST API

The HA REST API is the preferred way to query and manage HAOS programmatically.

| Setting   | Value                                   |
|-----------|-----------------------------------------|
| Base URL  | `http://192.168.0.202:8123/api/`        |
| Auth      | Long-lived access token (Bearer)        |

```bash
# Quick health check
curl -s -H "Authorization: Bearer <token>" \
  http://192.168.0.202:8123/api/

# All entity states
curl -s -H "Authorization: Bearer <token>" \
  http://192.168.0.202:8123/api/states

# Call a service (e.g. turn on a light)
curl -s -X POST \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"entity_id": "light.example"}' \
  http://192.168.0.202:8123/api/services/light/turn_on
```

## Scheduled Maintenance

| Task | Schedule | Command (Proxmox host) | Reason |
|------|----------|------------------------|--------|
| Full VM reboot | Daily 04:10 | `qm reboot 101` | Workaround for memory leak in 2026.4.x |

The daily reboot is configured in the Proxmox host crontab (`crontab -e` as root on 192.168.0.109). Remove once the memory leak is fixed upstream.

## Known Issues

### Memory leak in HA Core 2026.4.x (active as of 2026-04-17)

HA Core 2026.4.0-2026.4.2 has a memory leak that causes RAM to fill up over hours and eventually crash the VM. The leak fills 6 GB in ~13-15 hours. Symptoms:

- Python GC pauses cause HA to stop responding for >30s - Newt marks the target unhealthy, Pangolin returns 503 for public URLs
- After ~13h memory is exhausted, HA crashes entirely (OOM)

Diagnosis: check `journalctl -u newt` on the Proxmox host for `context deadline exceeded` (freeze) vs `connection refused` (crash).

Workaround: daily full VM reboot via Proxmox cron at 04:10 (`qm reboot 101` in root crontab on 192.168.0.109). The old HA-internal "Nightly HA Restart" automation (`automation.nightly_ha_restart`) is **disabled** - it only restarted the core process which did not clear RAM.

References:
- [GitHub issue #167401](https://github.com/home-assistant/core/issues/167401) - memory leak + crash in 2026.4.0/4.1
- [GitHub issue #168088](https://github.com/home-assistant/core/issues/168088) - severe memory pressure during 2026.4.x update

If reverting is needed: Settings - About - ... - Version History - select 2026.3.4.

## Lessons Learned

- **HAOS is a KVM VM, not an LXC** - `pct exec` does not work; `qm terminal 101` gives the HAOS console, which is very limited.
- **SSH user is `hassio`, not `root`** - the add-on config UI shows the `username` field set to `hassio`, which must match the SSH login.
- **SSH add-on must be configured before starting** - starting it without `authorized_keys` or `password` causes a fatal error and the add-on immediately stops.
- **The `ha` CLI requires Supervisor API token** - commands like `ha core info` fail from the SSH add-on shell; use the REST API instead.
- **Protection mode** blocks Docker access - to run `docker ps` or interact with containers, Protection Mode must be disabled in the add-on settings. Leave it enabled unless absolutely needed.
- **Alpine Linux inside, HAOS outside** - the SSH session runs in an Alpine 3.23 container sandbox, not on the HAOS host. Some host-level commands are unavailable or proxied.
