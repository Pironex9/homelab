# Hermes + Odysseus Agentic OS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a background "agentic OS" layer (Hermes + Odysseus) on a new dedicated LXC, wired to a local Ollama model on the Nobara GPU box, a DeepSeek fallback, and a security-scoped SSH channel into LXC 109 for delegated Claude Code work.

**Architecture:** New LXC 113 hosts Hermes (native install) and Odysseus (Docker Compose). Both point their model provider at the Nobara Ollama endpoint first, DeepSeek API second. Hermes reaches LXC 109 through a dedicated SSH key restricted by a forced command that only runs a bounded `claude -p` wrapper. Odysseus is reverse-proxied through the existing Caddy instance as `agentos.lan`.

**Tech Stack:** Proxmox LXC (Debian 12), Docker + Docker Compose, Hermes Agent (Python/uv installer), Odysseus (Docker Compose web app), Caddy (existing), Ollama (existing, Nobara + LXC 108), DeepSeek API.

## Global Constraints

- LXC 113: Debian 12 (`debian-12-standard_12.12-1_amd64.tar.zst`), 2 cores, 4096MB RAM, 20GB disk on `local-lvm`, unprivileged, `features: nesting=1,keyctl=1` (required for Docker-in-LXC, matching the Komodo LXC 105 pattern), bridge `vmbr0`, DHCP.
- Nobara Ollama endpoint: `http://192.168.0.100:11434` (existing, already used by Karakeep).
- DeepSeek provider: `DEEPSEEK_API_KEY` env var, Hermes provider name `deepseek`.
- No public/Pangolin exposure anywhere in this plan — LAN + Tailscale only.
- Never commit real secrets (Telegram bot token, DeepSeek API key) to git — only `.env.example` placeholders.
- Every reverse-proxied `*.lan` host follows the existing Caddyfile snippet pattern on LXC 110 (`@name host name.lan` / `handle @name { reverse_proxy IP:PORT }` inside the `lan_services` snippet).

---

## File Structure

- Create: `compose/proxmox-lxc-113/odysseus/docker-compose.yml` — Odysseus service definition
- Create: `compose/proxmox-lxc-113/odysseus/.env.example` — placeholder env template
- Create: `scripts/hermes-claude-code-wrapper.sh` — version-controlled copy of the forced-command wrapper deployed to LXC 109
- Create: `docs/hosts/agentos.md` — per-host reference doc for LXC 113, matching the existing `docs/hosts/*.md` pattern
- Modify: `docs/README.md` — add the new host doc to the index
- Modify: `mkdocs.yml` — add nav entry for `hosts/agentos.md`

Nothing else in the repo changes. All LXC provisioning, package installs, and remote config live on the Proxmox host / LXC 113 / LXC 109 / Nobara and are not git-tracked (consistent with how LXC 105/106/107/110 are managed today).

---

### Task 1: Provision LXC 113

**Files:** none (Proxmox host only)

**Interfaces:**
- Produces: `LXC113_IP` (the DHCP-assigned address), used by every later task that talks to this host.

- [ ] **Step 1: Create the container**

Run on the Proxmox host (192.168.0.109):

```bash
pct create 113 local:vztmpl/debian-12-standard_12.12-1_amd64.tar.zst \
  --hostname agentos \
  --cores 2 \
  --memory 4096 \
  --rootfs local-lvm:20 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --features nesting=1,keyctl=1 \
  --unprivileged 1 \
  --onboot 1
```

Expected: `Formatting '...vm-113-disk-0.raw'...` then no error, prompt returns.

- [ ] **Step 2: Start it and capture the IP**

```bash
pct start 113
sleep 10
pct exec 113 -- ip -4 -o addr show eth0
```

Expected: a line like `2: eth0    inet 192.168.0.XXX/24 ...`. Record this as `LXC113_IP` — every later task's commands substitute it in place of `<LXC113_IP>`.

- [ ] **Step 3: Verify basic reachability**

```bash
ping -c 2 <LXC113_IP>
ssh root@<LXC113_IP> "cat /etc/os-release | head -2"
```

Expected: 2 replies, then `PRETTY_NAME="Debian GNU/Linux 12 (bookworm)"`.

---

### Task 2: Base OS setup on LXC 113

**Files:** none

**Interfaces:**
- Consumes: `LXC113_IP` from Task 1
- Produces: a Debian host on 113 with Docker installed and running

- [ ] **Step 1: Update and install base packages**

