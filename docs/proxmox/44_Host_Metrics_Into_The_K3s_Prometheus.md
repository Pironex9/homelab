**Date:** 2026-08-30
**Hosts:** pve (192.168.0.109) and LXC 100 docker-host (192.168.0.110), scraped from the K3s cluster

---

# Home Host Metrics Into The K3s Prometheus

The K3s cluster - three machines running one workload - had 22 scrape targets and, since
this morning, six alerts on its storage layer. The Proxmox box running nine LXCs, 24
Compose stacks and 8.1 TB of data had no threshold alert that reached anybody. `pve/data`
has been at 92% before and the only thing that noticed was a person looking at a
dashboard.

This closes that with `node_exporter` on both hosts, scraped over the tailnet by the
cluster's existing Prometheus, and eight alerts into the Telegram group everything else
already uses.

---

## What was already there, and why it was not enough

This is the part that had to be checked before writing anything, and the first version of
this page was wrong about it.

**Netdata is running on pve** (v2.11.0 nightly, up since 2026-08-29) and it already has
329 alarms, including exactly the two that matter most here:

```
lvm.lv_data_vg_pve_lv_data_space_utilization.lvm_lv_data_space_utilization
lvm.lv_data_vg_pve_lv_metadata_space_utilization.lvm_lv_metadata_space_utilization
```

**They go nowhere.** There is no `/etc/netdata/health_alarm_notify.conf`, so the stock
defaults apply: `SEND_EMAIL="AUTO"` to `root`, `TELEGRAM_BOT_TOKEN=""`. Local mail that
nobody reads, and Telegram disabled for want of a token. In seven days of journal there
is not one `alarm-notify` line, and `/var/log/netdata/health-notifications.log` does not
exist.

So the thin pool alarm has existed the whole time. It has simply never told anyone. That
is the same failure shape as a dashboard nobody is looking at, one layer further in.

**Scrutiny is also running** - a container on LXC 100 with a collector timer on pve - and
covers SMART for the four SnapRAID disks with its own web UI.

The cheaper fix would have been to write a `health_alarm_notify.conf` with a bot token
and let Netdata's 329 alarms loose. It was not chosen, for three reasons: 329 default
thresholds is noise rather than signal, the bot token would have to live on pve outside
the repo, and it would create a second notification path with its own format and no
shared silencing with the Alertmanager that already handles the cluster. Netdata stays
as the live troubleshooting UI it is good at; the alerts that must reach a phone go
through the one Alertmanager.

---

## node_exporter, bound to the tailnet only

Debian package on both hosts, `prometheus-node-exporter` (1.9.0 on pve/trixie, 1.5.0 on
docker-host/bookworm).

```
ARGS="--web.listen-address=100.116.49.30:9100 ..."
```

`/metrics` has no authentication of any kind. On the default `0.0.0.0:9100` it is
readable by every device on 192.168.0.0/24, including the guest wifi if the router ever
merges those. Bound to the tailnet address it is reachable only by tailnet members.
Verified in both directions:

```console
$ curl -m3 http://192.168.0.109:9100/metrics   # LAN
000   (refused)
$ curl -m3 http://100.116.49.30:9100/metrics   # tailnet
200
```

The binding needs one more thing to survive a reboot. If `tailscaled` is not up yet the
bind fails, and the packaged unit's `Restart=on-failure` with the default rate limit
would put the unit in `failed` state permanently after five quick tries. A drop-in fixes
it:

```ini
[Unit]
StartLimitIntervalSec=0

[Service]
Restart=always
RestartSec=10
```

> The `ARGS` line has to go in `/etc/default/prometheus-node-exporter`, not in the
> drop-in. A drop-in `Environment=ARGS=...` is overridden by the unit's own
> `EnvironmentFile=`, which sets `ARGS=""`. `systemctl show` displays the drop-in value
> and the process still listens on `*:9100`, which makes this look like a systemd bug
> rather than an ordering rule.

---

## Debian excludes `/mnt`, so the disks that matter were missing

The exporter came up, the target went green, and four of the five filesystems that this
whole exercise is about were not in the output. Only `/`, `/boot/efi`, `/etc/pve`,
`/tmp` and `/var/lib/lxcfs` appeared - not one `/mnt/disk*`, not the mergerfs pool.

