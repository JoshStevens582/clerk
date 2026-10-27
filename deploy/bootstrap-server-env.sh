#!/usr/bin/env bash
# Run on the VPS once after clone (does not print secrets).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -f .env ]]; then
  echo ".env already exists; leaving it unchanged."
  exit 0
fi
openai=""
if [[ -f /opt/counter/.env ]]; then
  # shellcheck disable=SC1091
  set -a
  source /opt/counter/.env
  set +a
  openai="${OPENAI_API_KEY:-}"
fi
auth_secret="$(openssl rand -hex 32)"
owner_pass="$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 24)"
reception_pass="$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 24)"
cat > .env <<EOF
OPENAI_API_KEY=${openai}
OPENAI_CHAT_MODEL=gpt-4o-mini
PAGES_DIR=./pages
DATABASE_URL=sqlite:///./data/clerk.db
CORS_ORIGINS=
CLERK_AUTH_SECRET=${auth_secret}
CLERK_BOOTSTRAP_STAFF=owner:${owner_pass}:manager,reception:${reception_pass}:staff
CLERK_ADMIN_USERNAMES=owner
REDIS_URL=redis://redis:6379/1
REDIS_REQUIRED=true
LOGIN_LOCKOUT_ENABLED=true
LOGIN_LOCKOUT_FAIL_CLOSED=true
RATE_LIMIT_ENABLED=true
RATE_LIMIT_FAIL_CLOSED=true
RATE_LIMIT_PER_MINUTE=10
RATE_LIMIT_PER_DAY=40
RATE_LIMIT_GLOBAL_PER_DAY=200
LOG_LEVEL=INFO
EOF
chmod 600 .env
echo "Wrote ${ROOT}/.env — staff passwords are in CLERK_BOOTSTRAP_STAFF (only applied on first boot)."