```bash
ssh root@<LXC113_IP> "apt-get update && apt-get -y upgrade && apt-get -y install curl git ca-certificates gnupg"
```

Expected: exits 0, no errors.

- [ ] **Step 2: Install Docker Engine**

```bash
ssh root@<LXC113_IP> "curl -fsSL https://get.docker.com | sh"
```

Expected: script completes with `Client: Docker Engine ... Server: Docker Engine ...` version output at the end, no error.

- [ ] **Step 3: Verify Docker works inside the LXC**

```bash
ssh root@<LXC113_IP> "docker run --rm hello-world"
```

Expected: output contains `Hello from Docker!`. If this fails with a cgroup/nesting error, re-check `features: nesting=1,keyctl=1` was applied (`pct config 113 | grep features` on the Proxmox host) and `pct reboot 113`, then retry.

---

### Task 3: Install Hermes Agent and configure providers

**Files:** none (lives under `~/.hermes` on LXC 113)

**Interfaces:**
- Consumes: `LXC113_IP` from Task 1, Nobara Ollama endpoint `http://192.168.0.100:11434`
- Produces: a working `hermes` CLI on LXC 113 with two providers configured (`ollama-local`, `deepseek`)

- [ ] **Step 1: Run the Hermes installer**

```bash
ssh root@<LXC113_IP> "curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash"
```

Expected: installer finishes with a message telling you to `source ~/.bashrc` or open a new shell.

- [ ] **Step 2: Confirm the CLI is on PATH**

```bash
ssh root@<LXC113_IP> "source ~/.bashrc && hermes --version"
```

Expected: prints a version string, e.g. `hermes-agent x.y.z`.

- [ ] **Step 3: Verify the Nobara Ollama endpoint is reachable from LXC 113**

```bash
ssh root@<LXC113_IP> "curl -s http://192.168.0.100:11434/api/tags"
```

Expected: JSON with a `models` array. If this fails, the Nobara PC is off or its Ollama service isn't bound to `0.0.0.0` — check `OLLAMA_HOST=0.0.0.0` is set on Nobara before continuing.

- [ ] **Step 4: Add the local Ollama endpoint as a Hermes provider**

```bash
ssh root@<LXC113_IP> "hermes config set providers.ollama-local.base_url http://192.168.0.100:11434/v1"
ssh root@<LXC113_IP> "hermes config set providers.ollama-local.type ollama"
```

Expected: no error output (Hermes config commands are silent on success).

- [ ] **Step 5: Add the DeepSeek fallback provider**

Get a DeepSeek API key from https://platform.deepseek.com (paste your own key below — do not commit it anywhere):

```bash
ssh root@<LXC113_IP> "echo 'DEEPSEEK_API_KEY=sk-your-key-here' >> ~/.hermes/.env"
```

- [ ] **Step 6: Set the failover order**

```bash
ssh root@<LXC113_IP> "hermes model --profile default --set-primary ollama-local:qwen3:8b --add-fallback deepseek:deepseek-chat"
```

Expected: Hermes confirms the active model chain. If the flags above don't match your installed Hermes version's exact CLI syntax, run `hermes model --help` on the host and use its interactive picker instead — same end state: `ollama-local` primary, `deepseek` fallback.

- [ ] **Step 7: Pull the local model on Nobara**

On the Nobara PC:

```bash
ollama pull qwen3:8b
```

Expected: download completes, `success` printed.

- [ ] **Step 8: End-to-end smoke test**

```bash
ssh root@<LXC113_IP> "hermes --profile default --message 'Reply with exactly: hermes online'"
```

Expected: response contains `hermes online`.

- [ ] **Step 9: Run the built-in health check**

```bash
ssh root@<LXC113_IP> "hermes doctor"
```

Expected: no errors reported (warnings about unconfigured optional features, like messaging platforms not yet set up, are fine at this point).

- [ ] **Step 10: Verify the DeepSeek failover actually triggers**

Temporarily point the primary provider at an unreachable address to simulate the Nobara PC being off, without needing to touch the Nobara machine itself:

```bash
ssh root@<LXC113_IP> "hermes config set providers.ollama-local.base_url http://192.168.0.100:1/v1"
ssh root@<LXC113_IP> "hermes --profile default --message 'Reply with exactly: fallback online'"
```

Expected: the request still succeeds (response contains `fallback online`), and the Hermes logs show it tried `ollama-local`, failed, and used `deepseek`:

```bash
ssh root@<LXC113_IP> "hermes logs --tail 20 | grep -i deepseek"
```

