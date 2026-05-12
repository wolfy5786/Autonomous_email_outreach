# Planning Service

Consumes `plan.requested`, analyses a campaign's ICP + product profile via a configurable LLM, writes a structured Plan Document to MongoDB, and publishes `plan.ready` (consumed **only** by the Orchestrator — see root [`README.md`](../../README.md) § Message Queues).

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

See [`README.md`](../../README.md), [`planning_service_role.md`](../../design_docs/planning_service_role.md), and [`data_sourcing_map.md`](../../design_docs/data_sourcing_map.md) for how Plan Documents steer Sourcing versus Prospecting workloads.
