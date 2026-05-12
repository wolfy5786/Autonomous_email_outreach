# Messaging Service

Consumes `messaging.requested`, generates a personalized email draft via a configurable LLM, writes the draft into the user's mailbox via the configured email provider, persists an `email_drafts` record, and publishes `draft.written` (or `draft.failed`).

The service **does not send emails** — it stops at draft creation. The user reviews and sends from their own client.

## Run locally

```bash
# From the repo root
cd src/local_infrastructure
cp .env.example .env          # set GEMINI_API_KEY and (optionally) GMAIL_* values
docker compose up --build -d
docker compose logs -f messaging
```

`EMAIL_PROVIDER=stub` (default) writes a fake draft id and skips Gmail entirely — useful for local end-to-end smoke tests.

## Configuration

See `.env.example`. The LLM is fully swappable via `LLM_MODEL` (`gemini/gemini-1.5-pro`, `openai/gpt-4o`, `anthropic/claude-sonnet-4`, …). The email provider is selected via `EMAIL_PROVIDER` (`stub` | `gmail`).

## Tests

```bash
cd src/messaging
uv sync --extra dev
uv run pytest
```

See [`README.md`](../../README.md), [`docs/planning_service_role.md`](../../docs/planning_service_role.md), and the design plan for how Plan Documents and prospect data flow into draft generation.
