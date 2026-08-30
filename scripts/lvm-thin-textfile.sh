#!/bin/bash
# Exports LVM thin pool fill levels for the Prometheus node_exporter.
#
# node_exporter has no LVM collector. `node_filesystem_*` covers everything that
# is mounted, which is why the SnapRAID disks need nothing extra - but a thin
# pool is not a filesystem. `pve/data` is the pool every LXC and VM disk is
# carved out of, and it has hit 92% before with nothing reporting it.
#
# METADATA IS THE ONE THAT KILLS FIRST. When the metadata area fills the pool
# goes read-only and every guest on it stops writing, and that area is tiny
# (about 1 GiB for a 165 GiB pool here), so it can fill from snapshot churn
# while the data percentage still looks calm. Both numbers are exported.
#
# Runs from a systemd timer on pve, writing into the node_exporter textfile
# directory. Install:
#   scp scripts/lvm-thin-textfile.sh root@192.168.0.109:/usr/local/bin/
#   plus lvm-thin-textfile.service and .timer (see docs/proxmox/)
set -euo pipefail

OUT="${TEXTFILE_DIR:-/var/lib/prometheus/node-exporter}/lvm_thin.prom"
TMP="${OUT}.$$"

# Written to a temp file and renamed. The collector reads whole files on every
# scrape, so writing in place produces a parse error whenever a scrape lands
# mid-write - rare, and therefore the kind of bug that shows up once a month
# and looks like something else.
{
    echo "# HELP lvm_thin_pool_data_percent Used data space of an LVM thin pool, percent."
    echo "# TYPE lvm_thin_pool_data_percent gauge"
    echo "# HELP lvm_thin_pool_metadata_percent Used metadata space of an LVM thin pool, percent."
    echo "# TYPE lvm_thin_pool_metadata_percent gauge"
    echo "# HELP lvm_thin_pool_size_bytes Size of an LVM thin pool in bytes."
    echo "# TYPE lvm_thin_pool_size_bytes gauge"

    # lv_attr starting with 't' is a thin pool. Without the filter this would
    # also emit the thin volumes carved out of it, which report their own
    # data_percent and would make every guest disk look like a pool.
    lvs --noheadings --nosuffix --units b --separator '|' \
        -o vg_name,lv_name,lv_size,data_percent,metadata_percent \
        --select 'lv_attr =~ ^t' 2>/dev/null |
    while IFS='|' read -r vg lv size data meta; do
        vg="${vg// /}"; lv="${lv// /}"; size="${size// /}"
        data="${data// /}"; meta="${meta// /}"
        [ -n "$lv" ] || continue
        printf 'lvm_thin_pool_data_percent{vg="%s",lv="%s"} %s\n' "$vg" "$lv" "${data:-0}"
        printf 'lvm_thin_pool_metadata_percent{vg="%s",lv="%s"} %s\n' "$vg" "$lv" "${meta:-0}"
        printf 'lvm_thin_pool_size_bytes{vg="%s",lv="%s"} %s\n' "$vg" "$lv" "${size:-0}"
    done
} > "$TMP"

chmod 644 "$TMP"
mv -f "$TMP" "$OUT"
