# Homelab Repository Structure

Complete directory structure and file contents overview.

## 📁 Directory Tree

```
homelab/
├── .gitignore                    # Git ignore patterns
├── LICENSE                       # MIT License
├── README.md                     # Main portfolio landing page
├── GETTING_STARTED.md           # Quick start guide
│
├── compose/                      # Docker Compose configurations
│   ├── README.md                # Compose documentation
│   ├── proxmox-lxc-100/         # LXC 100 services
│   │   ├── README.md            # LXC 100 service list
│   │   ├── .gitkeep             # Placeholder
│   │   └── [service dirs]/      # Add your services here
│   ├── proxmox-baremetal/       # Proxmox host services
│   │   └── .gitkeep
│   ├── nobara/                  # Desktop services
│   │   └── .gitkeep
│   ├── k3s/                     # Kubernetes manifests
│   │   └── .gitkeep
│   └── vps/                     # Cloud VPS services
│       └── .gitkeep
│
├── docs/                        # Documentation
│   ├── README.md               # Documentation index
│   ├── proxmox/                # Proxmox guides
│   │   └── .gitkeep
│   ├── nobara/                 # Desktop setup
│   │   └── .gitkeep
│   ├── k3s/                    # Kubernetes docs
│   │   └── .gitkeep
│   ├── vps/                    # VPS deployment
│   │   └── .gitkeep
│   └── komodo/                 # Management platform (moved to proxmox/17_Komodo_complete_setup.md)
│
└── scripts/                    # Automation scripts
    ├── README.md              # Scripts documentation
    └── backup.sh              # Example backup script
```

## 📄 Key Files

### Root Level

**README.md**
- Portfolio landing page
- Tech stack overview
- Featured projects showcase
- Service metrics
- Links to documentation

**GETTING_STARTED.md**
- Quick start guide
- How to use this repository
- Customization checklist
- Learning path recommendations

**LICENSE**
- MIT License
- Open for personal/commercial use

**.gitignore**
- Protects sensitive data (.env files)
- Excludes logs and temporary files
- Prevents committing secrets

### Compose Directory

**compose/README.md**
- Standards and conventions
- Deployment procedures
- Environment variable guidelines
- Troubleshooting tips

**compose/proxmox-lxc-100/README.md**
- Service inventory
- Infrastructure details
- Management instructions
- Storage mount points

### Scripts Directory

**scripts/README.md**
- Script documentation
- Configuration guide
- Scheduling with cron
- Usage examples

**scripts/backup.sh**
- Example automated backup script
- Uses restic for encryption
- Includes retention policies
- Logging and notifications

### Docs Directory

**docs/README.md**
- Documentation index
- Quick start links
- Documentation standards
- Search guide

**docs/proxmox/17_Komodo_complete_setup.md**
- Complete Komodo installation guide
- LXC setup instructions
- Import workflow
- Git sync configuration

## 🎯 How to Use

### Initial Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Pironex9/homelab.git
   cd homelab
   ```

2. **Explore the structure**:
   - Read `README.md` for overview
   - Check `GETTING_STARTED.md` for setup guide
   - Browse `docs/` for detailed guides

3. **Add your services**:
   - Create directories in `compose/proxmox-lxc-100/`
   - Add `docker-compose.yml` for each service
   - Include `.env.example` templates
   - Document in service-specific README

### Adding New Content

**New Service**:
```bash
cd compose/proxmox-lxc-100
mkdir my-service
cd my-service
# Create docker-compose.yml
# Create .env.example
# Create README.md
```

**New Documentation**:
```bash
cd docs/proxmox
# Create new .md file
# Update docs/README.md index
```

**New Script**:
```bash
cd scripts
# Create new .sh file
chmod +x new-script.sh
# Update scripts/README.md
```

## 📝 File Templates

### Service docker-compose.yml Template

```yaml
services:
  service-name:
    image: org/image:tag
    container_name: service-name
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - /srv/docker-data/service:/config
      - /mnt/storage/media:/media
    environment:
      - PUID=0
      - PGID=0
      - TZ=Europe/Budapest
```

### Service README.md Template

```markdown
# Service Name

Brief description of what this service does.

## Configuration

- **Port**: 8080
- **Data**: /srv/docker-data/service
- **Dependencies**: None

## Setup

1. Copy .env.example to .env
2. Edit .env with your settings
3. Deploy: `docker compose up -d`

## Usage

Access at: http://your-server:8080

## Troubleshooting

Common issues and solutions.
```

### Documentation .md Template

```markdown
# Topic Title

## Overview

Brief introduction.

## Prerequisites

- Requirement 1
- Requirement 2

## Installation

Step-by-step instructions.

## Configuration

Configuration details.

## Verification

How to verify it's working.

## Troubleshooting

Common issues.

## References

- [External link 1]()
- [External link 2]()
```

## 🔄 Workflow

### Daily Use

1. **Deploy services**: Via Komodo UI or docker compose
2. **Monitor**: Check Uptime Kuma dashboard
3. **Logs**: View in Dozzle or docker compose logs

### Maintenance

1. **Updates**: Run update-all-stacks.sh weekly
2. **Backups**: Automated daily with backup.sh
3. **Documentation**: Update docs when procedures change

### Development

1. **Test locally**: Deploy in test LXC first
2. **Document**: Update README and docs
3. **Commit**: Git add, commit, push
4. **Deploy**: Import to Komodo or deploy manually

## 📦 What's Included

### Ready to Use

- Complete folder structure
- Documentation templates
- Example backup script
- Git configuration (.gitignore)
- License (MIT)

### Needs Your Content

- Service-specific docker-compose files
- Your infrastructure documentation
- Customized automation scripts
- Network diagrams
- Your actual .env files (not committed)

## 🚀 Next Steps

1. **Customize README.md**: Add your name, links
2. **Add services**: Copy your compose files
3. **Write docs**: Document your specific setup
4. **Create diagrams**: Use draw.io for network topology
5. **Push to GitHub**: Make it public (portfolio!)
6. **Share on LinkedIn**: Post about your homelab

## 📊 Statistics

- **Total directories**: 15+
- **Documentation files**: 8 README.md files
- **Example scripts**: 1 (backup.sh)
- **License**: MIT (open use)
- **Size**: ~50KB (without compose files)

## 🎓 Learning Resources

Use this structure to:
- Learn Docker Compose organization
- Understand IaC principles
- Build a DevOps portfolio
- Document your infrastructure
- Version control your configs

---

Ready to build your homelab? Start with GETTING_STARTED.md!
