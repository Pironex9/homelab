## Overview

Self-hosted AI tagging solution for Karakeep bookmark manager using remote Ollama inference with dedicated GPU acceleration.

**Architecture:**
- Karakeep: Proxmox LXC 106 (192.168.0.YOUR_KARAKEEP_IP)
- Ollama: Nobara PC (192.168.0.YOUR_PC_IP:11434) - RTX 2060 Super
- Proxmox Host: HP EliteDesk 800 G4 (Intel i5-8400, 32GB RAM)

## Problem Statement

Karakeep AI tagging failed with cloud providers:
- **Groq API**: Models don't support `json_schema` response format required by Karakeep
- **Gemini API**: `/openai/` endpoint returns 404, insufficient compatibility

**Solution:** Remote Ollama deployment on gaming PC with NVIDIA RTX 2060 Super for GPU-accelerated inference.

## Ollama Installation (Nobara PC)

### 1. Install Ollama Bare Metal
```bash
# On Nobara PC:
curl -fsSL https://ollama.com/install.sh | sh
```

**Installation automatically:**
- Detects NVIDIA GPU
- Creates ollama user
- Adds ollama user to render/video groups
- Creates systemd service
- Enables service on boot

### 2. Enable Network Access

**Default:** Ollama only listens on localhost (127.0.0.1)

**Enable remote access:**
```bash
sudo mkdir -p /etc/systemd/system/ollama.service.d/
sudo nano /etc/systemd/system/ollama.service.d/override.conf
```

**Content:**
```ini
[Service]
Environment="OLLAMA_HOST=0.0.0.0:11434"
```

**Apply changes:**
```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
sudo systemctl status ollama
```

### 3. Configure Firewall
```bash
# Open port 11434:
sudo firewall-cmd --permanent --add-port=11434/tcp
sudo firewall-cmd --reload

# Verify:
sudo firewall-cmd --list-ports
```

### 4. Download Model
```bash
ollama pull llama3.1:8b
```

**Model selection rationale:**
- llama3.2 only available in 1B/3B sizes (no 7B variant exists)
- llama3.1:8b provides better tagging quality (~4.9GB VRAM)
- RTX 2060 Super (8GB VRAM) handles this easily

### 5. Verify Installation
```bash
# Local test:
curl http://localhost:11434

# Remote test (from Proxmox):
curl http://192.168.0.YOUR_PC_IP:11434
```

**Expected response:** `Ollama is running`

## Karakeep Configuration

### 1. Edit Environment File

**File:** `/etc/karakeep/karakeep.env`
```bash
# Ollama configuration - Remote Nobara PC
OLLAMA_BASE_URL="http://192.168.0.YOUR_PC_IP:11434/"
OLLAMA_KEEP_ALIVE="5m"

# Model selection
INFERENCE_TEXT_MODEL="llama3.1:8b"
# INFERENCE_IMAGE_MODEL="gpt-4o-mini"  # Optional
```

**Remove any conflicting API configs:**
- OPENAI_API_KEY
- OPENAI_BASE_URL
- Gemini API keys

### 2. Restart Services
```bash
# In Karakeep LXC (106):
systemctl restart karakeep-web karakeep-workers
journalctl -u karakeep-workers.service -f
```

## Testing & Verification

### Expected Behavior

1. Save bookmark in Karakeep web interface
2. Monitor logs: `journalctl -u karakeep-workers.service -f`
3. First inference loads model into GPU VRAM
4. Subsequent inferences: 2-5 seconds per bookmark

### Sample Output
```
[inference][1386] Inferring tag for bookmark "d49zbyh0ae6wpeq2an3x7mjl" used 2133 tokens and inferred: Personal Development,Productivity,Skills for 2026,Career Advice,Artificial Intelligence,Robotics,Quantum Computing,Cybersecurity,Software Development,Cloud Computing,Networking,IoT,Linux,Programming,Virtualization
```

## Performance Metrics

**GPU-accelerated inference (RTX 2060 Super):**
- Tokens processed: 400-2100 per bookmark
- Inference time: **2-5 seconds** (vs 15 sec CPU-only)
- GPU usage during inference: ~70-90%
- GPU VRAM usage: ~5GB (model in memory)

**Comparison:**

| Hardware | Inference Time | Speedup |
|----------|----------------|---------|
| i5-8400 CPU | 15 seconds | 1x |
| RTX 2060 Super | 2-5 seconds | **~5x faster** |

