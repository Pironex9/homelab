# 33 - Daily AI News Digest Pipeline

**Date:** 2026-08-13
**Hostname:** claude-mgmt (LXC 109), karakeep (LXC 106), docker-host (LXC 100)
**IP address:** 192.168.0.204, 192.168.0.128, 192.168.0.110

## The problem

Keeping up with AI releases is a reading-volume problem, not a tooling problem.
Roughly twenty sources produce 40-60 items a day, of which maybe eight matter to
any one person. Every newsletter solves this for an imaginary average reader.

Before building anything, the existing options were surveyed:

| Option | Why it was rejected |
|---|---|
| [Meridian](https://github.com/iliane5/meridian) | Excellent output, but built on Cloudflare Workers/Workflows/Pages at roughly $1/day. Wrong platform for a homelab. Its briefing prompt is worth reading regardless. |
| [auto-news](https://finaldie.com/blog/auto-news-an-automated-news-aggregator-with-llm/) | RSS + Reddit + YouTube + Twitter via LangChain, Notion-centric. A whole compose stack for a twenty-line daily summary. |
| [Precis](https://github.com/leozqin/precis) | A nicer RSS reader with summaries. The personalised filtering, which is the actual hard part, is missing. |
| n8n templates | At least six ready-made ones exist. Maintaining a fifteen-node workflow is more work than fifty lines of Python, and prompt tuning inside JSON nodes is painful. |
| FreshRSS per-article AI extensions | Summarising sixty articles leaves sixty things to read. The goal is *fewer* items, not shorter ones. |

The conclusion: the pipeline is the easy part and everyone has already built it.
The hard part is deciding what is relevant to one specific person, and that is a
prompt, not an architecture.

## Architecture

```
cron 07:30 (LXC 109)
  └─ scripts/ai-digest.py
       ├─ FreshRSS GReader API  ──  categories "AI" and "AI Video"
       ├─ claude -p --model sonnet  +  the profile prompt
       ├─ markdown file            (working copy, gitignored)
       ├─ Telegram Bot API         (the thing actually read each morning)
       └─ Karakeep REST API        (permanent, searchable archive)
```

Nothing new was deployed for this. FreshRSS already ran on LXC 100, Karakeep on
LXC 106, and the `claude` CLI on LXC 109.

### Why FreshRSS does the fetching

The script contains no feed list and no feed parser. FreshRSS already polls every
fifteen minutes, deduplicates, and exposes everything through its Google Reader
API at `/api/greader.php`. Feeds are therefore managed in the FreshRSS UI, by
dropping them into the `AI` or `AI Video` category, and the script picks them up
without a code change.

### Why the archive is a separate system

FreshRSS is configured with `keep_period = P3M` and `keep_max = 200` per feed, so
it deletes articles after three months. It is a reading window, not an archive.
Karakeep is the archive: it stores the page itself with a snapshot, so the content
survives the link rotting, and it indexes everything in Meilisearch.

Only the items the model actually linked in the digest get archived. Rather than
asking the model for a second, separate list of what it kept, the script regexes
the `href` attributes out of the finished digest. Whatever it linked to is, by
definition, what it decided mattered.

### Source selection

Twelve text feeds and eight YouTube channels. Every candidate feed was checked for
a live HTTP 200 and a non-empty item list before being subscribed, which caught
three dead ones immediately:

- **Anthropic has no RSS feed.** Both `/rss.xml` and `/news/rss.xml` return 404.
- **MarkTechPost returns 403** to non-browser user agents.
- **Import AI and The Batch** have no active feeds either.

`arXiv cs.AI` was deliberately left out: several hundred items a day would drown
everything else.

YouTube channels are subscribed through their per-channel feed
(`youtube.com/feeds/videos.xml?channel_id=UC...`), which needs the channel ID, not
the handle. The ID is in the channel page HTML as `channel/UC...`.

## Design decisions worth knowing

**Video titles only, no transcripts.** Transcript extraction runs into YouTube bot
detection from datacenter IPs, needs cookie juggling, and burns a large number of
tokens per video. The digest lists the video so a decision can be made; deep dives
are on demand.

**Telegram HTML, never MarkdownV2.** MarkdownV2 requires eighteen characters to be
backslash-escaped and **silently breaks the message** if one is missed. HTML mode
only needs `<`, `>` and `&`. The prompt therefore asks for Telegram HTML directly
rather than markdown, which removes the escaping problem instead of handling it.
The message limit is 4096 characters; the script splits at 4000 on line boundaries.

**Two things are enforced in code, not in the prompt.** Unknown HTML tags are
stripped, because one unsupported tag makes Telegram reject the entire message with
a 400. And any preamble before the first `<b>` is cut, because the model writes
"here is the digest:" regardless of being told not to. Both are cheaper to fix in
three lines of Python than to fight in the prompt.

**A state file, not a fixed 24-hour window.** `.last-run` holds the previous run
timestamp with a 36-hour cap. A failed run therefore causes no gap, and a
successful one causes no duplicates.

## The part that actually determines quality

A single gitignored prompt file holds both the reader profile and the filtering
rules. It scores items for relevance to one person's actual work and drops
everything below the bar, then writes six fixed blocks in Hungarian with English
technical terms preserved.

The last block is a one-line noise report: how many items were dropped and roughly
why. That line exists purely as a feedback signal - it is the only way to notice
that the filter has started throwing away things that mattered.

The rules also permit "nothing significant happened today" as a legitimate output.
Without that, a daily digest inflates itself with noise to justify its own
existence.

## Cost

The `claude` CLI on LXC 109 authenticates with a Pro subscription, not an API key,
so a single daily call of roughly 30-40k tokens costs nothing extra. The failure
mode to know about: if the stored credential expires, cron fails **silently** - no
Telegram message arrives, and the reason is in the log file next to the digests.

## Lessons Learned

- **The aggregation pipeline is not the hard part.** Four mature open-source
  projects and half a dozen n8n templates already do it. What none of them can do
  is know which eight of today's sixty items matter to you, and that is one prompt
  file.
- **Verify feed URLs before subscribing, not after.** Three of the recommended
  "best AI feeds" were dead or blocking. A silently empty feed looks identical to
  a quiet news day.
- **Let the existing system do the boring work.** FreshRSS already handles polling,
  deduplication, retries and storage. Reimplementing that with a feed parser would
  have added a dependency, a feed list in code, and a second thing to maintain.
- **Deliver where the reading already happens.** A generated file nobody opens is
  the same as no digest. Telegram was chosen over a static page for exactly this
  reason, and over Discord for its 4096-character limit and simpler delivery.
