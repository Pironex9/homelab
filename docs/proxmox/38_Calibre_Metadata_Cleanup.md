# Cleaning Up a Calibre Library from the Shell, and the Four Traps That Bite

**Date:** 2026-08-21
**Hostname:** docker-host (LXC 100)
**IP address:** 192.168.0.110

---

## Overview

After [37 - Calibre-Web Bulk Ebook Import](./37_Calibre_Web_Automated_Bulk_Import.md) put 56 books into the library, a third of them carried metadata that was wrong rather than merely incomplete: an internal Word document name as the title, the date part of a filename as the author, or title and author swapped outright.

`calibredb` fixes this from a shell without stopping the container - Calibre-Web-Automated (CWA) itself calls `calibredb add` on every ingest, so a live library is the normal case, not a hack. But four things go wrong in ways that look fine until someone opens the web UI.

```bash
docker exec -e LD_LIBRARY_PATH=/app/calibre/lib -e HOME=/tmp calibre-web-automated \
  /app/calibre/bin/calibredb --with-library /calibre-library list --limit 2
```

`LD_LIBRARY_PATH` is required: the bundled binaries fail with `error while loading shared libraries: libcalibre-launcher.so`. `fetch-ebook-metadata` from the same directory is a dead end regardless - it pulls in Qt and Chromium and dies with `Running as root without --no-sandbox is not supported`.

## Identifying what a book actually is

Nine books had a title no lookup could resolve - `Microsoft Word - MARCUS.RTF`, `K906_Guts.indd`, `20051210175553`, `1a`, `Contents at a Glance`. The answer is inside the file. Unzipping the EPUB and stripping tags from the first few XHTML files identifies almost all of them in one pass:

```python
z = zipfile.ZipFile(epub)
names = [n for n in z.namelist() if n.lower().endswith((".htm", ".html", ".xhtml"))]
txt = re.sub(r"<[^>]+>", " ", z.read(names[0]).decode("utf-8", "ignore"))
```

| Title in the library | What the text said | What it is |
|---|---|---|
| `Microsoft Word - MARCUS.RTF` | "FORDÍTOTTA HUSZTI JÓZSEF ... M. Antoninus imperator ad se ipsum" | Marcus Aurelius, *Elmélkedések* |
| `K906_Guts.indd` | "The Way of the Superior Man" in the running head | a duplicate of a book already present |
| `Contents at a Glance` | every page header read `/cwa-book-ingest/<name>.pdf` | CompTIA Network+ Study Guide |
| `1a` | "Break the Worry Habit Before It Breaks You" | Dale Carnegie's Secrets of Success |

That last pattern is worth internalising: **a PDF converted to EPUB keeps the source path in the page header of every page.** When a title looks like nonsense, the first page of text usually names the original file.

One book resisted everything - a scan wrapped in a PDF wrapped in an EPUB, whose only extractable text was the list `x001.pdf, x002.pdf, ...`. The owner identified it from memory.

## Trap 1: `--field title:` does not update the sort field

```bash
calibredb set_metadata --field "title:Félelem és reszketés" --field "authors:Søren Kierkegaard" 51
```

This writes the title and the author, and leaves `books.sort` and `books.author_sort` at their old values. The web UI sorts on those columns, so the renamed book stays filed under the garbage name and nothing in the output hints at it:

```
Title       : Félelem és reszketés
Title sort  : felelem                <- stale
Author(s)   : David Burns [Good, Feeling]   <- author_sort stale from a swapped pair
```

Both are settable, but the field name for title sort is `sort`, not `title_sort` (`calibredb set_metadata --list-fields` is the authority). Recomputing them means reimplementing Calibre's two rules:

```python
ART = re.compile(r"^(A|The|An)\s+", re.I)          # angol nevelo hatra
def title_sort(t):
    m = ART.match(t)
    return "%s, %s" % (t[m.end():], t[:m.end()].strip()) if m else t

def author_sort_one(a):                             # "First Last" -> "Last, First"
    return a if "," in a else "%s, %s" % (a.split()[-1], " ".join(a.split()[:-1]))
```

35 of 93 books needed one or both rewritten.

## Trap 2: the placeholder cover has the wrong title painted on it

