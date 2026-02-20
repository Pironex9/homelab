# Documentation

Complete setup and operational documentation for the homelab infrastructure.

## 📚 Documentation Structure

### proxmox/
Proxmox VE setup, service installation, and configuration guides:
- `1_Proxmox_VE_9.1_MergerFS_SnapRAID_Installation_Documentation.md` - Initial Proxmox setup, MergerFS + SnapRAID storage
- `2_Proxmox_Docker_LXC_Setup_-_Detailed_Process.md` - LXC creation and Docker installation
- `3_USB_HDD_Integration_SnapRAID_Sync_and_Media_Structure_Fix.md` - USB HDD integration and SnapRAID sync
- `4_Home_Assistant_OS_VM_Zigbee2MQTT_Backup_Strategy_Setup.md` - Home Assistant VM, Zigbee2MQTT, backup strategy
- `5_AdGuard_Home_Setup_Dedicated_LXC_Tailscale_DNS_Integration.md` - AdGuard Home + Tailscale DNS
- `6_Immich_Setup_Full_Installation_Guide.md` - Immich photo management
- `7_Scrutiny_Disk_Health_Monitoring_Setup_Guide.md` - Scrutiny disk health monitoring
- `8_Netdata_System_Monitoring_Setup_Guide.md` - Netdata system metrics
- `9_Scanopy_Vaultwarden.md` - Scanopy + Vaultwarden password manager
- `11_Jellyfin_Hardware_Transcoding_Setup.md` - Jellyfin with GPU hardware transcoding
- `12_Security_Configuration_Guide.md` - Security hardening and firewall configuration
- `13_Karakeep_AI_Tagging_with_Ollama_Setup_Documentation.md` - Karakeep AI tagging with Ollama
- `14_USB_Disk_Unmount_Problem_Resolution_disk4_ADATA_HD710_PRO.md` - USB disk troubleshooting
- `15_NFS-Setup_Documentation.md` - NFS share configuration
- `16_Proxmox_Backup_System_Documentation.md` - Backup system and schedules
- `17_Komodo_complete_setup.md` - Komodo container management platform
- `18_SuggestArr_Setup_Troubleshooting_Guide.md` - SuggestArr media suggestion automation
- `19_Recommendarr_Setup_Troubleshooting_Guide.md` - Recommendarr AI recommendations

### komodo/
Komodo container management platform:
- See `proxmox/17_Komodo_complete_setup.md` - Full installation, migration from Dockge, and usage guide

### vps/
Cloud VPS and reverse proxy setup:
- `10_Hetzner_VPS_+_Pangolin_+_Jellyfin_Complete_Setup_Guide.md` - Hetzner VPS, Pangolin reverse proxy, public Jellyfin access

## 📖 Quick Start Guides

**New to the homelab?** Start here:
1. [Proxmox Setup + Storage](./proxmox/1_Proxmox_VE_9.1_MergerFS_SnapRAID_Installation_Documentation.md)
2. [LXC & Docker Setup](./proxmox/2_Proxmox_Docker_LXC_Setup_-_Detailed_Process.md)
3. [Komodo Management Setup](./proxmox/17_Komodo_complete_setup.md)

**Deploying a new service?**
1. [Create Docker Compose file](../compose/README.md)
2. [Import to Komodo](./proxmox/17_Komodo_complete_setup.md)
3. [Configure backups](./proxmox/16_Proxmox_Backup_System_Documentation.md)

## 🎯 Documentation Standards

All documentation follows these principles:

**Structure:**
- Clear hierarchy with headers
- Table of contents for long docs
- Step-by-step instructions with commands
- Prerequisites section at the top

**Format:**
- Markdown (.md) files
- Code blocks with syntax highlighting
- Screenshots for complex UI steps
- Links to related documentation

**Content:**
- Commands that can be copy-pasted
- Expected output examples
- Troubleshooting sections
- "Why" explanations, not just "how"

## 🔍 Finding Documentation

**By topic:**
- Use the directory structure above
- Each major component has its own folder

**By search:**
```bash
# Search all docs
grep -r "keyword" ./docs/

# Search with context
grep -r -C 3 "docker compose" ./docs/
```

**By service:**
- Check individual service README in [compose/](../compose/)
- Cross-references in related docs

## ✏️ Contributing to Documentation

When adding new documentation:

1. **Place it correctly:**
   - Infrastructure: `proxmox/`
   - Services: Inline in compose dirs
   - Tools/Platforms: Dedicated folder

2. **Follow the template:**
   ```markdown
   # Title

   ## Overview
   Brief description

   ## Prerequisites
   - Requirement 1
   - Requirement 2

   ## Installation/Setup
   Step-by-step instructions

   ## Configuration
   Configuration details

   ## Usage
   How to use

   ## Troubleshooting
   Common issues

   ## References
   - Link 1
   - Link 2
   ```

3. **Link from relevant places:**
   - Update this README
   - Add to related docs
   - Reference in main README

4. **Keep it updated:**
   - Update when procedures change
   - Add lessons learned
   - Remove outdated information

## 🔗 External Resources

Useful external documentation:
- [Proxmox Documentation](https://pve.proxmox.com/pve-docs/)
- [Docker Documentation](https://docs.docker.com/)
- [Komodo Documentation](https://komo.do/docs)
- [Linux Server.io Images](https://docs.linuxserver.io/)

## 📝 Documentation Wishlist

Documentation that needs to be written:
- [ ] Ansible playbooks for configuration management
- [ ] Grafana + Prometheus monitoring setup
- [ ] Network diagram with draw.io
- [ ] Disaster recovery testing procedures
- [ ] K3s cluster setup (when implemented)
