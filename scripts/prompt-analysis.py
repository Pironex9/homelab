#!/usr/bin/env python3
"""Extract and analyse your own typed prompts from Claude Code session transcripts.

Produces the kind of report an employer would build from prompt logs: how you
frame problems, how much context you supply, whether you iterate, whether you
verify output. Stats are deterministic; the qualitative scoring is left to an
LLM pass over the emitted corpus.

Usage:
  ./prompt-analysis.py                        # all projects
  ./prompt-analysis.py -p homelab             # one project
  ./prompt-analysis.py -p homelab -p uzlet    # several
  ./prompt-analysis.py --since 2026-06-01 --sample 80 -o /tmp/report.md
"""

import argparse
import collections
import datetime as dt
import glob
import json
import os
import re
import statistics

PROJECTS_DIR = os.path.expanduser("~/.claude/projects")
# promptSource values that mean "the human actually wrote this"
HUMAN_SOURCES = {"typed", "queued", "suggestion_accepted"}

# Signal markers. Deliberately shallow keyword matching - it measures habits at
# corpus scale, not the meaning of any single prompt.
MARKERS = {
    "verification": r"\b(ellen[őo]rizd|ellen[őo]rizz|n[ée]zd meg|tesztel|teszteld|pr[óo]b[áa]ld|check|verify|test it|make sure|gy[őo]z[őo]dj)\b",
    "research_first": r"\b(keress r[áa]|keress|search|n[ée]zz ut[áa]na|docs?|dokument[áa]ci[óo]|context7|web)\b",
    "correction": r"\b(nem j[óo]|rossz|nem az|m[ée]gse|ink[áa]bb|jav[íi]tsd|nem m[űu]k[öo]dik|hib[áa]s|wrong|no,|actually|instead)\b",
    "constraint": r"\b(ne |csak |kiz[áa]r[óo]lag|maximum|legfeljebb|fontos hogy|must|don't|do not|only|without)\b",
    "reasoning_request": r"\b(mi[ée]rt|magyar[áa]zd|indokold|gondolkodj|why|explain|think|reason|trade-?off|el[őo]ny|h[áa]tr[áa]ny)\b",
    "options_request": r"\b(mi a legjobb|melyik|opci[óo]|alternat[íi]v|javasolj|ajánl|aj[áa]nl|recommend|options?|compare|vs\.?)\b",
    "decomposition": r"\b(el[őo]sz[öo]r|azt[áa]n|ut[áa]na|l[ée]p[ée]s|step|first|then|finally|1\.|2\.)\b",
    "security": r"\b(secret|api[- ]?key|jelsz[óo]|password|token|redact|gitignore|priv[áa]t|private|credential)\b",
    "rollback": r"\b(backup|ments|mentsd|visszavon|rollback|git stash|commit el[őo]tt|ne commit)\b",
}
QUESTION = re.compile(r"\?")
PATHLIKE = re.compile(r"(/[\w.\-/]+|https?://\S+|`[^`]+`|\b\w+\.(py|sh|yml|yaml|md|json|conf|ts|js)\b)")
HU_HINT = re.compile(r"[őűáéíóúöü]|\b(hogy|nem|kell|lehet|csak|majd|akkor)\b", re.I)
SLASH_CMD = re.compile(r"^\s*/\w[\w:-]*")
# harness-injected wrappers that are not authored by the user
NOISE = re.compile(r"<(local-command|command-name|system-reminder|bash-std)", re.I)


def load_prompts(project_dirs, since=None):
    out = []
    for pdir in project_dirs:
        name = os.path.basename(pdir).lstrip("-").replace("-", "/")
        for path in glob.glob(os.path.join(pdir, "*.jsonl")):
            session = os.path.basename(path)[:8]
            for line in open(path, errors="replace"):
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if d.get("type") != "user" or d.get("isSidechain"):
                    continue
                if d.get("promptSource") not in HUMAN_SOURCES:
                    continue
                text = d.get("message", {}).get("content")
                if not isinstance(text, str) or not text.strip():
                    continue
                if NOISE.search(text):
                    continue
                ts = d.get("timestamp", "")
                if since and ts[:10] < since:
                    continue
                out.append({"project": name, "session": session, "ts": ts, "text": text.strip()})
    out.sort(key=lambda p: p["ts"])
    return out


