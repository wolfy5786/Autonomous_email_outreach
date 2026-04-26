# Planning Service

Consumes `plan.requested`, analyses a campaign's ICP + product profile via a configurable LLM, writes a structured Plan Document to MongoDB, and publishes `plan.ready`.

## Run locally

```bash
# From the repo root
cd src/local_infrastructure
cp .env.example .env          # add your GEMINI_API_KEY
docker compose up --build -d
docker compose logs -f planning
```

## Configuration

See `.env.example`. The LLM is fully swappable via `LLM_MODEL` — use `gemini/gemini-1.5-pro`, `openai/gpt-4o`, `anthropic/claude-sonnet-4`, etc.

## Tests

```bash
cd src/planning
uv sync --extra dev
uv run pytest
```

See [`/README.md`](../../README.md) for the full system design and [`/cloud_INFRASTRUCTURE.md`](../../cloud_INFRASTRUCTURE.md) for production deployment.
