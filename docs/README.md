# Documentation

## hosts/

Per-host reference documentation - current configuration, running services, and lessons learned for each VM and LXC container.

- [docker-host](./hosts/docker-host.md) - Primary Docker host (LXC 100) - 18 stacks, GPU passthrough, Komodo integration
- [haos](./hosts/haos.md) - Home Assistant OS VM (VM 101) - Zigbee2MQTT, MQTT, REST API
- [adguard](./hosts/adguard.md) - AdGuard Home (LXC 102) - DNS, blocklists, Quad9 DoH/DoT
- [komodo](./hosts/komodo.md) - Komodo (LXC 105) - GitOps deployment management, Periphery agents
- [karakeep](./hosts/karakeep.md) - Karakeep (LXC 106) - bookmarking, AI tagging with local Ollama
- [n8n](./hosts/n8n.md) - n8n (LXC 107) - workflow automation, Claude Code MCP integration
- [claude-mgmt](./hosts/claude-mgmt.md) - Claude Code management node (LXC 109) - tmux persistent session, code-server (Tailscale-only), GitHub/n8n MCP
- [nobara](./hosts/nobara.md) - Desktop PC - NVIDIA RTX 2060, Ollama GPU node, NFS/SSHFS client
- [winpc](./hosts/winpc.md) - Windows 11 side of the Nobara dual-boot - in-box OpenSSH, key distribution, the traps that fail silently
- [caddy](./hosts/caddy.md) - Caddy reverse proxy (LXC 110) - HTTPS for all .lan services, mkcert local CA
- [kan](./hosts/kan.md) - Kan kanban board (Docker stack on LXC 100) - self-hosted Trello alternative, PostgreSQL
- [agentos](./hosts/agentos.md) - Hermes + Odysseus agentic OS layer (LXC 113) - local Ollama primary, DeepSeek fallback, restricted Claude Code delegation
- [k3s-cluster](./hosts/k3s-cluster.md) - K3s cluster (3x Dell OptiPlex) - Kubernetes, Longhorn, Ansible-managed config layer, GitOps version upgrades via system-upgrade-controller, WoL, Tailscale access
- [vps](./hosts/vps.md) - Hetzner VPS (CX23) - Pangolin reverse proxy, Komodo managed via Tailscale

### Retired

- [raspberry-pi](./hosts/raspberry-pi.md) - Raspberry Pi 4 (retired, Aug 2024 - Dec 2025) - origin homelab, 20+ Docker services
- [ollama](./hosts/ollama.md) - Ollama (LXC 108, decommissioned Jul 2026) - unused, local LLM inference had no callers, freed thin pool space

## proxmox/

Chronological setup guides - how the homelab was built, step by step.

