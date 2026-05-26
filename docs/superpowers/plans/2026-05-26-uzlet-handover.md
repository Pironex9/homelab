# Uzlet Project Handover Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Az uzlet projekt (LXC 109 klón + LXC 111 scraper) átadása a megbízónak USB-n, semmilyen homelab secret nélkül, plusz a GitHub repo transzfer.

**Architecture:** LXC 109-et klónozzuk (VMID 120), a klónon futtatjuk a cleanup scriptet, vzdump-pal exportáljuk. LXC 111-et közvetlenül exportáljuk (nincs benne homelab secret). A GitHub repót áttranszferáljuk.

**Tech Stack:** Proxmox VE CLI (`pct`, `vzdump`), bash, GitHub web UI

---

## Fájl struktúra

- Létrehozni: `scripts/uzlet-handover-cleanup.sh` - cleanup script (a klónon fut)
- Létrehozni: `/root/uzlet/HANDOVER.md` - setup útmutató a megbízónak
- Plan: `docs/superpowers/plans/2026-05-26-uzlet-handover.md` (ez a fájl)

---

## Parancs helyszínek

Minden Task egyértelműen jelöli:
- `[PROXMOX HOST]` - SSH a pve hosthoz: `ssh root@192.168.0.109` (vagy Proxmox web UI Shell)
- `[LXC 109]` - ez a jelenlegi Claude Code session (a `/root/homelab` project)
- `[LXC 120]` - a klón, `pct exec 120 -- bash` -on keresztül

---

### Task 1: Pre-flight check

**Files:** -

- [ ] **Step 1: Thin pool szabad hely ellenőrzése** `[PROXMOX HOST]`

```bash
ssh root@192.168.0.109 "lvs pve/data --noheadings -o lv_name,data_percent,lv_size"
```

Elvárt kimenet: `data` sor, Data% < 88% (ha ≥ 90% → ne folytasd, először helyet kell felszabadítani).
LXC 109 disk 12 GB → a klónhoz ~11.7 GB kell a thin poolban.

- [ ] **Step 2: Dump könyvtár szabad hely ellenőrzése** `[PROXMOX HOST]`

```bash
ssh root@192.168.0.109 "df -h /var/lib/vz/dump 2>/dev/null || df -h /var/lib/vz"
```

Elvárt: legalább 25 GB szabad (LXC 109 klón ~4-6 GB tömörítve + LXC 111 ~3-5 GB tömörítve).

- [ ] **Step 3: USB eszköz azonosítása** `[PROXMOX HOST]`

```bash
ssh root@192.168.0.109 "lsblk -o NAME,SIZE,TYPE,MOUNTPOINT | grep -E 'disk|part'"
```

Keresd az USB drive-ot (pl. `/dev/sde`, méret alapján). Jegyezd fel a partition nevét (pl. `/dev/sde1`).

---

### Task 2: Cleanup script megírása

**Files:**
- Létrehozni: `scripts/uzlet-handover-cleanup.sh`

- [ ] **Step 1: Script ellenőrzése** `[LXC 109]`

A script már létezik a repóban (már megírva a plan készítésekor):

```bash
cat /root/homelab/scripts/uzlet-handover-cleanup.sh
```

Ellenőrizd hogy minden törlendő kategória szerepel: homelab projekt, SSH kulcsok, secrets, Claude fájlok (history, sessions, homelab memory, settings, shell-snapshots, session-env, paste-cache, file-history, backups, debug).

- [ ] **Step 2: Script tartalmának ellenőrzése**

```bash
cat /root/homelab/scripts/uzlet-handover-cleanup.sh
```

Ellenőrizd hogy minden törlendő sor szerepel-e (homelab, ssh, secrets, claude fájlok).

- [ ] **Step 3: Commit** `[LXC 109]`

```bash
cd /root/homelab
git add scripts/uzlet-handover-cleanup.sh
git commit -m "ops: add uzlet handover cleanup script"
```

---

### Task 3: HANDOVER.md megírása a megbízónak

**Files:**
- Létrehozni: `/root/uzlet/HANDOVER.md`

- [ ] **Step 1: HANDOVER.md létrehozása** `[LXC 109]`

