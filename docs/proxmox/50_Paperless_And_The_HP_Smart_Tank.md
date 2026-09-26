**Date:** 2026-09-26
**Host:** LXC 100 docker-host (192.168.0.110), ports 8000 (Paperless) and 8086 (scanservjs)
**LAN names:** `https://paperless.lan`, `https://scan.lan` via Caddy (LXC 110)
**Printer:** HP Smart Tank 750, 192.168.0.53

---

# Paperless-ngx and a Printer That Cannot Send a Scan Anywhere

The goal was a paper loop in both directions: a scanned page ends up in Paperless-ngx,
OCR'd and searchable, and a document in Paperless can go back out to the printer. The
printer is a consumer all-in-one, and the shape of the whole setup follows from three
things it turned out not to do.

**End to end, measured:** a flatbed scan started from the scanservjs API landed in the
consume folder as a 15 KB PDF, and Paperless had it OCR'd, archived as PDF/A-2b and
listed as document 1 about ten seconds later.

---

## What the printer can and cannot do

Everything below was read from the device itself, not from a spec sheet.

| Question | Answer | Where it came from |
|---|---|---|
| Can it push a scan to a network folder, FTP or email? | **No** | `/DevMgmt/DiscoveryTree.xml` lists no scan-destination or walk-up-scan manifest, only `eSCL:eSclManifest` and `ledm:hpLedmScanJobManifest` |
| Can something else pull a scan from it? | Yes, over eSCL | `https://192.168.0.53/eSCL/ScannerCapabilities` answers, Mopria-certified scan 1.5 |
| Does the feeder scan both sides? | **No** | eSCL advertises `AdfSimplexInputCaps` only, no duplex caps; 35-sheet feeder |
| Does it accept a PDF to print? | **No** | IPP `pdf-versions-supported = none`; `document-format-supported` is PCL, JPEG, URF, PWG raster and PCLm |
| Can it print both sides? | Yes | IPP `sides-supported` includes `two-sided-long-edge` |

Each "no" removed an option:

