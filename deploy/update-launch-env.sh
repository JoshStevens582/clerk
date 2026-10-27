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
  echo "${key}=${value}" >>"$ENV_FILE"
}

# shellcheck disable=SC1091
source "$ENV_FILE" || true

if [[ -z "${RESEND_API_KEY:-}" && -n "${SMTP_PASSWORD:-}" ]]; then
  set_kv "RESEND_API_KEY" "$SMTP_PASSWORD"
fi

set_kv "CLERK_INBOUND_ADDRESS" "clerk@customchatandautomation.co.za"
set_kv "CLERK_SEED_DEMO_INBOX" "false"

echo "Launch env updated. Set RESEND_WEBHOOK_SECRET after adding the Resend webhook (see docs/launch-inbound.md)."
