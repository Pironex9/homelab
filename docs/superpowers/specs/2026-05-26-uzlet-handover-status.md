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
- Cleanup script: `scripts/uzlet-handover-cleanup.sh` (törölve 2026-08-23, lásd a lezáró szakaszt)
- Megbízó útmutató: `/root/uzlet/HANDOVER.md` (uzlet repóban; a helyi másolat 2026-08-23-án törölve, az archívumban megvan)

---

## Lezárás: teljes eltávolítás a homelabból

**Dátum:** 2026-08-23

Az átadás után az uzlet még hónapokig ott maradt a homelabban félig letörölve:
az LXC 111 már nem futott, de a rá mutató hivatkozások igen. Ez a szakasz zárja le.

### Ami a gépekről ténylegesen eltűnt

| Hol | Mi | Mikor |
|---|---|---|
| pve | LXC 111 (`uzlet`, 192.168.0.115) | az átadáskor, 2026-05-26 |
| LXC 109 | `/root/uzlet` (81 MB) | 2026-08-23 |
| LXC 109 | `/root/.claude/projects/-root-uzlet` (14 MB) | 2026-08-23 |

A `/root/uzlet` **nem** volt teljesen commitolva a GitHub repóba: módosítva volt a
`.gitignore` és a `scripts/metro_multi_verify.py`, törölve a `prev_ar`, és hat
untracked fájl állt ott (motivációs levél PDF, `DESIGN.md`, `docs/adr/0002-*.md`,
`docs/osszegzes-2026-06*`, `.playwright/`). A GitHub repo tehát nem volt teljes
másolat - a tar az.

### Az archívum

Két bit-azonos példány, md5 `06d2ca62d131f53c41ad8fa37a6403ab`, 32 MB:

- `/root/uzlet-archive.tar.gz` (LXC 109)
- `/mnt/storage/backup/uzlet-archive-2026-08-23.tar.gz` (MergerFS, LXC 100)

```bash
tar czf /root/uzlet-archive.tar.gz /root/uzlet /root/.claude/projects/-root-uzlet
```

10834 bejegyzés (10772 + 62), pontosan annyi, amennyit a `find` számolt törlés
előtt. `gzip -t` OK, és két fájl próbakicsomagolása is ép volt. Tartalmazza a
`.env`-et a B2B scraper loginokkal, a teljes `.git`-et és a projekt-memóriát -
tehát ez a tar titkot tárol, root-only jogokkal kezelendő.

Harmadik menekülő út: az LXC 109 benne van a pve nightly vzdump jobjában (02:00,
`keep-daily=7,keep-weekly=4,keep-monthly=3`, `backup-hdd`), így a törlés előtti
állapot még ~3 hónapig kihúzható onnan is.

### Ami a repóból kikerült

- `compose/proxmox-lxc-100/homepage/config/` - az `Uzlet` bookmark-csoport a három
  linkjével (`bookmarks.yaml`) és a `layout:` bejegyzése (`settings.yaml`)
- `compose/proxmox-lxc-100/topology/nodes.yml` - az LXC 111 node; a build ezután
  14 node / 2 site
- `compose/vps/landing/` - `topology.png`, `topology.webp`, `og.png` újrarenderelve,
  `og.html` és `src/index.html` szöveges számai 15-ről 14-re
- `docs/assets/topology.png` - byte-azonos másolat a landing PNG-vel
- `AGENTS.md` + `CLAUDE.md` infra-tábla - az LXC 110 sor önállóan
- `scripts/uzlet-handover-cleanup.sh` - törölve
- `scripts/prompt-analysis.py` - a `-p uzlet` példa `-p furbify`-ra
- `docs/hosts/agentos.md`, `docs/hosts/claude-mgmt.md` - elavult uzlet-utak

Érintetlen maradt a `docs/superpowers/` alatti datált terv- és spec-anyag (ez a
fájl is): történelmi feljegyzések, és az `mkdocs.yml` `exclude_docs:` blokkja
amúgy is kizárja őket a publikált oldalból.

### Szándékosan bennehagyott maradványok

- `/root/.memsearch/milvus.db/collections/ms_uzlet_87c8443a` (27 MB) - a törölt
  transzkriptekből épített szemantikus index. A `/memory-recall` így továbbra is
  dobhat uzlet-találatokat egy nem létező projektből. Kézi `rm -rf` egy milvus
  collectionön az a művelet, ami korábban csendben megölte a keresést - ha megy,
  a memsearch saját eszközével.
- `/root/.claude.json` `projects` kulcs alatt egy `/root/uzlet` bejegyzés -
  elárvult beállítás-rekord, ártalmatlan.
- `docs/hosts/claude-mgmt.md` memsearch-méréses sora (`homelab 1199 chunks,
  uzlet 2951, rails 4`) - konkrét mérés eredménye, utólag nem írható át. Ez az
  egyetlen uzlet-találat, ami fent maradt a docs.homelabor.net-en.

### Két csapda, ami menet közben derült ki

1. **A Homepage SSG cache.** A Komodo `PullStack` a bind-mountolt `./config`-ot
   cseréli a futó konténeren belül, deploy nélkül is - de a renderelt HTML addig
   a régi marad, amíg `curl http://192.168.0.110:3002/api/revalidate` le nem üti.
2. **A landing diagram 24 órás böngésző-cache-e.** A `Caddyfile` `@diagram`
   szabálya `Cache-Control: public, max-age=86400` fejlécet küld a `*.png`/`*.webp`
   fájlokra, így a böngésző egy napig nem is kérdez rá az új ábrára. Az origin
   közben már a helyeset adja. A `/topology/` azért frissül azonnal, mert `.html`,
   és az a `@revalidate` szabály alá esik `no-cache`-sel. Nyitott javaslat: a
   `*.png *.webp` átvitele a `@revalidate` matcherbe, ára egy 304 látogatásonként.
