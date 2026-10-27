# Rotate Clerk secrets (after exposure)

Do this on the **VPS in SSH**. Do **not** paste new secrets into chat.

## 1. Resend

1. [Resend → API Keys](https://resend.com/api-keys): **revoke/delete** every old Clerk key.
2. Create one new key: **Full access**.
3. [Resend → Webhooks](https://resend.com/webhooks): delete webhooks pointing at Clerk if you want a clean slate (optional).

## 2. Server `.env`

```bash
ssh -i ~/.ssh/id_ed25519_atlas root@102.203.81.249
cd /opt/clerk
nano .env
```

Update (same new `re_…` on both mail lines):

- `RESEND_API_KEY=`
- `SMTP_PASSWORD=`

Generate a new inbound hook secret (run on server, copy output into nano):

```bash
openssl rand -hex 32
```

Set:

- `CLERK_INBOUND_WEBHOOK_SECRET=` (paste the hex from above)

Save: **Ctrl+O**, Enter, **Ctrl+X**.

## 3. Webhook + Resend env (one shot)

```bash
cd /opt/clerk
echo "Paste NEW Full access re_ key, then Enter:"
read -r RESEND_FULL_ACCESS_KEY
docker run --rm -v /opt/clerk/.env:/opt/clerk/.env \
  -v /opt/clerk/scripts/resend_setup_inbound.py:/app/scripts/resend_setup_inbound.py \
  -e RESEND_FULL_ACCESS_KEY="$RESEND_FULL_ACCESS_KEY" \
  -e CLERK_ENV_FILE=/opt/clerk/.env \
  clerk-api python /app/scripts/resend_setup_inbound.py
docker compose -f docker-compose.yml -f deploy/compose.edge.yml up -d api
```

## 4. Clerk auth (forces everyone to sign in again)

Optional but good if you want a clean break:

```bash
openssl rand -hex 32
```

Set `CLERK_AUTH_SECRET=` in `.env` to that value, restart API. All staff must log in again.

## 5. Staff passwords

In the Clerk desk: **People** (manager) → reset passwords / re-invite as you prefer.

## 6. Verify

Open https://agent.customchatandautomation.co.za/api/health — `inbound_resend_api_full_access` should be `true`.

Send a test to your `@….resend.app` address again.