- **No scan-to-folder** means the printer's own Scan button can never deliver to Paperless.
  The scan has to be started from a server that pulls it. That is
  [scanservjs](https://github.com/sbs20/scanservjs): a web page, open on the phone next to
  the printer, with a Scan button.
- **Single-sided feeder** means double-sided paper needs two passes. scanservjs has this
  built in as the batch mode *auto collate*: feed the stack, flip it, feed it again, and it
  interleaves the pages into one PDF. Paperless has its own version of the same trick
  (`PAPERLESS_CONSUMER_ENABLE_COLLATE_DOUBLE_SIDED`); it is not enabled, one mechanism is
  enough.
- **No PDF over IPP** means a server-side "print this document" would need a full CUPS
  with filters to rasterise the PDF first. It is not needed: Paperless has a Print button
  in the document view since
  [PR #10626](https://github.com/paperless-ngx/paperless-ngx/pull/10626), which hands the
  document to the browser's print dialog, and every client OS (Windows, Android, iOS)
  already rasterises for this printer through IPP Everywhere / AirPrint / Mopria.

## The stack

`compose/proxmox-lxc-100/paperless/` - three containers:

| Container | Image | Role |
|---|---|---|
| `paperless` | `ghcr.io/paperless-ngx/paperless-ngx:3.2` | The archive, OCR in Hungarian and Slovak |
| `paperless-broker` | `valkey/valkey:9-alpine` | Task queue |
| `scanservjs` | `sbs20/scanservjs:v3.3.0` | Scan UI; its output directory **is** the Paperless consume directory |

**SQLite, not Postgres.** It is the documented default in Paperless 3.x
(`PAPERLESS_DBENGINE: sqlite`), and a household archive with one or two users is far below
where it matters. It also saves a container on a host that had 3.1 GiB of RAM available
before this went in.

**Everything lives under `/srv/docker-data/paperless`**, on the LXC 100 root disk, which the
daily vzdump of the container backs up. The documents are therefore in the backup without
any extra job. The cost is disk: that root disk was at 84% after the images were pulled,
which is worth watching given the pve thin-pool history.

**Secrets** (`PAPERLESS_SECRET_KEY`, `PAPERLESS_ADMIN_PASSWORD`) are in the Komodo Stack
Environment, not in git. The admin password is only read on the very first start, when
Paperless creates the superuser.

**OCR languages:** `hun` and `slk` are not in the image. `PAPERLESS_OCR_LANGUAGES: hun slk`
makes the container install them at start (visible in the log as `init-tesseract-langs`),
and `PAPERLESS_OCR_LANGUAGE: hun+slk` uses both.

## Two things that broke, and why

### 1. scanservjs showed no scanner at all

`AIRSCAN_DEVICES` was set, `/etc/sane.d/airscan.conf` inside the container contained the
printer under `[devices]`, and `scanimage -L` still said *No scanners were identified*.
Opening the device by name failed with the misleading `Out of memory`.

The debug log (`SANE_DEBUG_AIRSCAN=1`) showed the cause one line before the empty result:

```
MDNS: avahi_client_new failed: Daemon not running
```

The container runs no avahi daemon. With discovery enabled, sane-airscan returned an empty
list, **including the manually configured device**. With `discovery = disable` in
`[options]` the same config listed it immediately:

```
device `airscan:e0:HP Smart Tank 750' is a eSCL HP Smart Tank 750 ip=192.168.0.53
```

The image cannot set that option from the environment: its entrypoint only does
`sed -i "/^\[devices\]/a $device"`. Bind-mounting over `/etc/sane.d/airscan.conf` would
break that same `sed -i` (it replaces the file by rename). So the stack ships a small
`sane/airscan.conf` and points `SANE_CONFIG_DIR` at it:

```yaml
SANE_CONFIG_DIR: "/etc/sane-extra:"
```

The trailing colon matters: it tells SANE to search the listed directory first and then
fall back to the default `/etc/sane.d`, so `dll.conf` and every other backend config still
load from the image. `AIRSCAN_DEVICES` was removed at the same time, otherwise the printer
appears twice.

A second, independent reason the UI was empty: `SCANIMAGE_LIST_IGNORE=true` tells scanservjs
not to run `scanimage -L` at all and to take the list from the `DEVICES` variable instead.
With it set and `DEVICES` empty, the list is empty no matter what SANE finds. It was dropped;
with discovery off, `scanimage -L` is fast anyway.

### 2. Login worked over http and failed over https

Measured with a scripted login (GET the form for the CSRF token, POST it back):

| URL | Before | After |
|---|---|---|
| `https://paperless.lan` | **403** | 302 to `/dashboard` |
| `http://paperless.lan` | 302 | 302 |
| `http://192.168.0.110:8000` | 302 | 302 |

Behind Caddy the request reaches Paperless as plain http, so Django computes the expected
origin as `http://paperless.lan`, while the browser sends `Origin: https://paperless.lan`.
The fix is `PAPERLESS_CSRF_TRUSTED_ORIGINS: https://paperless.lan`.

The documented alternative, `PAPERLESS_URL`, was deliberately not used: it also narrows
`ALLOWED_HOSTS` to that one name, which would lock out the direct `192.168.0.110:8000`
address that the Homepage status dot checks.

## AI suggestions on the desktop's Ollama

Added the same day. OCR stays Tesseract 5.5.0 under OCRmyPDF 17.12.1, local to the container;
the LLM only powers the optional features: the **Suggest** button (title, date, tags,
correspondent, type), the document chat, and the LLM index behind both.

| Setting | Value |
|---|---|
| Backend | `ollama` at `http://192.168.0.100:11434` (the Nobara desktop, RTX 2060 SUPER, 8 GB) |
| Model | `qwen3:8b-nothink` (5.2 GB) |
| Embeddings | `nomic-embed-text` via the same Ollama |
| Index refresh | `30 20 * * *` instead of the 02:10 default |

**Manual use only, no "Apply AI Suggestions" workflow.** The Ollama host is a desktop that is
off or booted into Windows part of the day, and its 8 GB of VRAM is shared with Immich ML and
games. Consumption, OCR, search and the classic (non-LLM) suggestions never touch it. The
index refresh moved to the evening for the same reason: at 02:10 the desktop is usually off.

**Measured on a fictional Hungarian electricity invoice** (uploaded as text, deleted after):

- consumption 0.4 s, the per-document embedding into the LLM index 4.1 s
- `ai_suggestions` answered in **33 s**, cold model load included
- issue date `2026-09-15` and due date `2026-10-01` correct; correspondent correct, plus one
  junk candidate (the service address); tags and title came back in English, because the
  output language follows the user's UI language unless `PAPERLESS_AI_LLM_OUTPUT_LANGUAGE`
  is set
- afterwards Ollama held **5.6 GB** of VRAM until its keep-alive expired - that is the window
  in which Immich ML or a game can be starved

### The classic date parser gets Hungarian numeric dates wrong

The same invoice got the created date **2026-01-08** from the built-in (non-AI) parser. The
cause is `PAPERLESS_DATE_ORDER`, default `DMY`. Tested with `dateparser` inside the container:

| Input | `DMY` (default) | `YMD` |
|---|---|---|
| `2026.08.01` (Hungarian numeric) | **2026-01-08** | 2026-08-01 |
| `2026-08-01` (ISO) | **2026-01-08** | 2026-08-01 |
| `2026. szeptember 15.` | 2026-09-15 | 2026-09-15 |
| `15.09.2026` (Slovak, 4-digit year) | 2026-09-15 | 2026-09-15 |
| `15. septembra 2026` | 2026-09-15 | 2026-09-15 |
| `15.09.26` (Slovak, 2-digit year) | 2026-09-15 | **2015-09-26** |

`YMD` fixes every 4-digit-year form in both languages and breaks only two-digit-year
day-first dates, which mostly appear on shop receipts. **Switched to `YMD` the same day**;
verified after the redeploy with a document containing `Kelt: 2026.08.01.`, which now gets
the created date 2026-08-01.

## LAN names

`paperless.lan` and `scan.lan` follow the usual pattern: AdGuard rewrite to Caddy
(192.168.0.208), a `handle` block each in the `lan_services` snippet, and the mkcert cert
regenerated with the two new SANs (35 in total).

**The AdGuard restart leaves the LAN without DNS for about ten seconds.** The YAML must be
edited with the service stopped (see [AdGuard](../hosts/adguard.md)), and on start AdGuard
loads its filter lists before it opens port 53: the log showed the web UI up at 15:09:32
and the DNS listener at 15:09:40. A `dig` right after `systemctl start` gets
*connection refused*, which looks like a failed start and is not.

## Using it

**Scan to Paperless:** open `https://scan.lan`, set Source to **ADF** (or Flatbed for a
single page), 300 dpi is plenty for OCR, pick a PDF pipeline, Scan. For double-sided paper
set Batch to **auto collate**: scan the stack, flip it, scan again. The PDF disappears from
scanservjs's file list a few seconds later - that is Paperless taking it, not an error.

**Print from Paperless:** open the document, **Print**. The client device needs the printer
installed once; Windows and Android find it on their own over IPP Everywhere / Mopria, iOS
over AirPrint.

## What was left out

- **Server-side printing** (a tag or workflow that prints without a browser): needs CUPS
  with filters, because the printer takes no PDF. Add it if printing ever has to happen
  unattended.
- **Tika and Gotenberg** (Office documents and emails): the input here is scans, which are
  PDFs already. Add them when `.docx` or `.eml` files start arriving.
- **Public access:** none. The archive holds personal documents and stays on the LAN and
  the tailnet.
