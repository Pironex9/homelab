**Date:** 2026-03-15
**Hostname:** docker-host
**IP address:** 192.168.0.110

# Public Form - E-Signature Automation

Self-hosted public web form that triggers an automated DocuSeal e-signature workflow. Visitors fill in their name and email, and receive a signing link by email - no account required on either side. Protected by Cloudflare Turnstile, honeypot field, and webhook header authentication.

---

## Overview

| Property | Value |
|----------|-------|
| Service | Caddy (static file server + reverse proxy) |
| Image | `caddy:alpine` |
| Host | LXC 100 (docker-host) |
| Port | 3004 |
| Public URL | https://form.homelabor.net |
| Files | `compose/proxmox-lxc-100/form/` |

### Architecture

```
form.homelabor.net (Caddy, port 3004)
  → user submits form (name, email)
  → JavaScript POST to /api/submit (same-origin - no CORS)
      → Caddy adds X-Form-Token header, proxies to n8n internally:
          192.168.0.112:5678/webhook/docuseal-form
      → n8n: Check Header Auth
      → n8n: Verify Turnstile (Cloudflare siteverify API)
      → n8n: Check Turnstile + honeypot
      → n8n: DocuSeal API (create submission, pre-fill fields)
      → DocuSeal: sends signing email to recipient
      → n8n: Telegram notification
```

Caddy acts as both a static file server and a reverse proxy. The form submits to `/api/submit` on the same domain - no cross-origin requests. Caddy adds the webhook secret header server-side before forwarding to n8n, so the secret never appears in the HTML source.

---

## Prerequisites

### Cloudflare Turnstile Widget

