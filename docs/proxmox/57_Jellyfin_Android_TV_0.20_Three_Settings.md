# Jellyfin Android TV 0.20: Three Settings the Update Changed

**Date:** 2026-11-21
**Hostname:** docker-host (LXC 100, Jellyfin 12.4.0) + two Android TVs
**IP address:** 192.168.0.110 (server), 192.168.0.49 (bedroom TV)

## Status: fixed

Jellyfin for Android TV 0.20.0 was released on 2026-11-10 and auto-updated on both TVs: the living-room TV on 2026-11-13, the bedroom TV between 2026-11-20 15:39 and 2026-11-21 13:21. Nothing on the server changed, but three things broke or changed on the client:

| Symptom | Cause in 0.20.0 | Setting that fixed it |
|---|---|---|
| AC3 episodes stutter on the living-room TV | AC3 dropped from the device profile when the TV reports no passthrough | Bitstream Dolby Digital audio: **Enable** |
| An anime with ASS subtitles never starts on the bedroom TV | ASS is still burned in server-side unless a new, default-off option is enabled | Direct play ASS subtitles: **on** |
| The English E-AC3 track of the same anime is silent | The TV claims E-AC3 passthrough it cannot deliver | Bitstream Dolby Digital Plus: **Disable** |

All three live in **Settings > Playback > Advanced playback preferences** (Hungarian UI: Beállítások > Lejátszás > Fejlett lejátszási beállítások). The labels and defaults below were read from the v0.20.0 source, not guessed from the UI.

## Telling the two app versions apart in the server log

The server log names the client in every `SessionManager` line, and the two versions use different app names:

```
User "..." started playback of '"..."' ("Jellyfin Android TV" "0.19.10")
User "..." started playback of '"..."' ("Jellyfin for Android TV" "0.20.0")
```

That is how the bedroom TV's update window was pinned down. It also matters for the diagnosis: an HEVC episode that played fine the day before had played on 0.19.10, so it proved nothing about 0.20.0.

## 1. AC3: the boolean that became a three-way mode (living room, 2026-11-13)

0.19.10 had a boolean `pref_bitstream_ac3`, default true, which simply added AC3 to the device profile. 0.20.0 replaced it with `bitstream_ac3_mode` (Auto / Enable / Disable, default **Auto**) and did not migrate the old key. In `deviceProfile.kt`, AC3 and E-AC3 are only in the allowed audio codecs when the mode is Enable, or when it is Auto **and** Android reports passthrough for that format:

```kotlin
BitstreamAudioMode.AUTO -> isPassthroughAudioAvailable(context, format.mimeType)
BitstreamAudioMode.ENABLE -> true
BitstreamAudioMode.DISABLE -> false
```

A TV playing through its own speakers has no passthrough, so AC3 fell out of the profile. The server then remuxed every AC3 episode to HLS with the audio converted (`-codec:v:0 copy`, AC3 to `libfdk_aac`), and that is what stuttered. The files were ruled out first: the same Columbo episodes had been DirectPlay on 0.19.10, and `mpdecimate` over 120 s found no duplicated or dropped frames.

Fix: **Bitstream Dolby Digital audio** (HU: *Bitstream Dolby Digital hang*) under **Media codecs** set to **Enable**. The next episode started with no `TranscodeManager` line at all, which means DirectPlay.

## 2. ASS subtitles: ten starts, ten failures (bedroom, 2026-11-21)

The file was a BD release: HEVC Main 10 1080p at 14 Mbps, a Japanese Opus track, an English E-AC3 track, three ASS subtitle tracks and ten embedded fonts. The activity log shows ten starts in three minutes, each ending with `stopped playback ... at "0"ms` about seven seconds later.

Every start had a full video transcode, because the app does not render ASS by default and the server burns the subtitle into the picture:

```
-codec:v:0 hevc_qsv ... -filter_complex "...subtitles=f='.../3.ass':alpha=1:sub2video=1:fontsdir='...'
,hwupload=derive_device=qsv...[sub];[0:0]...scale_vaapi=format=nv12...[main];[main][sub]overlay_qsv=..."
```

