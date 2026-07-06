# Hermes + Odysseus Agentic OS Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a background "agentic OS" layer (Hermes + Odysseus) on a new dedicated LXC, wired to a local Ollama model on the Nobara GPU box, a DeepSeek fallback, and a security-scoped SSH channel into LXC 109 for delegated Claude Code work.

**Architecture:** New LXC 113 hosts Hermes (native install) and Odysseus (its own upstream Docker Compose checkout). Both point their model provider at the Nobara Ollama endpoint first, DeepSeek API second. Hermes reaches LXC 109 through a dedicated SSH key restricted by a forced command and source-address lock, invoking a bounded wrapper that runs Claude Code under a deliberately reduced permission set. Odysseus is reverse-proxied through the existing Caddy instance as `agentos.lan`.

**Tech Stack:** Proxmox LXC (Debian 12), Docker + Docker Compose, Hermes Agent (Python/uv installer), Odysseus (upstream Docker Compose web app), Caddy (existing), Ollama (existing, Nobara + LXC 108), DeepSeek API.

## Global Constraints

- LXC 113: Debian 12 (`debian-12-standard_12.12-1_amd64.tar.zst`), 2 cores, 4096MB RAM, 20GB disk on `local-lvm`, unprivileged, `features: nesting=1,keyctl=1` (required for Docker-in-LXC, matching the Komodo LXC 105 pattern), bridge `vmbr0`, DHCP.
- Nobara Ollama endpoint: `http://192.168.0.100:11434` (existing, already used by Karakeep).
- DeepSeek provider: `DEEPSEEK_API_KEY` env var, model `deepseek-v4-flash`.
- No public/Pangolin exposure anywhere in this plan - LAN + Tailscale only.
- Never commit real secrets (Telegram bot token, DeepSeek API key) to git - only `.env.example` placeholders.
- Every reverse-proxied `*.lan` host follows the existing Caddyfile snippet pattern on LXC 110 (`@name host name.lan` / `handle @name { reverse_proxy IP:PORT }` inside the `lan_services` snippet).
- Real credentials (Telegram bot token, DeepSeek API key, the LXC 113→109 SSH key) are obtained/generated during execution - they cannot be known in advance, so steps that need them say exactly where to get them and what to do with them.

---

## File Structure

- Create: `scripts/hermes-claude-code-wrapper.sh` - version-controlled copy of the forced-command wrapper deployed to LXC 109
- Create: `scripts/hermes-delegate-settings.json` - version-controlled copy of the restricted Claude Code permission settings used by the wrapper
- Create: `docs/hosts/agentos.md` - per-host reference doc for LXC 113, matching the existing `docs/hosts/*.md` pattern
- Modify: `docs/README.md` - add the new host doc to the index
- Modify: `mkdocs.yml` - add nav entry for `hosts/agentos.md`
- Modify: `docs/hosts/caddy.md` - add the new `agentos.lan` proxy entry

Odysseus is not repo-tracked: it ships its own multi-service Docker Compose file (and a Dockerfile-based build, not a pre-built image) directly from its upstream repository, so it is cloned and run straight from that checkout on LXC 113 rather than duplicated into `compose/`. Everything else (LXC provisioning, package installs, Hermes config, Caddy edits) lives on the Proxmox host / LXC 113 / LXC 109 / Nobara and is not git-tracked, consistent with how LXC 105/106/107/110 are managed today.

---

### Task 1: Provision LXC 113

**Files:** none (Proxmox host only)

**Interfaces:**
- Produces: `LXC113_IP` (the DHCP-assigned address), used by every later task that talks to this host.

- [ ] **Step 1: Confirm there's enough disk space**

```bash
pvesm status | grep local-lvm
```

Expected: the `Available` column shows at least ~20GB free (as of this plan being written, deleting the unused Minecraft LXC 112 brought this to ~24.4GB). If it's lower, free up space before continuing - don't shrink the requested rootfs below 20GB to work around it.

- [ ] **Step 2: Create the container**

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

