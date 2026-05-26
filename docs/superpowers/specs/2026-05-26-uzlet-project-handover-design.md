# Uzlet projekt átadás - Design Spec

**Dátum:** 2026-05-26  
**Cél:** Az uzlet (Slovak B2B price scraper) projekt átadása a megbízónak, homelab secretek szivárgása nélkül.

---

## Összefoglalás

Két LXC-t adunk át `vzdump` exporttal USB-n, plusz a GitHub repót áttranszferáljuk. A megbízónak Proxmox kell az importhoz.

**Átadott komponensek:**
- **LXC 111** (scraper, 192.168.0.115) - teljes export, nincs cleanup szükséges
- **LXC 109 klón** (claude-mgmt) - klón + cleanup script + export
- **GitHub repo** - `Pironex9/uzlet` → megbízó GitHub accountja

---

## Scope - mi marad, mi törlődik

### LXC 111 (scraper) - érintetlen export

Nincs homelab secret benne, egyből exportálható:
- `/root/uzlet/.env` - B2B scraper login adatok, marad (kell a megbízónak)
- PostgreSQL 15 adatbázis (termékek, árak, historia) - marad
- Python + Playwright + systemd service-ek - marad

### LXC 109 klón - cleanup script

**Törlendő (homelab secretek és projektek):**

| Mit | Miért |
|-----|-------|
| `/root/homelab/` | homelab git repo |
| `/root/learning/`, `/root/youtube/` | személyes projektek |
| `~/.ssh/id_ed25519` + `.pub` | SSH private key - hozzáfér az összes homelab hosthoz |
| `~/.ssh/config` | homelab host lista (proxmox, docker-host, komodo, stb.) |
| `~/.ssh/known_hosts` | homelab host fingerprint-ek |
| `~/.secrets/*` | mind a 11 API kulcs fájl (github-token, haos-api-key, n8n-*, stb.) |
| `~/.claude/history.jsonl` | vegyes homelab+uzlet beszélgetések |
| `~/.claude/sessions/` | vegyes session-ök |
| `~/.claude/projects/-root-homelab/` | homelab project memory |
| `~/.claude/settings.json` | github + karakeep MCP konfig (homelab specifikus) |
| `~/.claude.json` | tavily/firecrawl wrapper (törölt secrets-re mutat) |

**Megmaradó (uzlet-specifikus):**

| Mit | Tartalom |
|-----|----------|
| `/root/uzlet/` | teljes uzlet projekt kód |
| `~/.claude/projects/-root-uzlet/` | uzlet memory, PLAN mentések, projekt kontextus |
| `~/.claude/plugins/` | superpowers, skill-creator, stb. |
| `~/.claude/agents/` | research, planner, writer, code-reviewer |
| `~/.claude/skills/` | uzlet custom skill-ek |
| System packages | Python, Playwright, Node, pip csomagok |

---

## Folyamat

### 1. lépés - LXC 109 klón létrehozása (Proxmox hoston - nem az LXC-n belül!)

```bash
# Proxmox web UI termináljában vagy SSH-val a pve hosthoz (192.168.0.109)
pct clone 109 120 --full --description "uzlet-handover-temp"
pct start 120
# majd belépés a klónba:
pct exec 120 -- bash
```

### 2. lépés - Cleanup script futtatása (LXC 120-on)

```bash
# Projektek
rm -rf /root/homelab /root/learning /root/youtube

# SSH (KRITIKUS)
rm -f ~/.ssh/id_ed25519 ~/.ssh/id_ed25519.pub
rm -f ~/.ssh/config ~/.ssh/known_hosts ~/.ssh/known_hosts.old

# Secrets (mind)
rm -rf ~/.secrets/

# Claude - homelab specifikus fájlok
rm -f ~/.claude/history.jsonl
rm -rf ~/.claude/sessions/
rm -rf ~/.claude/projects/-root-homelab/
rm -f ~/.claude/settings.json
rm -f ~/.claude.json
```

### 3. lépés - Audit (semmi nem maradhat)

