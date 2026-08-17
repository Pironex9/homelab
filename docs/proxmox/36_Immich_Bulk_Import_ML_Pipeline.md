# Bulk Photo Import to Immich, and the ML Failures It Exposed

**Date:** 2026-08-17
**Hostname:** pve, docker-host (LXC 100), nobara
**IP address:** 192.168.0.109, 192.168.0.110, 192.168.0.100

---

## Overview

A 116 GB USB stick plugged into the Proxmox host held roughly 9,400 files, about 40 GB, in a decade of unsorted phone dumps and event folders. The goal was not just to get them into Immich (see [06 - Immich Setup](./06_Immich_Setup_Full_Installation_Guide.md)) but to get them into the ML pipeline: face recognition across the whole library, not a second disconnected pile of photos.

The import itself took 20 minutes and produced zero errors. Everything interesting happened afterwards, in the machine learning stage, where three separate problems each looked like success.

## Choosing the transfer path

The stick was on `pve`; Immich runs in LXC 100. Three options, in order of how much work they cost:

| Path | Cost |
|---|---|
| Bind-mount the stick into LXC 100 | Mountpoint changes need a container restart - 22 Docker stacks down |
| Copy 40 GB to LXC 100, then upload locally | The container disk is 52 GB; the data would land twice |
| Upload from `pve` over the LAN | No mount, no restart, no second copy |

