# Autonomous Email Outreach System

An event-driven microservices platform for autonomous B2B email outreach — from lead discovery through personalized messaging.

**Live Deployment**: [https://aioutreach.duckdns.org](https://aioutreach.duckdns.org)

## Architecture

```
                    ┌──────────────┐
   POST /campaigns  │ Orchestrator │  ← Express + PostgreSQL + MongoDB
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

## My Contributions (Krishna Panjiyar)

I was responsible for three core areas of this system:

### 1. Orchestrator Service

The Orchestrator is the most critical service — it is the only HTTP entry point for the Web UI and acts as the central coordinator for the entire 5-stage pipeline. I designed and implemented:

- **Pipeline State Machine** — 5-stage state machine (Planning → Sourcing → Prospecting → Messaging → Completed) where every stage transition is triggered by a RabbitMQ event
- **Dual Database Strategy** — Every stage transition writes to both MongoDB (full campaign document) and PostgreSQL (lightweight status row for fast list queries)
- **Full REST API** — 12 endpoints covering campaign CRUD, pipeline status, prospects, drafts, stats, timeline, and health checks
- **Retry and Fault Tolerance** — Configurable retry policy for draft failures with automatic re-publishing of `messaging.requested`, plus silent event dropping for paused/cancelled campaigns
- **Campaign Rerun** — Allows completed/failed campaigns to restart from scratch without creating a new campaign

#### Pipeline State Machine

| Stage | Trigger Event | Action | Next Event |
|-------|--------------|--------|------------|
| Planning | Campaign created via API | Save to MongoDB + PostgreSQL | `plan.requested` |
| Sourcing | `plan.ready` received | Save plan ID, advance stage | `sourcing.requested` |
| Prospecting | `sourcing.completed` received | Collect entity IDs | `prospecting.requested` |
| Messaging | `prospecting.completed` received | Filter by ICP score, cap by max_drafts | `messaging.requested` (x N) |
| Completed | All `draft.written` / `draft.failed` received | Finalize campaign | `campaign.completed` |

#### REST API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | /api/campaigns | Create campaign, kick off pipeline |
| GET | /api/campaigns | List all campaigns (joins Postgres + Mongo) |
| GET | /api/campaigns/:id | Full campaign detail |
| PATCH | /api/campaigns/:id | Pause, resume, or update config |
| DELETE | /api/campaigns/:id | Cancel campaign |
| POST | /api/campaigns/:id/rerun | Restart a failed or completed campaign |
| GET | /api/campaigns/:id/stats | Draft counts and success rate |
| GET | /api/campaigns/:id/prospects | List scored prospects with ICP scores |
| GET | /api/campaigns/:id/companies | List sourced companies with POCs |
| GET | /api/campaigns/:id/drafts | List email drafts with recipient info |
| GET | /api/campaigns/:id/timeline | Full event trace from MongoDB |
| GET | /health | Service liveness check |

### 2. Deployment & DevOps

I was solely responsible for getting the entire system deployed and running in production:

- **Cloud Provider**: Microsoft Azure VM (Ubuntu 24)
- **Public URL**: [https://aioutreach.duckdns.org](https://aioutreach.duckdns.org)
- **DNS**: DuckDNS pointing to Azure VM
- **SSL**: Let's Encrypt certificate via Certbot
- **Reverse Proxy**: nginx routing HTTPS traffic to Docker containers
- **Docker Compose**: All 10 containers with proper service dependencies, health checks, and networking

#### Docker Compose Services

| Container | Port | Role |
|-----------|------|------|
| email-outreach-web | 8082 | React SPA served by nginx |
| email-outreach-orchestrator | 3000 | REST API and pipeline coordinator |
| email-outreach-planning | 8080 | LLM-based campaign planning |
| email-outreach-sourcing | — | Company discovery and enrichment |
| email-outreach-prospecting | 8004 | ICP scoring and ranking |
| email-outreach-messaging | 8081 | Email draft generation |
| email-outreach-observability | 8090 | Campaign timeline and metrics |
| email-outreach-rabbitmq | 5672/15672 | Message broker |
| email-outreach-mongo | 27017 | Document store |
| email-outreach-postgres | 5432 | Campaign status store |

### 3. Sourcing Integration

I integrated and debugged the Sourcing Service, which discovers companies from public data sources and enriches them with company context and point-of-contact information:

- **Discovery Pipeline**: Finds companies from YC Directory, Product Hunt, Hacker News, and OpenCorporates with cache-first strategy
- **Enrichment Operations**: LinkedIn POC lookup, YC directory lookup, and company website extraction via crawl4ai
- **External APIs**: SerpAPI, Product Hunt GraphQL API, Gemini 2.5 Flash, crawl4ai
- **Production Results**: 766 companies discovered per campaign run

### 4. Production Debugging

I identified and resolved critical production-blocking bugs:

- **Model Deprecation Loop**: `gemini-2.0-flash` returned 404 errors causing infinite nack-requeue loop with 1200+ stuck messages. Fixed by updating to `gemini-2.5-flash` and purging queues.
- **MongoDB Duplicate Key Error**: Non-sparse unique index on `draft_id` blocked draft creation. Fixed by recreating as sparse unique index.
- **RabbitMQ Health Check Failure**: Docker health check timing issue prevented service startup. Established independent restart procedure.

## RabbitMQ Message Architecture

All inter-service communication flows through a single topic exchange (`email_outreach.events`):

| Queue | Published By | Consumed By |
|-------|-------------|-------------|
| plan.requested | Orchestrator | Planning |
| plan.ready | Planning | Orchestrator |
| sourcing.requested | Orchestrator | Sourcing |
| sourcing.completed | Sourcing | Orchestrator |
| prospecting.requested | Orchestrator | Prospecting |
| prospecting.completed | Prospecting | Orchestrator |
| messaging.requested | Orchestrator | Messaging |
| draft.written | Messaging | Orchestrator |
| draft.failed | Messaging | Orchestrator |

Every queue has a corresponding dead-letter queue (e.g., `plan.requested.dlq`).

## Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Orchestrator | TypeScript, Express, Node.js | REST API and pipeline coordination |
| Worker Services | Python, FastAPI, aio-pika | Planning, Sourcing, Prospecting, Messaging |
| Message Broker | RabbitMQ 3.13 | Async inter-service communication |
| Document Store | MongoDB 7 | Campaigns, companies, drafts, traces |
| Relational DB | PostgreSQL 16 | Campaign status for fast list queries |
| LLM | Google Gemini 2.5 Flash via LiteLLM | Planning and email draft generation |
| Web Scraping | crawl4ai, Playwright | Company website extraction |
| Frontend | React, TypeScript, Vite, Tailwind CSS | Campaign management Web UI |
| Containerization | Docker, Docker Compose | Service isolation and orchestration |
| Reverse Proxy | nginx | HTTPS termination and routing |
| DNS | DuckDNS + Let's Encrypt | Public domain and SSL |
| Cloud | Microsoft Azure VM (Ubuntu 24) | Production hosting |
| IaC | Terraform | AWS EKS infrastructure (cloud-native target) |

## Project Structure

```
Autonomous_email_outreach/
├── docker-compose.yml          # Orchestrates all 10 services
├── .env.example                # Root environment template
├── README.md
├── src/
│   ├── orchestrator/           # TypeScript/Express — REST API + pipeline coordinator
│   │   ├── app.ts
│   │   ├── main.ts
│   │   ├── routes/             # Campaign, health, API routes
│   │   ├── services/           # PipelineService — state machine
│   │   ├── postgres/           # CampaignStatusRepository
│   │   ├── rabbit/             # EventsBroker — RabbitMQ client
│   │   ├── config/             # Environment config
│   │   └── types/              # Queue payload types
│   ├── planning/               # Python — LLM-based ICP planning
│   ├── sourcing/               # Python — Company discovery + enrichment
│   ├── prospecting/            # Python — ICP scoring + ranking
│   ├── messaging/              # Python — Email draft generation
│   ├── observability/          # Python — Campaign timeline API
│   ├── web-ui/                 # React — Campaign management dashboard
│   ├── shared/                 # Common models, types, utilities
│   └── local_infrastructure/   # RabbitMQ definitions, broker interface
├── deploy/                     # Helm charts + platform config
├── cloud_terraform/            # Terraform infrastructure as code
└── design_docs/                # Architecture and design decisions
```

## Quick Start

### Prerequisites

- Docker Desktop (Mac/Windows) or Docker Engine + Docker Compose (Linux)
- Git
- A Google Gemini API key — get one free at [https://aistudio.google.com](https://aistudio.google.com)
- Minimum 8GB RAM recommended

### Setup

```bash
# Clone the repository
git clone https://github.com/wolfy5786/Autonomous_email_outreach.git
cd Autonomous_email_outreach
git checkout Krishna_orchestrator

# Configure environment
cp .env.example .env
# Edit .env and set your GEMINI_API_KEY

# Create per-service .env files
cp src/planning/.env.example src/planning/.env
cp src/messaging/.env.example src/messaging/.env
cp src/sourcing/.env.example src/sourcing/.env
cp src/orchestrator/.env.example src/orchestrator/.env
cp src/prospecting/.env.example src/prospecting/.env

# Build and start
docker compose build --no-cache
docker compose up -d

# Verify
docker compose ps
```

### Access the Application

| Service | URL |
|---------|-----|
| Web UI | http://localhost:8082 |
| Orchestrator API | http://localhost:3000/api/campaigns |
| RabbitMQ Management | http://localhost:15672 (guest / guest) |
| Observability API | http://localhost:8090 |
| **Live Production** | **https://aioutreach.duckdns.org** |

## Team

| Team Member | Primary Contribution |
|------------|---------------------|
| Krishna Panjiyar | Orchestrator Service, Deployment, DevOps, Sourcing integration |
| Ankush Makhijani | Planning Service, LLM integration, system architecture |
| Mani Mokshith Noonety | Sourcing Service, web scraping, data enrichment pipeline |
| Shubham Baid | Messaging Service, Prospecting Service, email provider integration |

## Design Documents

- [Orchestrator Service Role](design_docs/orchestrator_service_role.md)
- [Data Sourcing Map](design_docs/data_sourcing_map.md)
- [Enrichment Redesign](design_docs/enrichment_redesign.md)
- [Observability Stack](design_docs/observability.md)
- [Cloud Infrastructure](design_docs/cloud_INFRASTRUCTURE.md)
- [Planning Service Role](design_docs/planning_service_role.md)
- [Repository Structure](design_docs/Repository_structure.md)

## Cloud-Native Architecture (AWS / Kubernetes / Terraform)

The system is designed and architected for production-grade cloud-native deployment on Amazon EKS. The local Docker Compose deployment on Azure VM mirrors this architecture at a smaller scale.

### Infrastructure as Code with Terraform

The cloud infrastructure is managed using Terraform (`cloud_terraform/`), which provisions and maintains all AWS resources declaratively:

- **VPC** with public and private subnets across availability zones
- **Amazon EKS** cluster with managed node groups
- **Three node groups**: general workloads, scraping workloads (memory-heavy for crawl4ai/Playwright), and stateful workloads (MongoDB)
- **ECR repositories** for storing Docker images for each service
- **AWS Secrets Manager** for API keys, OAuth credentials, and database passwords
- **IAM roles and IRSA** (IAM Roles for Service Accounts) for least-privilege service permissions
- **S3 backup buckets** for MongoDB snapshots
- **CloudWatch Log Groups** for centralized log aggregation
- **AWS Network Load Balancer** for public ingress

### Kubernetes Deployment on Amazon EKS

Each microservice is deployed as a Kubernetes Deployment with resource requests/limits, liveness and readiness probes, and environment variables injected from Kubernetes Secrets (via External Secrets Operator).

| Service | K8s Resource Type | Node Group |
|---------|------------------|------------|
| Orchestrator | Deployment | General |
| Planning | Deployment + KEDA ScaledObject | General |
| Sourcing | Deployment + KEDA ScaledObject | Scraping (isolated) |
| Prospecting | Deployment + KEDA ScaledObject | General |
| Messaging | Deployment + KEDA ScaledObject | General |
| Web UI | Deployment + HPA | General |
| MongoDB | StatefulSet + PVC (EBS) | Stateful (isolated) |
| RabbitMQ | StatefulSet | General |
| PostgreSQL | StatefulSet + PVC (EBS) | Stateful (isolated) |
| Observability | Deployment | General |

### Autoscaling with KEDA

KEDA (Kubernetes Event-Driven Autoscaler) scales the four worker services based on RabbitMQ queue depth rather than CPU usage — the correct scaling signal for asynchronous workflows. When campaigns are created and messages pile up, KEDA automatically increases replicas to process the backlog, then scales back down once the queue drains.

### Service Mesh with Linkerd

Linkerd provides automatic mTLS between all pods (zero-config encryption for internal traffic), per-service latency P50/P95/P99 metrics, real-time success rate monitoring, and request rate dashboards showing pipeline throughput.

### Observability Stack

- **Prometheus + Grafana**: In-cluster metrics — RabbitMQ queue depths, service pod counts, KEDA scaling events, MongoDB connection pool, node resource utilization
- **CloudWatch Logs + Fluent Bit**: DaemonSet collecting structured JSON logs from all containers, shipped to CloudWatch Log Groups
- **RabbitMQ Management**: Built-in queue depth monitoring with DLQ alerts

### CI/CD Pipeline

On push to main branch, GitHub Actions triggers: build → test → push Docker images to ECR → validate Helm charts → deploy to EKS via `helm upgrade --install` → Terraform apply for infrastructure changes. Rolling updates ensure zero-downtime deployments.

### Docker Compose vs Kubernetes Mapping

| Docker Compose | Kubernetes Equivalent |
|---------------|----------------------|
| container + image | Deployment + container spec |
| env_file / environment | Secret + ConfigMap (via ESO) |
| depends_on + healthcheck | readinessProbe + livenessProbe |
| volumes | PersistentVolumeClaim (EBS) |
| ports | Service (ClusterIP / LoadBalancer) |
| docker compose scale | KEDA ScaledObject |
| restart: always | restartPolicy: Always |