```bash
cat > /root/uzlet/HANDOVER.md << 'EOF'
# Uzlet Projekt - Telepítési Útmutató

## Mit tartalmaz az USB

- `vzdump-lxc-111-*.tar.zst` - Scraper LXC (PostgreSQL + Python + Playwright)
- `vzdump-lxc-120-*.tar.zst` - Claude Code dev környezet (uzlet projekt + Claude memory)

## Előfeltétel

- Proxmox VE (bármely verzió)
- LVM-thin storage pool legalább 25 GB szabad hellyel

## Import

```bash
# Proxmox hoston - válassz szabad VMID-eket
pct restore <VMID-A> vzdump-lxc-111-*.tar.zst --storage local-lvm
pct restore <VMID-B> vzdump-lxc-120-*.tar.zst --storage local-lvm
```

Proxmox web UI-ban mindkét LXC-hez:
- Network → IP cím beállítása a saját hálózatodnak megfelelően
- Start LXC

## SSH összekötés (Claude dev env → Scraper)

A Claude dev LXC-n (VMID-B) belül:

```bash
# Új SSH keypair generálása
ssh-keygen -t ed25519 -C "uzlet-claude-mgmt"

# Public key másolása a scraper LXC-re
ssh-copy-id root@<SCRAPER-LXC-IP>

# SSH config létrehozása
cat > ~/.ssh/config << 'SSHEOF'
Host scraper
    HostName <SCRAPER-LXC-IP>
    User root
    IdentityFile ~/.ssh/id_ed25519
SSHEOF

# Teszt
ssh scraper "hostname"
```

## Claude API key beállítása

A Claude dev LXC-n (VMID-B):

```bash
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.bashrc
source ~/.bashrc
```

Saját Claude API key szükséges: https://console.anthropic.com/

## Git remote frissítése

```bash
cd /root/uzlet
git remote set-url origin git@github.com:<TE-GITHUB-USER>/uzlet.git

# SSH public key feltöltése GitHub-ra:
cat ~/.ssh/id_ed25519.pub
# → GitHub → Settings → SSH and GPG keys → New SSH key
```

## Első indítás

```bash
cd /root/uzlet
claude
```

A projekt memória (CLAUDE.md, korábbi tervek, architektúra leírások) automatikusan betöltődik.

## Opcionális: Web search MCPs (Tavily / Firecrawl)

Saját API kulcsok megszerzése után:

```bash
mkdir -p ~/.secrets
echo "sajat-api-key" > ~/.secrets/tavily-api-key
chmod 600 ~/.secrets/tavily-api-key

claude mcp add --scope user tavily -- bash -c \
  "TAVILY_API_KEY=\$(cat ~/.secrets/tavily-api-key) npx -y tavily-mcp"
```

## Scraper státusz ellenőrzése

```bash
ssh scraper "systemctl status uzlet-web.service"
ssh scraper "systemctl status scraper.timer"
ssh scraper "cd /root/uzlet && python check.py"
```
EOF
```

- [ ] **Step 2: Ellenőrzés**

```bash
cat /root/uzlet/HANDOVER.md
```

- [ ] **Step 3: Commit az uzlet repóba** `[LXC 109]`

```bash
cd /root/uzlet
git add HANDOVER.md
git commit -m "docs: add handover guide for new operator"
git push
```

---

### Task 4: LXC 109 klónozása

**Files:** -

- [ ] **Step 1: SSH a Proxmox hosthoz** (külön terminálban, NEM a Claude session-ben)

```bash
ssh root@192.168.0.109
```

- [ ] **Step 2: Klón létrehozása** `[PROXMOX HOST]`

```bash
pct clone 109 120 --full --description "uzlet-handover-temp"
```

Ez eltart 2-5 percig. Sikeres ha: `clone exit code 0`

- [ ] **Step 3: Klón elindítása** `[PROXMOX HOST]`

```bash
pct start 120
sleep 5
pct status 120
```

Elvárt: `status: running`

- [ ] **Step 4: Thin pool ellenőrzése klón után** `[PROXMOX HOST]`

```bash
lvs pve/data --noheadings -o data_percent
```

Elvárt: < 95%. Ha ≥ 95% → azonnal futtasd a cleanup-ot és exportálj, ne hagyd ott a klónt.

---

### Task 5: Cleanup futtatása LXC 120-on

**Files:** -

- [ ] **Step 1: Cleanup parancsok futtatása** `[PROXMOX HOST]`

A parancsok közvetlenül a klónon futnak `pct exec`-en keresztül (nincs szükség fájlmásolásra):

```bash
pct exec 120 -- bash -c '
set -e
echo "[1/5] Homelab projektek..."
rm -rf /root/homelab /root/learning /root/youtube
echo "OK"

echo "[2/5] SSH kulcsok (KRITIKUS)..."
rm -f /root/.ssh/id_ed25519 /root/.ssh/id_ed25519.pub
rm -f /root/.ssh/config /root/.ssh/known_hosts /root/.ssh/known_hosts.old
echo "OK"

echo "[3/5] Secrets..."
rm -rf /root/.secrets/
echo "OK"

echo "[4/5] Claude homelab fájlok..."
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

echo "[5/5] Cleanup kész!"
'
```