The third path needs an uploader on `pve`, which has no Node.js, so the official `@immich/cli` (npm) was out and [immich-go](https://github.com/simulot/immich-go) - a single static binary, v0.32.0 - was in. That is the whole reason for the tool choice; it is not a judgement about which uploader is better.

```bash
mount -o ro /dev/sde1 /mnt/usbstick
```

Read-only, because nothing in an import should be able to write to the source.

## Dry run first

`immich-go` has `--dry-run`, and on a 9,400-file import it is worth the eight minutes because it answers the design questions with real numbers instead of guesses:

```
Total Assets:       8726  (32.4 GB)
  uploaded successfully              :    6302  (26.3 GB)
  server has duplicate               :    2424  ( 6.1 GB)
  added to album                     :    8476
  discovered unknown file            :      20   (pdf/docx/zip - skipped)
```

The 2,424 already-present files are the useful signal. Two of the top-level folders were the same phone dumped twice, a year apart, with identical subfolder names. Immich rejects them on SHA-1 of file content, so the overlap costs nothing and needs no planning.

## Folders as albums

The stick's structure was ~60 folders, most named after real events, some named `DCIM`, `Screenshots`, or the Slovak and Hungarian equivalents of "New Folder".

```bash
immich-go upload from-folder --no-ui \
  -s http://192.168.0.110:2283 -k "$API_KEY" --admin-api-key "$API_KEY" \
  --folder-as-album FOLDER \
  --ban-file "Screenshots/" --ban-file "Smartbanking/" \
  --on-errors continue -l /root/immich-import.log "/mnt/usbstick/<folder>"
```

Two behaviours worth knowing before choosing `FOLDER` over `PATH`:

- **Albums do not hide anything.** An asset you upload always appears in the main timeline; an album is a view over it, not a location. (The exception is an album *another user* shares with you - those stay in the Shared section and never enter your timeline. That does not apply to your own imports.) So there is no downside to importing into albums.
- **Same-named folders merge into one album.** With two phone dumps sharing subfolder names, this is the desired outcome rather than a collision.

`--pause-immich-jobs` defaults to true and needs `--admin-api-key`. It holds the ML queue for the duration of the upload and releases it at the end, so the GPU processes one large batch instead of competing with the transfer.

Result: 6,302 new assets, 0 errors, verified server-side (4,663 -> 10,965 assets, exactly +6,302). Of the 56 albums created, 12 were junk names and were deleted through the API - deleting an album never touches its assets, and the count stayed at 10,965 throughout.

## Failure 1: the GPU was full and nothing said so

Immich's ML runs on a separate machine, a desktop with an RTX 2060 SUPER (8 GB), reached over the network (see [Nobara host notes](../hosts/nobara.md)). Once the queue released, three job types ran concurrently - `faceDetection`, `smartSearch`, `ocr` - so three model families were resident at once: a 4.5 GB multilingual CLIP model, the face model, and PaddleOCR. The card sat pinned at 7,696 / 8,192 MiB.

What made this hard to see is that **nothing failed**. Every Immich queue reported `failed=0`, the ML container healthcheck stayed green, and the work visibly progressed. ONNX Runtime caught the allocation failure and silently fell back to the CPU execution provider.

The evidence was only in the ML container's own log:

```bash
docker logs --since 10m immich_machine_learning_remote 2>&1 | grep -ic "failed to allocate"
# 2002
```

Two thousand allocation failures in ten minutes, while the queue drained and the dashboard looked fine. The corroborating tell is the pair of numbers that should never appear together: **GPU utilization at 10% while the Immich server burns 235% CPU.**

Throughput at each stage of the fix:

| State | Faces/min | VRAM | OOM/min |
|---|---|---|---|
| All three job types running | 96 | 7696 MiB | ~200 |
| OCR queue paused | 161 | 7696 MiB | ~209 |
| ML container restarted | **904** | 4706 MiB | **0** |

Pausing the OCR queue helped throughput but did not fix the cause: the already-loaded model stays resident until its TTL expires. Only `docker restart` returned the VRAM, and the difference between contended and clean is **9.4x**. This is the same card and the same silent-failure mode documented in the smart search incident, arrived at from a completely different direction.

## Failure 2: the restart silently dropped in-flight jobs

After the restart, every queue read `waiting=0 active=0 failed=0`. That is indistinguishable from finished.

It was not finished:

```bash
curl -X PUT .../api/jobs/faceDetection -d '{"command":"start","force":false}'   # force:false = "Missing"
# -> immediately queued 2668 assets
```

2,668 photos had been consumed from the queue during the restart and never processed. No error, no failed counter, no log line - they simply stopped existing as work. Had nobody run the Missing pass, a quarter of the import would have had no face data, and the only symptom would have been people vaguely under-represented in search results months later.

**A single Missing pass is not proof either.** Only a second Missing pass that queues zero proves completion. The first one has real work to do and tells you nothing about what it might also be missing.

Final state after both passes: `faceDetection`, `facialRecognition`, `smartSearch` all at 0 waiting, 0 failed. Recognized people went from 329 to **642**.

## Failure 3: a duplicate threshold that flagged burst photos

Immich has two unrelated duplicate mechanisms, and conflating them wastes a lot of effort:

| Mechanism | When | Basis |
|---|---|---|
| Upload rejection | At upload | SHA-1 of file content, exact |
| Duplicate Detection job | On demand | CLIP embedding distance, fuzzy |

The first had already done the real work - 2,424 files, 6.1 GB, with no human involvement. The second exists for resized or re-compressed copies that hash differently.

The default `maxDistance` is 0.01. Loosening it to 0.03 to catch more resized copies was a mistake, and the result shows exactly why:

```
0.03:  1664 groups,  4712 images  (43% of the library)
0.01:   774 groups,  2096 images
```

Sampling the largest groups explains the inflation:

```
34-image group:  IMG_20210624_092932_BURST001_COVER.jpg   09:29:32
                 IMG_20210624_092932_BURST002.jpg         09:29:32
                 IMG_20210624_092932_BURST003.jpg         09:29:33
21-image group:  three frames, 2-3 seconds apart, all distinct photos
```

These are burst sequences. **Tightening the threshold does not remove them** - they are still there at 0.01, because burst frames genuinely are near-identical in CLIP space. No threshold separates "consecutive frames of one moment" from "the same file stored twice"; that distinction does not exist in the embedding.

What does separate them is resolution. Splitting the 0.01 results by whether a group contains a copy at less than half the maximum pixel count:

| | Groups | Images | Reclaimable |
|---|---|---|---|
| Genuine resized copies (>=2x resolution gap) | 75 | 222 | **0.09 GB** |
| Same resolution (bursts, series) | 699 | 1874 | 4.41 GB |

Only the first group is safe to act on automatically, and it is worth 90 MB. The 4.4 GB sits behind 699 groups of manual review, most of which are legitimate photographs. Deleting the resized copies - keeping *every* asset at the maximum resolution per group, not just one - removed 105 assets totalling 12 MB, to the trash rather than permanently.

The honest conclusion is that CLIP-based duplicate detection had almost nothing to find here, because checksum deduplication at upload had already found everything that mattered.

## OCR: the model list is in the container, not the docs

Immich's OCR defaulted to `EN__PP-OCRv5_mobile`, which drops diacritics on Hungarian text. Web search and the relevant GitHub discussion both said the Latin-script model "is available in PaddleOCR but not yet integrated into Immich."

That is false for v3.1.0. The authoritative list is a hardcoded set in the running container:

```bash
docker exec immich_machine_learning_remote \
  grep -A12 "_PADDLE_MODELS" /usr/src/immich_ml/models/constants.py
```

```python
_PADDLE_MODELS = {
    "PP-OCRv5_server", "PP-OCRv5_mobile",
    "CH__PP-OCRv5_server", "CH__PP-OCRv5_mobile",
    "EL__PP-OCRv5_mobile",      # greek
    "EN__PP-OCRv5_mobile",
    "ESLAV__PP-OCRv5_mobile",   # east slavic
    "KOREAN__PP-OCRv5_mobile",
    "LATIN__PP-OCRv5_mobile",   # ~45 latin-script languages
    "TH__PP-OCRv5_mobile",
}
```

Switching is cheap because of how the models are split. Text *detection* is language-independent and shared; only *recognition* is per-language:

```
/cache/ocr/PP-OCRv5_mobile/detection/model.onnx          <- shared
/cache/ocr/EN__PP-OCRv5_mobile/recognition/model.onnx    <- per-language
/cache/ocr/LATIN__PP-OCRv5_mobile/recognition/model.onnx <- downloaded on switch
```

One trap while verifying: models download from `immich-app/<model_name>` on HuggingFace, but probing `https://huggingface.co/api/models/immich-app/<name>` returns **401 for every one of them, including models already cached and working**. A 401 is not evidence the repo is missing. The only real test is setting the name and watching `/cache/ocr/` for the new directory.

Verified after the switch by searching the OCR index for the specifically Hungarian characters an English model cannot produce - `ő` and `ű` both return hits.

## Results

| | |
|---|---|
| New assets | 6,302 (26.3 GB), 0 errors |
| Rejected as exact duplicates | 2,424 (6.1 GB), automatic |
| Albums | 44 (56 created, 12 junk deleted) |
| Recognized people | 329 -> 642 |
| Duplicate cleanup | 105 resized copies to trash |
| Face processing throughput | 96/min -> 904/min |

## Lessons

1. **A green healthcheck and `failed=0` are not evidence of GPU inference.** ONNX Runtime falls back to CPU on allocation failure without raising anything Immich can see. Check `nvidia-smi` and the ML container log; GPU utilization near zero alongside high server CPU is the signature.
2. **Restarting the ML container discards in-flight jobs, and the queue then reads as finished.** Always run a Missing pass afterwards, then run it a second time. Only a pass that queues zero proves completion.
3. **No duplicate threshold can separate burst frames from duplicate files.** Resolution difference can. Checksum deduplication at upload does the work that matters; treat the CLIP duplicate list as a review queue, never as a delete list.
4. **For "does this software support X", read the constant in the running container** before trusting documentation, changelogs, or search results.
5. **Dry-run a bulk import.** Eight minutes of `--dry-run` replaced every design question - how many duplicates, how many albums, which files get skipped - with a number.
