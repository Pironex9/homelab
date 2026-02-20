

## Docker Compose Configuration

```yaml
services:
  suggestarr:
    image: ciuse99/suggestarr:latest
    container_name: suggestarr
    ports:
      - "5000:5000"
    environment:
      - TZ=Europe/Bratislava
      - LOG_LEVEL=info
      - SUGGESTARR_PORT=5000
    restart: unless-stopped
    volumes:
      - /srv/docker-data/suggestarr:/app/config/config_files
    networks:
      - arr_stack

networks:
  arr_stack:
    external: true
```

## File Paths

- **Config:** `/srv/docker-data/suggestarr/config.yaml`
- **Logs:** `/srv/docker-data/suggestarr/app.log`
- **Database:** `/srv/docker-data/suggestarr/requests.db`
- **Lock file:** `/srv/docker-data/suggestarr/.__app.lock`

## Web UI Setup

**Access:** `http://192.168.0.110:5000`

### Setup Wizard Configuration

#### 1. TMDb API Key
- Register: https://www.themoviedb.org/settings/api
- Copy API Key (v3 auth): `YOUR_TMDB_API_KEY`

#### 2. Media Server (Jellyfin)
- **Type:** Jellyfin
- **URL:** `http://192.168.0.110:8096`
- **API Token:** Get from Jellyfin Dashboard → API Keys
- **Libraries:** ⚠️ **MUST SELECT ALL** - do not leave empty (see Bug #1)

#### 3. Request Service (Jellyseerr)
- **Type:** Jellyseerr
- **URL:** `http://192.168.0.110:5055`
  - Docker network alternative: `jellyseerr:5055`
- **API Key:** From Jellyseerr Settings → General

#### 4. Schedule
- **Cron:** `0 12 * * *` (daily at noon)
- Examples:
  - `0 */6 * * *` - every 6 hours
  - `0 2 * * *` - daily 2 AM
  - `0 0 * * 0` - weekly Sunday midnight

#### 5. Content Settings
- **Max Similar Movies:** 5
- **Max Similar TV Shows:** 2
- **Content Checks:** 10
- **Search Size:** 20

#### 6. Filters
- **Languages:** Hungarian (hu), English (en)
- **Region Provider:** HU
- **Release Year:** From 1970 onwards
- **Genres to Exclude:** Horror, Sci-Fi, Fantasy (configurable)
- **Include No Rating:** true

#### 7. User Authentication (Optional)
- **User Email:** `your@email.com`
- **Password:** `YOUR_PASSWORD`
- Used to submit requests as specific user in Jellyseerr

#### 8. Advanced Settings
- **Base URL Subpath:** ⚠️ Leave EMPTY (causes issues if set)

---

## ⚠️ CRITICAL BUGS & FIXES

### Bug #1: Setup Wizard Library Selection

**Symptom:**
- "Next Step" button disabled during setup
- Browser console: `POST /api/config/complete-setup [HTTP/1.1 400 Bad Request]`
- Backend log: `'JELLYFIN_LIBRARIES': []`

**Cause:** UI text says "leave empty for all" but backend validation requires at least 1 library.

**Solution:**
1. Manually **select ALL Jellyfin libraries** in wizard
2. Do NOT leave selection empty despite UI hint
3. Known bug in SuggestArr v2.0+ (as of Feb 2026)

---

### Bug #2: Genre Exclude Duplication Crash ⚠️ CRITICAL

**Symptom:**
- Setup wizard completes successfully
- Force Run immediately fails with 500 Internal Server Error
- Logs show: `ERROR - Content automation process failed: 'int' object is not subscriptable`
- Error occurs after: `Retrieved X valid items in [Libraries]`

**Cause:** Setup wizard creates **duplicate** genre exclude entries in `config.yaml`:
```yaml
FILTER_GENRES_EXCLUDE:
- id: 27
  name: Horror
- id: 878
  name: Science Fiction
- id: 14
  name: Fantasy
- 27      # ❌ DUPLICATE INTEGER - causes crash!
- 14      # ❌ DUPLICATE INTEGER - causes crash!
- 878     # ❌ DUPLICATE INTEGER - causes crash!
```

When code tries to access `genre['id']` on a plain integer, Python raises:
```
TypeError: 'int' object is not subscriptable
```

**Fix:**
```bash
# 1. Edit config
nano /srv/docker-data/suggestarr/config.yaml

# 2. Find FILTER_GENRES_EXCLUDE section
# 3. Delete the duplicate plain integer entries (bottom 3 lines)
# 4. Keep ONLY the dict entries with id/name pairs

# Correct format:
FILTER_GENRES_EXCLUDE:
- id: 27
  name: Horror
- id: 878
  name: Science Fiction
- id: 14
  name: Fantasy
# NO plain integers below this!

# 5. Save and restart
docker restart suggestarr

# 6. Test Force Run
```

**Verification:**
```bash
# Check for duplicates
cat /srv/docker-data/suggestarr/config.yaml | grep -A 10 FILTER_GENRES_EXCLUDE

# Should see ONLY dict format entries, no plain integers
```

**Prevention:**
- After completing setup wizard, ALWAYS verify `config.yaml`
- Remove any plain integer entries in `FILTER_GENRES_EXCLUDE`
- This is a GUI bug in SuggestArr (as of Feb 2026)

---

## Operational Procedures

### Fresh Installation
```bash
docker stop suggestarr
rm -rf /srv/docker-data/suggestarr/*
docker start suggestarr

# Access http://192.168.0.110:5000
# Complete setup wizard
# CRITICAL: Check config.yaml for genre duplicates
# Fix if needed, restart, then test
```

### Post-Setup Verification Checklist
1. ✅ Setup wizard completed
2. ✅ `cat /srv/docker-data/suggestarr/config.yaml` - verify FILTER_GENRES_EXCLUDE has NO plain integers
3. ✅ `docker restart suggestarr` - restart after config verification
4. ✅ Force Run test - should complete without errors
5. ✅ Check Jellyseerr for new requests

### Manual Force Run Test
1. Navigate to Settings tab
2. Click "Force Run" button
3. Switch to Logs tab
4. Watch for:
   - ✅ `Initializing ContentAutomation`
   - ✅ `Retrieved X valid items in [Library]`
   - ✅ Process completes without errors
   - ❌ If `'int' object is not subscriptable` → Fix Bug #2

### Config Backup
```bash
# Before making changes
cp /srv/docker-data/suggestarr/config.yaml \
   /srv/docker-data/suggestarr/config.yaml.backup

# Restore if needed
cp /srv/docker-data/suggestarr/config.yaml.backup \
   /srv/docker-data/suggestarr/config.yaml
docker restart suggestarr
```

---

## Troubleshooting

### 400 Bad Request on Setup Complete
**Symptom:** Button clicks but nothing happens
**Solution:** See Bug #1 - select all libraries manually

### 'int' object is not subscriptable
**Symptom:** Force Run fails immediately after setup
**Solution:** See Bug #2 - fix genre exclude duplicates in config.yaml

### Jellyseerr Session Expired
**Symptom:** Authentication errors in logs
**Solution:** Re-run setup wizard, re-enter Jellyseerr credentials

### No Recommendations Generated
**Check:**
1. Users have watched content in Jellyfin
2. TMDb API key is valid
3. Jellyseerr is accessible
4. Libraries are properly selected
5. Content filters not too restrictive

### Container Won't Start
```bash
# Check logs
docker logs suggestarr

# Common issues:
# - Port 5000 already in use
# - Volume permission issues
# - Corrupt config.yaml (delete and re-setup)
```

### Port Conflict
```bash
# Find what's using port 5000
sudo ss -tlnp | grep 5000

# Change port in docker-compose.yml
ports:
  - "5001:5000"
```

---

## Integration URLs

- **SuggestArr:** http://192.168.0.110:5000
- **Jellyfin:** http://192.168.0.110:8096
- **Jellyseerr:** http://192.168.0.110:5055
- **Recommendarr:** http://192.168.0.110:3003

---

## Notes

- Automation runs on configured schedule (default: daily noon)
- Recommendations appear in Jellyseerr for approval
- Based on watched content from selected Jellyfin users
- Multi-user support via user selection in setup
- TMDb free tier: 20 req/10sec, 150k req/day

---

## Known Issues (Feb 2026)

1. **Library selection bug** - UI misleading, must select manually
2. **Genre exclude duplication** - GUI creates duplicate entries causing crash
3. **Base URL subpath** - Known to cause routing issues, leave empty
4. **Session token expiry** - Jellyseerr tokens expire, requires re-authentication

**Bug Reports:** Submit to https://github.com/ciuse99/suggestarr/issues