Elvárt kimenet:
```
[1/5] Homelab projektek... OK
[2/5] SSH kulcsok (KRITIKUS)... OK
[3/5] Secrets... OK
[4/5] Claude homelab fájlok... OK
[5/5] Cleanup kész!
```

---

### Task 6: Audit - homelab secret scan

**Files:** -

- [ ] **Step 1: Secrets mappa üres?** `[PROXMOX HOST]`

```bash
pct exec 120 -- bash -c "ls /root/.secrets/ 2>/dev/null && echo 'WARN: secrets nem üres!' || echo 'OK: secrets törölve'"
```

Elvárt: `OK: secrets törölve`

- [ ] **Step 2: SSH private key eltűnt?** `[PROXMOX HOST]`

```bash
pct exec 120 -- bash -c "ls /root/.ssh/id_* 2>/dev/null && echo 'WARN: SSH key maradt!' || echo 'OK: SSH key törölve'"
```

Elvárt: `OK: SSH key törölve`

- [ ] **Step 3: Homelab projekt eltűnt?** `[PROXMOX HOST]`

```bash
pct exec 120 -- bash -c "ls /root/homelab 2>/dev/null && echo 'WARN: homelab mappa maradt!' || echo 'OK'"
```

Elvárt: `OK`

- [ ] **Step 4: Claude homelab fájlok eltűntek?** `[PROXMOX HOST]`

```bash
pct exec 120 -- bash -c "
  [ -f /root/.claude/history.jsonl ] && echo 'WARN: history.jsonl maradt!' || echo 'OK: history törölve'
  [ -d /root/.claude/projects/-root-homelab ] && echo 'WARN: homelab memory maradt!' || echo 'OK: homelab memory törölve'
  [ -f /root/.claude/settings.json ] && echo 'WARN: settings.json maradt!' || echo 'OK: settings törölve'
  [ -f /root/.claude.json ] && echo 'WARN: .claude.json maradt!' || echo 'OK: .claude.json törölve'
"
```

Elvárt: mind a 4 sor `OK`-val kezdődik.

- [ ] **Step 5: Uzlet memory nem tartalmaz homelab referenciát?** `[PROXMOX HOST]`

```bash
pct exec 120 -- bash -c "
  grep -r 'github-token\|haos-api-key\|karakeep-api\|n8n-api\|vaultwarden\|homelable-mcp' \
    /root/.claude/projects/-root-uzlet/ 2>/dev/null \
    && echo 'WARN: gyanús tartalom az uzlet memoryben!' \
    || echo 'OK: uzlet memory tiszta'
"
```

Elvárt: `OK: uzlet memory tiszta`

- [ ] **Step 6: Uzlet projekt megvan?** `[PROXMOX HOST]`

```bash
pct exec 120 -- bash -c "ls /root/uzlet/ | head -10 && echo '---' && ls /root/uzlet/.env 2>/dev/null && echo '.env: OK' || echo 'WARN: .env hiányzik'"
```

Elvárt: uzlet fájlok listája + `.env: OK`

**Ha bármelyik audit WARN-t ad → NE exportálj. Kézzel javítsd a problémát, majd futtasd újra az auditot.**

---

### Task 7: LXC 120 exportálása (claude-mgmt klón)

**Files:** -

- [ ] **Step 1: Klón leállítása** `[PROXMOX HOST]`

```bash
pct stop 120
pct status 120
```

Elvárt: `status: stopped`

- [ ] **Step 2: vzdump futtatása** `[PROXMOX HOST]`

```bash
vzdump 120 --storage local --mode stop --compress zstd
```

Ez eltart 5-15 percig (tömörítés). Sikeres ha: `Backup job finished successfully`

- [ ] **Step 3: Dump fájl ellenőrzése** `[PROXMOX HOST]`

```bash
ls -lh /var/lib/vz/dump/vzdump-lxc-120-*.tar.zst
```

Elvárt: fájl létezik, mérete > 1 GB (ha < 500 MB → valami baj van)

---

### Task 8: LXC 111 exportálása (scraper)

**Files:** -

- [ ] **Step 1: Scraper leállítása** `[PROXMOX HOST]`

```bash
pct stop 111
pct status 111
```

Elvárt: `status: stopped`

- [ ] **Step 2: vzdump futtatása** `[PROXMOX HOST]`

