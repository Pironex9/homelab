
## Docker Compose Configuration

```yaml
services:
  recommendarr:
    image: qdread/recommendarr:latest
    container_name: recommendarr
    ports:
      - "3003:3000"
    restart: unless-stopped
    volumes:
      - /srv/docker-data/recommendarr:/data
    networks:
      - arr_stack

networks:
  arr_stack:
    external: true
```

## File Paths

- **Data Directory:** `/srv/docker-data/recommendarr/`
- **Storage/DB:** `/srv/docker-data/recommendarr/storage/` (auto-created)

## Initial Setup

### Default Credentials
```
Username: admin
Password: 1234
```

⚠️ **CRITICAL:** Change password immediately after first login!

**Access:** `http://192.168.0.YOUR_DOCKER_IP:3003`

---

## Configuration Steps

### 1. Ollama LLM Configuration

#### Ollama Service Setup (Nobara PC)

**Prerequisites:**
- Ollama installed on Nobara: `http://192.168.0.YOUR_PC_IP:11434`
- GPU: RTX 2060 SUPER (8GB VRAM)

**Required: Enable CORS for Browser Access**

```bash
# On Nobara PC
sudo systemctl edit ollama
```

**Add:**
```ini
[Service]
Environment="OLLAMA_ORIGINS=*"
```

**Save and restart:**
```bash
sudo systemctl daemon-reload
sudo systemctl restart ollama
```

**Verify CORS:**
```bash
# Should return Access-Control-Allow-Origin: *
curl -I -H "Origin: http://192.168.0.YOUR_DOCKER_IP:3003" http://localhost:11434/v1/models

# Test from LXC
curl http://192.168.0.YOUR_PC_IP:11434/v1/models
```

#### Recommendarr LLM Settings