HEVC 10-bit decode, libass rendering on the CPU, overlay and HEVC encode on the UHD 630 together ran at only 0.9-1.4x realtime. The server logged no warning or error, and ffmpeg was writing segments when the client sent `q`, so the exact client-side reason for giving up is not proven. It is also not needed, because 0.20.0 can avoid the transcode entirely: it added libass rendering on the device. The release post calls it experimental and off by default, and the source confirms the default:

```kotlin
var assDirectPlay = booleanPreference("libass_enabled", false)
var pgsDirectPlay = booleanPreference("pgs_enabled", true)
```

Fix: **Direct play ASS subtitles** (HU: *Közvetlen ASS felirat lejátszás*), a checkbox in the **Subtitles** section of the advanced playback screen. The next start was `PlayMethod: DirectPlay`, no new ffmpeg log was written, and the subtitles were rendered by the TV.

## 3. E-AC3: Auto believed the TV, and the TV was wrong

With video now playing directly, the English track (E-AC3 2.0) was silent while the Japanese Opus track played. The Dolby Digital Plus mode was on its default, Auto. The server never converted the audio on any English start. The session stayed DirectPlay with `AudioStreamIndex: 2`, which means the profile included E-AC3. Under Auto that only happens if `isPassthroughAudioAvailable` returned true, so the bedroom TV's Android `AudioCapabilities` reported E-AC3 passthrough that its speaker output does not actually deliver.

There is a second trap in the same path. `PlaybackController.switchAudioStream` switches tracks inside ExoPlayer when the stream is not being transcoded:

```java
if (!isTranscoding() && mVideoManager.setExoPlayerTrack(index, MediaStreamType.AUDIO, ...)) {
```

So a mid-playback switch to an unsupported track never reaches the server. Choosing the track on the episode page **before** pressing play is what makes the server decide.

Fix: **Bitstream Dolby Digital Plus** (HU: *Bitfolyam Dolby Digital Plus*) set to **Disable**, and the English track chosen before starting. The server then started a remux, not a transcode:

```
FFmpeg.DirectStream-2026-11-21_13-43-41_...log
-map 0:0 -map 0:2 -codec:v:0 copy -codec:a:0 libfdk_aac -ac 2 -ab 224000
frame=16107 fps=1464 ... speed=59.2x
```

Video untouched, audio converted to stereo AAC at 59x realtime, no measurable server load.

## What each TV is set to now

| Setting | Bedroom TV | Living-room TV |
|---|---|---|
| Bitstream Dolby Digital audio | Enable | Enable |
| Bitstream Dolby Digital Plus | Disable | Auto (untouched) |
| Direct play ASS subtitles | on | off (untouched) |
| Direct play PGS subtitles | on (default) | on (default) |

The living-room DD+ setting was deliberately left on Auto. Disable would force every E-AC3 track through the same HLS remux that stuttered there in November, and no E-AC3 playback on that TV has failed yet. The test is the same anime with the English track chosen before starting: sound means Auto works there, silence means it needs Disable too.

## Checking a "won't play" or "stutters" report next time

1. Find the client version in the `SessionManager` lines of `/srv/docker-data/jellyfin/log/log_YYYYMMDD.log`. Logs only go back about three days, but `GET /System/ActivityLog/Entries` goes further.
2. Look for the newest `FFmpeg.*.log`. `Transcode` with a `subtitles=` filter means a burned-in subtitle. `DirectStream` with `-codec:v:0 copy` means only the audio or the container was converted. No new file at all means DirectPlay.
3. `GET /Sessions` shows `PlayMethod`, `AudioStreamIndex` and `SubtitleStreamIndex` of a running playback. That is the quickest way to see which track the client actually selected.
4. Before re-encoding a file (see [doc 34](34_Transcode_Free_Re-encode_AV1_to_H264.md)), check whether a client setting already covers the format. Two of the three problems here would otherwise have led to a re-encode.
