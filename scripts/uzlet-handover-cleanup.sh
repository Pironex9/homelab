#!/bin/bash
# Uzlet handover cleanup - LXC 109 klónon futtatni!
# Homelab secreteket és projekteket töröl, uzlet projektet meghagyja.

set -e

echo "=== UZLET HANDOVER CLEANUP ==="
echo "Futtatás helye: $(hostname) ($(cat /etc/hostname))"
echo ""
echo "FIGYELEM: Ez a script törli a homelab projekteket és secreteket."
echo "Csak LXC 120-on (klónon) futtasd, NEM LXC 109-en!"
echo ""
read -p "Biztosan folytatod? (igen): " confirm
if [ "$confirm" != "igen" ]; then
  echo "Megszakítva."
  exit 1
fi

echo ""
echo "[1/5] Homelab projektek törlése..."
rm -rf /root/homelab /root/learning /root/youtube
echo "OK"

echo ""
echo "[2/5] SSH kulcsok és config törlése (KRITIKUS)..."
rm -f /root/.ssh/id_ed25519 /root/.ssh/id_ed25519.pub
rm -f /root/.ssh/config /root/.ssh/known_hosts /root/.ssh/known_hosts.old
echo "OK"

echo ""
echo "[3/5] Secrets törlése..."
rm -rf /root/.secrets/
echo "OK"

echo ""
echo "[4/5] Claude homelab fájlok törlése..."
rm -f /root/.claude/history.jsonl
rm -rf /root/.claude/sessions/
rm -rf /root/.claude/projects/-root-homelab/
rm -f /root/.claude/settings.json
rm -f /root/.claude.json
rm -rf /root/.claude/shell-snapshots/
rm -rf /root/.claude/session-env/
rm -rf /root/.claude/paste-cache/
rm -rf /root/.claude/file-history/
rm -rf /root/.claude/backups/
rm -rf /root/.claude/debug/
echo "OK"

echo ""
echo "[5/5] Cleanup befejezve!"
echo ""
echo "Következő lépés: futtasd az audit parancsokat a szivárgás ellenőrzéséhez."
