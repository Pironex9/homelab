#!/bin/bash
# Catches the intermittent Nobara SSH freeze with data instead of a guess.
#
# During a freeze, SSH to 192.168.0.100:22 stalls in the banner exchange while
# ping, HTTP and Tailscale to the same host keep working. Both are TCP over the
# same LAN path, and the only difference is that OpenSSH marks its packets with
# DSCP (observed tos 0xb8) - which the RE605X wireless backhaul puts in a
# separate WMM queue. Logging both side by side tells us which it is.
#
# Run: nohup scripts/nobara-freeze-watch.sh >/dev/null 2>&1 &
# Read: tail -f /var/log/nobara-freeze.log

LOG=/var/log/nobara-freeze.log
LAN=192.168.0.100
TS=100.109.197.79

probe() {  # name cmd... -> "name=ok/FAIL(secs)"
    local name=$1; shift
    local t0 rc
    t0=$(date +%s.%N)
    "$@" >/dev/null 2>&1; rc=$?
    printf '%s=%s(%.1fs)' "$name" "$( ((rc==0)) && echo ok || echo FAIL )" \
        "$(echo "$(date +%s.%N) - $t0" | bc)"
}

while true; do
    line="$(date '+%F %T')"
    line="$line $(probe ssh22   timeout 8 ssh -o ConnectTimeout=6 -o BatchMode=yes nex@$LAN true)"
    line="$line $(probe http    curl -sf -m 6 -o /dev/null http://$LAN:11434/)"
    line="$line $(probe sshTS   timeout 8 ssh -o ConnectTimeout=6 -o BatchMode=yes nex@$TS true)"
    line="$line $(probe ping    ping -c2 -W2 $LAN)"
    echo "$line" >> "$LOG"

    # ssh22 broken but http fine: the interesting case. Grab the sender-side
    # socket state over Tailscale, which still works when the LAN path does not.
    if [[ $line == *"ssh22=FAIL"* && $line == *"http=ok"* ]]; then
        {
            echo "--- $(date '+%F %T') ssh22 down, http up"
            timeout 15 ssh -o ConnectTimeout=8 -o BatchMode=yes nex@$TS \
                'ss -tinm "( sport = :22 )"; echo; ip -s link show enp39s0 | tail -4; iw dev wlp41s0 link' 2>&1
        } >> "$LOG"
    fi
    sleep 30
done