def analyse(prompts):
    words = [len(p["text"].split()) for p in prompts]
    sessions = collections.defaultdict(list)
    for p in prompts:
        sessions[(p["project"], p["session"])].append(p)

    def pct(pred):
        return 100.0 * sum(1 for p in prompts if pred(p)) / len(prompts)

    stats = {
        "prompts": len(prompts),
        "sessions": len(sessions),
        "days": len({p["ts"][:10] for p in prompts}),
        "words_median": statistics.median(words),
        "words_mean": round(statistics.mean(words), 1),
        "words_p90": sorted(words)[int(len(words) * 0.9) - 1],
        "one_liners_pct": pct(lambda p: len(p["text"].split()) <= 5),
        "long_pct": pct(lambda p: len(p["text"].split()) >= 40),
        "prompts_per_session": round(len(prompts) / len(sessions), 1),
        "questions_pct": pct(lambda p: bool(QUESTION.search(p["text"]))),
        "with_context_pct": pct(lambda p: bool(PATHLIKE.search(p["text"]))),
        "slash_cmd_pct": pct(lambda p: bool(SLASH_CMD.match(p["text"]))),
        "hungarian_pct": pct(lambda p: bool(HU_HINT.search(p["text"]))),
    }
    for name, pat in MARKERS.items():
        rx = re.compile(pat, re.I)
        stats[name + "_pct"] = pct(lambda p, rx=rx: bool(rx.search(p["text"])))

    by_project = collections.Counter(p["project"] for p in prompts)
    by_hour = collections.Counter(int(p["ts"][11:13]) for p in prompts if len(p["ts"]) > 13)
    session_lens = sorted((len(v) for v in sessions.values()), reverse=True)
    return stats, by_project, by_hour, session_lens


def bar(n, total, width=28):
    return "█" * max(1, round(width * n / total)) if n else ""


RUBRIC = """\
## Qualitative pass (feed this file to Claude)

Score the prompt corpus below 1-5 on each dimension, with concrete quotes as
evidence and one concrete improvement per dimension:

1. **Clarity & specificity** - is the goal unambiguous, is success defined?
2. **Context provision** - files, constraints, environment, prior state supplied up front?
3. **Problem decomposition** - big goals split into steps, or dumped as one blob?
4. **Iteration & steering** - how are wrong answers corrected: re-prompt with new
   information, or vague "no, again"?
5. **Output verification** - is the model asked to test, check, prove? Is its
   claim ever independently confirmed?
6. **Delegation judgement** - right level of autonomy: neither micromanaging
   trivia nor handing over decisions the human should own.
7. **Domain reasoning** - do the prompts show understanding of the system being
   worked on, or blind trust in the model?
8. **Safety & data hygiene** - secrets, backups, irreversible actions.

Finish with: strongest pattern, weakest pattern, and the single highest-leverage
habit change.
"""