- [01 - Proxmox VE 9.1 MergerFS + SnapRAID Installation](./proxmox/01_Proxmox_VE_9.1_MergerFS_SnapRAID_Installation_Documentation.md) - Initial Proxmox setup, MergerFS + SnapRAID storage
- [02 - Proxmox Docker LXC Setup](./proxmox/02_Proxmox_Docker_LXC_Setup_-_Detailed_Process.md) - LXC creation and Docker installation
- [03 - USB HDD Integration + SnapRAID Sync](./proxmox/03_USB_HDD_Integration_SnapRAID_Sync_and_Media_Structure_Fix.md) - USB HDD integration and SnapRAID sync
- [04 - Home Assistant OS VM + Zigbee2MQTT](./proxmox/04_Home_Assistant_OS_VM_Zigbee2MQTT_Backup_Strategy_Setup.md) - Home Assistant VM, Zigbee2MQTT, backup strategy
- [05 - AdGuard Home + Tailscale DNS](./proxmox/05_AdGuard_Home_Setup_Dedicated_LXC_Tailscale_DNS_Integration.md) - AdGuard Home + Tailscale DNS
- [06 - Immich Photo Management](./proxmox/06_Immich_Setup_Full_Installation_Guide.md) - Immich photo management
- [07 - Scrutiny Disk Health Monitoring](./proxmox/07_Scrutiny_Disk_Health_Monitoring_Setup_Guide.md) - Scrutiny disk health monitoring
- [08 - Netdata System Monitoring](./proxmox/08_Netdata_System_Monitoring_Setup_Guide.md) - Netdata system metrics
- [09 - Vaultwarden](./proxmox/09_Vaultwarden.md) - Vaultwarden password manager
- [10 - Helper Script LXCs](./proxmox/10_Helper_Script_LXCs.md) - Karakeep, n8n, Ollama via Proxmox helper scripts
- [11 - Jellyfin Hardware Transcoding](./proxmox/11_Jellyfin_Hardware_Transcoding_Setup.md) - Jellyfin GPU hardware transcoding
- [12 - Karakeep AI Tagging with Ollama](./proxmox/12_Karakeep_AI_Tagging_with_Ollama_Setup_Documentation.md) - Karakeep AI tagging with Ollama
- [13 - USB Disk Unmount Problem Resolution](./proxmox/13_USB_Disk_Unmount_Problem_Resolution_disk4_ADATA_HD710_PRO.md) - USB disk troubleshooting
- [14 - NFS Setup](./proxmox/14_NFS-Setup_Documentation.md) - NFS share configuration, plus the Windows SMB client
- [15 - Backup System](./proxmox/15_Proxmox_Backup_System_Documentation.md) - Backup system and schedules
- [16 - Komodo Complete Setup](./proxmox/16_Komodo_complete_setup.md) - Komodo container management platform
- [17 - SuggestArr Setup](./proxmox/17_SuggestArr_Setup_Troubleshooting_Guide.md) - SuggestArr media suggestion automation
- [18 - Claude Code Management LXC](./proxmox/18_Claude_Code_Management_LXC_Setup.md) - Claude Code management LXC, SSH key infrastructure, GitHub MCP server
- [19 - DocuSeal E-Signature](./proxmox/19_DocuSeal_E-Signature_Setup.md) - DocuSeal self-hosted e-signature platform
- [20 - MkDocs Portfolio Site](./proxmox/20_MkDocs_Portfolio_Site_Setup.md) - MkDocs Material theme, GitHub Actions auto-deploy, custom domain
- [21 - Public Form E-Signature Automation](./proxmox/21_Public_Form_E-Signature_Automation.md) - Public web form with Turnstile bot protection, n8n webhook validation, DocuSeal e-signature automation
- [22 - Dawarich GPS Tracking](./proxmox/22_Dawarich_GPS_Tracking_Setup.md) - Self-hosted GPS location history and family tracking, PostGIS, mobile app integration
- [23 - Homelable Network Visualization + MCP](./proxmox/23_Homelable_Setup.md) - Interactive homelab topology canvas, live status checks, nmap scanning, Claude Code MCP integration
- [24 - IP Conflict and DHCP Incident - Network Hardening](./proxmox/24_IP_Conflict_DHCP_Incident_Network_Hardening.md) - Rogue ARP claimants, DHCP-to-static migration of all LXCs/VM, Newt stale tunnel after router reboots
- [25 - Art Portfolio Static Site](./proxmox/25_Art_Portfolio_Static_Site.md) - Node build script (sharp, js-yaml, node:test) + Caddy static hosting, fail-loud build verification, gallery-paper frontend, built via subagent-driven development
- [26 - Interactive Network Topology Map](./proxmox/26_Network_Topology_Map.md) - YAML inventory baked into a static HTML map by a Node build script, clickable node detail panel, SVG wires, control-room blueprint design; also published publicly at homelabor.net/topology/
- [27 - Homepage GitOps Config](./proxmox/27_Homepage_GitOps_Config.md) - Homepage dashboard config moved into git, Komodo deploy settings, secret placeholder workflow, live mount verification
- [28 - SnapRAID Daemon Setup](./proxmox/28_SnapRAID_Daemon_Setup.md) - Replaced manual SnapRAID CLI + cron with snapraidd web dashboard, dpkg dependency conflict fix, doc/release drift workarounds (no auth in v1.14, explicit bind IP needed), old binary quarantine, and the 2026-08-12 tuning pass where the delete threshold had been aborting the weekly sync unnoticed
- [29 - Rails Learning Lab](./proxmox/29_Rails_Learning_Lab.md) - Disposable Rails 8 + PostgreSQL sandbox on docker-host, port collision on 3000 forced a move to 3300, Rails 8 host authorization, VS Code Remote-SSH editing workflow
- [30 - Backup Verification + Restore Test](./proxmox/30_Backup_Verification_Restore_Test.md) - Restic restore test with checksum comparison and 1% data read, per-guest vzdump coverage in the daily digest, the tmpfs-on-pve trap and the .vma.zst vs .tar.zst false alarm
- [31 - Tailscale Port Collision + DNS Audit](./proxmox/31_Tailscale_Port_Collision_DNS_Audit.md) - Four nodes sharing UDP 41641 behind one UPnP router made LXC 109 flap between direct and DERP, a LAN-only IP as tailnet global nameserver broke all mobile DNS, and both ssh.service and ssh.socket were enabled on 109
- [32 - Nobara SSH Freeze (open)](./proxmox/32_Nobara_SSH_Freeze_Investigation.md) - Unresolved: eight hypotheses excluded with the measurement that killed each, two real failures captured (port 22 blackholed in one direction with the MSS collapsing to 64, and a 17-minute root-only connect timeout with no UID mechanism to explain it), plus the two watchers now running to catch the next occurrence
- [33 - Daily AI News Digest Pipeline](./proxmox/33_AI_News_Digest_Pipeline.md) - Twenty sources into eight items a morning: why FreshRSS does the fetching and the script holds no feed list, why the archive is a separate system (FreshRSS deletes after three months), why Telegram HTML instead of MarkdownV2, and the three feeds that were dead or blocking before a single line was written
- [34 - Transcode-Free Re-encode (AV1 to H.264)](./proxmox/34_Transcode_Free_Re-encode_AV1_to_H264.md) - Why Jellyfin transcoded at 118% CPU for two independent reasons at once (no AV1 decoder on the UHD 630, plus a burned-in ASS subtitle), the NVENC recipe that offloads the work to a spare GPU on another machine, and the three traps: a read-only NFS share despite no_root_squash, a container Duration field that lies, and filename-based skip logic that re-encodes finished work
- [35 - Cron Job Monitoring (Uptime Kuma)](./proxmox/35_Cron_Job_Monitoring_Uptime_Kuma.md) - Dead man's switch monitoring for eight cron jobs across three hosts using push monitors on the off-site Uptime Kuma, why a cron manager UI would not have caught any of the three silent failures, creating monitors by SQLite insert because Kuma has no write API, the three gating traps (a zero-iteration loop that reports success, a healthy command that exits non-zero, a legitimate skip that must still ping), and why moving a host's timezone costs a heartbeat window unless the flip is timed
- [36 - Immich Bulk Import and ML Pipeline](./proxmox/36_Immich_Bulk_Import_ML_Pipeline.md) - Importing 6,302 photos from a USB stick with immich-go, and the three ML failures that each looked like success: a full GPU where ONNX silently fell back to CPU while every queue reported `failed=0` (9.4x throughput lost), a container restart that discarded 2,668 in-flight jobs and left the queue reading as finished, and a duplicate threshold that flagged burst sequences no threshold can separate - plus why the OCR model list lives in the container, not the docs
- [37 - Calibre-Web Bulk Ebook Import](./proxmox/37_Calibre_Web_Automated_Bulk_Import.md) - Uploading 56 missing ebooks (330 MB) into Calibre-Web-Automated by diffing the source folders against the library on SHA-256, because Calibre renames and truncates on import so no filename matches; the single 9.6 MB scanned PDF that blocked the serial ingest queue for eight minutes at 100% CPU in `pdftohtml`, the one-second `pdffonts` + `pdftotext | wc -c` test that identifies an unconvertible scan (0 fonts, 736 bytes over 736 pages), and why auto-convert to EPUB belongs on for MOBI/AZW3 and off for PDF
- [38 - Calibre Metadata Cleanup](./proxmox/38_Calibre_Metadata_Cleanup.md) - Fixing 30 books whose titles came from a Word document name or whose author was the date part of a filename, using `calibredb` against a live library, and the four traps: `--field title:` leaves `sort` and `author_sort` stale, `has_cover=1` hides a generated placeholder with the old title painted into it, the library grid serves a separate thumbnail cache the detail page does not, and a file whose size is exactly 72.0 MiB is truncated rather than corrupt - plus a two-file probe proving the EPUB's OPF beats the filename on ingest
- [39 - Auditing a Community Fork](./proxmox/39_Auditing_a_Community_Fork.md) - How to decide whether to run a container from a pseudonymous fork: resolving the tag to a digest and querying GitHub's SLSA attestation API (the fork has provenance, the popular upstream has none), diffing the source and the outbound hostnames against the version being replaced, finding the one build input the provenance does not cover, and why the blast radius of the service - not the star count - settles it
- [40 - Shelfmark Book Pipeline](./proxmox/40_Shelfmark_Book_Pipeline.md) - Reviving a dead dashboard tile into a book search and download pipeline: why every documented endpoint had to be re-measured over DNS-over-HTTPS because the router intercepts port 53, why a 403 with `cf-mitigated: challenge` is a working host and not a blocked one, finding a locale-specific metadata provider the setup wizard hardcodes out of its own list, the absolute-path agreement two containers must share or imports fail silently, and the Komodo pull/deploy race that produces a stale success instead of an error
- [41 - Hermes Agent Capability Hardening](./proxmox/41_Hermes_Agent_Capability_Hardening.md) - Auditing a background agent that had been running six weeks with its web toolset entirely dead: why a Hungarian Claude Code orchestration layer was not worth migrating to but was worth auditing against, why the provider advertised as "vector memory" is hash-based and not semantic, the uv-created venv with no pip that silently degrades a plugin, the free self-hosted search engine already running on the same host while a paid quota was being spent, the Home Assistant variable that quietly turns the agent into an event listener, and why a pasted one-liner is not a safe way to move a secret between hosts
- [42 - Sonarr/Radarr Missing Media Audit](./proxmox/42_Sonarr_Radarr_Missing_Media_Audit.md) - Tracking down 2600 episodes and 275 movies that Sonarr and Radarr reported as Missing: why `MissingFromDisk` is an alibi rather than a cause, how `tune2fs -l` dated the loss to two USB disk reformats that predate every surviving log, why a passing hardlink test on a MergerFS pool proves nothing about the general case, the recycle bin that becomes a cross-disk copy unless the directory exists on every branch, the unprivileged-LXC ownership trap that makes the feature fail silently, and why one parity disk protects a wiped array member only until the next sync runs
- [43 - Nobara DSCP SSH Timeout](./proxmox/43_Nobara_DSCP_SSH_Timeout.md) - Why every SSH from the Nobara desktop to every LAN host timed out while `ping` and raw TCP to the same port succeeded: the one-line asymmetry that isolates a client socket option from a network or sshd fault, the DSCP marking that a wireless backhaul drops, why the same hypothesis was correctly excluded by measurement three weeks earlier and is not wrong now, the per-host workaround that was itself the evidence the fault predated the report, and the second, unrelated authentication fault the timeout was hiding - a machine whose Windows key had been standing in for its Linux one all along

