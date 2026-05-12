# Orchestrator Service — Role, HTTP API, and queues

This document is the **Orchestrator-focused** design reference. It complements the system-wide summary in [`README.md`](../README.md) (Orchestrator Service, Message Queues, and API Endpoints sections) and the broker layout in [`src/local_infrastructure/rabbit_mq/definitions.json`](../src/local_infrastructure/rabbit_mq/definitions.json).

---

## Contents

1. [Role](#1-role)
2. [Data stores: PostgreSQL and MongoDB](#2-data-stores-postgresql-and-mongodb)
3. [HTTP endpoints exposed](#3-http-endpoints-exposed)
4. [Message broker topology](#4-message-broker-topology)
5. [Queues: publish](#5-queues-publish)
6. [Queues: subscribe (consume)](#6-queues-subscribe-consume)
7. [Non-goals](#7-non-goals)
8. [Related documents](#8-related-documents)

---

## 1. Role

The Orchestrator is the **only HTTP entry point** for the product surface. The Web UI and any API clients talk to it at `/api/*`; ingress routes those paths to the Orchestrator workload (static UI is served separately — see [§3.5](#35-web-ui-static-assets)).

**Responsibilities:**

- Accept campaign configuration (ICP, product profile, caps, email account reference) and persist or update campaign **documents and related records** in the **existing MongoDB** deployment (shared with other services where applicable).
- Maintain a **PostgreSQL** service connection for **per-`campaign_id` orchestration status**: pipeline stage, terminal states (completed / failed / cancelled), timestamps, and lightweight linkage fields (e.g. `plan_id`) so list/detail and ops APIs can query status cheaply and consistently.
- **Drive the async pipeline** by publishing the right events after each stage (planning → sourcing → prospecting → messaging fan-out).
- **Observe progress** by consuming completion and failure events from workers, updating **Postgres campaign status** and **MongoDB** content as needed, and enforcing caps and retries policy where applicable.
- Expose **read/query APIs** for campaigns, prospects, drafts, broker-backed **system status** (queue depths, DLQ signals), and per-campaign statistics (drawing status from Postgres where appropriate, detail from Mongo).

**Does not:** Run discovery, enrichment, ICP scoring, LLM planning, or draft generation. Those belong to Planning, Sourcing, Prospecting, and Messaging respectively.

---

## 2. Data stores: PostgreSQL and MongoDB

The Orchestrator integrates with **both** persistence systems below. Queued workers may use Mongo (or other stores) per their service design; the Orchestrator itself treats **Postgres + Mongo** as its dual backing store.

### 2.1 PostgreSQL — campaign status

**Role:** System of record for **orchestration state per `campaign_id`**.

- **Writes:** Status transitions when handling HTTP (create / cancel / resume) and when **consuming** pipeline events (`plan.ready`, `sourcing.completed`, `prospecting.completed`, `draft.written`, `draft.failed`, etc.).
- **Reads:** `GET /api/campaigns`, `GET /api/campaigns/:id`, and aggregations that depend on “where is this campaign in the pipeline?” rather than full document payloads.

**Illustrative schema** (implementation may vary):

| Column | Notes |
|--------|--------|
| `campaign_id` | Primary key (UUID or string), aligned with Mongo campaign documents |
| `status` | Coarse state: e.g. `pending`, `planning`, `sourcing`, `prospecting`, `messaging`, `completed`, `failed`, `cancelled` |
| `plan_id` | Optional, set after `plan.ready` |
| `last_error` | Optional short summary for failed / stuck campaigns |
| `updated_at` / `created_at` | Audit and ordering |

Optional **JSONB** (e.g. `stage_detail`) can hold counters or sub-stage hints without duplicating full Mongo documents.

### 2.2 MongoDB — existing document store

**Role:** Continue using the **existing MongoDB** cluster for rich, nested data already assumed by the architecture: full campaign config, plan documents, prospects, draft bodies, scores, and similar blobs.

**Coordination with Postgres:** `campaign_id` is the join key. **Postgres** answers “what stage and outcome?” quickly; **Mongo** remains authoritative for configuration and content. The Orchestrator keeps both in sync on transitions (e.g. after an event, update Postgres status and any Mongo fields that services expect).

---

## 3. HTTP endpoints exposed

All routes are **REST over HTTP**. The canonical public prefix is **`/api/*`**. No authentication is required in the current design (see [`README.md`](../README.md)).

### 3.1 Campaign management

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/campaigns` | Create and trigger a new outreach campaign |
| `GET` | `/api/campaigns` | List all campaigns with status |
| `GET` | `/api/campaigns/:id` | Campaign details and pipeline status |
| `PATCH` | `/api/campaigns/:id` | Update campaign config (e.g. resume) |
| `DELETE` | `/api/campaigns/:id` | Cancel and archive a campaign |

**`POST /api/campaigns` body** (summary): `name`, `icp`, `product_profile`, `config` (`email_account`, `min_icp_score`, `freshness_days`, `max_drafts`). Full shape: [`README.md` § Campaign Management](../README.md).

### 3.2 Prospect management

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/campaigns/:id/prospects` | List scored and ranked prospects for a campaign |
| `GET` | `/api/prospects/:id` | Full prospect record (company + POC + score) |

### 3.3 Draft management

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/campaigns/:id/drafts` | List drafts for a campaign with status |
| `GET` | `/api/drafts/:id` | One draft record |

### 3.4 System status and campaign statistics

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/status` | Queue depths, service statuses, DLQ count |
| `GET` | `/api/campaigns/:id/stats` | Per-campaign draft counts, success rate, throughput |

### 3.5 Web UI static assets

The **Web UI** is typically served by a separate `web-ui` deployment (`/` and `/assets/*`). Those routes are **not** implemented inside the Orchestrator container in the reference architecture; they are listed in [`README.md`](../README.md) for completeness.

---

## 4. Message broker topology

Inter-service traffic uses **RabbitMQ**. Application code publishes to a **topic exchange**; routing keys align with queue names so each logical event has a dedicated durable queue.

| Resource | Name | Notes |
|----------|------|--------|
| Events exchange | `email_outreach.events` | `type: topic`, durable |
| Dead-letter exchange | `email_outreach.dlx` | Routes failed messages to `*.dlq` queues |
| Routing convention | Same as queue name | e.g. publish with routing key `plan.requested` to reach queue `plan.requested` |

Local definitions (queues, bindings, DLQ wiring) live in [`definitions.json`](../src/local_infrastructure/rabbit_mq/definitions.json). Cloud deployments must preserve the **same logical names** ([`cloud_INFRASTRUCTURE.md`](cloud_INFRASTRUCTURE.md)).

---

## 5. Queues: publish

The Orchestrator **produces** these events (subject to pipeline state and idempotency rules):

| Queue (routing key) | Payload (logical) | Purpose |
|---------------------|-------------------|---------|
| `plan.requested` | `{ campaign_id }` | Start Planning for a campaign |
| `sourcing.requested` | `{ campaign_id, plan_id, target_entities[] }` | Start Sourcing after plan is ready |
| `prospecting.requested` | `{ campaign_id, plan_id, entity_ids[] }` | Start Prospecting after sourcing completes |
| `messaging.requested` | `{ campaign_id, poc_id }` | Request one draft for a ranked prospect |
| `campaign.completed` | `{ campaign_id, stats }` | Terminal event when work is finished |

**Publish pattern:** send to exchange `email_outreach.events` with **routing key equal to the queue/event name** (matches [`definitions.json`](../src/local_infrastructure/rabbit_mq/definitions.json) bindings).

---

## 6. Queues: subscribe (consume)

The Orchestrator **consumes** these queues to advance or reconcile pipeline state:

| Queue | Published by | Payload (logical) | Typical Orchestrator reaction |
|-------|----------------|-------------------|-------------------------------|
| `plan.ready` | Planning Service | `{ campaign_id, plan_id }` | Update Postgres status / Mongo linkage; publish `sourcing.requested` |
| `sourcing.completed` | Sourcing Service | `{ campaign_id, entity_ids[] }` | Update Postgres + Mongo pipeline state; publish `prospecting.requested` |
| `sourcing.partial` | Sourcing Service | `{ campaign_id, entity_id, missing_fields[] }` | Partial progress / alerting |
| `prospecting.completed` | Prospecting Service | `{ campaign_id, ranked_prospects[] }` | Update Postgres; fan out `messaging.requested` up to `max_drafts` / policy |
| `draft.written` | Messaging Service | `{ campaign_id, draft_id, poc_id, email_draft_ref }` | Update Mongo draft/campaign progress; refresh Postgres status if needed |
| `draft.failed` | Messaging Service | `{ campaign_id, draft_id, poc_id, error, retry_count }` | Retry or surface failure; DLQ after limits; reflect in Postgres |

**`campaign.completed`:** Published **by** the Orchestrator; nothing else consumes it in the design (terminal fan-out for analytics or external hooks if added later).

**Multi-consumer queues:** `plan.ready` (Orchestrator + Sourcing Service) and `prospecting.completed` (Orchestrator + Messaging Service) each have **more than one subscriber** on the same queue name in [README.md](../README.md). In RabbitMQ, **multiple consumers on the same queue share messages** (competing consumers). If the product requires **every** service to get a copy of an event, the architecture would use separate queues per consumer bound with the same routing key. Implementations should either (a) treat the Orchestrator as the sole consumer for coordination on a given queue and have workers use different queue names, or (b) accept the competing-consumer model and make handlers idempotent. Resolve this explicitly when implementing `src/orchestrator/`.

---

## 7. Non-goals

- No direct HTTP or RPC calls **to** Planning, Sourcing, Prospecting, or Messaging — only queues + **PostgreSQL** (campaign status) + **MongoDB** (documents).
- No sending email or final approval workflows; Messaging stops at **draft** in the user’s mailbox.

---

## 8. Related documents

| Document | Relevance |
|----------|-----------|
| [`README.md`](../README.md) | Orchestrator narrative, full API tables, queue payload table, end-to-end flow |
| [`planning_service_role.md`](planning_service_role.md) | Plan Document shape Orchestrator persists/links after `plan.ready` |
| [`Repository_structure.md`](Repository_structure.md) | `src/orchestrator/` as the code home for this service |
| [`cloud_INFRASTRUCTURE.md`](cloud_INFRASTRUCTURE.md) | K8s service DNS, ingress for `/api/*`, scaling notes |
| [`definitions.json`](../src/local_infrastructure/rabbit_mq/definitions.json) | Exchange, queue, DLQ, and binding definitions |
