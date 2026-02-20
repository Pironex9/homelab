# Getting Started with this Repository

This guide will help you use this homelab infrastructure repository as a starting point for your own setup or as a portfolio reference.

## 🎯 Purpose

This repository serves multiple purposes:
1. **Documentation** - Complete setup guides for my homelab
2. **Version Control** - All Docker Compose configs in git
3. **Portfolio** - Showcase infrastructure and DevOps skills
4. **Knowledge Sharing** - Help others build similar setups

## 📋 Prerequisites

To use this repository, you should have:
- Basic Linux command line knowledge
- Understanding of Docker and containers
- Proxmox VE server (or similar hypervisor)
- Network access to your infrastructure

## 🚀 Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/Pironex9/homelab.git
cd homelab
```

### 2. Explore the Structure

```
homelab/
├── compose/     # Docker Compose configurations
├── docs/        # Complete documentation
├── scripts/     # Automation scripts
└── README.md    # You are here!
```

### 3. Read the Documentation

Start with these key documents:
1. [Main README](./README.md) - Overview and features
2. [Proxmox Setup](./docs/proxmox/setup.md) - Infrastructure foundation
3. [Docker Compose Guide](./compose/README.md) - Service deployment
4. [Komodo Setup](./docs/proxmox/17_Komodo_complete_setup.md) - Management platform

### 4. Adapt to Your Environment

This is **my** homelab configuration. To use it:

**Option A: Use as Reference**
- Read the docs to understand the approach
- Copy individual service configs you need
- Adapt to your environment

**Option B: Fork and Customize**
- Fork the repository
- Update IPs, hostnames, paths
- Commit your customizations
- Keep sensitive data in `.env` files (gitignored)

## 🔧 Using the Configurations

### Deploy a Single Service

```bash
# Example: Deploy Jellyfin
cd compose/proxmox-lxc-100/jellyfin
cp .env.example .env
# Edit .env with your settings
docker compose up -d
```

### Run Automation Scripts

```bash
cd scripts
cp .env.example .env
# Configure your settings
./backup.sh jellyfin
```

### Import to Komodo

Follow the [Komodo setup guide](./docs/proxmox/17_Komodo_complete_setup.md) to:
1. Install Komodo Core
2. Setup Periphery agents
3. Import your compose files

## 📖 Documentation Guide

### For Learning

If you're learning to build a homelab:
1. Start with [docs/proxmox/](./docs/proxmox/) for infrastructure
2. Move to [docs/komodo/](./docs/komodo/) for management
3. Browse [compose/](./compose/) for service examples

### For Reference

If you need specific information:
- Use GitHub search: Press `/` and search
- Check [docs/README.md](./docs/README.md) for index
- Browse by category in docs folder

### For Troubleshooting

Each service directory has:
- `README.md` with setup notes
- `docker-compose.yml` with comments
- Common issues documented

## 🛠 Customization Checklist

Before deploying to your environment:

- [ ] Update all IP addresses
- [ ] Change default passwords/secrets
- [ ] Modify storage paths
- [ ] Adjust resource allocations
- [ ] Update domain names
- [ ] Configure your backup destinations
- [ ] Set your timezone (`TZ` variable)
- [ ] Update user/group IDs if needed

## 🔒 Security Notes

**DO NOT:**
- Commit `.env` files with real secrets
- Push real passwords to git
- Expose services directly to internet without protection

**DO:**
- Use strong, unique passwords
- Keep `.env` files gitignored
- Use VPN (Tailscale/WireGuard) for remote access
- Regularly update your services
- Review exposed ports

## 📦 What's Included

### Infrastructure Documentation
- Proxmox VE setup and configuration
- LXC container templates
- Storage configuration (MergerFS + SnapRAID)
- Network architecture

### Service Configurations
- 19 Docker Compose stacks (LXC 100) + 8 LXC/VM services
- Media server stack (Jellyfin, *arr apps)
- Automation tools (n8n, Home Assistant)
- Security services (Vaultwarden, reverse proxy)
- Monitoring (Uptime Kuma, Netdata)

### Management
- Komodo setup for centralized management
- Automated backup scripts
- Update and maintenance procedures

## 🤝 Contributing

This is primarily a personal infrastructure repository, but:
- **Issues**: Report problems or suggest improvements
- **Questions**: Feel free to open discussions
- **Improvements**: PRs welcome for documentation fixes

## 📚 Additional Resources

- [Proxmox Wiki](https://pve.proxmox.com/wiki/)
- [Docker Documentation](https://docs.docker.com/)
- [r/homelab](https://reddit.com/r/homelab) - Community
- [r/selfhosted](https://reddit.com/r/selfhosted) - Self-hosting community

## 🆘 Getting Help

1. **Check Documentation**: Most answers are in [docs/](./docs/)
2. **Search Issues**: Someone may have asked already
3. **Open an Issue**: Describe your problem clearly
4. **Community**: Ask in r/homelab or r/selfhosted

## ⚖️ License

This repository is licensed under the MIT License - see [LICENSE](./LICENSE) for details.

You're free to:
- Use this code for personal or commercial projects
- Modify and distribute
- Use as a learning resource

## 🎓 Learning Path

Recommended order if building from scratch:

1. **Week 1-2**: Setup Proxmox
   - Install Proxmox VE
   - Configure networking
   - Create first LXC container

2. **Week 3-4**: Deploy core services
   - Setup Docker in LXC
   - Deploy first stack (Homepage?)
   - Configure reverse proxy

3. **Week 5-6**: Add management
   - Install Komodo
   - Import existing stacks
   - Setup monitoring

4. **Week 7+**: Expand and automate
   - Add more services
   - Create backup scripts
   - Document your setup

## 🏁 Next Steps

Ready to get started?

1. **Choose your path**: Reference vs Full deployment
2. **Read the docs**: Start with infrastructure guides
3. **Deploy incrementally**: One service at a time
4. **Document your changes**: Keep notes as you go
5. **Share your setup**: Post to r/homelab when ready!

---

**Questions?** Open an issue or discussion!
**Found this helpful?** Star the repo ⭐
