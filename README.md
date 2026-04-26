# Orchestrator Service

> Entry point and pipeline coordinator for the Autonomous Email Outreach system. Receives campaign triggers, fans out work to downstream services through message queues, tracks pipeline state, and exposes the full REST API — including the absorbed Review Service endpoints.

---

## File Structure

```
orchestrator/
│
├── messaging/                          # Broker abstraction layer (shared infra)
│   ├── broker.interface.ts             # MessageBroker interface — publish / subscribe / disconnect
│   ├── broker.factory.ts               # Factory — reads BROKER_TYPE env to pick RabbitMQ or SQS
│   ├── rabbitmq.broker.ts              # RabbitMQ adapter (local dev)
│   └── sqs.broker.ts                   # AWS SQS adapter (production)
│
├── src/
│   ├── main.ts                         # Entry point — connects MongoDB, creates broker, starts server
│   ├── app.ts                          # Express app setup — wires routes, services, middleware
│   │
│   ├── config/
│   │   └── index.ts                    # Environment config loader (PORT, MONGO_URI, BROKER_TYPE, etc.)
│   │
│   ├── types/
│   │   └── index.ts                    # All TypeScript types — campaign, queue payloads, pipeline state
│   │
│   ├── models/
│   │   ├── index.ts                    # Barrel export
│   │   ├── campaign.model.ts           # Mongoose Campaign schema (with embedded PipelineState)
│   │   └── email-draft.model.ts        # Mongoose EmailDraft schema (status lifecycle)
│   │
│   ├── services/
│   │   ├── index.ts                    # Barrel export
│   │   ├── pipeline.service.ts         # Core brain — subscribes to 8 queues, advances pipeline stages
│   │   └── review.service.ts           # Draft review operations (approve/reject/edit/regenerate/bulk)
│   │
│   ├── routes/
│   │   ├── index.ts                    # Barrel export
│   │   ├── campaign.routes.ts          # Campaign CRUD, stats, prospects, drafts
│   │   ├── review.routes.ts            # Draft management & review queue endpoints
│   │   └── health.routes.ts            # /health and /status
│   │
│   └── middleware/
│       └── error-handler.ts            # Centralized error handler + AppError class
│
├── package.json
├── tsconfig.json
├── Dockerfile
├── .env                                # Local dev environment variables
└── README.md
```

---

## Prerequisites

- **Node.js** ≥ 20
- **MongoDB** — running locally or accessible via URI
- **RabbitMQ** — running locally for dev (production uses AWS SQS)

### Quick install (macOS)

```bash
brew install node
brew install mongodb-community
brew install rabbitmq

# Start services
brew services start mongodb-community
brew services start rabbitmq
```

### Quick install (Ubuntu/Debian)

```bash
# MongoDB
sudo apt install -y mongodb

# RabbitMQ
sudo apt install -y rabbitmq-server
sudo systemctl start rabbitmq-server

# Node.js 20 via nvm
nvm install 20 && nvm use 20
```

### Using Docker for dependencies

If you prefer not to install MongoDB and RabbitMQ locally:

```bash
docker run -d --name mongo -p 27017:27017 mongo:7
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management
```

---

## Setup

```bash
cd orchestrator

# Install dependencies
npm install

# (Optional) Review and edit environment variables
cat .env
```

### Environment Variables

| Variable        | Default                                  | Description                              |
|-----------------|------------------------------------------|------------------------------------------|
| `PORT`          | `3000`                                   | HTTP server port                         |
| `MONGO_URI`     | `mongodb://localhost:27017/email_outreach`| MongoDB connection string                |
| `BROKER_TYPE`   | `rabbitmq`                               | Message broker: `rabbitmq` or `sqs`      |
| `RABBITMQ_URL`  | `amqp://localhost`                       | RabbitMQ connection URL (dev only)       |
| `AWS_REGION`    | `us-east-1`                              | AWS region for SQS (prod only)           |
| `RETRY_LIMIT`   | `3`                                      | Max retries for failed email sends       |
| `LOG_LEVEL`     | `info`                                   | Log verbosity                            |

---

## Running

### Development (with ts-node)

```bash
npm run dev
```

### Production build

```bash
# Compile TypeScript
npm run build

# Run compiled JS
npm start
```

### Docker

```bash
# Build image
docker build -t orchestrator .

# Run container
docker run -d \
  --name orchestrator \
  -p 3000:3000 \
  -e MONGO_URI=mongodb://host.docker.internal:27017/email_outreach \
  -e BROKER_TYPE=rabbitmq \
  -e RABBITMQ_URL=amqp://host.docker.internal \
  orchestrator
```

---

## Verify It's Running

```bash
# Health check
curl http://localhost:3000/health
# → {"status":"ok","service":"orchestrator","timestamp":"..."}

# System status
curl http://localhost:3000/status
```

---

## API Endpoints

### Campaign Management

