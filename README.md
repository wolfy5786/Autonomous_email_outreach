# Email Outreach — Autonomous Email Campaign System

> End-to-end autonomous email outreach platform: from ICP definition to personalized email delivery, with human review in the loop.

---

## Architecture Overview

The system is composed of six services communicating asynchronously via message queues:

| Service | Purpose |
|---|---|
| **Orchestrator** | Entry point, pipeline coordinator, REST API (includes absorbed Review endpoints) |
| **Planning** | ICP analysis → Plan Document generation (LLM) |
| **Sourcing** | Data mining — Layer 1 APIs + Layer 2 headless browsers |
| **Prospecting** | ICP scoring + semantic search on enriched prospect data |
| **Messaging** | Personalized email draft generation (LLM) + delivery to user email account |
| **Web UI** | Static SPA — campaign management, prospects, draft review, pipeline monitoring |

### Pipeline Flow

```
planning → sourcing → prospecting → messaging → review → sending → completed
```

---

## Repository Structure

See [`Repository_structure.md`](./Repository_structure.md) for the full directory tree.

```
email_outreach/
├── cloud_terraform/        # AWS infrastructure (Terraform modules)
├── deploy/                 # Helm charts for EKS deployment
├── src/
│   ├── local_infrastructure/   # Local dev: RabbitMQ, broker factory, observability
│   ├── orchestrator/           # Pipeline coordinator + REST API
│   ├── planning/               # LLM-powered ICP planning
│   ├── sourcing/               # Data enrichment (APIs + scraping)
│   ├── prospecting/            # Prospect ranking
│   ├── messaging/              # Email draft generation + delivery
│   └── web-ui/                 # Frontend SPA
└── docs
```

---

## Quick Start (Local Development)

### Prerequisites

- Node.js ≥ 20
- MongoDB (local or Docker)
- RabbitMQ (local or Docker)

```bash
# Start dependencies via Docker
docker run -d --name mongo -p 27017:27017 mongo:7
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management

# Run the orchestrator
cd src/orchestrator
npm install
npm run dev
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `3000` | HTTP server port |
| `MONGO_URI` | `mongodb://localhost:27017/email_outreach` | MongoDB connection string |
| `BROKER_TYPE` | `rabbitmq` | Message broker: `rabbitmq` or `sqs` |
| `RABBITMQ_URL` | `amqp://localhost` | RabbitMQ connection URL (dev) |
| `AWS_REGION` | `us-east-1` | AWS region for SQS (prod) |
| `RETRY_LIMIT` | `3` | Max retries for failed email sends |

---

## Infrastructure

- **Cloud**: See [`cloud_INFRASTRUCTURE.md`](./cloud_INFRASTRUCTURE.md) for the full AWS/EKS deployment design.
- **Messaging**: See [`messaging_infrastructure.md`](./messaging_infrastructure.md) for the broker abstraction pattern.
- **Terraform**: `cloud_terraform/` contains all IaC modules.
- **Helm**: `deploy/` contains per-service charts and an umbrella chart for dev.

---

## API Endpoints

All endpoints are served by the **Orchestrator** on port 3000.

### Campaigns
- `POST /campaigns` — Create and trigger a campaign
- `GET /campaigns` — List all campaigns
- `GET /campaigns/:id` — Campaign details + pipeline state
- `PATCH /campaigns/:id` — Pause/resume, update send window
- `DELETE /campaigns/:id` — Cancel campaign
- `GET /campaigns/:id/stats` — Sent count, approval rate, bounce rate
- `GET /campaigns/:id/prospects` — Ranked prospects
- `GET /campaigns/:id/drafts` — Drafts (filterable by `?status=`)

### Drafts & Review
- `GET /drafts/:id` — Get draft
- `PATCH /drafts/:id` — Edit subject/body
- `POST /drafts/:id/approve` — Approve → publishes `send.requested`
- `POST /drafts/:id/reject` — Reject with optional regeneration
- `POST /drafts/:id/regenerate` — Request new draft
- `GET /review/queue` — Pending review queue
- `POST /review/bulk-approve` — Batch approve

### System
- `GET /health` — Liveness
- `GET /status` — Campaign counts, uptime

---

## Broker Switching

The messaging layer uses the **strategy pattern**. Service code is broker-agnostic.

- **Local dev**: `BROKER_TYPE=rabbitmq` + `RABBITMQ_URL=amqp://localhost`
- **Production**: `BROKER_TYPE=sqs` + `AWS_REGION=us-east-1`

The factory in `src/local_infrastructure/factory/broker.factory.ts` reads the env var at startup and returns the correct adapter.