1. Go to [dash.cloudflare.com](https://dash.cloudflare.com) - **Turnstile** - **Add site**
2. Settings:
   - Site name: `form.homelabor.net`
   - Hostname: `form.homelabor.net` (must match exactly - parent domain does not cover subdomains)
   - Widget type: **Managed**
   - Pre-clearance: **No** (site is DNS only, not Cloudflare proxied)
3. Note the **Site Key** (public, goes in HTML) and **Secret Key** (private, goes in n8n Verify Turnstile node)

### Cloudflare DNS - form subdomain

```
Type: A
Name: form
IPv4: <VPS IP>
Proxy: DNS only (gray cloud)
TTL: Auto
```

### Pangolin Resource

- Name: `Form`
- Subdomain: `form`
- Target: `192.168.0.110:3004`
- Authentication: Disabled (public form)

Note: n8n does not need a separate Pangolin resource. The form's JavaScript calls `/api/submit` on the same domain, and Caddy proxies the request to n8n on the internal LAN.

---

## Docker Compose

File: `compose/proxmox-lxc-100/form/docker-compose.yml`

```yaml
services:
  form:
    image: caddy:alpine
    container_name: form
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - ./html:/usr/share/caddy
    ports:
      - 3004:80
    restart: unless-stopped
```

---

## Caddyfile

File: `compose/proxmox-lxc-100/form/Caddyfile`

```
:80 {
    handle /api/submit {
        rewrite * /webhook/docuseal-form
        reverse_proxy http://192.168.0.112:5678 {
            header_up X-Form-Token "{env.FORM_TOKEN}"
        }
    }

    handle {
        root * /usr/share/caddy
        file_server
    }
}
```

- `/api/submit` - rewrites the path and proxies to n8n with the secret header added
- Everything else - served as static files from `html/`
- The token is injected from the `FORM_TOKEN` environment variable - set it in Komodo Stack Environment, never commit it to git

---

## HTML Form

File: `compose/proxmox-lxc-100/form/html/index.html`

Features:
- EN/HU language toggle (top right corner, default English)
- Full name, email address, phone number fields
- Consent checkbox
- Cloudflare Turnstile widget (bot protection)
- Honeypot field (hidden from real users, CSS off-screen)
- Submits via JavaScript `fetch` to `/api/submit` (same-origin)

The Turnstile site key is embedded in the HTML (it is public by design). The webhook header token is NOT in the HTML - it is added by Caddy server-side.

---

## DocuSeal Template

Template ID: 9

### Signing workflow

The Provider (operator) signs the document once in advance using DocuSeal's "Sign Yourself" feature, then downloads the signed PDF and uploads it as a new template. This means every client receives a document that already contains the Provider's signature - no waiting for the Provider to sign each submission.

Steps to set up a new pre-signed template:
1. Upload the PDF to DocuSeal - Templates - New Template
2. In the template editor, place the fields and add both roles (Provider + Client)
3. Click **Sign Yourself** and complete the Provider signature
4. Download the signed PDF
5. Upload the signed PDF as a new template (Client fields only - no Provider signature field needed)
6. Update the template ID in the n8n Send to DocuSeal node

### Fields in the template

Set up in the DocuSeal template editor (field names are case-sensitive):

| Field name | Type | Filled by |
|------------|------|-----------|
| Signature | Signature | Client (signer) |
| Full Name | Text | Pre-filled from form, readonly |
| Email | Text | Pre-filled from form, readonly |
| Phone Number | Text | Pre-filled from form, readonly |
| Date | Date | Pre-filled with submission date, readonly |

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

### Check Header Auth node

IF node checking the `x-form-token` header value. The token is added by Caddy, not the browser - it is a genuine secret.

### Verify Turnstile node

HTTP Request to `https://challenges.cloudflare.com/turnstile/v0/siteverify`:

```json
{
  "secret": "<Turnstile secret key>",
  "response": "{{ $('Webhook Form').item.json.body.turnstileToken }}"
}
```

### Check Turnstile node

IF node with two conditions (AND):
1. `{{ $json.success }}` is `true`
2. `{{ $('Webhook Form').item.json.body.website }}` equals `""` (honeypot empty)

### Send to DocuSeal node

```json
{
  "template_id": 9,
  "submitters": [{
    "name": "<from form>",
    "role": "First Party",
    "email": "<from form>",
    "fields": [
      { "name": "Full Name",    "default_value": "<from form>", "readonly": true },
      { "name": "Email",        "default_value": "<from form>", "readonly": true },
      { "name": "Phone Number", "default_value": "<from form>", "readonly": true },
      { "name": "Date",         "default_value": "<today YYYY-MM-DD>", "readonly": true }
    ]
  }]
}
```

The `Date` field is set to `new Date().toISOString().split('T')[0]` at submission time.

---

## Security Layers

| Layer | What it stops | Notes |
|-------|---------------|-------|
| Cloudflare Turnstile | Automated bots, headless scrapers | Primary protection - free, invisible |
| Honeypot field | Simple HTML-parsing bots | Zero UX impact |
| Webhook header token | Random URL scanners + unauthorized callers | Genuine secret - added by Caddy, not visible in HTML |

Turnstile tokens are single-use and expire after 5 minutes. The Cloudflare siteverify API is called from n8n (CORS blocks browser-side calls), so the Turnstile secret key never reaches the browser.

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
5. See [DocuSeal troubleshooting](19_DocuSeal_E-Signature_Setup.md#troubleshooting) for email delivery issues

### Form returns "no available server" or Caddy won't start

Check container logs: `docker logs form`

Common cause: syntax error in Caddyfile. Note that Caddy's `reverse_proxy` only accepts `scheme://host:port` as upstream - paths are not allowed. Use `rewrite` to set the target path before the `reverse_proxy` directive.

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

The `X-Form-Token` header is missing or wrong. Check the value in the Caddyfile matches what the n8n Check Header Auth node expects.

### Turnstile widget not appearing

- Check browser console for JS errors
- Verify the site key in the HTML matches the Turnstile widget's site key
- Ensure the registered hostname in Cloudflare Turnstile matches exactly (`form.homelabor.net`, not `homelabor.net`)

### Document fields not pre-filled

- Field names in the n8n `fields` array must match exactly what is set in the DocuSeal template editor (case-sensitive)
- Current fields: `Full Name`, `Email`, `Phone Number`, `Date`