Every book had a `cover.jpg` and `has_cover=1`, so a naive audit reports zero missing covers. But for a book with no cover image inside the file, Calibre *generates* one - a title banner over a plain background. That generated image bakes in whatever the title was at generation time, and renaming the book does not redraw it. The cover for book 45 read, in large serif type, `Microsoft Word - MARCUS.RTF` with `DL` underneath.

So **any title fix implies a cover fix**, for exactly the books whose titles were wrong.

Real covers came from Open Library's search API, matching on title and author:

```
https://openlibrary.org/search.json?title=<title>&author=<author>&fields=key,title,author_name,cover_i,isbn
https://covers.openlibrary.org/b/id/<cover_i>-L.jpg
```

Google Books was tried first and is not usable unauthenticated: `429 Quota exceeded for quota metric 'Queries' and limit 'Queries per day'` - the anonymous quota is pooled per source IP and was already spent.

Two guards turned out to be mandatory:

- **Reject a hit whose author shares no name token with the requested author.** Without it the search returns confidently wrong books: *Testbeszéd* by Erhard Thiel matched Allan Pease's identically-titled Hungarian book, and *Natural Game* matched an ethnography called *Games against nature*.
- **Reject a response under ~5 KB or one that does not start with `\xff\xd8`.** Open Library answers a missing cover with a tiny placeholder rather than a 404.

18 of 31 resolved to a real published cover. The other 13 got a generated one - with the *corrected* title on it this time - from 40 lines of PIL:

```python
d.text((W/2, y), line, font=ImageFont.truetype(SERIF, size), fill=FG, anchor="ma")
```

Applying either kind is the same call, and `cover` is a valid field name:

```bash
calibredb set_metadata --field "cover:/tmp/newcovers/45.jpg" 45
```

## Trap 3: the main page serves a cached thumbnail, not the cover

After all of that the book detail pages were correct and the main library grid still showed the old covers and old titles. Not a browser cache: Calibre-Web keeps a separate thumbnail cache, indexed in `app.db` and stored as files.

```
/config/thumbnails/                 582 files (book_<id>_r<res>.jpg / .webp)
app.db, table `thumbnail`           582 rows
```

The detail page serves `cover.jpg` directly, which is why clicking into a book showed the fix. The grid serves the thumbnail, and `calibredb` has no reason to know the cache exists. Regeneration is a *scheduled* task, not a page-load side effect.

Clearing both makes the grid correct on the next request, because `get_book_cover_internal` in `cps/helper.py` is explicitly written for this case - it queues a background regeneration and falls back to the original for the current request:

```
# Note: Thumbnails will be generated in background
# Current request will fall back to serving original cover.jpg
```

```python
sqlite3.connect("/config/app.db").execute("delete from thumbnail")
```
```bash
rm -f /config/thumbnails/*.jpg /config/thumbnails/*.webp
docker restart calibre-web-automated
```

## Trap 4: a truncated file is not a corrupt file

An audit that opens every EPUB with `zipfile.ZipFile` found exactly one failure:

```
CCDA 200-310 Official Cert Guide: File is not a zip file
```

The file starts with `PK\x03\x04`, so it is a zip - but there is no end-of-central-directory record anywhere in the last 2 MB, and the size is `75497472` bytes, which is **exactly 72.0 MiB**. A file that ends on a round power-of-two boundary was cut off, not corrupted, and no repair tool recovers content that was never written. The copy CWA had kept in `fixed_originals/` was the same size, byte for byte.

Deleting it needed the Proxmox host, not the container: the file was owned by `nobody:nogroup` and `rm` returned `Permission denied` both inside LXC 100 and on its own mount, because of the unprivileged container's ID map.

## Which duplicates are real

CWA's duplicate scanner flags groups but resolves nothing by default (`duplicate_auto_resolve_enabled = 0`). A normalized-title grouping over the whole library returned five groups, of which two were false:

```
#26 CCNA 200-301 ... Volume 1   |  #29 ... Volume 2     <- kulon kotetek
#2  CCNA Certification Study Guide | #50 ... Volume 2   <- kulon kotetek
#7  CompTIA Network+ (57 MB EPUB)  | #21 (41 MB, PDF-bol konvertalt)
#20 How to Make Love All Night     | #23 (bitre azonos)
#46 The Way of the Superior Man    | #91 (396 KB tiszta EPUB)
```

