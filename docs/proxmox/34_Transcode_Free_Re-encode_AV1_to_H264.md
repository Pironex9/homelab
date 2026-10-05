# Transcode-Free Re-encode: AV1 and Hi10P to H.264

**Date:** 2026-08-12 (Hi10P case and Jellyfin 12 re-probe added 2026-10-05)
**Hostname:** pve, docker-host (LXC 100), nobara
**IP address:** 192.168.0.109, 192.168.0.110, 192.168.0.100

---

## Overview

Playing a season of anime on the living-room TCL TV pinned the Proxmox host's CPU at around 118% for the whole episode. Jellyfin was transcoding every stream in software. Hardware transcoding is configured and working on this host ([11 - Jellyfin Hardware Transcoding](./11_Jellyfin_Hardware_Transcoding_Setup.md)), so the interesting question was not "why is transcoding slow" but **why the hardware path was not being used at all**.

The fix was to re-encode the source files once, on a machine with a spare GPU, into a format the TV plays directly. Twelve episodes, roughly four minutes each.

## Why it transcoded: two independent causes at once

Either one alone would have forced a transcode, which is why fixing one and re-testing would have proved nothing.

1. **The source was AV1.** The Intel UHD 630 in this host has no AV1 decoder - that arrived with Intel's 11th generation Xe graphics. The Jellyfin transcoding page already documents `Allow encoding in AV1 format` as unavailable here; the same silicon limit applies to *decoding*, and the UI does not spell that out. With no hardware decoder, the whole pipeline falls back to the CPU.
2. **A subtitle track was being burned in.** These releases carry two subtitle tracks, a "Signs & Songs" track and a full dialogue track. Burning an ASS subtitle into the picture requires a filter chain, and a filter chain forces a full decode-filter-encode cycle **regardless of codec**. Even an H.264 source would have transcoded while that track was selected.

## Target format

H.264 8-bit, High profile. Not the smallest option available, and deliberately so:

| Option | Size | Direct play risk |
|---|---|---|
| HEVC 10-bit | smallest | real - depends on the TV's decoder and container support |
| **H.264 8-bit High** | ~5x larger than the AV1 source | none worth worrying about |

Every Android TV made in the last decade direct-plays H.264 8-bit High. Storage is not the constraint here - the pool had 3.8 TB free - so the format that removes the problem outright wins over the one that saves space and might not.

Sizes went from 232-447 MB per episode to 1.3-1.5 GB, with the double-length finale at 2.7 GB. Total for the season: 14 GB, against roughly 3.4 GB before.

## Where the work runs, and why it is split across three machines

The encode happens on **nobara** (RTX 2060 SUPER, `h264_nvenc`), specifically so the Proxmox host stays idle during TV time - the original complaint was CPU load on pve, and doing the re-encode there would have traded a two-hour problem for a two-hour problem.

But nobara **cannot write to the media pool**. pve exports it with `no_root_squash`:

```
/mnt/storage 192.168.0.0/24(rw,sync,no_subtree_check,no_root_squash,fsid=1)
```

which sounds like it should be enough, and is not: `ssh nobara` lands as the unprivileged user `nex`, there is no root SSH to that machine and no passwordless sudo, so `no_root_squash` never comes into play. The share is effectively read-only from there.

So the script runs from LXC 109, reads over NFS on nobara, encodes to nobara's local `/var/tmp`, and pipes the result back over SSH to LXC 100, which does have root write access to the pool. The media path is identical on both machines, `/mnt/storage/media/anime/tv/...`, which is `/media3/tv` inside the Jellyfin container.

## The encode

```bash
ffmpeg -hide_banner -loglevel warning -stats \
  -i /var/tmp/mia_in.mkv \
  -map 0:v:0 -map 0:a:m:language:eng \
  -vf 'subtitles=/var/tmp/mia_in.mkv:si=0,format=yuv420p' \
  -c:v h264_nvenc -preset p6 -rc vbr -cq 20 -b:v 0 \
  -profile:v high -level 4.1 -spatial_aq 1 -aq-strength 8 \
  -c:a copy -sn \
  -max_muxing_queue_size 2048 \
  -y /var/tmp/mia_out.mkv
```

