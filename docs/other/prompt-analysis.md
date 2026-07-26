# Prompt Self-Audit Script

**Date:** 2026-07-26
**Language:** Python 3 (standard library only)
**Location:** `scripts/prompt-analysis.py`

## The Problem

After a year of daily work with Claude Code, I had thousands of my own prompts sitting in session transcripts and no idea what they said about how I actually work. Do I supply enough context? Do I verify what the model claims? Do I iterate, or do I just re-ask?

This matters beyond curiosity: some companies log and analyse the prompts of people who work with AI tools. Being able to audit your own prompting habits - before someone else does - is the same instinct as reading your own logs before the on-call page arrives.

There is no built-in feature for this. The Claude Team/Enterprise admin console exposes usage *metadata* only (who, when, how much) - never prompt text. Third-party LLM observability platforms (Langfuse, Helicone, PromptLayer) log API calls, but they do not see local Claude Code sessions. So the data source has to be the transcripts themselves.

## Data Source

Claude Code writes every session to `~/.claude/projects/<slugified-cwd>/<session-uuid>.jsonl`, one JSON object per line. Records carry a `type` and, for user records, a `promptSource` field:

| `promptSource` | meaning |
|---|---|
| `typed` | the human actually typed it |
| `queued` | typed while the model was busy |
| `suggestion_accepted` | accepted an autocomplete suggestion |
| `system` | harness-injected |
| `sdk` | programmatic |
| *(absent)* | tool results, attachments, hook output |

Only the first three are human-authored. Sidechain records (`isSidechain: true`) are subagent traffic and are excluded, as are harness wrappers such as `<local-command-stdout>` and `<system-reminder>` blocks - otherwise the corpus fills with text the user never wrote.

## What It Measures

Deterministic statistics first, since those are cheap and reproducible:

- **Volume** - prompts, sessions, active days, prompts per session, length distribution (median / mean / p90)
- **Habit signals** - regex markers over the corpus for context provision (paths, URLs, code), questions, requests for reasoning, requests for options, research-first instructions, verification requests, explicit constraints, multi-step decomposition, corrections, security/privacy mentions, backup/rollback mentions
- **Rhythm** - prompts per hour of day, ASCII histogram
- **Split** - per project, so a homelab session and a production project can be compared

The keyword matching is deliberately shallow. It measures habits at corpus scale, not the meaning of any single prompt - a 1700-prompt sample makes the noise average out.

The qualitative half is left to an LLM: the script emits a scoring rubric plus an evenly-sampled corpus, so the report can be handed straight back to Claude for grading on clarity, context provision, decomposition, iteration, verification, delegation judgement, domain reasoning, and data hygiene.

## Usage

```bash
./scripts/prompt-analysis.py --list                  # available projects
./scripts/prompt-analysis.py                         # all projects combined
./scripts/prompt-analysis.py -p homelab -o report.md # one project
./scripts/prompt-analysis.py --since 2026-06-01 --sample 100
```

`-p` is a repeatable substring match, `--since` takes an ISO date, `--sample` controls how many prompts land in the corpus section.

## What It Found

Across 1702 human-authored prompts, 48 sessions and 51 active days:

| Metric | Value |
|---|---|
| Median prompt length | 8 words (p90: 40) |
| One-liners (<=5 words) | 41% |
| Supplies concrete context | 14% |
| Asks a question | 36% |
| Requests verification | 6% |
| Mentions backup/rollback | 1% |

The interesting result was that the headline number is misleading. **41% one-liners looks like careless prompting, and it is not.** Nearly all of them are `mehet` ("go ahead"), `alkalmazd` ("apply it"), `2.`, `A opcio` - approval steps in a plan → review → approve loop. The reasoning happens while reading the generated plan, not while typing the prompt. A metric-only reading of the same corpus would score this as low effort and be exactly wrong.

The genuine finding was the 1%: state-changing prompts (`push`, `mehet prodba`) almost never came with a rollback question. That is a one-line habit change and the highest-leverage thing the audit surfaced.

## Design Notes

Standard library only - `json`, `glob`, `re`, `statistics`, `collections`, `argparse`. No dependencies for what is fundamentally a line-by-line JSON read and some counting. It ships with an assert-based `_selfcheck()` rather than a test framework:

```bash
python3 -c "import sys; sys.path.insert(0,'scripts'); \
  import importlib; m=importlib.import_module('prompt-analysis'); m._selfcheck()"
```

Everything stays local. The transcripts never leave the machine, and the report is a plain markdown file.
