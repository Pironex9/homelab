#!/usr/bin/env bash
# scripts/hermes-claude-code-wrapper.sh
# Deployed to /usr/local/bin/hermes-claude-code.sh on LXC 109.
# Invoked ONLY via a forced-command, source-IP-locked SSH key - never run
# directly with untrusted arguments from an interactive shell.
set -euo pipefail

LOG_FILE="/var/log/hermes-delegate.log"
MAX_TASK_LEN=2000

# SSH_ORIGINAL_COMMAND carries whatever the caller passed after the ssh
# command; we treat all of it as one opaque task string for `claude -p`.
TASK="${SSH_ORIGINAL_COMMAND:-}"

if [ -z "$TASK" ]; then
  echo "no task provided" >&2
  exit 1
fi

if [ "${#TASK}" -gt "$MAX_TASK_LEN" ]; then
  echo "task too long (max ${MAX_TASK_LEN} chars)" >&2
  exit 1
fi

# Strip newlines/control characters before logging so a crafted task can't
# forge extra log lines or hide its real content across multiple entries.
SAFE_TASK=$(printf '%s' "$TASK" | tr -d '\000-\037')
echo "$(date -u +%FT%TZ) from=${SSH_CLIENT%% *} task=${SAFE_TASK}" >> "$LOG_FILE"

cd /root/homelab
claude -p "$TASK" --settings /usr/local/etc/hermes-delegate-settings.json