Volume numbers live at the end of a title, which is exactly where Calibre's ~40-character truncation cuts. Any title-prefix match will pair up the volumes of a series; check the file sizes and formats before deleting anything.

## Which fields can be filled automatically, and which cannot

The same Open Library pipeline fills descriptions, publication years and subjects. Over 65 incomplete books:

| | Before | After |
|---|---|---|
| Description | 34 | 50 |
| Tags | 63 | 78 |
| Publication date | 63 | 73 |
| Language | 91 | 93 |

27 of the 65 returned no match at all. The split is not random: mainstream published books are catalogued, self-published and scene-released ebooks are not, and neither are most Hungarian titles. No provider fixes that - what remains is manual entry.

Two cleanups worth doing on the fetched text: strip a leading `Publication Date: ...` line and an `Amazon.com Review` heading, both of which Open Library carries verbatim inside `description`, and title-case the ALL-CAPS subjects (`SELF-HELP`, `PSYCHOLOGY`) so they do not stand out among the rest.

## Author names are a separate problem

Calibre treats the author *name* as the display string and stores an inter-name comma as `|` in the database. That makes two spellings of one person into two authors:

```
'Carnegie, Dale'  sort='Carnegie, Dale'
'Dale Carnegie'   sort='Carnegie, Dale'      <- ugyanaz az ember, ket sor
```

Sixteen books needed a rewrite: duplicate spellings unified, `By (author) Barbara Keesling Ph.d.` reduced to `Barbara Keesling`, `Joe Navarro;Marvin Karlins` split into two author records, and `Esther Villar` corrected to `Esther Vilar` (a typo that had created a second author).

## Does the next ingest go better?

Only for PDFs. A two-file probe settles what the ingest actually reads - build two minimal EPUBs, one with OPF metadata and one with the title and creator elements empty, name both `Something - Something Else.epub`, and drop them in the ingest folder:

```
#100  fajlnev: "ZZTeszt Kulso Cim - ZZTeszt Kulso Szerzo.epub"
      OPF:      <dc:title>ZZTeszt BELSO CIM</dc:title>
      eredmeny: cim='ZZTeszt BELSO CIM'  szerzo='ZZTeszt BELSO SZERZO'

#101  fajlnev: "ZZTeszt Nincs Opf Cim - ZZTeszt Fajlnev Szerzo.epub"
      OPF:      ures dc:title es dc:creator
      eredmeny: cim='ZZTeszt Nincs Opf Cim'  szerzo='ZZTeszt Fajlnev Szerzo'
```

**The EPUB's own OPF always wins; the filename is only a fallback, and the pattern is `Title - Author`.** So renaming files helps PDFs and nothing else, and the majority of the bad metadata here - which came from the OPF - would have arrived identically no matter what the files were called.

CWA does have an automatic provider lookup after ingest, `auto_metadata_fetch_enabled`, and it is off by default. It is worth leaving off. `_apply_metadata_to_book` in `cps/metadata_helper.py` guards title and description behind `auto_metadata_smart_application` - only replacing them when the fetched value is longer - but the author branch has no such guard:

```python
book.authors.clear()
for author_name in metadata.authors:
    ...
```

A wrong match silently destroys a correct author. And the lookup key is the guessed title, so it cannot help the books that are actually broken.

## Lessons

1. **`calibredb set_metadata --field title:` leaves `sort` and `author_sort` stale**, and nothing in the output says so. Recompute both, or the web UI files the book under its old name.
2. **`has_cover=1` is not evidence of a cover.** Calibre generates a placeholder with the title painted into the image, so a title fix silently invalidates it.
3. **A list view and a detail view can serve different images.** When one is right and the other is wrong, look for a cache with its own index before doubting the data.
4. **A file size that is an exact power of two is a truncated download**, not corruption. Check the last bytes for the format's terminator before trying to repair anything.
5. **Test what the importer reads rather than reasoning about it.** Two 1 KB probe files answered the filename-versus-OPF question in three minutes and made every naming recommendation either justified or pointless.