```bash
vzdump 111 --storage local --mode stop --compress zstd
```

- [ ] **Step 3: Scraper visszaindítása** `[PROXMOX HOST]`

```bash
pct start 111
sleep 10
pct exec 111 -- bash -c "systemctl status uzlet-web.service --no-pager | head -5"
```

Elvárt: `active (running)`

- [ ] **Step 4: Dump fájl ellenőrzése** `[PROXMOX HOST]`

```bash
ls -lh /var/lib/vz/dump/vzdump-lxc-111-*.tar.zst
```

Elvárt: fájl létezik, mérete > 1 GB

---

### Task 9: USB másolás + takarítás

**Files:** -

- [ ] **Step 1: USB mount** `[PROXMOX HOST]`

```bash
# USB eszköz azonosítása (amit a pre-flight checkben feljegyeztél)
lsblk | grep -E "sd[b-z]"

# Mount
mkdir -p /mnt/usb
mount /dev/sdX1 /mnt/usb    # sdX1 cseréld az USB partícióra
df -h /mnt/usb
```

Elvárt: `/mnt/usb` megjelenik a df outputban, elég szabad hely van.

- [ ] **Step 2: Dump fájlok másolása USB-re** `[PROXMOX HOST]`

```bash
cp -v /var/lib/vz/dump/vzdump-lxc-120-*.tar.zst /mnt/usb/
cp -v /var/lib/vz/dump/vzdump-lxc-111-*.tar.zst /mnt/usb/
sync
```

A `sync` fontos - megvárja hogy minden adat kiírásra kerüljön az USB-re.

- [ ] **Step 3: USB tartalom ellenőrzése** `[PROXMOX HOST]`

```bash
ls -lh /mnt/usb/
```

Elvárt: mindkét `.tar.zst` fájl látható, méretük megegyezik az eredetivel.

- [ ] **Step 4: USB leválasztása** `[PROXMOX HOST]`

```bash
umount /mnt/usb
echo "USB leválasztva."
```

- [ ] **Step 5: Klón törlése (thin pool felszabadítása)** `[PROXMOX HOST]`

```bash
pct destroy 120
lvs pve/data --noheadings -o data_percent
```

Elvárt: Data% visszaesett a klónozás előtti értékre (~87%).

- [ ] **Step 6: Dump fájlok törlése a Proxmox hostról** `[PROXMOX HOST]`

```bash
rm /var/lib/vz/dump/vzdump-lxc-120-*.tar.zst
rm /var/lib/vz/dump/vzdump-lxc-111-*.tar.zst
df -h /var/lib/vz
```

Elvárt: hely visszajött.

---

### Task 10: GitHub repo fork + átadás

**Files:** -

- [ ] **Step 1: (Opcionális) Fork referencia gyanánt**

GitHub böngészőben:
- Menj: `https://github.com/Pironex9/uzlet`
- Kattints: **Fork** → Create fork
- Repository name: `uzlet-archive`
- Ez megmarad nálad mint olvasható referencia

- [ ] **Step 2: Megbízó GitHub usernevének bekérése**

A megbízótól kérd el a GitHub felhasználónevét az átadáshoz.

- [ ] **Step 3: Repo átadás** (GitHub web UI)

- Menj: `https://github.com/Pironex9/uzlet/settings`
- Görgess le: **Danger Zone** → **Transfer repository**
- "New owner": add meg a megbízó GitHub usernevét
- Confirm: írd be `Pironex9/uzlet`
- Kattints: **I understand, transfer this repository**

- [ ] **Step 4: Megbízó elfogadja az emailben érkező meghívót**

A megbízónak email érkezik, el kell fogadnia az átadást. Ezután a repo az ő accountjában lesz.

- [ ] **Step 5: Ellenőrzés**

```bash
cd /root/uzlet
git remote -v
```

Elvárt: még `git@github.com:Pironex9/uzlet.git` (az átadás nem változtatja meg a helyi git config-ot - ez normális, a megbízónak kell frissíteni a sajátján).

---

## Összefoglalás: Mit kap a megbízó

| Komponens | Tartalom | Homelab secret? |
|-----------|----------|-----------------|
| `vzdump-lxc-120-*.tar.zst` | Claude dev env + uzlet projekt + projekt memory | Nem |
| `vzdump-lxc-111-*.tar.zst` | Scraper + PostgreSQL + Python + Playwright | Nem |
| GitHub repo (`github.com/<megbizo>/uzlet`) | Teljes uzlet forráskód | Nem |
| `HANDOVER.md` | Setup útmutató (a repóban) | Nem |
