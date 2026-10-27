"""Create Resend webhook + verify receiving API (requires full-access API key).

Usage on VPS (key is not echoed):

  bash deploy/finish-launch.sh   # on VPS; uses RESEND_API_KEY from .env

Or set RESEND_FULL_ACCESS_KEY in the environment before running.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import httpx

WEBHOOK_URL = "https://agent.customchatandautomation.co.za/api/hooks/resend"
def _env_file() -> Path:
    override = os.environ.get("CLERK_ENV_FILE", "").strip()
    if override:
        return Path(override)
    return Path("/opt/clerk/.env")


def _api_key_from_env() -> str:
    return (
        os.environ.get("RESEND_FULL_ACCESS_KEY", "").strip()
        or os.environ.get("RESEND_API_KEY", "").strip()
    )


def main() -> int:
    api_key = _api_key_from_env()
    if not api_key:
        print(
            "Set RESEND_FULL_ACCESS_KEY (or RESEND_API_KEY) to a Full access Resend key.",
            file=sys.stderr,
        )
        return 1

    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    base = "https://api.resend.com"

    with httpx.Client(timeout=30.0) as client:
        recv = client.get(f"{base}/emails/receiving", headers=headers, params={"limit": 1})
        if recv.status_code == 401:
            print(
                "API key cannot list received mail (need Full access, not send-only).",
                file=sys.stderr,
            )
            return 1
        if recv.status_code >= 400:
            print(f"Receiving API check failed: {recv.status_code}", file=sys.stderr)
            return 1

        hooks = client.get(f"{base}/webhooks", headers=headers)
        signing_secret = ""
        if hooks.status_code == 200:
            for row in hooks.json().get("data", []) or []:
                if isinstance(row, dict) and row.get("endpoint") == WEBHOOK_URL:
                    signing_secret = str(row.get("signing_secret") or "")
                    break

        if not signing_secret:
            created = client.post(
                f"{base}/webhooks",
                headers=headers,
                json={"endpoint": WEBHOOK_URL, "events": ["email.received"]},
            )
            if created.status_code >= 400:
                print(
                    f"Webhook create failed: {created.status_code} {created.text[:500]}",
                    file=sys.stderr,
                )
                return 1
            signing_secret = str(created.json().get("signing_secret") or "")
            if not signing_secret:
                print("Webhook created but no signing_secret in response.", file=sys.stderr)
                return 1

    env_file = _env_file()
    if not env_file.is_file():
        print(f"Env file not found: {env_file}", file=sys.stderr)
        print("Add these lines to /opt/clerk/.env on the server, then restart the API:")
        print(f"RESEND_API_KEY={api_key}")
        print(f"SMTP_PASSWORD={api_key}")
        print(f"RESEND_WEBHOOK_SECRET={signing_secret}")
        return 1

    text = env_file.read_text(encoding="utf-8")
    lines = text.splitlines()
    out: list[str] = []
    saw_resend_key = False
    saw_whsec = False
    for line in lines:
        if line.startswith("RESEND_API_KEY="):
            out.append(f"RESEND_API_KEY={api_key}")
            saw_resend_key = True
            continue
        if line.startswith("SMTP_PASSWORD="):
            out.append(f"SMTP_PASSWORD={api_key}")
            continue
        if line.startswith("RESEND_WEBHOOK_SECRET="):
            out.append(f"RESEND_WEBHOOK_SECRET={signing_secret}")
            saw_whsec = True
            continue
        out.append(line)
    if not saw_resend_key:
        out.append(f"RESEND_API_KEY={api_key}")
    if not saw_whsec:
        out.append(f"RESEND_WEBHOOK_SECRET={signing_secret}")

    env_file.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"OK: RESEND_API_KEY and RESEND_WEBHOOK_SECRET updated in {env_file}")
    print("Restart API: docker compose -f docker-compose.yml -f deploy/compose.edge.yml up -d api")
    print(
        json.dumps(
            {
                "webhook": WEBHOOK_URL,
                "next": "Forward Forge mail to @….resend.app or add subdomain MX in Resend.",
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
