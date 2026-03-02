# Documentation

## hosts/

Per-host reference documentation — current configuration, running services, and lessons learned for each VM and LXC container.

- [`docker-host.md`](./hosts/docker-host.md) - Primary Docker host (LXC 100) — 19 stacks, GPU passthrough, Komodo integration
- [`haos.md`](./hosts/haos.md) - Home Assistant OS VM (VM 101) — Zigbee2MQTT, MQTT, REST API
- [`adguard.md`](./hosts/adguard.md) - AdGuard Home (LXC 102) — DNS, blocklists, Quad9 DoH/DoT
- [`komodo.md`](./hosts/komodo.md) - Komodo (LXC 105) — GitOps deployment management, Periphery agents
- [`karakeep.md`](./hosts/karakeep.md) - Karakeep (LXC 106) — bookmarking, AI tagging with local Ollama
- [`n8n.md`](./hosts/n8n.md) - n8n (LXC 107) — workflow automation, Claude Code MCP integration
- [`ollama.md`](./hosts/ollama.md) - Ollama (LXC 108) — local LLM inference, Intel GPU via SYCL
- [`claude-mgmt.md`](./hosts/claude-mgmt.md) - Claude Code management node (LXC 109) — GitHub MCP, n8n MCP

## proxmox/

Chronological setup guides — how the homelab was built, step by step.

- [01 - Proxmox VE 9.1 MergerFS + SnapRAID Installation](./proxmox/01_Proxmox_VE_9.1_MergerFS_SnapRAID_Installation_Documentation.md) - Initial Proxmox setup, MergerFS + SnapRAID storage
- [02 - Proxmox Docker LXC Setup](./proxmox/02_Proxmox_Docker_LXC_Setup_-_Detailed_Process.md) - LXC creation and Docker installation
- [03 - USB HDD Integration + SnapRAID Sync](./proxmox/03_USB_HDD_Integration_SnapRAID_Sync_and_Media_Structure_Fix.md) - USB HDD integration and SnapRAID sync
- [04 - Home Assistant OS VM + Zigbee2MQTT](./proxmox/04_Home_Assistant_OS_VM_Zigbee2MQTT_Backup_Strategy_Setup.md) - Home Assistant VM, Zigbee2MQTT, backup strategy
- [05 - AdGuard Home + Tailscale DNS](./proxmox/05_AdGuard_Home_Setup_Dedicated_LXC_Tailscale_DNS_Integration.md) - AdGuard Home + Tailscale DNS
- [06 - Immich Photo Management](./proxmox/06_Immich_Setup_Full_Installation_Guide.md) - Immich photo management
- [07 - Scrutiny Disk Health Monitoring](./proxmox/07_Scrutiny_Disk_Health_Monitoring_Setup_Guide.md) - Scrutiny disk health monitoring
- [08 - Netdata System Monitoring](./proxmox/08_Netdata_System_Monitoring_Setup_Guide.md) - Netdata system metrics
- [09 - Scanopy + Vaultwarden](./proxmox/09_Scanopy_Vaultwarden.md) - Scanopy + Vaultwarden password manager
- [10 - Helper Script LXCs](./proxmox/10_Helper_Script_LXCs.md) - Karakeep, n8n, Ollama via Proxmox helper scripts
- [11 - Jellyfin Hardware Transcoding](./proxmox/11_Jellyfin_Hardware_Transcoding_Setup.md) - Jellyfin GPU hardware transcoding
- [12 - Security Configuration](./proxmox/12_Security_Configuration_Guide.md) - Security hardening and firewall
- [13 - Karakeep AI Tagging with Ollama](./proxmox/13_Karakeep_AI_Tagging_with_Ollama_Setup_Documentation.md) - Karakeep AI tagging with Ollama
- [14 - USB Disk Unmount Problem Resolution](./proxmox/14_USB_Disk_Unmount_Problem_Resolution_disk4_ADATA_HD710_PRO.md) - USB disk troubleshooting
- [15 - NFS Setup](./proxmox/15_NFS-Setup_Documentation.md) - NFS share configuration
- [16 - Backup System](./proxmox/16_Proxmox_Backup_System_Documentation.md) - Backup system and schedules
- [17 - Komodo Complete Setup](./proxmox/17_Komodo_complete_setup.md) - Komodo container management platform
- [18 - SuggestArr Setup](./proxmox/18_SuggestArr_Setup_Troubleshooting_Guide.md) - SuggestArr media suggestion automation
- [19 - Recommendarr Setup](./proxmox/19_Recommendarr_Setup_Troubleshooting_Guide.md) - Recommendarr AI recommendations
- [20 - Claude Code Management LXC](./proxmox/20_Claude_Code_Management_LXC_Setup.md) - Claude Code management LXC, SSH key infrastructure, GitHub MCP server

## vps/

- [Hetzner VPS + Pangolin + Jellyfin](./vps/Hetzner_VPS_+_Pangolin_+_Jellyfin_Complete_Setup_Guide.md) - Hetzner VPS, Pangolin reverse proxy, public Jellyfin access

## Quick Start

1. [Proxmox Setup + Storage](./proxmox/01_Proxmox_VE_9.1_MergerFS_SnapRAID_Installation_Documentation.md)
2. [LXC & Docker Setup](./proxmox/02_Proxmox_Docker_LXC_Setup_-_Detailed_Process.md)
3. [Komodo Management](./proxmox/17_Komodo_complete_setup.md)

## External Resources

- [Proxmox Documentation](https://pve.proxmox.com/pve-docs/)
- [Docker Documentation](https://docs.docker.com/)
- [Komodo Documentation](https://komo.do/docs)
- [LinuxServer.io Images](https://docs.linuxserver.io/)
