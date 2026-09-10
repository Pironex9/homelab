# When One File Is Two Episodes: Importing a Segment-Numbered Series

**Date:** 2026-09-10
**Hostname:** docker-host (LXC 100)
**IP address:** 192.168.0.110

---

## Overview

The report was: "Sonarr will not copy these episodes into their season folders, because it does not support multi-season torrents."

The multi-season part is a real limitation, and it is not the problem. A 50-file pack of *The New Adventures of Winnie the Pooh* cannot be mapped onto its own metadata at all, because the pack counts broadcast half-hours and every metadata provider counts the 11-minute stories inside them. There are 50 files and 82 episodes. No import setting reconciles those two numbers, and picking the naive mapping silently mislabels 28 of the 50 files.

The useful part is how to derive the correct mapping from data that is already on the host, how to tell that derivation apart from a guess, and the two traps that turn a finished rename back into the duplicate-episode bug it was meant to fix.

## Step 1: count before touching anything

The pack, one subfolder per season:

```bash
D="/mnt/storage/media/downloads/The.New.Adventures.of.Winnie.the.Pooh.S01-S04.WEB-DL.HUN.x264"
for sd in "$D"/*/; do echo "$(basename "$sd"): $(find "$sd" -type f | wc -l)"; done
```

```
S01.HDTV.HUN.x264:   22
S02.WEB-DL.HUN.x264: 10
S03.WEB-DL.HUN.x264: 10
S04.WEB-DL.HUN.x264:  8
```

What Sonarr says the series contains (series id 53, tvdbId 78442):

```bash
curl -s "http://localhost:8989/api/v3/series/53?apikey=your_sonarr_api_key_here" | python3 -c "
import sys,json
for se in json.load(sys.stdin)['seasons']:
    st=se.get('statistics',{})
    print(se['seasonNumber'], st.get('totalEpisodeCount'))
"
```

| | files in pack | provider episodes |
|---|---|---|
| S01 | 22 | 35 |
| S02 | 10 | 18 |
| S03 | 10 | 18 |
| S04 | 8 | 11 |
| **total** | **50** | **82** |

TMDB (id 2005) reports the same 35/18/18/11. So this is not a bad TVDB entry to be worked around by switching provider - both providers describe the show the same way, and the show really does have 82 stories. The pack really does have 50 files. Both are correct.

At this point Sonarr had already imported season 1 on its own, mapping the 22 files to provider episodes 1-22 in order:

```
S1 episodes with a file: [1,2,...,22]
```

That is the naive mapping, and it is wrong from the second file onward. File 2 contains two stories; labelled `S01E02` it claims to be only the first of them, and every story from the 23rd onward has no file at all while 13 episodes show as missing.

## Step 2: measure what one file actually is

The decisive measurement is duration, and it takes seconds per file:

```bash
ffprobe -v error -show_entries format=duration -of csv=p=0 "$f" \
  | awk '{printf "%.1f min\n", $1/60}'
```

Every one of the 50 files came back between 21.1 and 22.6 minutes. Not one was near 11. So no file is a bare segment - each is a complete broadcast slot, whether that slot held one full-length story or two shorts.

This immediately kills the tempting shortcut of splitting long files and keeping short ones. It also means duration alone cannot tell a one-story slot from a two-story slot, because both run 22 minutes.

## Step 3: derive the grouping from air dates, then check the derivation

Provider episodes carry air dates, and two stories broadcast in the same half hour share one. Grouping by air date turns segments back into slots:

```python
import collections, json
eps = json.load(open('eps.json'))
for sn in (1,2,3,4):
    se = sorted((e for e in eps if e['seasonNumber']==sn), key=lambda x: x['episodeNumber'])
    slots = collections.OrderedDict()
    for e in se:
        slots.setdefault(e['airDate'], []).append(e)
    print(sn, len(se), 'segments ->', len(slots), 'slots')
```

```
1 35 segments -> 22 slots
2 18 segments -> 10 slots
3 18 segments -> 10 slots
4 11 segments ->  9 slots
```

Against the pack: 22, 10, 10, 8. Three seasons match exactly, and the fourth is short by one slot, which also explains the one missing file. Fifty files against fifty-one slots.

**Three independent season counts matching exactly is the corroboration that separates this from a guess.** Had the release paired its shorts arbitrarily, 22/10/10 would not have fallen out of the provider's air dates three times in a row.