Expected: at least one line showing the `deepseek` provider handled the request.

Restore the real endpoint before moving on:

```bash
ssh root@<LXC113_IP> "hermes config set providers.ollama-local.base_url http://192.168.0.100:11434/v1"
```

---

### Task 4: Configure the Telegram gateway

**Files:** none

**Interfaces:**
- Consumes: Hermes install from Task 3
- Produces: a working Telegram bot wired to Hermes, DM-pairing enabled

- [ ] **Step 1: Create the bot**

In Telegram, message `@BotFather`: `/newbot`, follow the prompts (name it something distinct from the existing Form/DocuSeal bot, e.g. `YourNameAgentOS_bot`). Copy the token it returns.

- [ ] **Step 2: Store the token**

```bash
ssh root@<LXC113_IP> "echo 'TELEGRAM_BOT_TOKEN=your-token-here' >> ~/.hermes/.env"
```

- [ ] **Step 3: Enable DM pairing**

```bash
ssh root@<LXC113_IP> "hermes config set channels.telegram.dm_policy pairing"
```

Expected: no error.

- [ ] **Step 4: Start the gateway as a persistent service**

```bash
ssh root@<LXC113_IP> "hermes gateway --install-daemon"
ssh root@<LXC113_IP> "systemctl --user status hermes-gateway 2>/dev/null || hermes gateway status"
```

Expected: status shows the gateway running.

- [ ] **Step 5: Verify pairing from your phone**

Message your new bot anything from Telegram. Expected: bot replies with a short pairing code.

```bash
ssh root@<LXC113_IP> "hermes pairing approve <code-from-telegram>"
```

Then send another message. Expected: this time you get a real reply from Hermes (not a pairing code).

---

### Task 5: Harden Hermes tool permissions

**Files:** none

**Interfaces:**
- Consumes: Hermes install from Task 3

- [ ] **Step 1: Set file-modifying and shell tools to ask-first**

```bash
ssh root@<LXC113_IP> "hermes tools set bash --permission always_ask"
ssh root@<LXC113_IP> "hermes tools set write --permission always_ask"
ssh root@<LXC113_IP> "hermes tools set edit --permission always_ask"
```

Expected: no error output.

- [ ] **Step 2: Verify by triggering a tool call**

```bash
ssh root@<LXC113_IP> "hermes --profile default --message 'List the files in the current directory using your bash tool'"
```

Expected: Hermes's response indicates it is waiting for approval before running the command, rather than running it immediately. Approve or deny via whatever prompt the CLI/gateway surfaces, confirming the ask-first gate is active.

---

### Task 6: Deploy Odysseus

**Files:**
- Create: `compose/proxmox-lxc-113/odysseus/docker-compose.yml`
- Create: `compose/proxmox-lxc-113/odysseus/.env.example`

**Interfaces:**
- Consumes: Docker from Task 2, Ollama endpoint `http://192.168.0.100:11434`
- Produces: Odysseus reachable at `<LXC113_IP>:7000`

- [ ] **Step 1: Write the compose file**

```yaml
services:
  odysseus:
    image: ghcr.io/pewdiepie-archdaemon/odysseus:latest
    container_name: odysseus
    restart: unless-stopped
    ports:
      - "7000:7000"
    environment:
      TZ: Europe/Budapest
      OLLAMA_BASE_URL: http://192.168.0.100:11434
    volumes:
      - /srv/docker-data/odysseus:/data
```

- [ ] **Step 2: Write the env template**

```bash
# compose/proxmox-lxc-113/odysseus/.env.example
# No secrets required for the default local-model setup.
# Add API keys here only if you connect a cloud provider inside Odysseus itself.
```

- [ ] **Step 3: Commit the compose files**

```bash
git add compose/proxmox-lxc-113/odysseus/docker-compose.yml compose/proxmox-lxc-113/odysseus/.env.example
git commit -m "feat(odysseus): add compose file for LXC 113 agentos host"
```

- [ ] **Step 4: Deploy to LXC 113**

```bash
scp compose/proxmox-lxc-113/odysseus/docker-compose.yml root@<LXC113_IP>:/root/odysseus-compose.yml
ssh root@<LXC113_IP> "mkdir -p /srv/docker-data/odysseus && docker compose -f /root/odysseus-compose.yml up -d"
```

Expected: `Container odysseus  Started`.

- [ ] **Step 5: Verify it's up**

