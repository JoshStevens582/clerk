#!/usr/bin/env bash
# Re-register Resend webhook and sync RESEND_WEBHOOK_SECRET (run on VPS from /opt/clerk).
set -euo pipefail
cd "$(dirname "$0")/.."
KEY=$(grep -m1 '^RESEND_API_KEY=' .env | cut -d= -f2- || true)
if [[ -z "$KEY" ]]; then
  KEY=$(grep -m1 '^SMTP_PASSWORD=' .env | cut -d= -f2- || true)
fi
if [[ -z "$KEY" ]]; then
  echo "RESEND_API_KEY or SMTP_PASSWORD missing in .env" >&2
  exit 1
fi
docker run --rm --user root -v "$(pwd)/.env:/opt/clerk/.env" \
  -v "$(pwd)/scripts/resend_setup_inbound.py:/app/scripts/resend_setup_inbound.py" \
  -e "RESEND_FULL_ACCESS_KEY=${KEY}" \
  -e CLERK_ENV_FILE=/opt/clerk/.env \
  clerk-api python /app/scripts/resend_setup_inbound.py
