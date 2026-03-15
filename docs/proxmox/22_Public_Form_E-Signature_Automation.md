**Date:** 2026-03-15
**Hostname:** docker-host
**IP address:** 192.168.0.110

# Public Form - E-Signature Automation

Self-hosted public web form that triggers an automated DocuSeal e-signature workflow. Visitors fill in their name and email, and receive a signing link by email - no account required on either side. Protected by Cloudflare Turnstile, honeypot field, and webhook header authentication.

---

## Overview

| Property | Value |
|----------|-------|
| Service | Caddy (static file server) |
| Image | `caddy:alpine` |
| Host | LXC 100 (docker-host) |
| Port | 3004 |
| Public URL | https://form.homelabor.net |
| Files | `compose/proxmox-lxc-100/form/html/index.html` |

### Architecture

```
form.homelabor.net (Caddy, port 3004)
  → user submits form (name, email)
  → JavaScript POST to n8n.homelabor.net/webhook/docuseal-form
      → n8n: Check Header Auth
      → n8n: Verify Turnstile (Cloudflare siteverify API)
      → n8n: Check Turnstile + honeypot
      → n8n: DocuSeal API (create submission)
      → DocuSeal: sends signing email to recipient
      → n8n: Telegram notification
```

---

## Prerequisites

### Cloudflare Turnstile Widget

1. Go to [dash.cloudflare.com](https://dash.cloudflare.com) - **Turnstile** - **Add site**
2. Settings:
   - Site name: `form.homelabor.net`
   - Hostname: `form.homelabor.net` (must match exactly - parent domain does not cover subdomains)
   - Widget type: **Managed**
   - Pre-clearance: **No** (site is DNS only, not Cloudflare proxied)
3. Note the **Site Key** (public, goes in HTML) and **Secret Key** (private, goes in n8n)

### Cloudflare DNS - form subdomain

```
Type: A
Name: form
IPv4: <VPS IP>
Proxy: DNS only (gray cloud)
TTL: Auto
```

### Cloudflare DNS - n8n subdomain

The n8n webhook must be publicly reachable for the form's JavaScript to call it:

```
Type: A
Name: n8n
IPv4: <VPS IP>
Proxy: DNS only (gray cloud)
TTL: Auto
```

### Pangolin Resources

**Form:**
- Name: `Form`
- Subdomain: `form`
- Target: `192.168.0.110:3004`
- Authentication: Disabled (public form)

**n8n webhook:**
- Name: `n8n`
- Subdomain: `n8n`
- Target: `192.168.0.112:5678`
- Authentication: Disabled (webhook validates requests internally)

---

## Docker Compose

File: `compose/proxmox-lxc-100/form/docker-compose.yml`

```yaml
services:
  form:
    image: caddy:alpine
    container_name: form
    volumes:
      - ./html:/usr/share/caddy
    ports:
      - 3004:80
    restart: unless-stopped
```

No environment variables or secrets needed - Caddy just serves the static `html/` directory.

---

## HTML Form

File: `compose/proxmox-lxc-100/form/html/index.html`

Features:
- EN/HU language toggle (top right corner, default English)
- Name + email fields
- Consent checkbox
- Cloudflare Turnstile widget (invisible bot protection)
- Honeypot field (hidden from real users, CSS-positioned off-screen)
- Submits via JavaScript `fetch` to the n8n webhook

The Turnstile site key is embedded in the HTML (it is public by design). The webhook header token is also embedded in the HTML - it provides scanner noise reduction but is not a secret since the HTML source is publicly visible.

---

## n8n Workflow

Workflow: **DocuSeal - Form to E-Signature** (LXC 107, n8n)

### Flow

```
Webhook Form (POST /webhook/docuseal-form)
  → Check Header Auth (IF: X-Form-Token header matches)
      false → Respond 401 Unauthorized
  → Verify Turnstile (HTTP POST to Cloudflare siteverify API)
  → Check Turnstile (IF: success=true AND honeypot field empty)
      false → Respond 400 Invalid request
  → Send to DocuSeal (HTTP POST to DocuSeal API)
  → Telegram Notification + Respond 200 OK
```

### Webhook node

- Path: `docuseal-form`
- Method: POST
- Response mode: Response node (custom response per branch)
- CORS: `allowedOrigins: *`

### Check Header Auth node

IF node checking the `x-form-token` header value. Rejects scanner noise and drive-by requests. Not a real secret (visible in HTML source) but raises the bar above zero.

### Verify Turnstile node

HTTP Request to `https://challenges.cloudflare.com/turnstile/v0/siteverify`:

```json
{
  "secret": "<Turnstile secret key - stored in node>",
  "response": "{{ $('Webhook Form').item.json.body.turnstileToken }}"
}
```

Cloudflare returns `{ "success": true/false, ... }`.

### Check Turnstile node

IF node with two conditions (AND):
1. `{{ $json.success }}` is `true`
2. `{{ $('Webhook Form').item.json.body.website }}` equals `""` (honeypot empty)

### Send to DocuSeal node

- `POST https://sign.homelabor.net/api/submissions`
- Header: `X-Auth-Token` (DocuSeal API key from Settings - API)
- Body: `template_id`, `submitters` array with `name`, `email`, `role: "First Party"`
- Template ID 3 by default - change to use a different template

---

## Security Layers

| Layer | What it stops | Notes |
|-------|---------------|-------|
| Cloudflare Turnstile | Automated bots, headless scrapers | Primary protection - free, invisible |
| Honeypot field | Simple HTML-parsing bots | Zero UX impact |
| Webhook header token | Random URL scanners | Not a real secret - visible in HTML |

Turnstile tokens are single-use and expire after 5 minutes. The Cloudflare siteverify API is called server-side from n8n (CORS blocks browser-side calls), so the Turnstile secret key never reaches the browser.

---

## Port Reference

Port 3004 was chosen because:
- 3000 - BentoPDF
- 3001 - Uptime Kuma
- 3002 - Homepage
- 3003 - DocuSeal

Check for conflicts: `ss -tlnp | grep 300`

---

## Troubleshooting

### Form submits but no signing email arrives

1. Check n8n execution log - did the workflow trigger?
2. Check the Verify Turnstile node output - `success` must be `true`
3. If Turnstile fails: token may have expired (5 min limit) or been reused
4. If DocuSeal node fails: check the API key and template ID
5. See [DocuSeal troubleshooting](20_DocuSeal_E-Signature_Setup.md#troubleshooting) for email delivery issues

### Webhook returns 404

The n8n webhook is not registered in memory despite the workflow being active. Fix:

```bash
N8N_KEY=$(cat ~/.secrets/n8n-api-key)
curl -X POST "http://192.168.0.112:5678/api/v1/workflows/lAfEe7g7cWJjCLSA/deactivate" \
  -H "X-N8N-API-KEY: $N8N_KEY"
sleep 3
curl -X POST "http://192.168.0.112:5678/api/v1/workflows/lAfEe7g7cWJjCLSA/activate" \
  -H "X-N8N-API-KEY: $N8N_KEY"
```

This happens when a full workflow update via MCP resets the internal webhook registration. Always deactivate/reactivate after structural workflow changes.

### Webhook returns 401

The `X-Form-Token` header is missing or incorrect. The form HTML must include the correct token value in the fetch call.

### Turnstile widget not appearing

- Check browser console for JS errors
- Verify the site key in the HTML matches the Turnstile widget's site key
- Ensure the registered hostname in Cloudflare Turnstile matches exactly (`form.homelabor.net`, not `homelabor.net`)