def render(prompts, stats, by_project, by_hour, session_lens, sample):
    L = []
    a = L.append
    a("# Prompt analysis\n")
    a(f"_Generated {dt.date.today()} from Claude Code session transcripts._\n")

    a("## Volume\n")
    a(f"- **{stats['prompts']}** human-authored prompts across **{stats['sessions']}** sessions, **{stats['days']}** active days")
    a(f"- **{stats['prompts_per_session']}** prompts per session (longest sessions: {session_lens[:5]})")
    a(f"- Length: median **{stats['words_median']:.0f}** words, mean {stats['words_mean']}, p90 {stats['words_p90']}")
    a(f"- {stats['one_liners_pct']:.0f}% are one-liners (<=5 words), {stats['long_pct']:.0f}% are detailed (>=40 words)\n")

    a("## Per project\n")
    total = sum(by_project.values())
    for name, n in by_project.most_common():
        a(f"- `{name}` {n} ({100*n/total:.0f}%) {bar(n, total)}")
    a("")

    a("## Habit signals\n")
    a("| Signal | % of prompts | reads as |")
    a("|---|---|---|")
    rows = [
        ("Supplies concrete context (paths, URLs, code)", "with_context_pct", "grounding vs vague asks"),
        ("Asks a question", "questions_pct", "dialogue vs pure command"),
        ("Requests reasoning / why", "reasoning_request_pct", "wants the model's thinking exposed"),
        ("Asks for options / comparison", "options_request_pct", "decision support vs order-taking"),
        ("Requests research first", "research_first_pct", "distrust of unverified recall"),
        ("Requests verification / testing", "verification_pct", "output evaluation habit"),
        ("Sets explicit constraints", "constraint_pct", "scope control"),
        ("Multi-step / sequenced", "decomposition_pct", "task decomposition"),
        ("Corrects or redirects", "correction_pct", "iterative steering"),
        ("Mentions secrets / privacy", "security_pct", "data hygiene"),
        ("Mentions backup / rollback", "rollback_pct", "risk awareness"),
        ("Slash command", "slash_cmd_pct", "tooling fluency"),
        ("Hungarian", "hungarian_pct", "working language"),
    ]
    for label, key, meaning in rows:
        a(f"| {label} | {stats[key]:.0f}% | {meaning} |")
    a("")

    a("## When you work\n```")
    peak = max(by_hour.values()) if by_hour else 1
    for h in range(24):
        n = by_hour.get(h, 0)
        a(f"{h:02d}  {bar(n, peak, 34):<34} {n}")
    a("```\n")

    a(RUBRIC)
    a(f"\n## Corpus ({min(sample, len(prompts))} of {len(prompts)} prompts, evenly sampled)\n")
    step = max(1, len(prompts) // sample)
    for p in prompts[::step][:sample]:
        text = " ".join(p["text"].split())
        if len(text) > 700:
            text = text[:700] + " […]"
        a(f"- `{p['ts'][:16]}` `{p['project']}` {text}")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-p", "--project", action="append", default=[],
                    help="project name substring (repeatable); default all")
    ap.add_argument("--since", help="ISO date, e.g. 2026-06-01")
    ap.add_argument("--sample", type=int, default=60, help="prompts to include in corpus (default 60)")
    ap.add_argument("-o", "--out", help="write markdown here instead of stdout")
    ap.add_argument("--list", action="store_true", help="list available projects and exit")
    args = ap.parse_args()

    dirs = sorted(d for d in glob.glob(os.path.join(PROJECTS_DIR, "*")) if os.path.isdir(d))
    if args.list:
        for d in dirs:
            n = len(glob.glob(os.path.join(d, "*.jsonl")))
            print(f"{os.path.basename(d)}  ({n} sessions)")
        return
    if args.project:
        dirs = [d for d in dirs if any(s.lower() in os.path.basename(d).lower() for s in args.project)]
    if not dirs:
        raise SystemExit("no matching projects; try --list")

    prompts = load_prompts(dirs, args.since)
    if not prompts:
        raise SystemExit("no prompts found for that filter")

    report = render(prompts, *analyse(prompts), sample=args.sample)
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(report)
        print(f"{len(prompts)} prompts -> {args.out}")
    else:
        print(report)


def _selfcheck():
    """python3 -c 'import prompt_analysis as m; m._selfcheck()' - no deps, no fixtures."""
    ps = [
        {"project": "x", "session": "s1", "ts": "2026-01-01T09:00:00Z",
         "text": "nezd meg a /etc/fstab-ot es ellenorizd hogy jo-e?"},
        {"project": "x", "session": "s1", "ts": "2026-01-01T10:00:00Z", "text": "nem jo, inkabb masik"},
    ]
    st, byp, byh, sl = analyse(ps)
    assert st["prompts"] == 2 and st["sessions"] == 1, st
    assert st["verification_pct"] == 50.0, st["verification_pct"]
    assert st["correction_pct"] == 50.0, st["correction_pct"]
    assert st["with_context_pct"] == 50.0, st["with_context_pct"]
    assert byh[9] == 1 and sl == [2]
    assert "Prompt analysis" in render(ps, st, byp, byh, sl, sample=5)
    print("ok")


if __name__ == "__main__":
    main()