1. Navigate to Settings → AI Settings
2. **API URL:** `http://192.168.0.YOUR_PC_IP:11434/v1`
3. **API Key:** Leave empty (local Ollama doesn't need key)
4. Click **Fetch Available Models**
5. **Select Model:** 
   - `qwen2.5:7b` (recommended for 8GB VRAM) ✅
   - `llama3.2:3b` (faster, smaller)
   - `mistral:7b` (alternative)
   - ❌ NOT `nomic-embed-text` (embedding-only, won't work for generation)

**Model Selection for RTX 2060 SUPER (8GB VRAM):**
- **Best performance:** `qwen2.5:7b` (36-40 tokens/s, better reasoning)
- **Fastest:** `llama3.2:3b` (50+ tokens/s)
- **Alternative:** `mistral:7b` (~40 tokens/s)
- **Avoid:** `llama3.1:8b` (too large, only 7-9 tokens/s, 80% VRAM)

**Pull models on Nobara:**
```bash
ollama pull qwen2.5:7b
ollama pull llama3.2:3b

# Verify
ollama list

# Test generation
ollama run qwen2.5:7b "Hello, test"
```

**GPU Verification:**
```bash
# Monitor GPU during generation
watch -n 1 nvidia-smi
```

---

### 2. Sonarr v4 Integration

**Problem:** Sonarr v4 **forces authentication**, "None" mode no longer valid.

**Failed Solutions:**
- Setting `<AuthenticationMethod>None</AuthenticationMethod>` - UI overrides on restart
- "Disabled for Local Addresses" - Docker IPs not considered local

**Working Solution: External Authentication Mode**

```bash
# Stop Sonarr
docker stop sonarr

# Edit config
nano /srv/docker-data/sonarr/config.xml
```

**Find and change:**
```xml
<AuthenticationMethod>Basic</AuthenticationMethod>
```

**To:**
```xml
<AuthenticationMethod>External</AuthenticationMethod>
```

**Restart and verify:**
```bash
docker start sonarr

# Verify
curl http://192.168.0.YOUR_DOCKER_IP:8989/api/v3/system/status \
  -H "X-Api-Key: YOUR_SONARR_API_KEY" | grep authentication

# Should return: "authentication": "external"
```

⚠️ **Security Warning:** External mode **completely disables** Sonarr authentication. Only safe on isolated local networks. Do NOT expose to internet!

#### Recommendarr Sonarr Settings

1. Navigate to Settings → Services
2. **Sonarr URL:** `http://192.168.0.YOUR_DOCKER_IP:8989`
3. **API Key:** Get from Sonarr Settings → General → Security
4. **Save**
5. Test connection - should work without auth errors

---

### 3. Radarr Integration (if used)

**Same pattern as Sonarr:**
```bash
docker stop radarr
nano /srv/docker-data/radarr/config.xml
# Change to External auth
docker start radarr
```

**Recommendarr Radarr Settings:**
- **URL:** `http://192.168.0.YOUR_DOCKER_IP:7878`
- **API Key:** From Radarr Settings → General → Security

---

### 4. Jellyfin Integration

**Recommendarr Jellyfin Settings:**
- **URL:** `http://192.168.0.YOUR_DOCKER_IP:8096`
- **API Key:** Jellyfin Dashboard → API Keys → Create New

**Usage:**
- Fetches watch history for generating recommendations
- Uses user activity to personalize suggestions

---

## ⚠️ CRITICAL BUGS & FIXES

### Bug #1: CORS Error - Cannot Connect to Ollama

**Symptom:**
- Browser error: `Failed to connect to LLM server at http://192.168.0.YOUR_PC_IP:11434/v1. Network Error`
- Console: `CORS policy: No 'Access-Control-Allow-Origin' header`
- Fetch Available Models button fails
- `curl` from host works, but browser blocks

**Cause:** Ollama default config doesn't allow cross-origin requests from browser.

**Solution:** See Ollama CORS Configuration section above.

---

### Bug #2: Sonarr v4 Authentication Bypass

**Symptom:**
- 401 Unauthorized errors when connecting to Sonarr
- API key works in `curl` but not in Recommendarr
- Sonarr UI forces authentication method selection

**Solution:** See Sonarr v4 Integration section above (External auth mode).

---

### Bug #3: Session/Storage Corruption

**Symptoms:**
- "Invalid or expired session" errors (401)
- 500 Internal Server Error on all settings saves
- "Unsupported protocol ttp:" (missing 'h' in URLs)
- Cannot save credentials or settings
- UI becomes unresponsive

**Cause:** Corrupt Recommendarr storage/database files.

**Solution: Reset Storage**
```bash
# Nuclear option - wipes all settings
docker stop recommendarr
rm -rf /srv/docker-data/recommendarr/*
docker start recommendarr

# Fresh browser tab (hard refresh: Ctrl+Shift+R)
# Login again (admin/1234)
# Reconfigure all services
```

**Prevention:**
- Ensure URLs are correct (`http://` not `ttp://`)
- Don't spam save button repeatedly
- Wait for saves to complete before navigating away

---

### Bug #4: Wrong Model Selected

**Symptom:**
- Recommendations fail to generate
- Errors about model incompatibility
- No output from LLM

**Cause:** Selected `nomic-embed-text` or other embedding-only model.

**Solution:**
- Embedding models (e.g., `nomic-embed-text`) **cannot generate text**
- Select a **generative model**:
  - ✅ `qwen2.5:7b`
  - ✅ `llama3.2:3b`
  - ✅ `mistral:7b`
  - ❌ NOT `nomic-embed-text`

---

## Operational Procedures

### Generate Recommendations

1. Navigate to Recommendations tab
2. Select user (if multi-user setup)
3. Click "Generate Recommendations"
4. Wait for LLM processing (GPU: 10-30 seconds)
5. Review generated suggestions
6. Click "Request in Sonarr/Radarr" to add

### Performance Monitoring

**GPU Usage (Nobara):**
```bash
# Real-time monitoring
watch -n 1 nvidia-smi

# Check Ollama process
ps aux | grep ollama

# If GPU not utilized - model might be CPU-only
# Re-pull model to force GPU: ollama pull qwen2.5:7b
```

**Ollama Process Management:**
```bash
# If Ollama consuming excessive resources
systemctl restart ollama

# Or kill runner processes
kill -9 $(pgrep -f ollama)
systemctl restart ollama
```

### Session Management

**If session expires:**
1. Logout
2. Login again (admin + password)
3. Settings should persist (unless storage corrupted)

**If settings lost:**
- Storage corruption likely (Bug #3)
- Reset storage and reconfigure

---

## Troubleshooting

### Cannot Fetch Ollama Models

**Check:**
1. Ollama service running: `systemctl status ollama`
2. CORS enabled: `sudo systemctl cat ollama` - check for OLLAMA_ORIGINS
3. Network connectivity: `curl http://192.168.0.YOUR_PC_IP:11434/v1/models`
4. Firewall: `sudo firewall-cmd --list-all` (if enabled)

**Fix:**
```bash
# Restart Ollama with CORS
sudo systemctl restart ollama

# Verify
curl -I -H "Origin: http://192.168.0.YOUR_DOCKER_IP:3003" \
  http://192.168.0.YOUR_PC_IP:11434/v1/models | grep Access-Control
```

### Sonarr Connection Failed

**Check:**
1. Sonarr running: `docker ps | grep sonarr`
2. Auth mode: `grep AuthenticationMethod /srv/docker-data/sonarr/config.xml`
3. API key valid: `curl http://192.168.0.YOUR_DOCKER_IP:8989/api/v3/system/status -H "X-Api-Key: KEY"`

**Fix:**
- Set External auth mode (see Bug #2)
- Verify API key copied correctly
- Test connection from Recommendarr Settings

### Recommendations Not Generating

**Check:**
1. Ollama model selected (not embedding model)
2. GPU being utilized: `nvidia-smi`
3. Jellyfin watch history exists for user
4. LLM accessible: `curl http://192.168.0.YOUR_PC_IP:11434/v1/models`

**Debug:**
```bash
# Recommendarr logs
docker logs recommendarr -f

# Ollama logs
journalctl -u ollama -f

# Test generation manually
ollama run qwen2.5:7b "Recommend movies similar to Inception"
```

### 500 Internal Server Errors

**Likely:** Storage corruption (Bug #3)

**Solution:**
```bash
docker stop recommendarr
rm -rf /srv/docker-data/recommendarr/*
docker start recommendarr
# Reconfigure
```

### Container Won't Start

```bash
# Logs
docker logs recommendarr

# Common issues:
# - Port 3003 conflict: change to 3004:3000
# - Volume permissions
# - Corrupt storage (rm -rf and restart)
```

---

## Integration URLs

- **Recommendarr:** http://192.168.0.YOUR_DOCKER_IP:3003
- **Ollama (Nobara):** http://192.168.0.YOUR_PC_IP:11434
- **Sonarr:** http://192.168.0.YOUR_DOCKER_IP:8989
- **Radarr:** http://192.168.0.YOUR_DOCKER_IP:7878
- **Jellyfin:** http://192.168.0.YOUR_DOCKER_IP:8096
- **SuggestArr:** http://192.168.0.YOUR_DOCKER_IP:5000

---

## Performance Notes

### GPU vs CPU (Ollama)

**RTX 2060 SUPER (8GB VRAM):**
- qwen2.5:7b: 36-40 tokens/s ✅
- llama3.2:3b: 50+ tokens/s ✅
- llama3.1:8b: 7-9 tokens/s ❌ (too slow, 80% VRAM)

**CPU-only (Proxmox LXC):**
- Any 7B+ model: <5 tokens/s ❌ (unusable)

**Recommendation:** Always use GPU for LLM inference.

---

## Known Issues (Feb 2026)

1. **CORS requirement** - Ollama needs explicit CORS configuration for browser access
2. **Sonarr v4 auth** - Forces authentication, External mode only workaround
3. **Storage corruption** - UI/settings can become corrupted, requires reset
4. **Session expiry** - Periodic logouts, no permanent session option
5. **Model confusion** - Embedding models don't work for generation

**Bug Reports:** Submit to https://github.com/qdread/recommendarr/issues

---

## Advanced Configuration

### Multi-User Setup
- Configure multiple Jellyfin users
- Generate personalized recommendations per user
- Separate watch histories analyzed

### Custom Prompts (if supported)
- Modify LLM prompt templates
- Adjust recommendation criteria
- Fine-tune generation parameters

### Backup Strategy
```bash
# Backup settings (before making changes)
cp -r /srv/docker-data/recommendarr /srv/docker-backups/recommendarr-$(date +%Y%m%d)

# Restore
docker stop recommendarr
rm -rf /srv/docker-data/recommendarr
cp -r /srv/docker-backups/recommendarr-YYYYMMDD /srv/docker-data/recommendarr
docker start recommendarr
```
