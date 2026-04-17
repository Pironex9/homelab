# Documentation

## hosts/

Per-host reference documentation - current configuration, running services, and lessons learned for each VM and LXC container.

- [docker-host](./hosts/docker-host.md) - Primary Docker host (LXC 100) - 18 stacks, GPU passthrough, Komodo integration
- [haos](./hosts/haos.md) - Home Assistant OS VM (VM 101) - Zigbee2MQTT, MQTT, REST API
- [adguard](./hosts/adguard.md) - AdGuard Home (LXC 102) - DNS, blocklists, Quad9 DoH/DoT
- [komodo](./hosts/komodo.md) - Komodo (LXC 105) - GitOps deployment management, Periphery agents
- [karakeep](./hosts/karakeep.md) - Karakeep (LXC 106) - bookmarking, AI tagging with local Ollama
- [n8n](./hosts/n8n.md) - n8n (LXC 107) - workflow automation, Claude Code MCP integration
- [ollama](./hosts/ollama.md) - Ollama (LXC 108) - local LLM inference, Intel GPU via SYCL
- [claude-mgmt](./hosts/claude-mgmt.md) - Claude Code management node (LXC 109) - GitHub MCP, n8n MCP
- [nobara](./hosts/nobara.md) - Desktop PC - NVIDIA RTX 2060, Ollama GPU node, NFS/SSHFS client
- [caddy](./hosts/caddy.md) - Caddy reverse proxy (LXC 110) - HTTPS for all .lan services, mkcert local CA
- [minecraft](./hosts/minecraft.md) - Minecraft server (LXC 112) - PaperMC + GeyserMC + Floodgate, Java + Bedrock cross-play
- [k3s-cluster](./hosts/k3s-cluster.md) - K3s cluster (3x Dell OptiPlex) - Kubernetes, WoL, Tailscale access
- [vps](./hosts/vps.md) - Hetzner VPS (CX23) - Pangolin reverse proxy, Komodo managed via Tailscale

### Retired

- [raspberry-pi](./hosts/raspberry-pi.md) - Raspberry Pi 4 (retired, Aug 2024 - Dec 2025) - origin homelab, 20+ Docker services

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
- [14 - NFS Setup](./proxmox/14_NFS-Setup_Documentation.md) - NFS share configuration
- [15 - Backup System](./proxmox/15_Proxmox_Backup_System_Documentation.md) - Backup system and schedules
- [16 - Komodo Complete Setup](./proxmox/16_Komodo_complete_setup.md) - Komodo container management platform
- [17 - SuggestArr Setup](./proxmox/17_SuggestArr_Setup_Troubleshooting_Guide.md) - SuggestArr media suggestion automation
- [18 - Claude Code Management LXC](./proxmox/18_Claude_Code_Management_LXC_Setup.md) - Claude Code management LXC, SSH key infrastructure, GitHub MCP server
- [19 - DocuSeal E-Signature](./proxmox/19_DocuSeal_E-Signature_Setup.md) - DocuSeal self-hosted e-signature platform
- [20 - MkDocs Portfolio Site](./proxmox/20_MkDocs_Portfolio_Site_Setup.md) - MkDocs Material theme, GitHub Actions auto-deploy, custom domain
- [21 - Public Form E-Signature Automation](./proxmox/21_Public_Form_E-Signature_Automation.md) - Public web form with Turnstile bot protection, n8n webhook validation, DocuSeal e-signature automation
- [22 - Dawarich GPS Tracking](./proxmox/22_Dawarich_GPS_Tracking_Setup.md) - Self-hosted GPS location history and family tracking, PostGIS, mobile app integration
- [23 - Homelable Network Visualization + MCP](./proxmox/23_Homelable_Setup.md) - Interactive homelab topology canvas, live status checks, nmap scanning, Claude Code MCP integration
- [24 - Minecraft Server Setup](./proxmox/24_Minecraft_Server_Setup.md) - PaperMC + GeyserMC + Floodgate on dedicated LXC, Pangolin raw TCP/UDP public access

### Deprecated

- [Recommendarr](./proxmox/deprecated/Recommendarr_Setup_Troubleshooting_Guide.md) - Recommendarr AI recommendations (removed due to security concerns, Mar 2026)
- [Scanopy](./proxmox/deprecated/Scanopy.md) - Network topology visualizer (decommissioned, replaced)

## other/

Side projects outside the homelab.

- [factory-copy-script](./other/factory-copy-script.md) - PowerShell script to fix broken defect map imports on an industrial laser cutter (self-initiated, factory job)

## vps/

- [01 - Hetzner VPS + Pangolin + Jellyfin](./vps/01_Hetzner_VPS_Pangolin_Jellyfin_Setup.md) - Hetzner VPS, Pangolin reverse proxy, public Jellyfin access
- [02 - Security Configuration](./vps/02_Security_Configuration_Guide.md) - Cloudflare, Pangolin 2FA, GeoIP rules, incident response
- [03 - Uptime Kuma Migration to VPS](./vps/03_Uptime_Kuma_VPS_Migration.md) - Migrate Uptime Kuma to VPS for external monitoring, host networking, Tailscale accept-routes, Pangolin local site, UFW bridge rule

## Quick Start

1. [Proxmox Setup + Storage](./proxmox/01_Proxmox_VE_9.1_MergerFS_SnapRAID_Installation_Documentation.md)
2. [LXC & Docker Setup](./proxmox/02_Proxmox_Docker_LXC_Setup_-_Detailed_Process.md)
3. [Komodo Management](./proxmox/16_Komodo_complete_setup.md)

## External Resources

- [Proxmox Documentation](https://pve.proxmox.com/pve-docs/)
- [Docker Documentation](https://docs.docker.com/)
- [Komodo Documentation](https://komo.do/docs)
- [LinuxServer.io Images](https://docs.linuxserver.io/)
