**Date:** 2026-03-14
**Hostname:** claude-mgmt (LXC 109)
**IP address:** 192.168.0.204

---

## Overview

This guide documents the setup of a public documentation portfolio site using MkDocs with the Material theme, deployed automatically to GitHub Pages via GitHub Actions, and served under a custom domain.

**Result:** All homelab docs are available at `https://docs.homelabor.net` - searchable, navigable, and linkable for job applications and LinkedIn posts.

**Why MkDocs + GitHub Pages instead of self-hosting:**
- Static HTML - no server-side code, no attack surface
- GitHub handles TLS, DDoS protection, and uptime
- No extra load on the VPS or homelab
- Free - no additional cost beyond the domain

---

## Prerequisites

- GitHub repository with docs in `docs/` subdirectory
- Domain managed via Cloudflare (homelabor.net)
- GitHub Pages enabled on the repository

---

## 1. Project Structure

MkDocs reads from the `docs/` directory and uses `mkdocs.yml` at the repo root.

```
homelab/
├── mkdocs.yml               # MkDocs configuration
├── docs/
│   ├── index.md             # Homepage (MkDocs entry point)
│   ├── CNAME                # Custom domain for GitHub Pages
│   ├── hosts/               # Per-host reference docs
│   ├── proxmox/             # Numbered setup guides
│   └── vps/                 # VPS and Pangolin docs
└── .github/
    └── workflows/
        └── deploy.yml       # GitHub Actions auto-deploy
```

Note: `docs/README.md` (the GitHub-facing docs index) coexists with `docs/index.md` (the MkDocs homepage). MkDocs uses `index.md` and excludes `README.md` automatically when both are present.

---

## 2. Local Testing (optional)

The build runs entirely in GitHub Actions - no local MkDocs installation is needed or kept on claude-mgmt. If you need to test a change locally before pushing:

```bash
apt install python3-pip -y
python3 -m pip install mkdocs-material --break-system-packages

cd /root/homelab
python3 -m mkdocs build
# Expected: "Documentation built in X seconds"
# site/ directory created (gitignored)

# Optional live preview
python3 -m mkdocs serve
# Opens at http://127.0.0.1:8000
```

Uninstall after testing to keep the LXC clean:

```bash
python3 -m pip uninstall mkdocs-material mkdocs --break-system-packages -y
rm -rf /root/homelab/site
```

---

## 3. mkdocs.yml Configuration

Key settings in `mkdocs.yml`:

```yaml
site_name: Norbert Csicsay - Homelab
site_description: Self-hosted infrastructure running 27 services on Proxmox VE.
site_author: Norbert Csicsay
site_url: https://docs.homelabor.net/
repo_url: https://github.com/Pironex9/homelab
repo_name: Pironex9/homelab

docs_dir: docs
theme:
  name: material
  palette:
    - scheme: default
      primary: indigo
      accent: indigo
      toggle:
        icon: material/weather-night
        name: Switch to dark mode
    - scheme: slate
      primary: indigo
      accent: indigo
      toggle:
        icon: material/weather-sunny
        name: Switch to light mode
  features:
    - navigation.tabs
    - navigation.sections
    - navigation.top
    - search.highlight
    - search.suggest
    - content.code.copy
  icon:
    repo: fontawesome/brands/github

extra_css:
  - stylesheets/extra.css

extra:
  social:
    - icon: fontawesome/brands/github
      link: https://github.com/Pironex9
    - icon: fontawesome/brands/linkedin
      link: https://www.linkedin.com/in/norbert-csicsay-497195334

nav:
  - Home: index.md
  - Hosts:
      - Docker Host (LXC 100): hosts/docker-host.md
      - Home Assistant (VM 101): hosts/haos.md
      - AdGuard Home (LXC 102): hosts/adguard.md
      - Komodo (LXC 105): hosts/komodo.md
      - Karakeep (LXC 106): hosts/karakeep.md
      - n8n (LXC 107): hosts/n8n.md
      - Ollama (LXC 108): hosts/ollama.md
      - Claude Code Mgmt (LXC 109): hosts/claude-mgmt.md
  - Setup Guides:
      - 01 - Proxmox + MergerFS + SnapRAID: proxmox/01_...md
      - 02 - Docker LXC Setup: proxmox/02_...md
      - ...
      - 22 - MkDocs Portfolio Site: proxmox/22_MkDocs_Portfolio_Site_Setup.md
  - VPS:
      - Hetzner VPS + Pangolin + Jellyfin: vps/Hetzner_VPS_...md

plugins:
  - search

markdown_extensions:
  - admonition
  - pymdownx.highlight:
      anchor_linenums: true
      line_spans: __span
      pygments_lang_class: true
  - pymdownx.inlinehilite
  - pymdownx.superfences
  - tables
  - toc:
      permalink: true
```