### Deprecated

- [Recommendarr](./proxmox/deprecated/Recommendarr_Setup_Troubleshooting_Guide.md) - Recommendarr AI recommendations (removed due to security concerns, Mar 2026)
- [Scanopy](./proxmox/deprecated/Scanopy.md) - Network topology visualizer (decommissioned, replaced)
- [Minecraft Server Setup](./proxmox/deprecated/Minecraft_Server_Setup.md) - PaperMC + GeyserMC + Floodgate, Java + Bedrock cross-play (LXC 112 deleted, Jul 2026)

## other/

Side projects outside the homelab.

- [factory-copy-script](./other/factory-copy-script.md) - PowerShell script to fix broken defect map imports on an industrial laser cutter (self-initiated, factory job)
- [prompt-analysis](./other/prompt-analysis.md) - Python script that audits my own Claude Code prompting habits from session transcripts
- [claude-output-style](./other/claude-output-style.md) - Custom Claude Code output style: why tone rules belong in the system prompt, not CLAUDE.md

## k3s/

The K3s cluster's own code layers. The live cluster state lives on the
[k3s-cluster host page](./hosts/k3s-cluster.md).

- [01 - Infrastructure as Code](./k3s/01_K3s_Infrastructure_as_Code.md) - the three layers that describe the cluster: Ansible for k3s itself, Argo CD for its contents, and the restore proofs behind the backups