```bash
ssh root@<LXC113_IP> "curl -s -o /dev/null -w '%{http_code}\n' http://localhost:7000"
```

Expected: `200`.

- [ ] **Step 6: Get the first-run admin password**

```bash
ssh root@<LXC113_IP> "docker compose -f /root/odysseus-compose.yml logs odysseus | grep -i 'admin password'"
```

Expected: a line containing the generated password — save it somewhere safe (e.g. your password manager), not in git.

---

### Task 7: Reverse proxy Odysseus through Caddy

**Files:** none (live-edits the existing Caddyfile on LXC 110, consistent with how every other `*.lan` entry is managed today)

**Interfaces:**
- Consumes: `<LXC113_IP>` from Task 1, Odysseus running on port 7000 from Task 6

- [ ] **Step 1: Add the site block**

SSH into LXC 110 and add a new matcher inside the `(lan_services)` snippet, following the exact pattern of the existing entries (e.g. `@karakeep` / `@n8n`):

```
    @agentos host agentos.lan
    handle @agentos {
        reverse_proxy <LXC113_IP>:7000
    }
```

Insert this block anywhere before the closing `handle { respond 404 }` block of `(lan_services)` in `/etc/caddy/Caddyfile`.

- [ ] **Step 2: Validate and reload Caddy**

```bash
pct exec 110 -- caddy validate --config /etc/caddy/Caddyfile
pct exec 110 -- caddy reload --config /etc/caddy/Caddyfile
```

Expected: `Valid configuration` then reload with no errors.

- [ ] **Step 3: Verify from a LAN machine**

```bash
curl -sk -o /dev/null -w '%{http_code}\n' https://agentos.lan
```