## Architecture Benefits

**Remote GPU inference:**
- ✅ **Performance:** ~5x faster than CPU-only
- ✅ **Reusability:** Ollama available for other services
- ✅ **Resource optimization:** Proxmox server stays lightweight
- ✅ **GPU utilization:** Gaming PC GPU useful when idle
- ✅ **Scalability:** Multiple services can use same Ollama instance

**Trade-offs:**
- ⚠️ Requires Nobara PC powered on for AI tagging
- ⚠️ Network dependency between Proxmox and Nobara PC
- ⚠️ Nobara PC idle power consumption when running 24/7

## Power Considerations

**Nobara PC (estimated):**
- Idle: 80-100W
- AI inference: 160-180W (GPU active, brief)
- If running 24/7: ~60-75 kWh/month (~€15-20 extra)

**Recommendation:** Only power on Nobara PC when needed, or accept idle power cost if PC already runs frequently.

## Troubleshooting

### Cannot Connect from Proxmox

**Test connectivity:**
```bash
# From Proxmox host:
curl http://192.168.0.YOUR_PC_IP:11434
```

**Common causes:**
1. Firewall blocking port 11434
2. OLLAMA_HOST not set to 0.0.0.0
3. Ollama service not running: `sudo systemctl status ollama`

### Slow Inference Despite GPU

**Check GPU usage:**
```bash
# On Nobara PC during inference:
nvidia-smi
```

**Expected:** GPU utilization 70-90%, VRAM usage ~5GB

**If GPU not used:**
- Driver issue: `nvidia-smi` should show driver version
- Ollama not detecting GPU: Check `journalctl -u ollama.service`

### Model Not Found
```bash
# On Nobara PC:
ollama list
# Should show llama3.1:8b

# If missing:
ollama pull llama3.1:8b
```

## Alternative Providers (Tested)

| Provider | Status | Notes |
|----------|--------|-------|
| Ollama (GPU) | ✅ Working | Local, fast, privacy-focused |
| Groq | ❌ Failed | No json_schema support |
| Gemini | ❌ Failed | /openai/ endpoint incompatible |
| OpenRouter | ⚠️ Untested | Should work (pay-per-use) |
| OpenAI | ⚠️ Untested | Expensive, requires API key |

## File Paths Reference
```
Karakeep (Proxmox LXC 106):
  - Config: /etc/karakeep/karakeep.env
  - Install: /opt/karakeep
  - Services: /etc/systemd/system/karakeep-*.service

Ollama (Nobara PC):
  - Binary: /usr/local/bin/ollama
  - Models: ~/.ollama/models (user) or /usr/share/ollama/.ollama/models (system)
  - Service: /etc/systemd/system/ollama.service
  - Override: /etc/systemd/system/ollama.service.d/override.conf
```

## Network Architecture
```
Internet → Proxmox Host (192.168.0.YOUR_PROXMOX_IP)
              ↓
          LXC 106: Karakeep (192.168.0.YOUR_KARAKEEP_IP)
              ↓ HTTP API Call
          Nobara PC (192.168.0.YOUR_PC_IP:11434)
              ↓ GPU Inference
          RTX 2060 Super → Fast AI Tagging
```

## Future Enhancements

**Hybrid fallback (optional):**
- Primary: Nobara PC (GPU-accelerated)
- Fallback: Proxmox CPU (if Nobara unavailable)
- Implementation: HAProxy with health checks

**Model upgrades:**
- Current: llama3.1:8b (4.9GB VRAM)
- Alternative: llama3.1:70b (requires quantization, ~40GB VRAM - not feasible)
- Alternative: llama3.2:3b (faster, lower quality)

## Conclusion

Remote GPU-accelerated Ollama provides:
- **Performance:** 5x faster inference vs CPU
- **Privacy:** No data sent to external APIs
- **Cost:** Zero ongoing API costs
- **Reliability:** Direct network communication

**Ideal for:**
- Gaming PC already running frequently
- Proxmox server resource optimization
- High-volume bookmark tagging workloads

---

**Date:** 2026-02-05  
**Hardware:**
- Proxmox: HP EliteDesk 800 G4 (i5-8400, 32GB RAM)
- Ollama: Nobara PC (RTX 2060 Super, 8GB VRAM)

**Software:**
- Proxmox: 8.x
- Nobara: Latest (Fedora-based)
- Ollama: 0.15.4+
- Karakeep: Latest
