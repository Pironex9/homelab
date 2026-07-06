# Hermes + Odysseus Agentic OS - Design

**Date:** 2026-07-06
**Status:** Approved

## Overview

A local "agentic OS" layer that sits alongside Claude Code: a self-improving background agent (Hermes) with a graphical workspace UI (Odysseus), routed to a local GPU model first, a cheap cloud model second, and full Claude Code (with all existing MCPs/skills) only for tasks that actually need it. Goals:

- A GUI to see skills, scrapers, and files (the original ask), instead of everything living in a terminal
- Offload routine/background work (cron reports, log triage, note maintenance, scraper monitoring) away from Claude Code tokens
- Keep the expensive, high-quality model (Claude) reserved for work that needs it

## Non-Goals

- Not replacing Claude Code for actual coding/refactoring work
- Not deploying OpenClaw (Hermes explicitly targets it as the lighter/safer alternative; community consensus favors Hermes for orchestration)
- No Discord integration for now (Telegram only)
- No public exposure via Pangolin/VPS - LAN + Tailscale only
- Not migrating the uzlet scraper itself onto this stack (separate, future concern)

## Architecture

```
Nobara PC (RTX 2060 Super, 8GB VRAM, Ryzen 3700X, 32GB RAM)
  Ollama :11434 - Qwen3 8B (Q4_K_M, routine tasks)
                - Qwen3.6-35B-A3B MoE (Q4, --n-cpu-moe, heavier local tasks)
       |
       | LAN
       v
LXC 113 "agentos" (new, Debian, 2 core / 4GB RAM / 20GB disk)
  +-- Odysseus (Docker Compose, :7000) --- Caddy (LXC 110) --- https://agentos.lan
  +-- Hermes Agent (native install, no Docker)
        - providers: Nobara Ollama (primary) -> DeepSeek API (fallback)
        - Telegram gateway (new dedicated bot, DM-pairing mode)
        - SSH backend -> LXC 109 for delegated coding tasks
       |
       | SSH, restricted key (forced command only)
       v
LXC 109 "claude-mgmt" (existing)
  /usr/local/bin/hermes-claude-code.sh - wraps `claude -p "<task>"`
  Full existing MCP/skill/memory setup stays untouched and reachable
  only through this one wrapper script
```

## Components

### LXC 113 (new)

- Debian, matching the majority of existing LXCs (106, 107)
- 2 cores / 4GB RAM / 20GB disk on `local-lvm` - sized like Karakeep/n8n plus headroom for Docker + Odysseus images
- DHCP-assigned IP, consistent with existing convention
- Freed by deleting the unused LXC 112 (minecraft), which brought `local-lvm` free space from ~19.5GB to ~24.4GB

### Hermes Agent

- Native install (`curl ... | bash`), no Docker - it's the lightweight orchestration layer
- Providers configured in order: Nobara Ollama endpoint (`http://192.168.0.100:11434`) as primary, `DEEPSEEK_API_KEY` as fallback via `~/.hermes/.env`
- New, dedicated Telegram bot (separate from the existing Form/DocuSeal bot) registered via BotFather, DM-pairing mode enabled so unknown senders only get a pairing code
- SSH backend targets LXC 109 using a dedicated key pair generated on LXC 113
- Agent toolset starts in a cautious sandbox posture: file-modifying/bash tools default to `always_ask` until proven trustworthy, then can be loosened per-tool

### Odysseus

- Docker Compose (`docker compose up -d --build`), default port `:7000`
- Same Ollama endpoint as Hermes for its local-model chat/research/document features
- Reverse-proxied through Caddy (LXC 110) as `agentos.lan` with the existing mkcert setup, LAN/Tailscale only - no Pangolin/public exposure

### LXC 109 integration (deep integration, chosen over isolated)

- A new SSH key pair is generated specifically for this integration (not reused from any existing key)
- The public key is installed in LXC 109's `authorized_keys` with a **forced command**: `command="/usr/local/bin/hermes-claude-code.sh"` - this key cannot open an interactive shell or run arbitrary commands, only invoke the wrapper
- The wrapper script accepts a bounded task string and runs `claude -p "<task>"` in a fixed working directory, giving Hermes-delegated work access to the full existing Claude Code environment (all MCPs, skills, memory) without granting raw shell access over that channel
- Rationale: if Hermes is ever manipulated via prompt injection (e.g. through a Telegram message), the blast radius on LXC 109 is limited to "ask Claude Code to do a bounded task," not arbitrary shell execution

## Model Routing / Failover Chain

1. **Primary:** Nobara Ollama (free, local) - only available while the Nobara PC is powered on
2. **Fallback:** DeepSeek API (`deepseek-v4-flash`, ~$0.14/1M input, ~$0.28/1M output) - used automatically when the local endpoint is unreachable
3. **Not part of the failover chain, invoked deliberately:** LXC 109 Claude Code via the SSH wrapper, for actual coding/refactoring/high-stakes work

This is deliberately a cost/quality ladder, not a single "best" model - routine work stays cheap, hard work still goes to Claude.

## Security

- Forced-command SSH key for the LXC 109 channel (see above) - the single most important control in this design
- Telegram DM-pairing mode - unknown senders can't interact until approved
- Hermes sandbox mode on for potentially destructive tools by default
- No public exposure of Odysseus or Hermes's gateway; both stay on LAN/Tailscale
- DeepSeek is a third-party (China-based) API - homelab logs/config/scraper data will transit their servers when the fallback triggers; acceptable for this use case, called out for awareness

## Verification / Acceptance Criteria

- `hermes doctor` reports no errors after install
- A test message sent through the new Telegram bot gets a response
- Stopping the Nobara Ollama service causes the next Hermes request to visibly fall back to DeepSeek (confirmed in Hermes logs)
- `https://agentos.lan` loads Odysseus and the admin account works
- A bounded test task sent to Hermes ("fix a typo in the docs") is actually delegated over SSH and executed by Claude Code on LXC 109
- The forced-command key cannot open a plain interactive shell on LXC 109 (manual check: `ssh -i <key> claude-mgmt` should refuse/only run the wrapper)