Expected: `200`. (If your OS doesn't resolve `.lan` names, add `192.168.0.110 agentos.lan` to your `/etc/hosts`/`hosts` file first, matching however you access the other `*.lan` services today.)

- [ ] **Step 4: Update the host doc index**

Add one line to `docs/hosts/caddy.md`'s list of proxied services: `agentos.lan -> LXC 113 :7000 (Odysseus)`, matching the existing entries' format in that file.

```bash
git add docs/hosts/caddy.md
git commit -m "docs(caddy): add agentos.lan proxy entry"
```

---

### Task 8: Restrict SSH access from LXC 113 into LXC 109

**Files:**
- Create: `scripts/hermes-claude-code-wrapper.sh`

**Interfaces:**
- Consumes: `<LXC113_IP>`, existing `claude` CLI on LXC 109
- Produces: a forced-command SSH key pair that can only invoke the wrapper, nothing else

- [ ] **Step 1: Write the wrapper script**

```bash
#!/usr/bin/env bash
# scripts/hermes-claude-code-wrapper.sh
# Deployed to /usr/local/bin/hermes-claude-code.sh on LXC 109.
# Invoked ONLY via a forced-command SSH key - never run directly with
# untrusted arguments from an interactive shell.
set -euo pipefail

# SSH_ORIGINAL_COMMAND carries whatever the caller passed after the ssh
# command; we treat all of it as one opaque task string for `claude -p`.
TASK="${SSH_ORIGINAL_COMMAND:-}"
if [ -z "$TASK" ]; then
  echo "no task provided" >&2
  exit 1
fi

cd /root/homelab
claude -p "$TASK"
```

- [ ] **Step 2: Commit it**

```bash
git add scripts/hermes-claude-code-wrapper.sh
git commit -m "feat(agentos): add restricted Claude Code delegation wrapper for LXC 109"
```

- [ ] **Step 3: Deploy the wrapper to LXC 109**

```bash
scp scripts/hermes-claude-code-wrapper.sh root@192.168.0.204:/usr/local/bin/hermes-claude-code.sh
ssh root@192.168.0.204 "chmod 755 /usr/local/bin/hermes-claude-code.sh"
```

- [ ] **Step 4: Generate a dedicated key pair on LXC 113**

```bash
ssh root@<LXC113_IP> "ssh-keygen -t ed25519 -f /root/.ssh/hermes-to-109 -N '' -C 'hermes-agentos-to-claude-mgmt'"
ssh root@<LXC113_IP> "cat /root/.ssh/hermes-to-109.pub"
```

Expected: prints a public key starting with `ssh-ed25519`. Copy it for the next step.

- [ ] **Step 5: Install the key on LXC 109 with a forced command**

On LXC 109, append this line to `/root/.ssh/authorized_keys`, substituting the public key from Step 4:

```bash
echo 'command="/usr/local/bin/hermes-claude-code.sh",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ssh-ed25519 AAAA...your-key-here... hermes-agentos-to-claude-mgmt' >> /root/.ssh/authorized_keys
```

- [ ] **Step 6: Verify the restriction works**

From LXC 113, confirm a plain interactive shell is refused:

```bash
ssh -i /root/.ssh/hermes-to-109 root@192.168.0.204
```

Expected: the connection runs the wrapper (which will exit with `no task provided` since no command was passed) rather than dropping into a shell prompt — it must NOT show a `root@claude-mgmt:~#` prompt.

Then confirm a bounded task actually runs Claude Code:

```bash
ssh -i /root/.ssh/hermes-to-109 root@192.168.0.204 "Say the word banana and nothing else"
```

Expected: output is Claude Code's response containing "banana" — proving the forced command successfully invoked `claude -p` with the passed task, and nothing more.

---

### Task 9: Wire Hermes's SSH backend to the delegation channel

**Files:** none

**Interfaces:**
- Consumes: key pair from Task 8, Hermes install from Task 3

- [ ] **Step 1: Register the SSH backend**

```bash
ssh root@<LXC113_IP> "hermes config set backends.claude-mgmt.type ssh"
ssh root@<LXC113_IP> "hermes config set backends.claude-mgmt.host 192.168.0.204"
ssh root@<LXC113_IP> "hermes config set backends.claude-mgmt.user root"
ssh root@<LXC113_IP> "hermes config set backends.claude-mgmt.identity_file /root/.ssh/hermes-to-109"
```

Expected: no error output.

- [ ] **Step 2: End-to-end delegation test**

Send Hermes a message through Telegram asking it to delegate a real, bounded task, e.g.:

> "Use the claude-mgmt backend to fix a typo in docs/README.md if you can find one, otherwise just report there are none."

Expected: Hermes's reply confirms it ran the task via the `claude-mgmt` backend, and (if a typo existed) a corresponding commit appears in `git log` on LXC 109's homelab checkout.

---

### Task 10: Documentation

**Files:**
- Create: `docs/hosts/agentos.md`
- Modify: `docs/README.md`
- Modify: `mkdocs.yml`

**Interfaces:**
- Consumes: `<LXC113_IP>` and every credential/config decision from Tasks 1-9

- [ ] **Step 1: Write the host doc**

Follow the existing `docs/hosts/*.md` format (see `docs/hosts/karakeep.md` for the template: header with Date/Hostname/IP, then sections for what it runs and how it's managed):

```markdown
**Date:** 2026-07-06
**Hostname:** agentos
**IP address:** <LXC113_IP>

# Agentos (LXC 113)

Hermes Agent (native) + Odysseus (Docker Compose) - the background "agentic OS"
layer. Routine/background work runs against the Nobara Ollama endpoint first,
DeepSeek API second; actual coding/refactoring work is delegated over a
restricted SSH channel to Claude Code on LXC 109 (claude-mgmt).

## Services

- **Hermes Agent** - cron, memory, Telegram gateway (new dedicated bot, DM-pairing mode)
- **Odysseus** - web workspace UI, reverse-proxied at https://agentos.lan

## Model routing

1. Nobara Ollama (`http://192.168.0.100:11434`) - primary, free, local
2. DeepSeek API - fallback when Nobara is off
3. LXC 109 Claude Code (via forced-command SSH, `/usr/local/bin/hermes-claude-code.sh`) - deliberate delegation only, not part of the failover chain

## Security

- SSH key `hermes-to-109` (on this host) can only invoke the wrapper script on
  LXC 109 - no interactive shell, no other commands
- Telegram gateway uses DM-pairing - unknown senders get a pairing code, not a response
- `bash`/`write`/`edit` tools default to `always_ask`
```

- [ ] **Step 2: Add it to the doc index**

Add a line to `docs/README.md`'s host list, matching the existing format (see the `karakeep`/`n8n` entries):

```markdown
- [agentos](./hosts/agentos.md) - Hermes + Odysseus agentic OS layer (LXC 113)
```

- [ ] **Step 3: Add the nav entry**

In `mkdocs.yml`, add alongside the other `hosts/*.md` entries:

```yaml
          - Agentos (LXC 113): hosts/agentos.md
```

- [ ] **Step 4: Commit**

```bash
git add docs/hosts/agentos.md docs/README.md mkdocs.yml
git commit -m "docs(agentos): document Hermes+Odysseus host (LXC 113)"
```