The `nav:` section explicitly maps all docs to human-readable titles. Any file not listed in `nav:` is excluded from the site.

---

## 4. Custom Domain Setup

### Cloudflare DNS

Add a CNAME record in the Cloudflare dashboard (homelabor.net - DNS):

```
Type:   CNAME
Name:   docs
Target: pironex9.github.io
Proxy:  DNS only (gray cloud)
TTL:    Auto
```

**Why DNS only (gray cloud):** GitHub Pages issues a Let's Encrypt certificate for the custom domain. If Cloudflare proxies the traffic (orange cloud), GitHub cannot complete the ACME challenge and the certificate request fails.

### docs/CNAME File

MkDocs copies `docs/CNAME` into the built `site/` directory. GitHub Pages reads this file from the `gh-pages` branch (or Pages artifact) to know which custom domain to serve.

```
docs.homelabor.net
```

### GitHub Repository Settings

`github.com/Pironex9/homelab` - Settings - Pages:

```
Source:        GitHub Actions
Custom domain: docs.homelabor.net
Enforce HTTPS: ON (enabled once GitHub issues the certificate)
```

Wait 5-10 minutes after adding the Cloudflare CNAME for GitHub to verify the domain and issue the SSL certificate.

---

## 5. GitHub Actions Workflow

`.github/workflows/deploy.yml` triggers on every push to `main`:

```yaml
on:
  push:
    branches:
      - main
  workflow_dispatch:   # also allows manual trigger from GitHub UI
```

The workflow has two jobs:

**build** - installs MkDocs Material, builds the site, uploads artifact
**deploy** - takes the artifact and deploys to GitHub Pages

Required permissions (set at workflow level):

```yaml
permissions:
  contents: read
  pages: write
  id-token: write
```

No secrets or tokens needed - GitHub automatically provides the `GITHUB_TOKEN` for Pages deployment via the `id-token: write` permission.

---

## 6. Adding New Docs

To add a new guide to the site:

1. Create the file in the appropriate directory (e.g. `docs/proxmox/23_New_Guide.md`)
2. Add it to the `nav:` section in `mkdocs.yml`:

```yaml
- Setup Guides:
    - 23 - New Guide Title: proxmox/23_New_Guide.md
```

3. Commit and push - GitHub Actions builds and deploys automatically within ~1-2 minutes

---

## 7. Deployment Flow

```
Push to main branch
    |
    v
GitHub Actions - build job
    |- checkout repo
    |- install python + mkdocs-material
    |- mkdocs build  -->  site/ directory
    |- upload as Pages artifact
    |
    v
GitHub Actions - deploy job
    |- deploy artifact to GitHub Pages
    |
    v
docs.homelabor.net (live within ~1-2 minutes)
```

---

## 8. Maintenance

**Updating docs:** edit Markdown files, push to main - site rebuilds automatically.

**Checking deploy status:** GitHub repo - Actions tab - "Deploy MkDocs to GitHub Pages" workflow.

**Local test before push:**

```bash
python3 -m mkdocs build
# Check for any warnings about broken links or missing files
```

**MkDocs Material updates:**

```bash
python3 -m pip install --upgrade mkdocs-material --break-system-packages
```

The GitHub Actions workflow always installs the latest version of `mkdocs-material` on each run, so the live site is always built with the latest version.

---

## Troubleshooting

**Custom domain resets to empty after deploy:**
- The `docs/CNAME` file is missing or not being included in the build. Verify it exists in `docs/CNAME` (not the repo root).

**Enforce HTTPS unavailable in GitHub Pages settings:**
- Cloudflare is set to orange cloud (proxied). Switch to gray cloud (DNS only) and wait 5-10 minutes.

**Build fails in GitHub Actions:**
- Check the Actions tab for the error. Common cause: a file listed in `nav:` does not exist, or a YAML syntax error in `mkdocs.yml`.

**Site shows 404 after deploy:**
- Wait 2-3 minutes for GitHub Pages CDN propagation.
- Verify the custom domain DNS record points to `pironex9.github.io`.