Constant-quality VBR (`-rc vbr -cq 20 -b:v 0`) rather than a bitrate target, so quiet episodes do not waste space and busy ones do not smear. `format=yuv420p` after the subtitle filter is what actually produces 8-bit output from a 10-bit source. Audio is copied, not re-encoded - the English track is already in a format the TV handles.

About 3-4 minutes per 24-minute episode, roughly 9x realtime. AV1 *decoding* stays on the CPU even here, since the 2060 SUPER predates NVIDIA's AV1 decoder as well, but 16 threads keep up with the GPU encoder without trouble.

Two details in the filter argument are not obvious:

- **`si=0` selects the first subtitle track**, which in these releases is Signs & Songs, with dialogue second. Verify per series with `ffprobe -show_entries stream=index:stream_tags=title` - guessing wrong burns the wrong track into every episode and the mistake is only visible on playback.
- **The source is reached through a symlink at a simple path.** The real filenames contain `[`, `]`, `(`, `)` and spaces, all of which the `subtitles=` filter would need escaped, with rules that differ from ordinary shell quoting. Symlinking to `/var/tmp/mia_in.mkv` sidesteps the whole problem. libass still finds the embedded font attachments, because it loads them from the file the filter opens.

## Three traps, each of which cost time

### The container Duration field lies

The script refuses to replace a source file unless the output length matches. That check failed on E11: source 1511 s, output 1422 s, a difference big enough to look like a truncated encode.

The encode was fine. The check was wrong. No stream in that file reaches 1511 seconds - the last video packet is at 1421.962, the two audio tracks end at 1421.993 and 1422.972, the subtitles at 1420.980. The container's `format=duration` header simply carries a wrong value in these releases.

**Compare the last video packet timestamp, not the container duration:**

```bash
ffprobe -v error -select_streams v:0 -show_entries packet=pts_time \
  -of csv=p=0 input.mkv | tail -1
```

This reads every packet header, so it is slower than reading the container field, and it is the only one of the two that describes the actual content.

### The filename does not change, so name-based skip logic re-encodes finished work

Output keeps the original filename - including the literal string `AV1` - so that Jellyfin's existing metadata, watch states and artwork stay attached. A `find -iname '*AV1*.mkv'` therefore matches converted files just as happily as unconverted ones, and a second run would re-encode the whole season.

Probe the codec instead:

```bash
[ "$(ffprobe -v error -select_streams v:0 -show_entries stream=codec_name \
     -of csv=p=0 "$f")" != "av1" ] && { echo "already converted, skipping"; continue; }
```

### Jellyfin keeps deciding from stale stream info

After the files change on disk, Jellyfin's database still holds the old codec, and it keeps making transcode decisions from that record - so the TV can still transcode a file that is now H.264.

The recipe used in August (a series-level `Refresh` with `metadataRefreshMode=None`) **no longer works on Jellyfin 12**. Measured on 2026-10-05 after the Hellsing re-encode, all of these returned 204 and none updated the streams:

| Call | Result |
|---|---|
| `POST /Items/{seriesId}/Refresh?metadataRefreshMode=None` | logs "File changed, pruning extracted data", updates the file Size, streams still `h264/10 flac` |
| same with `metadataRefreshMode=Default` | same |
| `POST /Library/Refresh` (full library scan) | same |

What works is a **per-episode FullRefresh that keeps the existing metadata**:

```bash
H='Authorization: MediaBrowser Token="your_jellyfin_api_key_here"'
J=http://192.168.0.110:8096
for e in $(curl -s -H "$H" "$J/Shows/$SERIES_ID/Episodes" | jq -r '.Items[].Id'); do
  curl -s -X POST -H "$H" "$J/Items/$e/Refresh?metadataRefreshMode=FullRefresh&imageRefreshMode=None&replaceAllMetadata=false&replaceAllImages=false"
done
```

