# Clerk

Clerk is the automation agent for Custom Chat and Automation. It is its own app (not inside Atlas or Counter).

**What it does**

- Reads approved firm pages (markdown on disk).
- Sends **pre-agreed** replies on its own (exact stored sentences — the model does not rewrite them).
- Drafts bookings and client emails, shows the draft **and** the cited page, and waits for the owner to click **yes** before anything goes out.
- Refuses prices or leave-day counts that are not on the cited pages. Does not hold a appointment slot until approval.

**How it fits**

- **Counter** and **Atlas** answer questions from pages.
- **Clerk** does the paperwork after that answer: acknowledgement, booking form, outbound email.

The agent uses **Pydantic AI** with a read-page tool. There is no send tool — only [`policy.py`](src/clerk/services/policy.py) may auto-send or queue.

## Local development

```bash
uv sync --group dev
cp .env.example .env
# optional: OPENAI_API_KEY for free-text messages (demo samples work without it)

uv run uvicorn clerk.main:app --reload --port 8789 --app-dir src
cd frontend && npm install && npm run dev
```

Open `http://localhost:5175`. **Staff sign-in (v2):** username + password. Local demo accounts from `CLERK_BOOTSTRAP_STAFF` in `.env` (default **owner** / **reception** with passwords in `.env.example`).

Managers can add users: `uv run python -m clerk.staff_cli newname --role staff` or `POST /api/staff/users` while signed in as a manager.

## Tests and quality

```bash
uv run ruff check .
uv run mypy .
uv run pytest --cov=clerk --cov-branch
```

## Docker

```bash
docker network create cca-edge
docker compose up -d --build
```

Open `http://localhost:8090`.

## Production

See [docs/deploy.md](docs/deploy.md) — live URL target: `https://agent.customchatandautomation.co.za`.