Not a permission problem, and not a stuck mount: they were absent entirely, without even
a `node_filesystem_device_error` entry. The reason is in the exporter's own startup log:

```
msg="Parsed flag --collector.filesystem.mount-points-exclude"
flag=^/(dev|proc|run|sys|mnt|media|var/lib/docker/.+|var/lib/containers/storage/.+)($|/)
```

`mnt` and `media` are in there. **Upstream node_exporter does not exclude `/mnt` at
all** - this is a Debian patch to the default. Every guide that says "install
node_exporter and your disks appear" is written against upstream.

The override keeps `/mnt/pve/` excluded, because those are Proxmox autofs/NFS storages
and a `statfs` against a dead NFS server blocks:

```
--collector.filesystem.mount-points-exclude=^/(dev|proc|run|sys|mnt/pve|media|var/lib/docker/.+|var/lib/containers/storage/.+)($|/)
```

After that, measured through the cluster's Prometheus:

| instance | mountpoint | fstype | full |
|---|---|---|---|
| pve | / | ext4 | 57.87% |
| pve | /mnt/disk1 | ext4 | 55.90% |
| pve | /mnt/disk2 | ext4 | 56.01% |
| pve | /mnt/disk3 | ext4 | **82.85%** |
| pve | /mnt/disk4 | ext4 | 35.19% |
| pve | /mnt/storage | fuse.mergerfs | 54.30% |
| docker-host | / | ext4 | 75.98% |

`/mnt` is deliberately left excluded on docker-host: its only `/mnt` entry is the same
mergerfs pool, bind-mounted in, and counting an 8.1 TB pool twice under two instance
labels is worse than not counting it.

---

## The thin pool needs a textfile collector

node_exporter has no LVM collector. `node_filesystem_*` covers everything mounted, which
is why the SnapRAID disks need nothing extra - but a thin pool is not a filesystem, and
`pve/data` is what every LXC and VM disk is carved out of.

`scripts/lvm-thin-textfile.sh` runs from a systemd timer every five minutes and writes
into the node_exporter textfile directory the Debian package already uses:

```
lvm_thin_pool_data_percent{vg="pve",lv="data"} 62.55
lvm_thin_pool_metadata_percent{vg="pve",lv="data"} 3.41
lvm_thin_pool_size_bytes{vg="pve",lv="data"} 177100292096
```

Two details in the script are not decoration. The `lv_attr =~ ^t` selector keeps it to
thin **pools**; without it every thin volume carved out of the pool reports its own
`data_percent` and each guest disk looks like a pool of its own. And the file is written
to a temporary name and renamed, because the collector reads whole files on every scrape
and writing in place produces a parse error whenever a scrape lands mid-write - rare, and
therefore the kind of bug that surfaces once a month looking like something else.

The package's own textfile timers come along for free: `apt.prom`, `nvme.prom` and
`smartmon.prom` were already being written, so SMART attributes for all five disks
arrived without any extra work.

---

## Eight alerts

`k8s/manifests/homelab-hosts/prometheusrule.yaml`, into the same Alertmanager and the
same Telegram group as the cluster's own alerts.

| Alert | Threshold | `for` | Severity |
|---|---|---|---|
| `HomelabHostDown` | `up == 0` | 5m | critical |
| `LvmThinPoolFillingUp` | data > 85% | 15m | warning |
| `LvmThinPoolMetadataFillingUp` | metadata > 70% | 15m | critical |
| `HomelabThinPoolMetricsStale` | textfile older than 30m | 15m | warning |
| `HomelabDiskFillingUp` | `/mnt/*` > 90% | 15m | warning |
| `HomelabRootFilesystemFillingUp` | `/` > 85% | 15m | warning |
| `HomelabDiskSmartFailing` | SMART health == 0 | 5m | critical |
| `HomelabDiskBadSectors` | pending/reallocated/uncorrectable > 0 | 15m | warning |

**Metadata gets a lower threshold and a higher severity than data.** The metadata area is
about 1 GiB for this 165 GiB pool, it fills from snapshot churn rather than from stored
data, and when it runs out the pool goes read-only - which stops every guest on it at
once. The data percentage is the number everyone watches; the metadata percentage is the
one that ends the evening.

