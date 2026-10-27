# Clerk behind Atlas Caddy

Clerk shares the same VPS and `cca-edge` Docker network as Atlas and Counter.

## DNS

Create an **A** record:

- `agent.customchatandautomation.co.za` → `102.203.81.249`

## Server steps

1. `docker network create cca-edge` (once per VPS).
2. Clone to `/opt/clerk`, copy `.env.example` to `.env`, set:
   - `OPENAI_API_KEY`
   - `OWNER_PASSWORD` (strong; not the demo default)
   - `SESSION_SECRET` (long random string)
   - `CORS_ORIGINS` empty (same-origin via Caddy)
3. From `/opt/clerk`:

   ```bash
   docker compose -f docker-compose.yml -f deploy/compose.edge.yml up -d --build
   ```

4. Append [caddy-atlas-clerk.caddy](./caddy-atlas-clerk.caddy) to Atlas `deploy/Caddyfile`, redeploy Atlas `web` on `cca-edge`.
5. Open `https://agent.customchatandautomation.co.za`, sign in with `OWNER_PASSWORD`, click each demo sample.

## OpenAI spend cap

Set a hard project spend cap in the OpenAI dashboard (same practice as Atlas demo). Clerk also enforces per-minute and daily request limits in the app.