- [ ] **Step 3: Start it and capture the IP**

```bash
pct start 113
sleep 10
pct exec 113 -- ip -4 -o addr show eth0
```

Expected: a line like `2: eth0    inet 192.168.0.XXX/24 ...`. Record this as `LXC113_IP` - every later task's commands substitute it in place of `<LXC113_IP>`.

- [ ] **Step 4: Authorize root SSH access**

Every other LXC in this homelab accepts passwordless root SSH from the key already in use on this host (LXC 109). New containers don't get it automatically - install it explicitly before any later step tries `ssh root@<LXC113_IP>`:

```bash
pct exec 113 -- bash -c "mkdir -p /root/.ssh && chmod 700 /root/.ssh"
pct exec 113 -- bash -c "cat >> /root/.ssh/authorized_keys" < ~/.ssh/id_ed25519.pub
pct exec 113 -- chmod 600 /root/.ssh/authorized_keys
```

- [ ] **Step 5: Verify reachability**

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
- Produces: a working `hermes` CLI on LXC 113 with a custom-endpoint primary model and a DeepSeek fallback

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

- [ ] **Step 3: Pull the local model on Nobara**

On the Nobara PC:

```bash
ollama pull qwen3:8b
```

Expected: download completes, `success` printed. (Optionally also pull the heavier MoE model for harder local tasks, per the design spec: `ollama pull qwen3.6:35b-a3b` if your Ollama build has it available - this one is a stretch goal, not required for the acceptance criteria below.)

- [ ] **Step 4: Verify the Nobara Ollama endpoint is reachable from LXC 113**

```bash
ssh root@<LXC113_IP> "curl -s http://192.168.0.100:11434/api/tags"
```

Expected: JSON with a `models` array containing `qwen3:8b`. If this fails, the Nobara PC is off or its Ollama service isn't bound to `0.0.0.0` - check `OLLAMA_HOST=0.0.0.0` is set on Nobara before continuing.

- [ ] **Step 5: Add the Nobara endpoint as the primary model (interactive)**

Hermes's provider/model setup is an interactive wizard, not a scriptable flag - it needs a real terminal, so use `ssh -t`:

```bash
ssh -t root@<LXC113_IP> hermes model
```