Streams updated within 10 seconds for all 10 episodes, and titles and overviews stayed in place, because `replaceAllMetadata=false` keeps the existing values. Verify with `GET /Shows/$SERIES_ID/Episodes?Fields=MediaStreams`. Since Jellyfin 12 the only accepted auth is the `Authorization: MediaBrowser Token="..."` header; `X-Emby-Token` and `?api_key=` return 401.

## Second case: Hi10P (H.264 10-bit)

AV1 is not the only source the TCL TVs refuse. **H.264 High 10 (Hi10P, `yuv420p10le`)** is common in anime BD releases, and Android TV hardware decoders generally only handle 8-bit H.264, so Jellyfin transcodes it in the same way. Same codec name as the target, different profile - `codec_name=h264` alone does not tell the two apart, `pix_fmt` does.

Hellsing Ultimate (10 OVAs, `[SCY] ... (BD 1080p Hi10 FLAC)`, 2026-10-05) went through the same pipeline with three changes:

- **No subtitle burn-in.** Watched with the English dub, so the subtitle tracks are dropped (`-sn`) instead of burned in, and the filter chain is just `format=yuv420p`. No symlink needed either: without the `subtitles=` filter, the filename is only an `-i` argument.
- **One audio track by index, not by language.** These files carry English 5.1 FLAC, Japanese 5.1 FLAC and an English commentary 2.0 FLAC. `-map 0:a:m:language:eng` would take the commentary too, so the script maps `0:a:0`.
- **FLAC 5.1 becomes AAC stereo** (`-c:a aac -b:a 192k -ac 2`). Copying FLAC would leave an audio track the TV may also not direct play.

The skip check probes `pix_fmt` instead of the codec, for the same filename reason as above (`Hi10` stays in the name):

```bash
[ "$(ffprobe -v error -select_streams v:0 -show_entries stream=pix_fmt \
     -of csv=p=0 "$f")" != "yuv420p10le" ] && continue
```

| | Value |
|---|---|
| Speed | ~10x realtime on 1080p Hi10P, 6-9 min per episode including the copy back |
| Episodes | 10, 2558-4064 s each |
| Size | 60 GB -> 29 GB (FLAC 5.1 was most of the bulk) |
| Checks | all 10 passed the last-packet length check |

ffmpeg prints `Invalid value of WAVEFORMATEXTENSIBLE_CHANNEL_MASK` while reading these FLAC tracks. It is about the source's channel header and harmless here, since the output is downmixed to stereo.

## Verifying the result

The originals are renamed to `.av1.bak` rather than deleted, and removed only after the TV confirms Direct Play. Confirm the conversion itself from outside Jellyfin:

```console
root@docker-host:~# ffprobe -v error -select_streams v:0 \
    -show_entries stream=codec_name,profile,pix_fmt -of default=nw=1 "…S02E01….mkv"
codec_name=h264
profile=High
pix_fmt=yuv420p
```

Then on the TV, during playback, the Jellyfin info panel must read **Direct Play** rather than Transcoding. That is the only check that answers the original question, since it is the client's decision that was causing the CPU load.

## Script

`private/mia_s2_av1_reencode.sh` (AV1) and `private/hellsing_ultimate_reencode.sh` (Hi10P), both gitignored because they hardcode a series path. Run them from LXC 109; `DRY=1` processes only the first file.

## Related

- [11 - Jellyfin Hardware Transcoding](./11_Jellyfin_Hardware_Transcoding_Setup.md) - the GPU passthrough and Jellyfin-side settings this doc assumes are already in place
- [14 - NFS Setup](./14_NFS-Setup_Documentation.md) - the export whose `no_root_squash` does not help here
