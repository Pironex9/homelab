# Uzlet Projekt Átadás - Státusz Dokumentáció

**Dátum:** 2026-05-26  
**Státusz:** Részben kész - GitHub repo átadás függőben

---

## Összefoglalás

Az uzlet (Slovak B2B price scraper) projekt átadása a megbízónak. Két LXC export USB-n elkészült és átadásra kész. A GitHub repo átadás még nem történt meg - külön lépés.

---

## Elvégzett lépések

### 1. HANDOVER.md a megbízónak
- Fájl: `/root/uzlet/HANDOVER.md`
- Commit: `4f51286 docs: add handover guide for new operator`
- Tartalom: telepítési útmutató az LXC-k importálásához, SSH összekötéshez, Claude API key beállításhoz
- Push: `git@github.com:Pironex9/uzlet.git main` - sikeres

### 2. LXC 109 klón cleanup (VMID 120)
Klón létrehozva, alábbiak törölve, majd klón megsemmisítve:

**Törölt homelab anyagok:**
- `/root/homelab/`, `/root/learning/`, `/root/youtube/`
- `~/.ssh/id_ed25519` + `.pub` (SSH private key - homelab hozzáférés)
- `~/.ssh/config`, `~/.ssh/known_hosts`
- `~/.secrets/` (mind a 11 API kulcs fájl)
- `~/.claude/history.jsonl`
- `~/.claude/sessions/`
- `~/.claude/projects/-root-homelab/`
- `~/.claude/settings.json`
- `~/.claude.json`
- `~/.claude/shell-snapshots/`, `session-env/`, `paste-cache/`, `file-history/`, `backups/`, `debug/`
- `~/.claude/projects/-root-uzlet/*.jsonl` (session logok - MCP wrapper referenciákat tartalmaztak)

**Megmaradt (uzlet-specifikus):**
- `/root/uzlet/` - teljes projekt kód + `.env`
- `~/.claude/projects/-root-uzlet/memory/` - strukturált projekt memória (MEMORY.md + 11 feedback/project fájl)
- `~/.claude/plugins/`, `~/.claude/agents/`, `~/.claude/skills/` - Claude eszköztár

**Audit eredmény:** Mind a 8 ellenőrzési pont OK - semmilyen homelab secret nem maradt.

### 3. LXC 120 vzdump export
- Fájl: `vzdump-lxc-120-2026_05_26-19_30_07.tar.zst`
- Méret: 3.3 GB
- Tartalom: Claude Code dev környezet + uzlet projekt + uzlet memory

### 4. LXC 111 vzdump export (scraper)
- Fájl: `vzdump-lxc-111-2026_05_26-19_31_44.tar.zst`
- Méret: 3.5 GB
- Tartalom: PostgreSQL 15 (distributor_db), Python + Playwright scrapers, FastAPI web app (port 8001), Metabase (port 3000), systemd service-ek

### 5. USB másolás
- USB: `/dev/sde1` (FAT32, 58.6 GB)
- Mindkét `.tar.zst` fájl átmásolva, `sync` futtatva, leválasztva
- Proxmox hostról dump fájlok törölve
- Klónozásból maradt snapshot (`snap_vm-109-disk-0_snap-for-clone`, 12 GB) törölve

---

## Függőben: GitHub repo átadás

**Mikor kell elvégezni:** Amikor a megbízó készen áll átvenni a repót.

**Lépések (böngészőből):**

1. Menj: `https://github.com/Pironex9/uzlet/settings`
2. Görgess le: **Danger Zone**
3. Kattints: **Transfer repository**
4. "New owner" mezőbe: megbízó GitHub felhasználóneve
5. Confirm mezőbe: `Pironex9/uzlet`
6. Kattints: **I understand, transfer this repository**
7. Megbízónak emailben érkezik a meghívó - el kell fogadnia

**Fontos tudni:**
- Az átadás után te elveszíted a repo hozzáférést (hacsak a megbízó nem ad vissza collaborator jogot)
- A helyi másolat megmarad: `/root/uzlet/` LXC 109-en
- GitHub nem engedi saját repo forkolását ugyanarra az accountra - ha kell archive, előtte új repóba kell pusholni (`git push archive main`)
- Az átadás után a megbízónak frissítenie kell a git remote-ot a saját LXC-jén: `git remote set-url origin git@github.com:<o-username>/uzlet.git`

---

## Mit kap a megbízó

| Komponens | Fájl / Helyszín | Tartalom |
|-----------|-----------------|----------|
| Claude dev env | `vzdump-lxc-120-2026_05_26-19_30_07.tar.zst` | uzlet projekt + Claude memory |
| Scraper | `vzdump-lxc-111-2026_05_26-19_31_44.tar.zst` | PostgreSQL + Python + Playwright |
| GitHub repo | `github.com/Pironex9/uzlet` (átadás után: megbízó accountján) | Teljes forráskód |
| Setup útmutató | `HANDOVER.md` (a repóban) | Import + konfigurálás lépései |

---

## Kapcsolódó fájlok

- Design spec: `docs/superpowers/specs/2026-05-26-uzlet-project-handover-design.md`
- Implementációs terv: `docs/superpowers/plans/2026-05-26-uzlet-handover.md`
- Cleanup script: `scripts/uzlet-handover-cleanup.sh`
- Megbízó útmutató: `/root/uzlet/HANDOVER.md` (uzlet repóban)