| Method   | Path                         | Description                                    |
|----------|------------------------------|------------------------------------------------|
| `POST`   | `/campaigns`                 | Create and trigger a new outreach campaign     |
| `GET`    | `/campaigns`                 | List all campaigns with status                 |
| `GET`    | `/campaigns/:id`             | Get campaign details and pipeline state        |
| `PATCH`  | `/campaigns/:id`             | Pause/resume campaign, update send window      |
| `DELETE` | `/campaigns/:id`             | Cancel and archive a campaign                  |
| `GET`    | `/campaigns/:id/stats`       | Sent count, approval rate, bounce rate         |
| `GET`    | `/campaigns/:id/prospects`   | List ranked prospect IDs for a campaign        |
| `GET`    | `/campaigns/:id/drafts`      | List all drafts (filterable by `?status=`)     |

### Draft Email Management

| Method   | Path                         | Description                                    |
|----------|------------------------------|------------------------------------------------|
| `GET`    | `/drafts/:id`                | Get a specific draft                           |
| `PATCH`  | `/drafts/:id`                | Update draft subject or body                   |
| `POST`   | `/drafts/:id/approve`        | Approve → publishes `send.requested`           |
| `POST`   | `/drafts/:id/reject`         | Reject with optional regeneration              |
| `POST`   | `/drafts/:id/regenerate`     | Request a new draft for this prospect          |

### Review Queue

| Method   | Path                         | Description                                    |
|----------|------------------------------|------------------------------------------------|
| `GET`    | `/review/queue`              | Get all drafts pending review                  |
| `POST`   | `/review/bulk-approve`       | Approve a batch of draft IDs                   |

### System

| Method   | Path                         | Description                                    |
|----------|------------------------------|------------------------------------------------|
| `GET`    | `/health`                    | Service liveness check                         |
| `GET`    | `/status`                    | Campaign counts, uptime, queue status          |

---

## Example: Create a Campaign

```bash
curl -X POST http://localhost:3000/campaigns \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Q3 SaaS Outreach",
    "icp": {
      "industries": ["SaaS", "FinTech"],
      "employee_count_range": { "min": 50, "max": 500 },
      "funding_stages": ["series_a", "series_b"],
      "geographies": ["US", "UK"],
      "target_titles": ["CTO", "VP Engineering", "Head of Platform"],
      "target_seniorities": ["vp", "c_level", "director"]
    },
    "product_profile": {
      "name": "Acme DevOps Platform",
      "description": "Infrastructure automation for growing engineering teams",
      "value_propositions": [
        "Cut deploy time by 80%",
        "Zero-config CI/CD pipelines"
      ]
    },
    "config": {
      "email_channel": "sendgrid",
      "email_channel_config": {
        "api_key": "SG.xxxx"
      },
      "min_icp_score": 0.7,
      "freshness_days": 30,
      "send_window": {
        "start_hour": 9,
        "end_hour": 17,
        "timezone": "America/New_York"
      }
    }
  }'
```

This creates the campaign, sets status to `running`, and publishes a `plan.requested` event to kick off the Planning Service.

---

## Message Queue Events

The orchestrator **publishes** these events:

| Event                  | When                                              |
|------------------------|---------------------------------------------------|
| `plan.requested`       | Campaign created → kicks off Planning Service     |
| `sourcing.requested`   | Plan ready → kicks off Sourcing Service           |
| `messaging.requested`  | Prospects ranked → one per qualified prospect     |
| `send.requested`       | Draft approved (or retry after send failure)      |
| `campaign.completed`   | All prospects processed                           |

The orchestrator **subscribes** to these events from downstream services:

| Event                    | Source              | Action                                   |
|--------------------------|---------------------|------------------------------------------|
| `plan.ready`             | Planning Service    | Store plan ID, advance to sourcing       |
| `sourcing.completed`     | Sourcing Service    | Track entity IDs, advance to prospecting |
| `sourcing.partial`       | Sourcing Service    | Log missing fields (non-blocking)        |
| `prospecting.completed`  | Prospecting Service | Filter by min score, fan out messaging   |
| `messaging.completed`    | Messaging Service   | Track draft, advance to review when done |
| `review.completed`       | Review (self)       | Track review decisions for stats         |
| `send.completed`         | Send Service        | Track sent drafts, check for completion  |
| `send.failed`            | Send Service        | Retry up to RETRY_LIMIT, then mark failed|

---

## Pipeline Stages

Each campaign progresses through these stages, tracked in `pipeline_state`:

```
planning → sourcing → prospecting → messaging → review → sending → completed
```

The `pipeline_state` object on each campaign record holds:

- `current_stage` — where the campaign is right now
- `plan_id` — reference to the Plan Document
- `sourced_entity_ids` — companies/POCs found during sourcing
- `ranked_prospect_ids` — prospects that passed the ICP score threshold
- `draft_ids` — all generated email drafts
- `sent_draft_ids` — successfully delivered emails
- `failed_draft_ids` — permanently failed sends
- `stage_timestamps` — when each stage was entered

---

## Broker Switching

The messaging layer uses the **strategy pattern**. Your service code never knows which broker is running underneath.

- **Local dev:** Set `BROKER_TYPE=rabbitmq` and `RABBITMQ_URL=amqp://localhost`
- **Production:** Set `BROKER_TYPE=sqs` and `AWS_REGION=us-east-1`

The factory in `messaging/broker.factory.ts` reads the env var once at startup and returns the correct adapter. All queue operations (`publish`, `subscribe`, `disconnect`) are identical regardless of broker.
