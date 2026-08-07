#!/bin/bash
# Measures what the user actually experiences: an established interactive SSH
# session going silent. nobara-freeze-watch.sh only opens new connections, so
# it cannot see a stall inside a session that is already up.
#
# Two heartbeats, one per direction, 5s apart. A gap longer than STALL seconds
# is logged with the sender-side socket state, fetched over Tailscale (which
# stays up when the LAN path does not).
#
# Run: nohup scripts/nobara-session-stall.sh >/dev/null 2>&1 &
# Read: tail -f /var/log/nobara-stall.log

LOG=/var/log/nobara-stall.log
LAN=192.168.0.100
TS=100.109.197.79
STALL=8
# Every gap over this is logged as a bare line, no socket dump. Lets sub-STALL
# jitter show up in the record instead of being invisible.
NOTE=6

HB='while :; do echo .; sleep 5; done'

# $1 = label, rest = ssh args producing a 5s heartbeat
heartbeat() {
    local label=$1; shift
    local last now gap
    last=$(date +%s)
    while read -r _; do
        now=$(date +%s); gap=$((now - last)); last=$now
        if ((gap > NOTE && gap <= STALL)); then
            echo "$(date '+%F %T') $label gap ${gap}s" >> "$LOG"
        fi
        if ((gap > STALL)); then
            echo "$(date '+%F %T') $label STALL ${gap}s" >> "$LOG"
            timeout 20 ssh -o ConnectTimeout=8 -o BatchMode=yes nex@$TS \
                'ss -tinm "( sport = :22 or dport = :22 )"; iw dev wlp41s0 link | head -6' \
                >> "$LOG" 2>&1
        fi
    done < <(timeout 86400 ssh -o BatchMode=yes -o ServerAliveInterval=0 \
                 -o ConnectTimeout=10 "$@" 2>/dev/null)
    echo "$(date '+%F %T') $label heartbeat ended" >> "$LOG"
}

while true; do
    # 109 -> nobara over the LAN
    heartbeat "109->nobara" nex@$LAN "$HB" &
    # nobara -> 109 over the LAN: the direction the desktop terminal uses.
    # The outer hop rides Tailscale so it cannot be the thing that stalls; the
    # inner hop is the LAN SSH we are actually measuring.
    heartbeat "nobara->109" nex@$TS \
        "ssh -o BatchMode=yes -o ServerAliveInterval=0 root@192.168.0.204 '$HB'" &
    wait
    echo "$(date '+%F %T') both heartbeats down, reconnecting in 15s" >> "$LOG"
    sleep 15
done
