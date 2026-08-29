#!/bin/sh
# SnapRAID Daemon notify_result handler.
#
# The daemon pipes the full task report into stdin and passes the subject line
# as $1. Called from /etc/snapraidd.conf on pve:
#
#   notify_result = sh /usr/local/bin/snapraid-notify.sh "%s"
#
# The Kuma push token lives in /etc/snapraid-notify.env (chmod 600, NOT in this
# repo) rather than in the command line, so nothing secret has to travel through
# the daemon's config parser or into git:
#
#   KUMA_PUSH_URL=http://100.118.239.117:3001/api/push/<token>
#
# Two destinations on purpose: ntfy carries the full report, Kuma carries the
# alert. Kuma is the one that reaches a phone (Discord notifier), ntfy is the
# detail you read afterwards.
set -u

[ -r /etc/snapraid-notify.env ] && . /etc/snapraid-notify.env

SUBJECT="${1:-[SnapRAID] report}"
NTFY_URL="${NTFY_URL:-http://192.168.0.71:8091/snapraid}"

# Read stdin exactly once. The daemon writes the report into a pipe; if nothing
# reads it, the write side can block.
REPORT="$(cat)"

printf '%s\n' "$REPORT" | curl -fsS -m 20 -o /dev/null \
    -H "Title: $SUBJECT" \
    -H "Priority: high" \
    -H "Tags: rotating_light" \
    --data-binary @- "$NTFY_URL" \
    || echo "snapraid-notify: ntfy push failed" >&2

if [ -n "${KUMA_PUSH_URL:-}" ]; then
    # Both parameters go through -G. Appending "&status=down" by hand breaks when
    # KUMA_PUSH_URL carries no query string: the token swallows it and Kuma 404s.
    curl -fsS -m 15 -o /dev/null -G \
        --data-urlencode "status=down" \
        --data-urlencode "msg=$SUBJECT" \
        "$KUMA_PUSH_URL" \
        || echo "snapraid-notify: kuma push failed" >&2
fi

# Never fail: a dead notification target must not make the daemon think the
# task itself went wrong.
exit 0
