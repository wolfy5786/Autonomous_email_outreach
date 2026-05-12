# Autonomous Email Outreach

An event-driven microservices platform for autonomous B2B email outreach — from lead discovery through personalized messaging.

## Architecture

```
                    ┌──────────────┐
   POST /campaigns  │ Orchestrator │  ← Express + PostgreSQL
                    │  (Node.js)   │
                    └──────┬───────┘
                           │ RabbitMQ (topic exchange)
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
     ┌────────────┐ ┌────────────┐ ┌────────────┐
     │  Planning   │ │  Sourcing  │ │ Prospecting│
     │  (Python)   │ │  (Python)  │ │  (Python)  │
     └──────┬─────┘ └──────┬─────┘ └──────┬─────┘
            │              │              │
            ▼              ▼              ▼
     ┌────────────┐ ┌────────────┐ ┌────────────┐
     │  Messaging  │ │ Observabil │ │   Web UI   │
     │  (Python)   │ │  (Python)  │ │  (React)   │
     └────────────┘ └────────────┘ └────────────┘
```

## Services

| Service | Language | Port | Description |
|---------|----------|------|-------------|
| Orchestrator | TypeScript | 3000 | Campaign CRUD, pipeline coordination |
| Planning | Python | 8000 | ICP → outreach plan generation |
| Sourcing | Python | 8001 | Company discovery (YC, HN, PH, OpenCorp) |
| Prospecting | Python | 8002 | Contact enrichment and scoring |
| Messaging | Python | 8003 | Email draft generation and sending |
| Observability | Python | 8004 | Metrics, logs, and dashboards |
| Web UI | React | 5173 | Campaign management dashboard |

## Quick Start

```bash
# Start infrastructure
docker compose up -d rabbitmq mongodb postgres redis

# Start orchestrator
cd src/orchestrator && npm install && npm run dev

# Start sourcing
cd src/sourcing && pip install -r requirements.txt && python -m sourcing.main
```

## Project Structure

```
├── src/
│   ├── orchestrator/    # Express API + RabbitMQ coordination
│   ├── planning/        # Outreach plan generation
│   ├── sourcing/        # Company discovery pipeline
│   ├── prospecting/     # Contact enrichment
│   ├── messaging/       # Email drafting + SMTP
│   ├── observability/   # Metrics and monitoring
│   ├── web-ui/          # React dashboard
│   ├── shared/          # Common models, logger, rate limiter
│   └── local_infrastructure/  # Dev environment setup
├── deploy/              # Helm charts + platform config
├── cloud_terraform/     # AWS infrastructure as code
└── design_docs/         # Architecture and design decisions
```

## Design Documents

- [Orchestrator Service Role](design_docs/orchestrator_service_role.md)
- [Data Sourcing Map](design_docs/data_sourcing_map.md)
- [Enrichment Redesign](design_docs/enrichment_redesign.md)
- [Observability Stack](design_docs/observability.md)
- [Cloud Infrastructure](design_docs/cloud_INFRASTRUCTURE.md)