**`HomelabThinPoolMetricsStale` is the dead man's switch for the script.** If the timer
stops, node_exporter keeps serving the last values it read, for ever, with no error
anywhere - and the two thin-pool alerts above would be watching a frozen number while
reporting healthy. Six missed runs trip it.

**`HomelabDiskBadSectors` fires at `> 0` because every one of those counters is exactly
0 today** on all four SnapRAID disks and the NVMe. That is a threshold picked from a
measurement, not one picked to stay quiet. These counters move before the overall SMART
health flag does, which is why both alerts exist.

---

## The selector that matched nothing, again

Written by hand, first try:

```promql
time() - node_textfile_mtime_seconds{file="lvm_thin.prom"} > 1800
```

Zero series. The `file` label carries the **full path**, not the basename:

```
node_textfile_mtime_seconds{file="/var/lib/prometheus/node-exporter/lvm_thin.prom"}
```

The alert loads, evaluates, reports `health=ok` and `state=inactive`, and is dead. This is
the second selector in one day to fail the same way - the first was
`longhorn_volume_robustness{robustness="degraded"}`, which is
[a `state` label on this version](../k3s/03_Longhorn_Storage.md#alerting-on-the-storage-layer-2026-08-30).

Hence the check that now runs on every new rule, before trusting any of them: **query the
selector without the condition first.** It has to return series. Then apply the condition
and confirm it returns none on a healthy system. An alert whose selector matches nothing
is indistinguishable, from the outside, from an alert that is simply not firing.

```
node_textfile_mtime_seconds{job="homelab-hosts"}   5 series   <- the label exists
node_textfile_mtime_seconds{file="lvm_thin.prom"}  0 series   <- the value does not
node_filesystem_size_bytes{mountpoint=~"/mnt/.*"}  5 series
smartmon_current_pending_sector_raw_value          4 series
lvm_thin_pool_data_percent                         1 series
```

---

## Reachability was measured, not assumed

Pod egress to a `100.64.0.0/10` address is not obvious - the Prometheus pod is not on the
tailnet, its node is. From a throwaway pod in the `monitoring` namespace:

```console
$ kubectl -n monitoring run reach --rm -i --restart=Never --image=curlimages/curl -- \
    sh -c 'curl -s -o /dev/null -w "%{http_code}\n" http://100.116.49.30:9100/metrics'
200
```

Both targets answered, and both came up in Prometheus within one scrape interval.

## Netdata, narrowed instead of silenced (2026-08-30)

Leaving 329 alarms wired to a mailbox nobody reads was not an option once it was known,
and turning all 329 loose on a phone would have been worse. What it got instead: local
mail off, critical-only to ntfy, and the three alarms that now overlap with the
Alertmanager muted.

### The division of labour

**Prometheus owns storage.** `disk_space_usage`, `lvm_lv_data_space_utilization` and
`lvm_lv_metadata_space_utilization` are muted in Netdata, because the same disk filling
up would otherwise arrive twice, on two channels, at two different thresholds, with no
shared silencing during maintenance.

**Netdata owns everything Prometheus is not watching on this host** - CPU, RAM, swap,
TCP accept/SYN queue drops, conntrack saturation, file descriptors, inode exhaustion,
process counts. Of its 329 alarms only 65 have a CRITICAL threshold at all, across 22
distinct names, and that is the set that can now reach a phone.

### `to: silent` in `health.d` did nothing, the silencers file did

The obvious way to disarm a stock alarm is a file in `/etc/netdata/health.d/` that
redeclares the template with `to: silent`. It was written, `netdatacli reload-health`
returned 0, no error appeared in any log - and the recipients were unchanged:

```
disk_space_usage                    9 instances  recipient=['sysadmin']
lvm_lv_data_space_utilization       1 instance   recipient=['sysadmin']
```

A partial redeclaration is not enough to replace the stock template, and nothing says so.
The mechanism that does work is the health management API, which persists to
`/var/lib/netdata/health.silencers.json` immediately:

```bash
TOKEN=$(cat /var/lib/netdata/netdata.api.key)
for A in disk_space_usage lvm_lv_data_space_utilization lvm_lv_metadata_space_utilization; do
  curl -s -H "X-Auth-Token: $TOKEN" \
    "http://localhost:19999/api/v1/manage/health?cmd=SILENCE&alarm=$A"
done
```

`SILENCE` keeps evaluating the alarm and only stops the notification, so it stays visible
in the Netdata UI. `DISABLE` would stop the evaluation too. The dead `health.d` file was
removed rather than left in place looking like it works.

### The `|critical` filter is broken for ntfy on this version

Netdata's documented way to say "critical only" is a suffix on the recipient:

```
DEFAULT_RECIPIENT_NTFY="https://ntfy.lan/homelab-digest|critical"
```

On v2.11.0-174-nightly `send_ntfy()` puts the recipient string straight into the curl URL
without stripping that suffix, so the POST goes to a URL that does not exist:

```
failed to send ntfy notification to 'https://ntfy.lan/homelab-digest|critical'
... with HTTP response status code 404.
```

Measured both ways from the host: suffixed **404**, plain **200**. The generic recipient
loop in `alarm-notify.sh` does strip it (`arr_var[${r/|*/}]`), and ntfy is in
`method_names`, so this reads like it should work - which is why it is worth writing
down rather than rediscovering.

What makes it dangerous is where the failure shows up. The severity filter itself works,
so warnings correctly stop; only criticals are attempted, and they fail in the
notification log. A quick test on a warning alarm reports success. The narrowing would
have looked configured and delivered exactly nothing - the same shape as the original
problem, one layer in.

### `custom_sender()` instead

`SEND_NTFY="NO"`, `SEND_CUSTOM="YES"`, and a sender that gates on `${status}` itself:

```bash
custom_sender() {
    case "${status}" in
        CRITICAL) prio="urgent"; tags="rotating_light" ;;
        CLEAR)
            [ "${old_status}" != "CRITICAL" ] && return 1
            prio="default"; tags="white_check_mark"
            ;;
        *) return 1 ;;
    esac
    ...
}
```

The `CLEAR` arm is not optional. Without it an alarm that goes critical and then resolves
itself stays open as far as the phone is concerned, and the next one reads as a
continuation rather than a new event.

Verified with `alarm-notify.sh test`, which walks all three transitions:

```
# SENDING TEST WARNING ALARM TO ROLE: sysadmin
# FAILED        <- the gate: nothing sent, which is the intended result
# SENDING TEST CRITICAL ALARM TO ROLE: sysadmin
# OK
# SENDING TEST CLEAR ALARM TO ROLE: sysadmin
# OK
```

A warning transition logs nothing at all, so the suppressed path leaves no trail that
looks like a fault later.

### The file only holds the differences

`alarm-notify.sh` sources the stock config first and `/etc/netdata/health_alarm_notify.conf`
second, so the user file needs only what changes. Copying the whole stock file - which is
what `edit-config` does - would freeze every other default at the version it was copied
from, and that drift is invisible until something else stops working.

### The mkcert CA had to go into pve's trust store

`ntfy.lan` is served by Caddy with an mkcert certificate. pve resolved the name but did
not trust the issuer:

```console
$ curl https://ntfy.lan/
curl: (60) SSL certificate problem: unable to get local issuer certificate
```

Every homelab script had been papering over this with `curl -k`. The custom sender
deliberately does not, so the CA went in properly - `rootCA.pem` from the Caddy LXC into
`/usr/local/share/ca-certificates/homelab-mkcert.crt`, then `update-ca-certificates`.
Only the public CA, never `rootCA-key.pem`. Adding `-k` to the sender instead would have
worked and would also have silenced a genuine certificate failure for ever.

---

## What this does not cover

Six LXCs are not on the tailnet and cannot be scraped from the cluster: 102 adguard, 103
vaultwarden, 106 karakeep, 107 n8n, 110 caddy, 113 agentos. They need the home-side
Tailscale subnet router that is still on the roadmap, or a Tailscale client each. The two
hosts covered here are the ones where the storage and the 24 Compose stacks live, which
is where the pain has actually come from.
