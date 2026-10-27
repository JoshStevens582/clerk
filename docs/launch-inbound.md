# Launch: automatic patient email

Production target: **`clerk@customchatandautomation.co.za`** → Resend → Clerk → approve → SMTP reply.

## Server (VPS `/opt/clerk/.env`)

| Variable | Purpose |
|----------|---------|
| `SMTP_*` | Outbound via Resend (`smtp.resend.com`) |
| `RESEND_API_KEY` | Same value as `SMTP_PASSWORD`; must be **Full access** |
| `RESEND_WEBHOOK_SECRET` | From Resend webhook (`whsec_…`) |
| `CLERK_INBOUND_ADDRESS` | `clerk@customchatandautomation.co.za` |
| `CLERK_SEED_DEMO_INBOX` | `false` in production |
| `SMTP_FROM` | e.g. `Cape Town Physio <noreply@customchatandautomation.co.za>` |

Register webhook + update `.env` (key read from file, not echoed):

```bash
cd /opt/clerk
bash deploy/finish-launch.sh
docker compose -f docker-compose.yml -f deploy/compose.edge.yml up -d api
```

Clerk **polls** Resend ~every 45s when the API key has full access; the webhook is optional but recommended.

## Domain mail (domains.co.za)

Root MX is **TLD-MX** (`mx1.tld-mx.com`), not Resend. Forward into Resend:

1. **domains.co.za** → **Manage Services** → **Email Only Hosting** → **customchatandautomation.co.za** → **Login to cPanel**
2. **Email** → **Forwarders** → **Add Forwarder**
3. Address: `clerk` → domain `customchatandautomation.co.za` → forward to your **`@….resend.app`** (Resend → Emails → Receiving → ⋯ → Receiving address)
4. Test: Gmail → `clerk@customchatandautomation.co.za` → Resend **Receiving** → Clerk desk

## Health

`GET /api/health`:

- `inbound_automation_ready` — full-access key + inbound address
- `inbound_resend_api_full_access` — key can list received mail
- `inbound_webhook_configured` — webhook secret set
- `inbound_setup_note` — plain-English fix hint when something is missing

## Manual fallback

`POST /api/hooks/inbound` with header `X-Clerk-Inbound-Secret` (see `.env.example`).

Secret rotation: [rotate-secrets.md](rotate-secrets.md).
