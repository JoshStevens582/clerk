"""Probe Resend API for domain/receiving config (run on VPS inside clerk-api)."""
import os
import sys

import httpx

key = os.environ.get("RESEND_API_KEY", "") or os.environ.get("SMTP_PASSWORD", "")
if not key:
    print("NO_KEY")
    sys.exit(1)

headers = {"Authorization": f"Bearer {key}"}
base = "https://api.resend.com"

with httpx.Client(timeout=30.0) as client:
    domains = client.get(f"{base}/domains", headers=headers)
    print("domains_status", domains.status_code)
    print(domains.text[:3000])
    if domains.status_code == 200:
        data = domains.json()
        for item in data.get("data", []):
            did = item.get("id")
            name = item.get("name")
            if not did:
                continue
            detail = client.get(f"{base}/domains/{did}", headers=headers)
            print(f"--- domain {name} detail {detail.status_code} ---")
            print(detail.text[:2500])
