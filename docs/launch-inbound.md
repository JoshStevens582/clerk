# Launch: automatic patient email (Resend)

Clerk is launch-ready when **outbound** (SMTP) and **inbound** (Resend receiving) are configured.

## 1. Outbound (already on VPS if Atlas sends mail)

In `/opt/clerk/.env`:

- `SMTP_HOST=smtp.resend.com`
- `SMTP_USERNAME=resend`
- `SMTP_PASSWORD=` your Resend API key (`re_…`)
- `SMTP_FROM=` e.g. `Cape Town Physio <noreply@customchatandautomation.co.za>`

Desk shows **SMTP ready**.

## 2. Inbound address

Choose an address on your verified domain, e.g.:

`clerk@customchatandautomation.co.za`

Set in `/opt/clerk/.env`:

```env
CLERK_INBOUND_ADDRESS=clerk@customchatandautomation.co.za
RESEND_API_KEY=re_…   # same as SMTP password if using Resend
CLERK_SEED_DEMO_INBOX=false   # optional: hide demo samples in production
```

Forward or MX-route practice mail to this address (see Resend **Receiving** docs).

## 3. Resend dashboard

1. **Domains** → enable **Receiving** for `customchatandautomation.co.za` (MX records Resend provides).
2. **Webhooks** → Add webhook:
   - URL: `https://agent.customchatandautomation.co.za/api/hooks/resend`
   - Event: **`email.received`**
   - Copy the **signing secret** (`whsec_…`) into `/opt/clerk/.env`:

```env
RESEND_WEBHOOK_SECRET=whsec_…
```

3. Restart API:  
   `docker compose -f docker-compose.yml -f deploy/compose.edge.yml up -d api`

4. Test: `GET https://agent.customchatandautomation.co.za/api/hooks/resend/health` → OK.

Send a test email **to** `clerk@…`. Within a minute:

- Desk pill **inbound automation** should be ready.
- **Needs your approval** or **Sent** updates without using **Add inbound message**.

## 4. Staff workflow (production)

1. Sign in at `https://agent.customchatandautomation.co.za`
2. Patient emails `clerk@…` → Clerk runs automatically.
3. **Needs your approval** (left) → **Approve** or **Reject**.
4. **Sent** (right) → **Delivered via SMTP**.

**Add inbound message** = manual fallback only.

## 5. OpenAI

Set `OPENAI_API_KEY` in `/opt/clerk/.env` for real patient wording (not demo `sample_id` routes). Demo samples work without it.
