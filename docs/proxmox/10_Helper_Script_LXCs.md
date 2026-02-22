# Helper Script LXC Services

**Date:** 2026-02-20
**System:** Proxmox VE 9.1

All LXCs in this document were installed using [Proxmox VE Helper Scripts](https://community-scripts.github.io/ProxmoxVE/).

---

## LXC 105 - Komodo Core

### What it does
A self-hosted Docker management platform used to manage, deploy, and monitor all Docker Compose stacks running in LXC 100. Replaced Dockge (deprecated). Full setup documented in Doc 17.

### Installation

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/community-scripts/ProxmoxVE/main/ct/komodo-core.sh)"
```

### Details

- **Port:** 9120
- **LXC ID:** 105
- **IP:** 192.168.0.105
- **See also:** [17_Komodo_complete_setup.md](17_Komodo_complete_setup.md)

---

## LXC 106 - Karakeep

### What it does
A self-hostable bookmark manager that saves links, notes, and images with AI-based automatic tagging and full-text search. Self-hosted alternative to read-it-later services like Pocket or Instapaper.

AI tagging uses the **Nobara PC Ollama** (GPU, 192.168.0.100:11434) - requires Nobara to be on. See Doc 13 for setup details.

### Installation

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/community-scripts/ProxmoxVE/main/ct/karakeep.sh)"
```

### Details

- **Port:** 3000
- **LXC ID:** 106

---

## LXC 107 - n8n

### What it does
A workflow automation platform for building automated pipelines connecting apps and services. Used here primarily with Ollama (LXC 108) for AI-assisted automation tasks.

### Installation

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/community-scripts/ProxmoxVE/main/ct/n8n.sh)"
```

### Details

- **Port:** 5678
- **LXC ID:** 107

---

## LXC 108 - Ollama

### What it does
Runs open-source large language models locally. This instance is always-on, CPU-based, and handles light inference tasks - primarily integrated with n8n for automation workflows.

For GPU-accelerated inference, a separate Ollama instance runs on the Nobara desktop (not 24/7).

### Installation

```bash
bash -c "$(curl -fsSL https://raw.githubusercontent.com/community-scripts/ProxmoxVE/main/ct/ollama.sh)"
```

### Details

- **Port:** 11434
- **LXC ID:** 108
- **OLLAMA_HOST:** set to `0.0.0.0` to allow access from other LXCs (e.g. n8n)
