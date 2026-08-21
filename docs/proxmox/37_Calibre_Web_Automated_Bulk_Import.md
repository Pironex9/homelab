# Bulk Ebook Import to Calibre-Web-Automated, and the One PDF That Stalled the Queue

**Date:** 2026-08-21
**Hostname:** nobara, docker-host (LXC 100)
**IP address:** 192.168.0.100, 192.168.0.110

---

## Overview

Three ebook folders on the desktop had accumulated over years, partly overlapping with what was already in Calibre-Web-Automated (CWA) on LXC 100. The task was to upload only what was actually missing.

The diffing and the transfer took under five minutes. Then a single 9.6 MB PDF blocked the ingest queue for eight minutes at 100% CPU and would have held it for fifteen, because CWA converts every ingested book to EPUB by default, and this one had nothing to convert.

## Finding what is actually missing

CWA's library lives at `/mnt/storage/media/konyvek` (mapped into the container as `/calibre-library`), the watched ingest folder at `/mnt/storage/media/konyv_ingest` (`/cwa-book-ingest`):

```yaml
volumes:
  - /srv/docker-data/calibrewebauto:/config
  - /mnt/storage/media/konyv_ingest:/cwa-book-ingest
  - /mnt/storage/media/konyvek:/calibre-library
```

Filename comparison is useless here. Calibre renames on import, truncates titles to roughly 40 characters, and rewrites the author part, so `13 Things Mentally Strong People Don't Do_ Take Back Your Power, Embrace Change, Face Your Fears, and Train Your Brain for Happiness and Success - Amy Morin, Dec, 2014.epub` on the source becomes `13 Things Mentally Strong People Don't Do_ - Amy Morin.epub` in the library. The same book, nothing in common that a string match can use.

Content hashing does work, because CWA stores the original EPUB byte-for-byte:

```bash
# both sides
find <dirs> -type f \( -iname "*.epub" -o -iname "*.pdf" \) -print0 | xargs -0 sha256sum
```

| | |
|---|---|
| Source book files | 109 (105 EPUB, 4 PDF) |
| Unique by SHA-256 | 87 |
| Already in the library by hash | 30 |
| Missing | 57 |

The 109-to-87 collapse is the collections overlapping with each other; the sources were partly copies of one another.

Hash equality only catches byte-identical files, so a second pass compared normalized titles - lowercased, stripped to `[a-z0-9]`, first 25 characters - against the library filenames to catch the same book re-converted. That found two, of which one was a genuine already-present book under an identical name but a different conversion, and one was a false positive caused by Calibre's truncation: source `CCNA Certification Study Guide, Volume 2` collided with library `CCNA Certification Study Guide` because the volume number falls past the truncation point.

Final upload list: **56 files, 330 MB**.

## The transfer

Neither the desktop nor LXC 100 needed a new mount or a key exchange; the management LXC already has SSH to both, so the files streamed through it:

```bash
ssh nobara "tar cf - --null -T /tmp/list0 --transform 's|.*/||'" \
  | ssh root@192.168.0.110 "tar xvf - -C /mnt/storage/media/konyv_ingest"
```

Two details that matter:

- `--transform 's|.*/||'` flattens the nested source paths, because the upload list spans three directory trees and the ingest folder wants files, not structure. Check for basename collisions before doing this - here there were none.
- A NUL-separated list (`--null -T`) rather than newline-separated, because the filenames contain spaces, commas, colons, ampersands and accented characters.

tar exits **2** with `Cannot change ownership to uid 1000, gid 1000: Operation not permitted` for every file. This is the unprivileged LXC ID map, not a failure - all 56 files extracted. The same limitation shows up on every CWA import as `chown -R abc:abc /calibre-library returned non-zero exit status 1`, and it is equally harmless.

Writing straight into the watched folder is safe: CWA watches with `inotifywait -m -r -e close_write -e moved_to /cwa-book-ingest`, and `close_write` fires only after a file is fully written and closed.

## The PDF that stalled everything

The ingest counter dropped from 56 to 48 and then stopped for eight minutes. CWA processes one file at a time, so whatever is stuck blocks everything behind it:

```
timeout 2700 python3 .../ingest_processor.py /cwa-book-ingest/<book>.pdf
/app/calibre/bin/ebook-convert /cwa-book-ingest/<book>.pdf /config/.cwa_conversion_tmp/<book>.epub
99.8 %CPU  7:42  /app/calibre/bin/pdftohtml -enc UTF-8 -noframes -p -nomerge -nodrm src.pdf index.xml -xml
```

The `timeout 2700` is CWA's safety net; the configured limit is `ingest_timeout_minutes = 15`. Either way the queue was going nowhere.

Parking the file and killing the processor released the queue, and the remaining 47 EPUBs finished in about three minutes:

```bash
mkdir -p /mnt/storage/media/konyv_hold
mv "/mnt/storage/media/konyv_ingest/<book>.pdf" /mnt/storage/media/konyv_hold/
docker exec calibre-web-automated pkill -f ingest_processor.py
docker exec calibre-web-automated pkill -f pdftohtml
```

