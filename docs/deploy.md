# Deploy Clerk

Production shape: **web** (Caddy + React) → **api** (FastAPI + SQLite).

## Server (same VPS as Atlas)

Clerk shares **one HTTPS front door** with Atlas. Full steps: [deploy/with-atlas-edge.md](../deploy/with-atlas-edge.md).

Summary:

1. DNS: `agent.customchatandautomation.co.za` → VPS IP (`102.203.81.249`).
2. `docker network create cca-edge` (once).
3. Clone to `/opt/clerk`, `.env` with `OPENAI_API_KEY`, `SESSION_SECRET`, `CLERK_BOOTSTRAP_STAFF` (or run `bash deploy/bootstrap-server-env.sh` once), `CORS_ORIGINS` empty.
4. `docker compose -f docker-compose.yml -f deploy/compose.edge.yml up -d --build`
5. Add the Clerk site block to Atlas Caddy and redeploy Atlas `web`.
6. Open `https://agent.customchatandautomation.co.za` and sign in before using the demo.

## Local Docker smoke test

```bash
docker network create cca-edge
docker compose up -d --build
```

Open `http://localhost:8090` (default owner password from `.env`).
