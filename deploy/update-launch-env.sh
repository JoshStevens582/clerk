#!/usr/bin/env bash
# Append launch-related env vars on the VPS (idempotent). Run from /opt/clerk.
set -euo pipefail
cd "$(dirname "$0")/.."
ENV_FILE=".env"
touch "$ENV_FILE"

set_kv() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" "$ENV_FILE" 2>/dev/null; then
    return 0
  fi
  printf '%s=%s\n' "$key" "$value" >>"$ENV_FILE"
}

smtp_password="$(grep -m1 '^SMTP_PASSWORD=' "$ENV_FILE" 2>/dev/null | cut -d= -f2- || true)"
if [[ -n "$smtp_password" ]] && ! grep -q '^RESEND_API_KEY=' "$ENV_FILE" 2>/dev/null; then
  set_kv "RESEND_API_KEY" "$smtp_password"
fi

set_kv "CLERK_INBOUND_ADDRESS" "clerk@customchatandautomation.co.za"
set_kv "CLERK_SEED_DEMO_INBOX" "false"

echo "Launch env updated. Set RESEND_WEBHOOK_SECRET after adding the Resend webhook (see docs/launch-inbound.md)."