```bash
# Secrets mappa üres?
ls ~/.secrets/ 2>/dev/null && echo "WARN: secrets mappa nem üres!" || echo "OK: secrets törölve"

# SSH private key eltűnt?
ls ~/.ssh/id_* 2>/dev/null && echo "WARN: SSH key maradt!" || echo "OK: SSH key törölve"

# Homelab projekt eltűnt?
ls /root/homelab 2>/dev/null && echo "WARN: homelab mappa maradt!" || echo "OK"

# Nincs maradék homelab referencia az uzlet memoryben?
grep -r "homelab\|karakeep\|haos\|vaultwarden\|n8n-api\|github-token" \
  ~/.claude/projects/-root-uzlet/ 2>/dev/null \
  && echo "WARN: gyanús szöveg az uzlet memoryben" || echo "OK: uzlet memory tiszta"
```

### 4. lépés - Export

```bash
# Proxmox hoston futtatni
pct stop 120

# LXC 109 klón export
vzdump 120 --storage local --mode stop --compress zstd
# → /var/lib/vz/dump/vzdump-lxc-120-YYYY_MM_DD-HH_MM_SS.tar.zst

# LXC 111 export (rövid downtime a scraper service-re)
pct stop 111
vzdump 111 --storage local --mode stop --compress zstd
# → /var/lib/vz/dump/vzdump-lxc-111-YYYY_MM_DD-HH_MM_SS.tar.zst
pct start 111

# Fájlok másolása USB-re
mount /dev/sdX1 /mnt/usb
cp /var/lib/vz/dump/vzdump-lxc-120-*.tar.zst /mnt/usb/
cp /var/lib/vz/dump/vzdump-lxc-111-*.tar.zst /mnt/usb/
umount /mnt/usb

# Klón törlése (neked már nem kell)
pct destroy 120
```

### 5. lépés - GitHub repo átadás

**Előtte (opcionális, ajánlott):** fork magadnak referencia gyanánt:
- GitHub: `Pironex9/uzlet` → Fork → `Pironex9/uzlet-archive`

**Átadás:**
- GitHub → `Pironex9/uzlet` → Settings → Danger Zone → "Transfer repository"
- Megbízó GitHub felhasználónevét megadni
- A megbízó elfogadja az emailben érkező meghívót

---

## Megbízónál - setup (20-30 perc)

### Import

```bash
# Proxmox-on - VMID-ket a megbízó választja
pct restore 100 vzdump-lxc-111-*.tar.zst --storage local-lvm
pct restore 101 vzdump-lxc-120-*.tar.zst --storage local-lvm
pct start 100
pct start 101
```

### Hálózat + SSH összekötés

```bash
# claude-mgmt klónon (101-es LXC)
ssh-keygen -t ed25519 -C "uzlet-claude-mgmt"

# SSH public key feltöltése GitHub-ra (Settings → SSH keys)
cat ~/.ssh/id_ed25519.pub

# ~/.ssh/config létrehozása
cat > ~/.ssh/config << 'EOF'
Host scraper
    HostName <uj-scraper-ip>
    User root
    IdentityFile ~/.ssh/id_ed25519
EOF

# Public key másolása a scraper LXC-re
ssh-copy-id root@<uj-scraper-ip>
```

### Claude API key

```bash
# ~/.bashrc-be vagy ~/.profile-ba
export ANTHROPIC_API_KEY="sk-ant-..."
```

### Git remote frissítése

```bash
cd /root/uzlet
git remote set-url origin git@github.com:<megbizo-github>/uzlet.git
git pull  # ellenőrzés
```

### Első indítás

```bash
cd /root/uzlet
claude
# Az uzlet project memory automatikusan betöltődik
```

---

## Opcionális: MCPs visszaállítása

Ha a megbízó szeretné a Tavily / Firecrawl MCP-ket (web search, scraping):

```bash
# Saját API kulcsok megszerzése után
mkdir -p ~/.secrets
echo "sajat-tavily-api-key" > ~/.secrets/tavily-api-key
chmod 600 ~/.secrets/tavily-api-key

claude mcp add --scope user tavily -- bash -c \
  "TAVILY_API_KEY=\$(cat ~/.secrets/tavily-api-key) npx -y tavily-mcp"
```

---

## Kockázatok és megjegyzések

- **`~/.claude/history.jsonl` törlése visszafordíthatatlan** - a nyers beszélgetés-előzmények elvesznek, de az uzlet project memory megmarad
- **LXC 111 `.env`-je tartalmaz B2B scraper loginokat** - ez szándékos, kell a megbízónak
- A megbízó saját `ANTHROPIC_API_KEY`-t kell szerezzen (nem adható tovább a tied)
- Az audit lépés kötelező - ne hagyd ki az export előtt
