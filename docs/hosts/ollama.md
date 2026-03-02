# ollama LXC

## Overview

| Property | Value |
|----------|-------|
| Hostname | ollama |
| IP Address | 192.168.0.231 |
| VMID | 108 |
| OS | Ubuntu 24.04.3 LTS (Noble Numbat) |
| Kernel | 6.17.4-1-pve |
| CPU | 4 cores |
| RAM | 8 GB |
| Swap | 512 MB |
| Disk | 35 GB (local-lvm, 77% used) |
| Purpose | Local LLM inference server |

## Running Services

| Service | Description |
|---------|-------------|
| `ollama.service` | Ollama LLM server |
| `ssh.service` | OpenSSH server |
| `rsyslog.service` | System logging |

## Open Ports

| Port | Protocol | Service |
|------|----------|---------|
| 22 | TCP | SSH |
| 11434 | TCP | Ollama API (`OLLAMA_HOST=0.0.0.0`) |

## Ollama

**Version:** 0.15.5
**Binary:** `/usr/local/bin/ollama`

### Installed Models

| Model | Size |
|-------|------|
| `llama3.1:8b` | 4.9 GB |

### Service Configuration

| Setting | Value | Description |
|---------|-------|-------------|
| `OLLAMA_HOST` | `0.0.0.0` | Listen on all interfaces (network-accessible) |
| `OLLAMA_INTEL_GPU` | `true` | Enable Intel GPU acceleration |
| `OLLAMA_NUM_GPU` | `999` | Use all available GPU layers |
| `OLLAMA_ORIGINS` | `*` | Allow requests from any origin (CORS) |
| `SYCL_CACHE_PERSISTENT` | `1` | Persistent SYCL kernel cache for Intel GPU |
| `ZES_ENABLE_SYSMAN` | `1` | Enable Intel oneAPI system management |

### Intel GPU Passthrough

The LXC has `/dev/dri/card0` and `/dev/dri/renderD128` passed through from the Proxmox host, enabling Intel GPU acceleration for inference. Ollama uses the Intel oneAPI SYCL backend.

```
/dev/dri/card0       - Intel graphics card
/dev/dri/renderD128  - Intel render device (used for GPU compute)
```

## API Usage

The Ollama API is available at `http://192.168.0.231:11434` from the local network.

**Example:**
```bash
curl http://192.168.0.231:11434/api/generate \
  -d '{"model": "llama3.1:8b", "prompt": "Hello"}'
```

## Two Ollama Instances

This homelab runs two separate Ollama endpoints:

| Instance | Address | GPU | Use case |
|----------|---------|-----|----------|
| Nobara workstation | `192.168.0.100:11434` | RTX 2060 Super | Heavy/fast inference (Karakeep AI tagging) |
| This LXC | `192.168.0.231:11434` | Intel integrated (SYCL) | Lightweight / secondary endpoint |

## Lessons Learned

- **Ubuntu instead of Debian:** This LXC runs Ubuntu 24.04 rather than Debian 12. Ubuntu's wider hardware support package ecosystem made it easier to set up Intel GPU drivers and oneAPI toolkits.
- **Intel GPU acceleration in an LXC:** Requires passing through `/dev/dri/card0` and `/dev/dri/renderD128` in the Proxmox config, plus the `SYCL_CACHE_PERSISTENT` and `ZES_ENABLE_SYSMAN` environment variables for the Intel SYCL backend. Without these, Ollama falls back to CPU-only inference.
- **Disk usage at 77%:** With a 4.9 GB model and 35 GB disk, there is room for 1-2 more medium-sized models before the disk fills up. Each additional 7B model requires ~4-5 GB.
- **`OLLAMA_ORIGINS=*` is permissive:** Allowing all CORS origins is convenient for local development but means any page loaded in a browser on the LAN can make requests to the Ollama API. Acceptable for a homelab but worth noting.