That is corroboration, not proof, and the difference is worth being explicit about, because everything that would have made it proof failed:

| attempted check | result |
|---|---|
| embedded track/format title tags | absent - only `LANGUAGE`, `creation_time`, `ENCODER` |
| Matroska chapter marks | none |
| `blackdetect` around the 11-minute mark | short fades in both one-story and two-story files, no reliable signature |
| extracted frame at the midpoint | mid-scene action, no inter-story title card - the source is a Disney Junior HD broadcast with the transitions cut |

So which two stories sit inside a given file is not recoverable from the file. The counts say the pairing follows the original broadcast; only watching an episode can confirm it.

## Step 4: name for the multi-episode case

Both applications understand the same prefixed-range form, which is what makes this work at all:

```
The New Adventures of Winnie the Pooh - S01E01 - HDTV.HUN.x264.mkv
The New Adventures of Winnie the Pooh - S01E02-E03 - HDTV.HUN.x264.mkv
The New Adventures of Winnie the Pooh - S01E04-E05 - HDTV.HUN.x264.mkv
```

Sonarr counts such a file against every episode in the range, so the seasons report complete. Jellyfin creates one entry per file and joins the story titles with a slash. Season folders stay `Season 1` rather than `Season 01`, matching the `seasonFolderFormat` already configured, so Sonarr never creates a parallel folder later.

Generate the plan first and read it, rather than renaming in a loop. Fifty operations is enough to hide an off-by-one:

```bash
python3 plan.py            # prints the slot -> filename table, writes apply.sh
bash verify-sources.sh     # every source exists, no destination collides
bash apply.sh
```

The verification step earned its place immediately - and so did doing it in Python. A first attempt in shell,

```bash
while read -r op flag src dst; do ... done < <(grep -E "^(mv|cp) " apply.sh)
```

reported 22 of 50 sources missing. `read` had split the quoted paths on their spaces. **A verification pass that reports failures it invented is worse than no verification pass**, because the natural next move is to go looking for a problem that does not exist. A tab-separated manifest parsed by `shlex` found all 50 sources present and no collisions.

## Step 5: the trap that undoes the rename

With the files renamed, a `RescanSeries` looked like the obvious way to make Sonarr notice. It made Sonarr re-import the entire pack instead:

```
Season 1: 22 files, 4.7G   ->   44 files, 9.2G
```

Twenty-two `downloadFolderImported` events inside 45 seconds, restoring every original release name next to the renamed copy - the duplicate-episode bug the whole exercise was meant to remove.

The cause is in the queue, where one torrent had produced 35 rows, all sharing a single `downloadId`:

```
importBlocked | One or more episodes expected in this release were not imported or missing from the release
```

While the torrent sits in the `tv-sonarr` category, completed download handling keeps reprocessing it. After the rename, the old names parse as valid `S01E01..E22` again, so Sonarr considers them importable. **`monitored: false` does not prevent this** - not on the series and not on any season. Completed download handling does not consult monitoring.

So the order of operations is fixed, and step 2 belongs *before* any renaming:

1. Clear the torrent's queue rows, leaving the download client alone:

```bash
curl -X DELETE "http://localhost:8989/api/v3/queue/bulk?apikey=your_sonarr_api_key_here&removeFromClient=false&blocklist=false&skipRedownload=true" \
     -H "Content-Type: application/json" -d '{"ids":[...]}'
```

2. Move the torrent out of the watched category. Seeding is unaffected - state stays `stalledUP` and `seeding_time` keeps climbing - but Sonarr stops managing it. This is the durable brake; clearing the queue alone is not, because the next client poll puts the rows back.

```bash
docker exec qbittorrent curl -s -X POST http://127.0.0.1:8080/api/v2/torrents/setCategory \
  --data-urlencode "hashes=<hash>" --data-urlencode "category=UPLOADING - DO NOT DELETE"
```

3. Only then rename and rescan.

Reaching that API needs one detail. The container has `WebUI\LocalHostAuth=false`, but a request to the host's own `127.0.0.1:8080` arrives through the port mapping from the Docker gateway address, not from localhost, and gets a 403. `docker exec` into the container is what actually satisfies the localhost exemption. The stored WebUI password is a PBKDF2 hash and cannot be recovered to authenticate the normal way.