At the prompts:
- Choose **Custom endpoint**
- Base URL: `http://192.168.0.100:11434/v1`
- Model name: `qwen3:8b`
- Context length: `32768` if asked (accept the wizard's suggestion if it proposes one instead)
- Give it a recognizable name when asked, e.g. `nobara-ollama`

This writes a `model:` block and a `custom_providers:` entry to `~/.hermes/config.yaml` and makes it the active model.

- [ ] **Step 6: Add the DeepSeek API key**

Get a key from https://platform.deepseek.com (paste your own key below - do not commit it anywhere):

```bash
ssh root@<LXC113_IP> "echo 'DEEPSEEK_API_KEY=sk-your-key-here' >> ~/.hermes/.env"
```

- [ ] **Step 7: Add DeepSeek to the fallback chain (interactive)**

```bash
ssh -t root@<LXC113_IP> hermes fallback add
```

At the prompts: choose the DeepSeek provider (it should pick up `DEEPSEEK_API_KEY` from `.env` automatically), then pick the `deepseek-v4-flash` model.

- [ ] **Step 8: Confirm the fallback chain**

```bash
ssh root@<LXC113_IP> "hermes fallback list"
```

Expected: shows `deepseek-v4-flash` (or equivalent DeepSeek entry) as a configured fallback, with the Nobara custom endpoint as the primary model.

- [ ] **Step 9: End-to-end smoke test**

```bash
ssh root@<LXC113_IP> "hermes chat -q 'Reply with exactly: hermes online'"
```

Expected: response contains `hermes online`.

- [ ] **Step 10: Run the built-in health check**

```bash
ssh root@<LXC113_IP> "hermes doctor"
```

Expected: no errors reported (warnings about unconfigured optional features, like messaging platforms not yet set up, are fine at this point).

- [ ] **Step 11: Verify the DeepSeek fallback actually triggers**

The real test is turning off Ollama on the Nobara PC and confirming Hermes still answers via DeepSeek. Do this once, deliberately:

On the Nobara PC, stop the Ollama service (e.g. quit the Ollama app, or `sudo systemctl stop ollama` if it runs as a systemd service), then:

```bash
ssh root@<LXC113_IP> "hermes chat -q 'Reply with exactly: fallback online'"
```

Expected: the request still succeeds (response contains `fallback online`) even though the primary endpoint is down, and the logs confirm which provider actually served it:

```bash
ssh root@<LXC113_IP> "hermes logs --tail 20 | grep -i deepseek"
```

Expected: at least one line showing the DeepSeek provider handled the request. Restart Ollama on Nobara afterwards.

If you can't access the Nobara PC directly at plan-execution time, a same-effect simulation (without needing to touch Nobara) is to temporarily point the custom endpoint at an unreachable port and repeat the same two commands, restoring the real URL via `ssh -t root@<LXC113_IP> hermes model` afterwards - but treat this as a stand-in for the real outage test above, not a replacement for it.

---

### Task 4: Configure the Telegram gateway

**Files:** none

**Interfaces:**
- Consumes: Hermes install from Task 3
- Produces: a working Telegram bot wired to Hermes, DM-pairing enabled

- [ ] **Step 1: Create the bot**

In Telegram, message `@BotFather`: `/newbot`, follow the prompts (name it something distinct from the existing Form/DocuSeal bot, e.g. `YourNameAgentOS_bot`). Copy the token it returns.

- [ ] **Step 2: Run the messaging setup wizard (interactive)**

```bash
ssh -t root@<LXC113_IP> "hermes gateway setup"
```

Choose Telegram, paste the bot token from Step 1, and accept the pairing/allowlist mode when asked (pick the pairing-code option, not open access) - the wizard is the documented way to configure a channel and its access policy, rather than hand-editing config keys.

- [ ] **Step 3: Install and start the gateway as a persistent service**

```bash
ssh root@<LXC113_IP> "hermes gateway install"
ssh root@<LXC113_IP> "hermes gateway start"
ssh root@<LXC113_IP> "hermes gateway status"
```

Expected: status shows the gateway running.

- [ ] **Step 4: Verify pairing from your phone**

Message your new bot anything from Telegram. Expected: bot replies with a short pairing code.

```bash
ssh root@<LXC113_IP> "hermes pairing list"
ssh root@<LXC113_IP> "hermes pairing approve telegram <code-from-telegram>"
```

Then send another message. Expected: this time you get a real reply from Hermes (not a pairing code).

---

### Task 5: Harden Hermes tool permissions

**Files:** none

**Interfaces:**
- Consumes: Hermes install from Task 3

- [ ] **Step 1: Open the interactive tool configuration UI**

`hermes tools` has no scriptable flags for per-tool permission - it's an interactive picker, so run it with a real terminal:

```bash
ssh -t root@<LXC113_IP> hermes tools
```

In the UI, set the bash/shell tool and the file-write/edit tools to their ask-first/confirm mode (rather than always-allow). Leave read-only tools (file read, search) on allow. Exit and save when done.

- [ ] **Step 2: Confirm the summary reflects this**

```bash
ssh root@<LXC113_IP> "hermes tools --summary"
```

Expected: the bash and write/edit-equivalent tools are listed as ask-first/confirm, not auto-allow.

- [ ] **Step 3: Verify by triggering a tool call**

```bash
ssh root@<LXC113_IP> "hermes chat -q 'List the files in the current directory using your shell tool'"
```

Expected: Hermes's response indicates it is waiting for approval before running the command, rather than running it immediately.

---

### Task 6: Deploy Odysseus

**Files:** none (Odysseus is cloned and run from its own upstream repo directly on LXC 113 - see File Structure above for why it isn't duplicated into this repo)

**Interfaces:**
- Consumes: Docker from Task 2, Ollama endpoint `http://192.168.0.100:11434`
- Produces: Odysseus reachable at `<LXC113_IP>:7000`

- [ ] **Step 1: Clone and configure**

```bash
ssh root@<LXC113_IP> "git clone https://github.com/pewdiepie-archdaemon/odysseus.git /opt/odysseus"
ssh root@<LXC113_IP> "cd /opt/odysseus && cp .env.example .env"
```

- [ ] **Step 2: Point it at the Nobara Ollama endpoint**

Odysseus discovers local models the same way the Ollama-connected apps in this homelab already do (Karakeep points at the same endpoint) - add the URL to its `.env`:

```bash
ssh root@<LXC113_IP> "echo 'OLLAMA_BASE_URL=http://192.168.0.100:11434' >> /opt/odysseus/.env"
```

- [ ] **Step 3: Build and start it**

```bash
ssh root@<LXC113_IP> "cd /opt/odysseus && docker compose up -d --build"
```

Expected: build completes and all services in Odysseus's compose file report `Started` (this includes any bundled services it ships alongside its main container, not just one).

- [ ] **Step 4: Verify it's up**

```bash
ssh root@<LXC113_IP> "curl -s -o /dev/null -w '%{http_code}\n' http://localhost:7000"
```

Expected: `200`.

- [ ] **Step 5: Get the first-run admin password and confirm login works**

```bash
ssh root@<LXC113_IP> "cd /opt/odysseus && docker compose logs odysseus | grep -i 'admin password'"
```

Expected: a line containing the generated password. Save it in your password manager (not in git), then actually log in at `http://<LXC113_IP>:7000` with it and confirm you land on the authenticated home screen - a `200` on the login page alone doesn't prove the account works.

---

### Task 7: Reverse proxy Odysseus through Caddy

**Files:**
- Modify: `docs/hosts/caddy.md`

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

- [ ] **Step 4: Update the host doc index and commit**

Add one line to `docs/hosts/caddy.md`'s list of proxied services: `agentos.lan -> LXC 113 :7000 (Odysseus)`, matching the existing entries' format in that file.

```bash
git add docs/hosts/caddy.md
git commit -m "docs(caddy): add agentos.lan proxy entry"
```

---

### Task 8: Restrict SSH access from LXC 113 into LXC 109

**Files:**
- Create: `scripts/hermes-claude-code-wrapper.sh`
- Create: `scripts/hermes-delegate-settings.json`

**Interfaces:**
- Consumes: `<LXC113_IP>`, existing `claude` CLI on LXC 109
- Produces: a forced-command, source-locked SSH key pair that can only invoke the wrapper, which itself runs Claude Code under a reduced permission set

This is the security-critical task. Three layers, not one: (1) the SSH key can only run one fixed command and only from LXC 113's own IP, (2) that command caps the task size and logs every invocation, (3) the Claude Code invocation itself runs with a restricted tool permission set rather than its normal full access - a compromised or manipulated Hermes can still only ask Claude Code to do bounded, logged work with fewer tools, not get an open shell or full unrestricted Claude Code on LXC 109.

- [ ] **Step 1: Write the restricted permission settings**

```json
{
  "permissions": {
    "allow": ["Read", "Grep", "Glob"],
    "ask": ["Edit", "Write"],
    "deny": ["Bash", "WebFetch", "WebSearch"]
  }
}
```

Save as `scripts/hermes-delegate-settings.json`. This is intentionally read-mostly - it lets a delegated task inspect and propose edits, but not run shell commands or reach the network. Loosen it later, deliberately, only for specific delegation use cases you've thought through - don't start from the full permission set Claude Code normally has interactively on this host.

- [ ] **Step 2: Write the wrapper script**

```bash
#!/usr/bin/env bash
# scripts/hermes-claude-code-wrapper.sh
# Deployed to /usr/local/bin/hermes-claude-code.sh on LXC 109.
# Invoked ONLY via a forced-command, source-IP-locked SSH key - never run
# directly with untrusted arguments from an interactive shell.
set -euo pipefail

LOG_FILE="/var/log/hermes-delegate.log"
MAX_TASK_LEN=2000

# SSH_ORIGINAL_COMMAND carries whatever the caller passed after the ssh
# command; we treat all of it as one opaque task string for `claude -p`.
TASK="${SSH_ORIGINAL_COMMAND:-}"

if [ -z "$TASK" ]; then
  echo "no task provided" >&2
  exit 1
fi

if [ "${#TASK}" -gt "$MAX_TASK_LEN" ]; then
  echo "task too long (max ${MAX_TASK_LEN} chars)" >&2
  exit 1
fi

echo "$(date -u +%FT%TZ) from=${SSH_CLIENT%% *} task=${TASK}" >> "$LOG_FILE"

cd /root/homelab
claude -p "$TASK" --settings /usr/local/etc/hermes-delegate-settings.json
```

- [ ] **Step 3: Commit both files**

```bash
git add scripts/hermes-claude-code-wrapper.sh scripts/hermes-delegate-settings.json
git commit -m "feat(agentos): add restricted Claude Code delegation wrapper for LXC 109"
```

- [ ] **Step 4: Deploy both files to LXC 109**

```bash
scp scripts/hermes-claude-code-wrapper.sh root@192.168.0.204:/usr/local/bin/hermes-claude-code.sh
scp scripts/hermes-delegate-settings.json root@192.168.0.204:/usr/local/etc/hermes-delegate-settings.json
ssh root@192.168.0.204 "chmod 755 /usr/local/bin/hermes-claude-code.sh && touch /var/log/hermes-delegate.log && chmod 600 /var/log/hermes-delegate.log"
```

- [ ] **Step 5: Generate a dedicated key pair on LXC 113**

```bash
ssh root@<LXC113_IP> "ssh-keygen -t ed25519 -f /root/.ssh/hermes-to-109 -N '' -C 'hermes-agentos-to-claude-mgmt'"
ssh root@<LXC113_IP> "cat /root/.ssh/hermes-to-109.pub"
```

Expected: prints a public key starting with `ssh-ed25519`. Copy it for the next step.

- [ ] **Step 6: Install the key on LXC 109 with a forced command and source-address lock**

On LXC 109, append this line to `/root/.ssh/authorized_keys`, substituting the public key from Step 5 and `<LXC113_IP>`:

```bash
echo 'from="<LXC113_IP>",command="/usr/local/bin/hermes-claude-code.sh",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty ssh-ed25519 AAAA...your-key-here... hermes-agentos-to-claude-mgmt' >> /root/.ssh/authorized_keys
```

The `from="<LXC113_IP>"` clause means this key is refused outright from any other source address, even if the private key is ever copied elsewhere.

- [ ] **Step 7: Verify the restriction works**

From LXC 113, confirm a plain interactive shell is refused:

```bash
ssh -i /root/.ssh/hermes-to-109 root@192.168.0.204
```

Expected: the connection runs the wrapper (which will exit with `no task provided` since no command was passed) rather than dropping into a shell prompt - it must NOT show a `root@claude-mgmt:~#` prompt.

Then confirm a bounded task actually runs Claude Code, and that it's actually restricted:

```bash
ssh -i /root/.ssh/hermes-to-109 root@192.168.0.204 "Say the word banana and nothing else"
ssh -i /root/.ssh/hermes-to-109 root@192.168.0.204 "Run 'whoami' using your shell tool"
```

Expected: the first prints a response containing "banana". The second should show Claude Code declining or asking for approval to use a shell tool, since `Bash` is denied in the delegate settings - if it just runs `whoami` without any pushback, the `--settings` flag isn't being picked up and needs debugging before continuing.

- [ ] **Step 8: Confirm the source-address lock actually blocks other hosts**

From a different host that also holds the operator's normal SSH key but not this restricted one (e.g. attempt from the Proxmox host itself using the same private key copied there temporarily, or just check the log):

```bash
ssh root@192.168.0.204 "tail -5 /var/log/hermes-delegate.log"
```

Expected: shows the two test invocations from Step 7 with `from=<LXC113_IP>`. If you want to fully verify the address lock, temporarily copy `hermes-to-109` to any other host on the LAN and confirm the connection is refused - then delete that copy.

---

### Task 9: Wire Hermes's SSH backend to the delegation channel

**Files:** none

**Interfaces:**
- Consumes: key pair from Task 8, Hermes install from Task 3

- [ ] **Step 1: Register the SSH backend (interactive)**

Hermes's backend configuration (like its provider configuration) goes through its setup wizard rather than raw `config set` keys whose exact schema isn't guessed here - check the current backend/terminal-target documentation on the host itself before wiring this up, since it may be named "terminal backend," "SSH executor," or similar depending on the installed version:

```bash
ssh root@<LXC113_IP> "hermes --help | grep -i -E 'backend|terminal|ssh'"
```

Follow whatever subcommand that surfaces (e.g. `hermes backends add` or equivalent) and supply: host `192.168.0.204`, user `root`, identity file `/root/.ssh/hermes-to-109`, a name like `claude-mgmt`.

- [ ] **Step 2: Confirm the backend is registered**

```bash
ssh root@<LXC113_IP> "hermes config show | grep -A5 claude-mgmt"
```

Expected: shows the host, user, and identity file recorded in the previous step.

- [ ] **Step 3: End-to-end delegation test with independent verification**

Send Hermes a message through Telegram asking it to delegate a real, bounded task that leaves independently-checkable evidence, e.g.:

> "Use the claude-mgmt backend to create a file at /tmp/hermes-delegation-test.txt on that host containing the current UTC timestamp."

Don't rely on Hermes's own chat reply as proof - independently confirm on LXC 109 itself, using your normal (non-restricted) SSH access:

```bash
ssh root@192.168.0.204 "cat /tmp/hermes-delegation-test.txt"
ssh root@192.168.0.204 "tail -3 /var/log/hermes-delegate.log"
```

Expected: the file exists with a recent timestamp, and the delegate log shows the matching invocation - proving the task actually executed via the restricted channel rather than Hermes just claiming it did.

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

Hermes Agent (native) + Odysseus (upstream Docker Compose checkout) - the
background "agentic OS" layer. Routine/background work runs against the
Nobara Ollama endpoint first, DeepSeek API second; actual coding/refactoring
work is delegated over a restricted SSH channel to a permission-reduced
Claude Code invocation on LXC 109 (claude-mgmt).

## Services

- **Hermes Agent** - cron, memory, Telegram gateway (new dedicated bot, DM-pairing mode)
- **Odysseus** - web workspace UI at `/opt/odysseus`, reverse-proxied at https://agentos.lan

## Model routing

1. Nobara Ollama (`http://192.168.0.100:11434`, model `qwen3:8b`) - primary, free, local
2. DeepSeek API (`deepseek-v4-flash`) - fallback when Nobara is off
3. LXC 109 Claude Code (via restricted SSH, `/usr/local/bin/hermes-claude-code.sh`) - deliberate delegation only, not part of the failover chain

## Security

- SSH key `hermes-to-109` (on this host) can only invoke the wrapper script on
  LXC 109, only from this host's IP (`from=` lock in `authorized_keys`) - no
  interactive shell, no other commands
- The wrapper caps task length, logs every invocation to
  `/var/log/hermes-delegate.log` on LXC 109, and runs Claude Code with
  `scripts/hermes-delegate-settings.json` (Bash/WebFetch/WebSearch denied,
  Edit/Write ask-first, Read/Grep/Glob allowed) instead of its normal
  interactive permission set
- Telegram gateway uses DM-pairing - unknown senders get a pairing code, not a response
- Hermes's shell and file-write/edit tools default to ask-first
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