The `inotifywait` events for the already-delivered files sit buffered in the pipe feeding the ingest loop, so killing the current processor does not lose the queue - the loop simply moves to the next file.

## Why that PDF was unconvertible

Three commands separate a text PDF from a scan, and they are worth running before ever queueing a PDF for conversion:

```bash
pdfinfo  book.pdf   # page count, page size
pdffonts book.pdf   # embedded fonts
pdftotext book.pdf - | wc -c
```

| PDF | Pages | Embedded fonts | Extractable text |
|---|---|---|---|
| the blocking one | 736 | **0** | **736 B** |
| CompTIA Network+ study guide | 1043 | 637 | 1,971,453 B |
| willpower instinct | 269 | 3 | 563,778 B |
| body language | 54 | 5 | 150,854 B |
| two others | 93 / 7 | 12 / 18 | 278,113 B / 5,137 B |

736 bytes over 736 pages is one byte per page: page separators and nothing else. `pdfimages -list` confirms what it actually is:

```
page  num  type   width height color comp bpc  enc    object ID x-ppi y-ppi size ratio
  10    0  image   2587  4535  gray     1   1  jbig2         40    72    72  11.9K 0.8%
```

A pure scan: 1-bit JBIG2 bitmaps on 1508x2330 pt pages, zero fonts, zero text layer. `pdftohtml` was not slow, it was doing an impossible job - there is nothing to extract, so the only possible EPUB is 736 images wrapped in markup. Unsearchable, non-reflowable, larger than the original, and strictly worse than the PDF.

Converting it is not a conversion problem, it is an OCR problem (`ocrmypdf -l eng`), and that is a separate decision.

## The fix: exclude PDF from auto-conversion

CWA stores its own settings in `/config/cwa.db`, table `cwa_settings`. The relevant fields before the change:

```
auto_convert                = 1
auto_convert_target_format  = epub
auto_convert_ignored_formats =            <- empty, so PDFs were converted too
auto_backup_conversions     = 1
ingest_timeout_minutes      = 15
```

The setting should be **on for reflowable formats and off for PDF**:

- MOBI, AZW3, FB2, LIT to EPUB is worth it. It is reflowable-to-reflowable, so text, chapter structure and metadata survive, and Calibre-Web's in-browser reader (epub.js) can only display EPUB - a MOBI in the library is download-only.
- PDF to EPUB is fixed-layout to reflowable, which is a guess. On text PDFs it breaks tables, pulls footnotes into the body and leaves hyphens inside words; on scans it produces nothing usable at all.

In the UI: **CWA Settings -> Auto-Converter -> tick PDF under the ignored formats**. The field is a set of per-format checkboxes (`cwa_functions.py` lists it in `skip_settings` and rebuilds it from `ignore_convert_<format>` form fields), stored as a lowercase comma-joined string. Back up `/config/cwa.db` before touching it either way.

Verification is the point, not the setting. Feeding the same scanned PDF back in after a container restart:

```
15:47:37 ingest: 1
15:47:48 ingest: 0
```

**11 seconds instead of 15 minutes**, and it landed as a PDF:

```
(99, 'David Burns', 'PDF', 10038705, 'Feeling Good')
```

Note the swap in that row: `title` and `author` are reversed. A scanned PDF carries no metadata, so CWA guessed from the filename and read the `Author - Title` pattern as `Title - Author`. Not a side effect of the ignored-format setting - the same would have happened after a conversion - but it needs a manual fix in the book's Edit dialog.

`auto_backup_conversions = 1` should stay on. It is what puts every pre-conversion original into `/mnt/storage/media/konyvek/converted/`, which is why all six PDFs in this library still exist in their original form alongside their converted EPUBs.

## Results

| | |
|---|---|
| Books in library, before | 41 |
| Books in library, after | 97 |
| Files uploaded | 56 (330 MB) |
| Imported as EPUB | 55 |
| Imported as PDF, unconverted | 1 |
| Failed imports | 0 |
| Duplicate groups flagged by CWA afterwards | 1 |

## Lessons

1. **Diff an ebook library by content hash, never by filename.** Calibre renames and truncates on import, so the same book has no string in common between source and library. A normalized-title pass on top of the hash catches re-conversions, but expect false positives exactly where the truncation cuts - volume and edition numbers live at the end of a title.
2. **A serial ingest queue is only as fast as its worst file.** CWA runs one `ingest_processor.py` at a time. One unconvertible file holds every book behind it for the full `ingest_timeout_minutes`.
3. **`pdffonts` and `pdftotext | wc -c` tell you in one second whether a PDF can become an EPUB.** Zero fonts and near-zero bytes means it is a scan, and no conversion setting will help - only OCR.
4. **Auto-convert to EPUB is right for reflowable formats and wrong for PDF.** The browser reader needs EPUB, which justifies the setting existing at all; fixed-layout sources are the one case where the original is the better artifact.
5. **`Operation not permitted` on chown is the normal state of an unprivileged LXC.** It appears in the tar exit code and in every CWA import log line, and it means nothing. Check whether the files arrived, not whether the exit code was zero.