Clean up duplicates through the application, not with `rm`, so no orphaned rows survive:

```bash
curl -X DELETE "http://localhost:8989/api/v3/episodefile/bulk?apikey=your_sonarr_api_key_here" \
     -H "Content-Type: application/json" -d '{"episodeFileIds":[...]}'
```

Season statistics lie briefly afterwards - 13/35 against 22 files that cover all 35 - and a second rescan settles them.

## Step 6: the folder name Jellyfin reads

With all 50 files correctly named, Jellyfin still had the series as:

```
The New Adventures of Winnie the Pooh S01   |  year: none  |  ProviderIds: {}
```

It had taken the series folder name, `The.New.Adventures.of.Winnie.the.Pooh.S01-S04.WEB-DL.HUN.x264`, swallowed the `S01` of the season range into the title, and matched nothing. **Correct filenames cannot rescue a series folder whose name defeats the match** - with no provider ID there are no titles to display, however precise the episode ranges are.

The documented provider-ID form fixes it, and Sonarr will perform the move itself so its database stays consistent:

```bash
curl -X PUT "http://localhost:8989/api/v3/series/53?apikey=your_sonarr_api_key_here&moveFiles=true" \
     -H "Content-Type: application/json" --data-binary @series53.json
# path: /tv/hun/The New Adventures of Winnie the Pooh (1988) [tvdbid-78442]
```

After a library scan Jellyfin resolves it fully, in Hungarian:

```
Micimackó újabb kalandjai | 1988 | {Tvdb: 78442, Tmdb: 2005, Imdb: tt0165052}
  1. évad  E01      Micimackó filmet forgat
           E02-E03  Ki az igazi barát / A szamár napja
           E04-E05  A sátor is jó, de legjobb otthon / Lufi bolond
```

Four seasons, each with a real path, no phantom season, one entry per file.

A renamed folder is the case where the targeted item re-probe does not apply: the old item's path no longer exists, so the new folder has to be discovered by a `POST /Library/Refresh`.

### The auth header that changed underneath this

Every Jellyfin call above returned 401 at first, using a key that had worked earlier the same week. The server had moved to 12.0.0 on its `latest` tag, which drops the legacy authentication methods. Only one form works now:

```bash
curl -H "Authorization: MediaBrowser Token=\"$KEY\"" http://192.168.0.110:8096/System/Info
```

`X-Emby-Token`, `X-MediaBrowser-Token` and `?api_key=` all return 401. The key itself was still valid - worth checking the header before concluding a credential was revoked.

## What is left

The 4th season is missing one broadcast slot: `S04E11 - Owl's Well That Ends Well`, aired 1991-11-02. Eight files were mapped onto the first eight of nine slots, which is right if the absent slot is the last one. If it is a middle one instead, the tail of season 4 is shifted, and no measurement on the host can decide it.

The pairing itself rests on the count corroboration from Step 3, not on proof. The cheapest falsification is to play one file: the second file of season 1 should contain "Ki az igazi barát" and then "A szamár napja". Jellyfin also joins that pair in provider order rather than screen order in at least one case - `E30-E31` displays as "A sötétben / Tigris cipője" while the provider lists Tigger's Shoes before Lights Out - which is cosmetic and does not affect which file plays.

## Takeaways

- Count the files against the provider's episode total before configuring anything. When they disagree by more than a rounding error, the disagreement is the problem, and no import setting addresses it.
- A show with 11-minute segments has two legitimate numbering schemes. Providers pick the segment; releases pick the broadcast slot. Grouping provider episodes by air date converts between them.
- `ffprobe` duration across every file is a few seconds of work and rules out whole classes of layout in one pass.
- Matching counts across several independent seasons is strong corroboration. Say so, and say that it is not proof, when the frame-level checks come back empty.
- A completed torrent in the arr application's own download category will re-import a pack after any rescan. Move it out of that category before renaming anything by hand, and keep seeding by changing the category rather than removing the torrent.
- `monitored: false` does not stop completed download handling.
- A verification script that mis-parses its own input invents failures. Parse paths with something that respects quoting.
- A series folder named after a release, with a season range in it, can defeat Jellyfin's match entirely. The `[tvdbid-nnnnn]` suffix settles it, and Sonarr's `moveFiles=true` performs the rename without desynchronising its database.