## vps/

- [01 - Hetzner VPS + Pangolin + Jellyfin](./vps/01_Hetzner_VPS_Pangolin_Jellyfin_Setup.md) - Hetzner VPS, Pangolin reverse proxy, public Jellyfin access
- [02 - Security Configuration](./vps/02_Security_Configuration_Guide.md) - Cloudflare, Pangolin 2FA, GeoIP rules, incident response
- [03 - Uptime Kuma Migration to VPS](./vps/03_Uptime_Kuma_VPS_Migration.md) - Migrate Uptime Kuma to VPS for external monitoring, host networking, Tailscale accept-routes, Pangolin local site, UFW bridge rule
- [04 - Landing Page (homelabor.net)](./vps/04_Landing_Page_Setup.md) - Public one-page site at the apex domain, Caddy on the VPS, live status widget

## Quick Start

1. [Proxmox Setup + Storage](./proxmox/01_Proxmox_VE_9.1_MergerFS_SnapRAID_Installation_Documentation.md)
2. [LXC & Docker Setup](./proxmox/02_Proxmox_Docker_LXC_Setup_-_Detailed_Process.md)
3. [Komodo Management](./proxmox/16_Komodo_complete_setup.md)

## External Resources

- [homelabor.net](https://homelabor.net/) - infrastructure overview
- [Proxmox Documentation](https://pve.proxmox.com/pve-docs/)
- [Docker Documentation](https://docs.docker.com/)
- [Komodo Documentation](https://komo.do/docs)
- [LinuxServer.io Images](https://docs.linuxserver.io/)
