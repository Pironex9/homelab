# Custom Claude Code Output Style

**Date:** 2026-08-18
**Hostname:** claude-mgmt (LXC 109)
**IP address:** 192.168.0.204
**Location:** `claude/output-styles/norbert.md`, symlinked to `~/.claude/output-styles/`

## The Problem

Claude Opus 5 shipped on 2026-07-24 and the loudest complaint about it was not accuracy, it was register: the answer arrives buried under explanation, hedging and recap. The community named the failure mode "Claudeslop" and "too talkative" was the top-voted reaction to the launch.

I had written my behaviour rules - answer first, search before claiming, no flattery, no emojis - into the account-level preferences field, and they worked for the first stretch of a session and then quietly stopped mattering. The rules were not being ignored on purpose. They were in the wrong place.

## Why CLAUDE.md Is The Wrong Layer For This

Claude Code has several customisation layers, and they are not interchangeable:

| Layer | Mechanism |
|---|---|
| `CLAUDE.md` | injected as a **user message after** the system prompt |
| Output style | **modifies the system prompt itself** |
| `--append-system-prompt` | one-off addition for a single invocation |
| Agents | separate system prompt, own scope |
| Skills | loaded on demand when relevant |

That first row is the whole problem. A `CLAUDE.md` rule is a message near the start of the conversation, and as the transcript grows it slides further back behind tool output, file contents and diffs. Nothing re-asserts it.

An output style does not slide, because it is not in the conversation. It is in the system prompt, and the harness additionally emits per-turn reminders to adhere to it. Anthropic's own documentation draws the line the same way: project knowledge belongs in `CLAUDE.md`, how Claude should talk belongs in an output style.

The practical rule that follows: **"what Claude should know" goes in `CLAUDE.md`, "how Claude should behave every single turn" goes in an output style.** Writing tone rules into `CLAUDE.md` also bloats the context of every session with something that is not project knowledge.

## What Makes One Actually Work

The community collection at `smixs/awesome-claude-output-styles` benchmarks 19 styles and publishes the conventions they share. Five of them contradict how most people write this kind of file:

1. **Specs, not adjectives.** "No sentence over 20 words" is checkable. "Be concise" is not, and is the reason most brevity instructions fail.
2. **Positive framing.** Describe the wanted voice. Long ban lists summon the banned patterns. Mechanical bans (em dashes, emoji) are the exception and are followed reliably.
3. **Byte-exact guardrails.** Code, commands, error messages, paths, identifiers and numbers are never stylised, and the persona switches off entirely for security warnings and destructive-action confirmations.
4. **Cut ceremony, not reasoning.** Only the wrapper shrinks. The "why" stays.
5. **Every constraint names its own failure mode.** A depth request has to suspend the brevity budget, or the style goes quiet exactly where an explanation was wanted.

The file structure they all follow: frontmatter, an identity line, a `# <Name> Style Active` marker, numbered procedural rules, a worked example, a guardrails block, and a self-check. The marker and the self-check are not decoration - the per-turn reminder refers back to them.

## The Frontmatter Trap

```yaml
---
name: Norbert
description: Answer-first, web-verified, no flattery
keep-coding-instructions: true
---
```

`keep-coding-instructions` defaults to **`false`**, and that default is the most common way to break a custom style. Left out, Claude Code drops its built-in software engineering instructions - how to scope a change, how to verify work, how to handle comments - and you get a polite assistant that has forgotten how to do the job. Anything that still writes code needs it set to `true`.

## Rules Worth Stealing

Most of my file is personal calibration, but three rules generalise.

**Verification has a local exception.** "Always search the web before answering" is a good rule that misfires on a homelab: asking about my own compose stack or LXC does not need a search, it needs a file read. The rule states that reading the machine's own repo, hosts, containers and logs *is* verification, so the search budget goes to versions, pricing and third-party configs where it belongs.

**"Skip the basics" needs a counter-rule.** Listing what not to re-explain (Linux, routing, Docker, git, Proxmox) is only half of it. Without an explicit "explain anything actually asked about, however basic it looks", the style goes silent precisely when the user is trying to learn something.

**Turn a measured weakness into a guardrail.** The [prompt self-audit](prompt-analysis.md) found that only 1% of my state-changing prompts asked about rollback. So the style does not say "mention rollback if asked" - it requires the rollback path to be stated *unprompted*, in full sentences, before anything destructive, and to wait. That line is not style. It is the one piece of the file doing safety work.

## Installing It

```bash
mkdir -p ~/.claude/output-styles
ln -s /path/to/repo/claude/output-styles/norbert.md ~/.claude/output-styles/norbert.md
```

Then select it with `/config` → **Output style**, or set it directly in `~/.claude/settings.json` so it applies across every project:

```json
{
  "outputStyle": "Norbert"
}
```

Settings precedence runs managed → CLI args → `.claude/settings.local.json` → `.claude/settings.json` → `~/.claude/settings.json`, so a project-level file silently wins over the user-level one. Worth checking with `grep -rn outputStyle .claude/` if a style appears to have no effect.

Two things that cost time if you do not know them:

- **The style is read once at session start.** Edits do nothing until `/clear` or a new session. Editing the file and watching the current session for changes proves nothing.
- **Styles apply to the main conversation only.** A subagent runs its own system prompt and ignores the style. A fork is the exception, since it inherits the parent's system prompt.

The symlink is the reason this doc exists in a git repo at all: the file lives in version control, and `~/.claude/` holds only a pointer, so the config survives a container rebuild.

## What I Did Not Do

There is an undocumented `CLAUDE_CODE_SIMPLE_SYSTEM_PROMPT` environment variable, and the theory circulating is that Opus 5 gets a short system prompt in Claude Code with none of the anti-verbosity rules, so forcing the long preset fixes the verbosity at the source.

The variable is real - it is present in the v2.1.234 binary alongside `CLAUDE_CODE_SIMPLE`:

```bash
grep -aoh "CLAUDE_CODE_SIMPLE[A-Z_]*" ~/.local/share/claude/versions/2.1.234 | sort -u
```

But it appears in no official documentation, and I could not verify that the value does what the claim says - only that the name exists in the binary. Building a permanent workflow on an undocumented internal flag that can change in any release is a worse trade than a supported feature that solves the same problem. The output style is the supported feature.

## Sources

- [Output styles - Claude Code documentation](https://code.claude.com/docs/en/output-styles)
- [Settings and precedence - Claude Code documentation](https://code.claude.com/docs/en/settings)
- [smixs/awesome-claude-output-styles](https://github.com/smixs/awesome-claude-output-styles) - benchmarked style collection and authoring conventions
