**Date:** 2026-03-12
**Hostname:** docker-host
**IP address:** 192.168.0.110

# DocuSeal E-Signature Setup

Self-hosted e-signature platform. Allows sending documents to recipients who sign them in the browser - no account or software required on the recipient's side. Built on the eIDAS simple electronic signature (SES) standard.

---

## Overview

| Property | Value |
|----------|-------|
| Service | DocuSeal |
| Image | `docuseal/docuseal:latest` |
| Host | LXC 100 (docker-host) |
| Port | 3003 |
| Public URL | https://sign.homelabor.net |
| Data | `/srv/docker-data/docuseal` |
| SMTP relay | Brevo (smtp-relay.brevo.com) |

---

## Prerequisites

### Brevo SMTP Account

DocuSeal requires an SMTP relay to send signing invitation emails to recipients.

1. Register at [brevo.com](https://brevo.com)
2. Go to **Senders & IPs -> Domains** and authenticate your domain:
   - Select "Authenticate the domain yourself"
   - Add the 4 DNS records to Cloudflare (Brevo code TXT, DKIM 1 CNAME, DKIM 2 CNAME, DMARC TXT)
   - All records must use **DNS only** (gray cloud) proxy status
   - Wait for "Authenticated" status
3. Go to **SMTP & API -> SMTP** and generate a new **Standard** SMTP key
4. Note the SMTP credentials:
   - Server: `smtp-relay.brevo.com`
   - Port: `587`
   - Login: `xxxxxx@smtp-brevo.com` (displayed on the SMTP page)
   - Password: the generated API key

### Cloudflare DNS

Add an A record for the signing subdomain:

```
Type: A
Name: sign
IPv4: YOUR_VPS_IP
Proxy status: DNS only (gray cloud)
TTL: Auto
```

### Pangolin Resource

Create a new resource in Pangolin dashboard:

- Name: DocuSeal
- Subdomain: `sign`
- Target: `192.168.0.110:3003`
- Authentication: Disabled (signing links must be publicly accessible)

---

## Docker Compose

File: `compose/proxmox-lxc-100/docuseal/docker-compose.yml`

```yaml
services:
  docuseal:
    image: docuseal/docuseal:latest
    container_name: docuseal
    environment:
      - TZ=Europe/Budapest
      - SECRET_KEY_BASE=${DOCUSEAL_SECRET_KEY}
      - SMTP_ADDRESS=${SMTP_ADDRESS}
      - SMTP_PORT=${SMTP_PORT}
      - SMTP_USERNAME=${SMTP_USERNAME}
      - SMTP_PASSWORD=${SMTP_PASSWORD}
      - SMTP_FROM=${SMTP_FROM}
    volumes:
      - /srv/docker-data/docuseal:/data
    ports:
      - 3003:3000
    restart: unless-stopped
```

---

## Komodo Stack Environment

Set the following in Komodo Stack Environment (not in the compose file):

```
DOCUSEAL_SECRET_KEY=<output of: openssl rand -hex 32>
SMTP_ADDRESS=smtp-relay.brevo.com
SMTP_PORT=587
SMTP_USERNAME=<login from Brevo SMTP page>
SMTP_PASSWORD=<generated Brevo SMTP key>
SMTP_FROM=noreply@homelabor.net
```

Note: DocuSeal requires `SMTP_FROM` specifically - `SMTP_FROM_EMAIL` is not recognized by its mail interceptor.

---

## Initial Setup

1. Deploy via Komodo
2. Open https://sign.homelabor.net/setup
3. Fill in:
   - First name, Last name, Email, Company name
   - Password (this is the admin login)
   - App URL: `https://sign.homelabor.net` (auto-filled)
4. Skip the developer newsletter prompt

---

## Signing Workflow

### Sending a document for signing

1. Go to https://sign.homelabor.net
2. **Upload a New Document** - drag and drop a PDF
3. In the template editor, drag a **Signature** field onto the document where the recipient should sign
4. Click **Send** - enter the recipient's name and email
5. The recipient gets an email with a signing link

### Recipient experience

1. Recipient clicks the link in the email
2. Opens in browser - no account or software needed
3. Clicks the signature field, draws or types their signature
4. Submits - gets a completion confirmation

### After signing

- You receive a notification email (if enabled in Settings -> Notifications)
- The signed PDF with audit trail is available in the DocuSeal dashboard
- Audit trail includes: signer name, email, IP address, timestamp, completion certificate

---

## Troubleshooting

### Email not received

If DocuSeal says sent but no email arrives:

1. Check spam folder
2. Check Brevo dashboard -> Transactional -> Logs
3. Verify SMTP env vars in container: `docker exec docuseal printenv | grep SMTP`
4. Test SMTP connectivity: `docker exec docuseal sh -c 'nc -zv smtp-relay.brevo.com 587'`
5. Common mistake: using `SMTP_FROM_EMAIL` instead of `SMTP_FROM` - DocuSeal's interceptor only reads `SMTP_FROM`

### Sign button not visible on signing page

The submission was created before a signature field was added to the template. Delete the submission and send a new one.

### Port conflict on deploy

Port 3003 was chosen because:
- 3000 - BentoPDF
- 3002 - Homepage

Check for conflicts: `ss -tlnp | grep 300`

---

## Notes

- DocuSeal uses SQLite by default - no separate database container needed
- Data is persisted at `/srv/docker-data/docuseal`
- eIDAS level: Simple Electronic Signature (SES) - legally valid for most business purposes, but not equivalent to QES (qualified) which requires a certified CA
- Authentication on the Pangolin resource must remain disabled so signing links work for external recipients without a Pangolin account
