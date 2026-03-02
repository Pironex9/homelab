# komodo LXC

## Overview

| Property | Value |
|----------|-------|
| Hostname | komodo |
| IP Address | 192.168.0.105 |
| VMID | 105 |
| OS | Alpine Linux v3.23 |
| Kernel | 6.17.4-1-pve |
| CPU | 1 core |
| RAM | 32 GB |
| Swap | 8 GB |
| Disk | 10 GB (local-lvm, 37% used) |
| Purpose | Komodo deployment and infrastructure management platform |

## Running Services

| Service | Description |
|---------|-------------|
| `sshd` | OpenSSH server |
| `crond` | Scheduled tasks |
| Docker daemon | Container runtime |

## Open Ports

| Port | Protocol | Service |
|------|----------|---------|
| 22 | TCP | SSH |
| 9120 | TCP | Komodo Core web UI and API |

## Docker Stack

All three Komodo components run as Docker containers from a single Compose stack.

### Containers

| Container | Image | Port | Description |
|-----------|-------|------|-------------|
| `komodo-core-1` | `ghcr.io/moghtech/komodo-core:latest` | 9120 | Core API server and web UI |
| `komodo-mongo-1` | `mongo` | 27017 (internal) | MongoDB - stores all Komodo state |
| `komodo-periphery-1` | `ghcr.io/moghtech/komodo-periphery:latest` | 8120 (internal) | Local periphery agent |

### Docker Volumes

| Volume | Description |
|--------|-------------|
| `komodo_mongo-data` | MongoDB data directory |
| `komodo_mongo-config` | MongoDB configuration |

## Komodo Configuration

| Setting | Value |
|---------|-------|
| Database | MongoDB at `mongo:27017` |
| Auth | Local auth enabled |
| OIDC / OAuth | Disabled |
| Monitoring interval | 15 seconds |
| JWT TTL | 1 day |
| First server | `https://periphery:8120` (local agent) |

## Architecture

Komodo is a self-hosted alternative to tools like Portainer or Dockge with a focus on GitOps-style deployments. It consists of:

- **Core** - Central server. Manages resources (servers, stacks, builds). Exposes the web UI on port 9120.
- **Periphery** - Lightweight agent installed on each managed server. Executes actions on behalf of Core (deploy stacks, restart containers, collect stats).
- **MongoDB** - Stores all state: servers, stacks, alerts, resource definitions.

The `periphery.service` systemd unit on **docker-host** connects outward to Komodo Core, allowing Komodo to manage Docker stacks on docker-host remotely.

## Managed Servers

| Server | Address | Notes |
|--------|---------|-------|
| Local | `https://periphery:8120` | Built-in local agent on the komodo LXC itself |
| docker-host | via `periphery.service` on docker-host | Main Docker host managed via Komodo |

## Lessons Learned

- **Alpine does not have `ss`:** The `iproute2` package (which includes `ss`) is not installed by default on Alpine. Use `netstat` from the `net-tools` package instead, or install `iproute2` with `apk add iproute2`.
- **High RAM allocation:** 32 GB RAM is allocated to this LXC, but actual usage is lower. This may be intentional for MongoDB's working set cache or could be reduced after profiling.
- **Swap is configured:** Unlike most other LXCs in this homelab, komodo has 8 GB swap - useful because MongoDB can have large memory requirements during indexing.
- **Periphery on managed hosts:** Each host managed by Komodo must run the `periphery` agent. On docker-host this runs as `periphery.service`. The agent opens an outbound connection to Core - no inbound firewall rules are needed on the managed host.
