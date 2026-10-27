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
session="$(openssl rand -hex 32)"
owner="$(openssl rand -base64 24 | tr -dc 'A-Za-z0-9' | head -c 24)"
cat > .env <<EOF
OPENAI_API_KEY=${openai}
OPENAI_CHAT_MODEL=gpt-4o-mini
PAGES_DIR=./pages
DATABASE_URL=sqlite:///./data/clerk.db
CORS_ORIGINS=
SESSION_SECRET=${session}
OWNER_PASSWORD=${owner}
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=10
RATE_LIMIT_PER_DAY=40
RATE_LIMIT_GLOBAL_PER_DAY=200
LOG_LEVEL=INFO
EOF
chmod 600 .env
echo "Wrote ${ROOT}/.env — owner login password is in that file on the server."
