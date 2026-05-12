# Email Outreach — Autonomous Email Campaign System

> A distributed, AI-powered outbound sales engine that mines public data, scores prospects, generates personalized email drafts, and writes them directly to the user's email account — all orchestrated through asynchronous message queues and managed through a Web UI.

---

## Architecture Overview

1. [System Overview](#system-overview)
2. [Architecture](#architecture)
3. [Services](#services)
   - [Orchestrator Service](#orchestrator-service)
   - [Planning Service](#planning-service)
   - [Sourcing Service](#sourcing-service)
   - [Prospecting Service](#prospecting-service)
   - [Messaging Service](#messaging-service)
4. [Web UI (Frontend)](#web-ui-frontend)
5. [Data Pipeline](#data-pipeline)
   - [Cache-First Strategy](#cache-first-strategy)
   - [Scraping Decision Tree](#scraping-decision-tree)
   - [Discovery & enrichment pipeline](#discovery--enrichment-pipeline)
6. [Data Sources](#data-sources)
7. [Data Schema](#data-schema)
8. [Message Queues](#message-queues)
9. [API Endpoints](#api-endpoints)
10. [MongoDB storage design](#mongodb-storage-design)
11. [Semantic Search on Unknown Columns](#semantic-search-on-unknown-columns)
12. [System Flow — End to End](#system-flow--end-to-end)

| Service | Purpose |
|---|---|
| **Orchestrator** | Entry point, pipeline coordinator, REST API (includes absorbed Review endpoints) |
| **Planning** | ICP analysis → Plan Document generation (LLM) |
| **Sourcing** | Data mining — Layer 1 APIs + Layer 2 headless browsers |
| **Prospecting** | ICP scoring + semantic search on enriched prospect data |
| **Messaging** | Personalized email draft generation (LLM) + delivery to user email account |
| **Web UI** | Static SPA — campaign management, prospects, draft review, pipeline monitoring |

## System Overview

The system automates outbound sales prospecting up to the draft stage:

1. **Mine** publicly available data to find companies and persons of contact (POC) matching an Ideal Customer Profile (ICP).
2. **Score and rank** prospects against the ICP using a structured scoring model.
3. **Generate** a personalized outbound email draft per prospect.
4. **Write draft** to the user's email account (e.g., Gmail Drafts API) and save the record.
5. **Mark complete** — the system's job ends at draft creation. The user reviews, edits, and sends from their own email client.

There is **no user authentication**. A **Web UI** provides a full dashboard for campaign management, prospect browsing, draft status tracking, and pipeline monitoring. All inter-service communication is handled exclusively through **message queues**.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DISTRIBUTED WEB ARCHITECTURE                         │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────┐       │
│  │                         WEB UI (SPA)                             │       │
│  │  Campaign management · Prospect browsing · Draft status          │       │
│  │  Pipeline monitoring · Notifications                             │       │
│  └──────────────────────────────┬───────────────────────────────────┘       │
│                                 │ HTTP /api/*                               │
│                                 ▼                                           │
│  ┌──────────────┐                                                           │
│  │ Orchestrator │ ← Entry point. Coordinates the full pipeline.            │
│  │              │   Serves all API endpoints consumed by Web UI.           │
│  └──────┬───────┘                                                           │
│         │ publishes to queues                                               │
│         ▼                                                                   │
│  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐                   │
│  │   Planning   │   │   Sourcing   │   │ Prospecting  │                   │
│  │   Service    │   │   Service    │   │   Service    │                   │
│  │              │   │              │   │              │                   │
│  │ Analyse ICP  │   │Discover/enrich │   │Apollo/Hunter │
│  │ & product    │   │+ POC cues     │   │ enrich +    │
│  │ Build plan   │   │per data map   │   │score vs ICP  │
│  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘                   │
│         │                  │                   │                           │
│         └──────────────────┴───────────────────┘                           │
│                            │ all via queues                                │
│                            ▼                                               │
│                   ┌──────────────────┐                                     │
│                   │  Messaging Svc   │                                     │
│                   │  Generate draft  │                                     │
│                   │  Write to user   │                                     │
│                   │  email as draft  │                                     │
│                   └────────┬─────────┘                                     │
│                            │                                               │
│                            ▼                                               │
│                   ┌──────────────────┐                                     │
│                   │  Draft Written   │                                     │
│                   │  Task complete.  │                                     │
│                   │  User reviews &  │                                     │
│                   │  sends from own  │                                     │
│                   │  email client.   │                                     │
│                   └──────────────────┘                                     │
│                                                                             │
│  ════════════════════════════════════════════════════                      │
│  All services READ and WRITE to shared MongoDB                            │
│  All services communicate ONLY via message queues                          │
│  Web UI talks only to the Orchestrator API (HTTP)                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Docker development stack (local)

- **Single compose file:** run everything from the repository root with [docker-compose.yml](docker-compose.yml) (RabbitMQ, MongoDB, and app services share the default Compose network).
- **RabbitMQ** runs as the **broker container** only. Exchanges and queues are declared by loading [src/local_infrastructure/rabbit_mq/definitions.json](src/local_infrastructure/rabbit_mq/definitions.json) into that container via a volume mount. That directory is **infrastructure config** for the server process, not a Python messaging library. Application services are **AMQP clients** and connect with `RABBITMQ_URL` (from the host use `localhost`; from another container use the hostname `rabbitmq`).
- **MongoDB** is optional per service; set `MONGO_URI` / `MONGO_DB_NAME` as needed. The root compose wires typical values for local dev.
- **Environment:** compose `env_file` entries point at per-service `.env` files under `src/<service>/`. Commit only `.env.example` files with placeholders ([Ai_rules.md](Ai_rules.md)).
- **Service Dockerfiles** (for example [src/sourcing/Dockerfile](src/sourcing/Dockerfile)) copy application code such as `shared/` and the service package. Do **not** bake `local_infrastructure` into service images to “ship” the broker — the broker is the separate RabbitMQ service.

---

## Repository Structure

See [`Repository_structure.md`](./Repository_structure.md) for the full directory tree.

**Role:** Entry point and pipeline coordinator. Receives a campaign trigger (ICP definition + product profile), fans out work to downstream services through queues, and monitors pipeline state.

**Responsibilities:**
- Accept a campaign configuration payload (ICP, product profile, target volume, email channel config).
- Publish a `plan.requested` event to kick off the Planning Service.
- After Sourcing finishes a batch, consume `sourcing.completed` and publish `prospecting.requested` so Prospecting work is explicit on its own queue.
- Monitor queue depths and service health.
- Handle retry logic for failed pipeline stages.
- Publish a `campaign.completed` event when all prospects have been processed.
- Expose HTTP endpoints for triggering campaigns and querying pipeline status.

**Does not:** Execute business logic. It only coordinates.

---

## Quick Start (Local Development)

**Role:** Analyzes the ICP and product profile to produce a structured **Plan Document** used by every downstream worker.

**Responsibilities:**
- Consume `plan.requested` events from the queue.
- Use an LLM (or rule-based logic) to analyze the ICP and product profile.
- Produce a **Plan Document** containing:
  - Key company attributes to look for during mining (industry, size, tech stack, funding stage, geography, etc.).
  - Key person attributes for POC identification (title, seniority, department, LinkedIn/page signals, etc.).
  - Scoring weights for each ICP dimension.
  - Personalization hooks to look for (recent news, product launches, job postings, blog posts, etc.).
  - Email tone and angle guidance (and optional `outreach_context` per additive spec).
  - Optional per-source **`search_blocks`**, **`global_filters`**, and related knobs for Sourcing (`planning_service_role.md`).
- Persist the Plan Document to **MongoDB**.
- Publish `plan.ready` event with the plan ID.

**Canonical spec for additive sourcing configuration:** [`planning_service_role.md`](planning_service_role.md).

**Key output:** A reusable Plan Document that anchors all downstream services to the same ICP interpretation.

# Run the orchestrator
cd src/orchestrator
npm install
npm run dev
```

### Environment Variables

**Role:** Runs **validated company discovery**, **deep enrichment**, and **POC identity resolution** exactly as enumerated in [`data_sourcing_map.md`](data_sourcing_map.md): Tier A directories, Tier B hint feeds, enrichment via owned web crawl + filings + anchored SERP, etc. Implements the cache-first workflows below.

**Implementation spec:** [`docs/data-sourcing-service.md`](docs/data-sourcing-service.md) — attribute source map, discovery vs enrichment, validation gates, crawl4ai + LLM extraction, provenance/hints in MongoDB, queues.

**Responsibilities:**
- Consume `sourcing.requested` events and merge any Plan-level `search_blocks` from [`planning_service_role.md`](planning_service_role.md).
- Execute the **cache-first sourcing decision** per company/domain and per POC identity skeleton.
- Run **Phase 1 discovery** and **Phase 2 enrichment** per `data_sourcing_map.md` (with crawl4ai / LLM extraction, allowed scrapers/APIs).
- Identify **who** qualifies as a POC from public cues (sites, filings, announcements, Product Hunt makers, etc.) — **without** invoking commercial email enrichment APIs here.
- Normalize + persist **`company_record`**, POC documents, **`hints`**, provenance payloads in MongoDB; publish `sourcing.completed` / `sourcing.partial`.

**Does not:** Run Apollo/Hunter email waterfalls, compute ICP scores, or gate prospects for Messaging.

---

### Prospecting Service

**Role:** Turns sourced companies + POC identities into ranked, email-ready prospects.

**Responsibilities:**
- Consume `prospecting.requested` events (published by the Orchestrator after `sourcing.completed`).
- Load the Plan Document for the current campaign.
- **Acquire and verify commercial contact emails** (Apollo.io, Hunter.io, or equivalent APIs) wherever policy allows — this step sits **after** Sourcing identities exist.
- For each POC/company pairing, compute an **ICP fit score** across the Plan weights; use semantic search on `extra` fields when schemas diverge (see [Semantic search](#semantic-search-on-unknown-columns)).
- Rank prospects, apply minimum score thresholds.
- Persist scores + email verification flags back to **MongoDB**; publish `prospecting.completed` with ranked prospect IDs.

**Does not:** Own long-form company discovery/enrichment spiders (that's Sourcing) or orchestrate Messaging drafts.

---

### Messaging Service

**Role:** Generates a personalized outbound email draft for each ranked prospect, writes it as a draft in the user's email account, and marks the prospect task as completed.

**Responsibilities:**
- Consume `messaging.requested` events.
- Load prospect record (company + POC data) and the Plan Document.
- Use an LLM to generate a personalized email leveraging:
  - POC name, title, and company context.
  - Personalization hooks identified during sourcing (news, signals, stack, etc.).
  - Tone and angle guidance from the Plan Document.
- **Write the generated email as a draft** in the user's email account via the configured email provider's draft API (e.g., Gmail `drafts.create`, Microsoft Graph `createDraft`).
- Store the draft record in **MongoDB** linked to the prospect record with status `draft_created`.
- Publish `draft.written` event.

**Does not:** Send emails. The system's responsibility ends at draft creation. The user reviews, edits, and sends drafts from their own email client.

---

## Web UI (Frontend)

**Role:** A static single-page application (SPA) that serves as the primary human interface for the entire system. It communicates exclusively with the Orchestrator's REST API.

**Capabilities:**
- **Campaign Management** — Create, view, edit, pause, resume, and cancel outreach campaigns. Define ICP, product profile, and email account configuration.
- **Pipeline Monitoring** — Real-time view of pipeline stage progress (planning → sourcing → prospecting → messaging → draft written). Queue depths, service health, and DLQ counts.
- **Prospect Browsing** — View scored and ranked prospects per campaign. Inspect full company + POC records. Skip individual prospects.
- **Draft Status Tracking** — View all generated drafts with their current status (`generating`, `draft_created`, `failed`). See which drafts have been written to the user's email account.
- **Draft Notifications** — When a draft is written to the user's email, the UI displays a notification with the prospect context and a link/reference to the draft in their email client.
- **Data Exploration** — Semantic search across company and POC records. Browse cached data, force re-scrape of stale records.
- **Campaign Statistics** — Draft creation count, success rate, pipeline throughput per campaign.

**Technical details:**
- Static SPA served by a dedicated `web-ui` nginx pod.
- All data fetched via REST calls to the Orchestrator at `/api/*`.
- No authentication required (internal tool).
- No server-side rendering — pure client-side React (or similar) build.

---

## Data Pipeline

### Cache-first strategy

Before running external calls, **Sourcing** checks MongoDB + supporting caches (`company_record`, linked POC identities, hint trails). Missing fields dictate how much of **`data_sourcing_map.md`** Phase 1/Phase 2 to re-run.

| Condition | Mode | Action |
|---|---|---|
| No usable document for entity | **Pull all sources** | Run relevant discovery **and** enrichment steps for company + POC cues |
| Partial coverage (sparse company attrs or missing POC identity lines) | **Targeted refill** | Re-hit only failing attributes / sources respecting freshness TTLs |
| Complete + fresh | **Cache hit** | Skip external mining; enqueue downstream enrichment for Prospecting if emails still absent |

**Freshness:** Configurable SLA windows (`freshness_days` on campaigns) differentiate long-lived structural facts vs fast-moving hires/news snippets.

**Split responsibilities:**
- **Sourcing gaps** revolve around company truth + identifiable POC personas (titles, bios, canonical URLs).
- **Prospecting** performs Apollo/Hunter passes when POC rows lack deliverable `@domain` inbox candidates.

---

### Scraping decision tree

```
Sourcing receives seeded targets / domains
        │
        ▼
Hydrate MongoDB snapshot for entity
        │
   ┌────┴─────────────────────────────┐
   │                                  │
   ▼                                  ▼
Cold record                      Warm snapshot
   │                                  │
   ▼                                  ▼
Run discovery + enrichment        Evaluate completeness
per data sourcing map tiers       vs freshness_budget
                                              │
                              ┌───────────────┴──────────────┐
                              │                              │
                              ▼                              ▼
                         Satisfied                       Gaps detected
                              │                              │
                              ▼                              ▼
                    Skip external mining          PATCH fields / rerun
                    emit sourcing.completed           targeted sources
                                                          emit sourcing.partial
```

---

### Discovery & enrichment pipeline

`data_sourcing_map.md` is authoritative; Sourcing mechanically mirrors its stages:

**Phase 1 — discovery (validated company enumeration)**  
Tier A directories (examples): Y Combinator roster, Product Hunt launches. Tier B *hints only* feed raw leads (HN Show HN/job threads, public LinkedIn company surfaces) → must pass deterministic validation gates before enrichment spend.

**Phase 2 — enrichment (known domains only)**  
- crawl4ai (or equivalents) → markdown → LLM JSON for corporate sites/blogs/`/careers` + ATS embeds  
- Regulatory / reference signals (`SEC EDGAR Form D`)  
- Anchored SERP/news pulls **after** canonical `(name,domain)`

**Supporting automation:** Browser automation stacks (browser-use, Firecrawl, etc.) may accelerate targeted fetch workloads but stay within the crawl policy defined in [`docs/data-sourcing-service.md`](docs/data-sourcing-service.md).

**Explicitly downstream from Sourcing:** Commercial email lookups (Apollo/Hunter) happen in Prospecting once personas exist.

---

## Data Sources

The table summarizes the same catalogue as **`data_sourcing_map.md`** (see that file for URLs, quotas, Tier A/Tier B rules, fallback chains):

| Source | Phase | Typical use | Domain focus |
|---|---|---|---|
| Y Combinator companies | Discovery / validation | Canonical startup domains + narratives | SW + HC |
| Product Hunt | Discovery | Recent launches & maker metadata | SW |
| Hacker News (Algolia) | Hint feed | Announcements/job threads needing validation | SW |
| LinkedIn (public listings) | Hint + enrichment | Employee bands, HQ clarity | SW + HC |
| Company websites & blogs | Enrichment | Product story, personalization hooks | SW + HC |
| Careers endpoints / ATS embeds | Enrichment | Hiring velocity, stack hints | SW + HC |
| Targeted SERP | Enrichment only | Anchored funding/news arcs | SW + HC |
| SEC EDGAR Form D | Enrichment | Regulatory funding disclosure | SW + HC |
| Apollo.io / Hunter.io | Prospecting (post-sourcing) | Commercial email retrieval + verification | — |

Operational limits (LinkedIn pacing, SerpAPI monthly caps, Crawl quotas) inherit from `data_sourcing_map.md` § *Pipeline Architecture Notes*.

---

## Data Schema

Data lives in MongoDB collections as **semi-structured documents** with enforced core paths plus permissive `extra` blobs discovered during sourcing. Semantic search overlays those dynamic keys (`extra`) as described later.

### Company Record

```
company_record {
  // ── Enforced Core Fields ─────────────────────────────
  id:                   string (uuid)
  name:                 string
  domain:               string
  industry:             string
  employee_count:       integer | null
  headquarters:         { city, country }
  funding_stage:        enum [ bootstrapped, seed, series_a, series_b, growth, public, unknown ]
  tech_stack:           string[]
  description:          string | null
  linkedin_url:         string | null
  website_url:          string | null
  icp_fit_score:        float | null          // set by Prospecting Service
  data_completeness:    float                 // 0.0 – 1.0
  freshness_timestamp:  ISO-8601 datetime
  scrape_mode_last:     enum [ all, partial, none ]
  campaign_ids:         string[]

  // ── Semi-Structured Additional Fields ────────────────
  extra: {
    [key: string]: any                        // arbitrary fields from scraping
  }
}
```

### Person of Contact (POC) Record

```
poc_record {
  // ── Enforced Core Fields ─────────────────────────────
  id:                   string (uuid)
  company_id:           string (ref → company_record.id)
  first_name:           string
  last_name:            string
  title:                string
  seniority:            enum [ ic, manager, director, vp, c_level, founder, unknown ]
  department:           string
  email:                string | null
  email_verified:       boolean
  linkedin_url:         string | null
  icp_poc_score:        float | null
  freshness_timestamp:  ISO-8601 datetime

  // ── Semi-Structured Additional Fields ────────────────
  extra: {
    [key: string]: any
  }
}
```

### Draft Email Record

```
email_draft_record {
  id:                   string (uuid)
  campaign_id:          string
  company_id:           string
  poc_id:               string
  subject:              string
  body:                 string
  personalization_hooks: string[]
  generated_at:         ISO-8601 datetime
  status:               enum [ generating, draft_created, failed ]
  email_draft_ref:      string | null          // provider draft ID (e.g., Gmail draft ID)
  email_provider:       enum [ gmail, microsoft ] | null
  error:                string | null          // populated on failure
  retry_count:          integer
}
```

### Campaign Record

```
campaign_record {
  id:                   string (uuid)
  name:                 string
  icp:                  { ... ICP definition object ... }
  product_profile:      { ... product description object ... }
  plan_id:              string (ref → plan_record.id)
  status:               enum [ draft, running, completed, paused ]
  created_at:           ISO-8601 datetime
  config: {
    email_account: {
      provider:         enum [ gmail, microsoft ]
      credentials_ref:  string                   // reference to stored OAuth token
    }
    min_icp_score:      float
    freshness_days:     integer
    max_drafts:         integer                  // cap on drafts per campaign
  }
}
```

### Plan Record

```
plan_record {
  id:                   string (uuid)
  campaign_id:          string
  company_signals:      string[]    // attributes to look for in companies
  poc_signals:          string[]    // attributes to look for in POCs
  scoring_weights: {
    [dimension: string]: float
  }
  personalization_hooks: string[]   // signals to surface per prospect
  email_tone:           string
  email_angle:          string
  created_at:           ISO-8601 datetime
}
```

**Additive sourcing configuration:** the persisted document may extend this shape with **`search_blocks`**, **`global_filters`**, and **`outreach_context`** described in [`planning_service_role.md`](planning_service_role.md).

---

## Message Queues

All inter-service communication is asynchronous via named message queues. Services never call each other directly.

**Message broker:** **RabbitMQ** everywhere — local Docker (`src/local_infrastructure/rabbit_mq/`), in-cluster on EKS, or Amazon MQ — with durable queues, at-least-once delivery, and dead-letter queues. Logical names below map directly to RabbitMQ queues/exchanges per environment ([`cloud_INFRASTRUCTURE.md`](./cloud_INFRASTRUCTURE.md)).

### Queue Definitions

| Queue Name | Published By | Consumed By | Payload |
|---|---|---|---|
| `plan.requested` | Orchestrator | Planning Service | `{ campaign_id }` |
| `plan.ready` | Planning Service | Orchestrator, Sourcing Service | `{ campaign_id, plan_id }` |
| `sourcing.requested` | Orchestrator | Sourcing Service | `{ campaign_id, plan_id, target_entities[] }` |
| `sourcing.completed` | Sourcing Service | Orchestrator | `{ campaign_id, entity_ids[] }` |
| `sourcing.partial` | Sourcing Service | Orchestrator | `{ campaign_id, entity_id, missing_fields[] }` |
| `prospecting.requested` | Orchestrator | Prospecting Service | `{ campaign_id, plan_id, entity_ids[] }` |
| `prospecting.completed` | Prospecting Service | Orchestrator, Messaging Service | `{ campaign_id, ranked_prospects[] }` |
| `messaging.requested` | Orchestrator | Messaging Service | `{ campaign_id, poc_id }` |
| `draft.written` | Messaging Service | Orchestrator | `{ campaign_id, draft_id, poc_id, email_draft_ref }` |
| `draft.failed` | Messaging Service | Orchestrator | `{ campaign_id, draft_id, poc_id, error, retry_count }` |
| `campaign.completed` | Orchestrator | — (terminal event) | `{ campaign_id, stats }` |

**Removed queues** (vs. earlier design iterations): `review.requested`, `review.completed`, `send.requested`, `send.completed`, `send.failed`, `messaging.completed`. The system no longer reviews or sends — it writes drafts and marks the task done.

### Queue Behaviors

- All queues are **durable** — messages survive service restarts.
- Consumers use **at-least-once delivery** with idempotency keys on all records.
- Failed messages are moved to a **Dead Letter Queue (DLQ)** after a configurable retry limit.
- Queue depth is monitored by the Orchestrator for backpressure and alerting.

---

## API Endpoints

All endpoints are HTTP/REST. No authentication is required. The Orchestrator Service owns the public API surface. The Web UI consumes these endpoints at `/api/*`.

### Campaigns
- `POST /campaigns` — Create and trigger a campaign
- `GET /campaigns` — List all campaigns
- `GET /campaigns/:id` — Campaign details + pipeline state
- `PATCH /campaigns/:id` — Pause/resume, update send window
- `DELETE /campaigns/:id` — Cancel campaign
- `GET /campaigns/:id/stats` — Sent count, approval rate, bounce rate
- `GET /campaigns/:id/prospects` — Ranked prospects
- `GET /campaigns/:id/drafts` — Drafts (filterable by `?status=`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/campaigns` | Create and trigger a new outreach campaign |
| `GET` | `/api/campaigns` | List all campaigns with status |
| `GET` | `/api/campaigns/:id` | Get campaign details and pipeline status |
| `PATCH` | `/api/campaigns/:id` | Update campaign config (pause, resume) |
| `DELETE` | `/api/campaigns/:id` | Cancel and archive a campaign |

**`POST /api/campaigns` request body:**
```
{
  name: string,
  icp: { ... },
  product_profile: { ... },
  config: {
    email_account: {
      provider: "gmail" | "microsoft",
      credentials_ref: string          // reference to stored OAuth token
    },
    min_icp_score: float,
    freshness_days: integer,
    max_drafts: integer                // cap on how many drafts to create per campaign
  }
}
```

---

## Broker Switching

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/campaigns/:id/prospects` | List scored and ranked prospects for a campaign |
| `GET` | `/api/prospects/:id` | Get full prospect record (company + POC + score) |
| `PATCH` | `/api/prospects/:id/skip` | Mark a prospect as skipped (exclude from messaging) |

- **Local dev**: `BROKER_TYPE=rabbitmq` + `RABBITMQ_URL=amqp://localhost`
- **Production**: `BROKER_TYPE=sqs` + `AWS_REGION=us-east-1`

### Draft Management

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/campaigns/:id/drafts` | List all drafts for a campaign with status |
| `GET` | `/api/drafts/:id` | Get a specific draft record |
| `POST` | `/api/drafts/:id/regenerate` | Request a new draft for this prospect (re-run messaging) |

Drafts are **read-only** from the system's perspective after creation. The user edits and sends drafts directly in their email client (Gmail, Outlook, etc.). The system does not approve, reject, or send.

---

### Data & Cache

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/companies/:id` | Get a company document from MongoDB |
| `GET` | `/api/persons/:id` | Get a POC document from MongoDB |
| `POST` | `/api/companies/:id/refresh` | Force re-scrape of a company regardless of cache |
| `GET` | `/api/search` | Semantic search across MongoDB-backed records (see below) |

---

### Pipeline & System Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Service liveness check |
| `GET` | `/api/status` | Queue depths, service statuses, DLQ count |
| `GET` | `/api/campaigns/:id/stats` | Draft count, success rate, pipeline throughput per campaign |
| `GET` | `/api/campaigns/:id/pipeline` | Stage-by-stage progress for the campaign |

---

### Web UI Static Assets

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Serve the Web UI SPA (index.html + assets) |
| `GET` | `/assets/*` | Static JS/CSS/image bundles |

The Web UI is served by a dedicated `web-ui` nginx pod. All `/api/*` requests are routed to the Orchestrator via ingress rules.

---

## MongoDB storage design

**Database:** MongoDB (document store backing every service).

**Collections:**

| Collection | Primary Key | Notes |
|---|---|---|
| `campaigns` | `campaign_id` | Campaign config and status |
| `plans` | `plan_id` | Planning Service output, linked to campaign |
| `companies` | `company_id` | Company records with enforced + extra fields |
| `persons` | `poc_id` | POC records with enforced + extra fields |
| `email_drafts` | `draft_id` | Draft records with status lifecycle |

**Indexing strategy:**
- `company_id`, `domain`, `campaign_ids` indexed on `companies`.
- `poc_id`, `company_id`, `email` indexed on `persons`.
- `campaign_id`, `status` indexed on `email_drafts` for Web UI queries.
- `freshness_timestamp` indexed on `companies` and `persons` for cache expiry checks.

---

## Semantic Search on Unknown Columns

Applies primarily to **`companies` and `persons` collections** in MongoDB.

Because documents are semi-structured, the `extra` map on companies and POCs may expose arbitrary keys (e.g. `annual_recurring_revenue`, `primary_use_case`).

When the Prospecting Service or any downstream service needs to query on a field that is not in the enforced schema, it uses **semantic search on the column key**:

**How it works:**
1. The query specifies an intent (e.g., "find prospects that use Kubernetes").
2. The system embeds the query intent and compares it against the embedded keys present in `extra` fields across all records.
3. Records where a key is semantically similar to the query (cosine similarity above a threshold) are returned with the matched key and value.
4. This enables discovery of relevant data regardless of inconsistent naming across scraping sources.

**`GET /search` endpoint:**

| Parameter | Type | Description |
|---|---|---|
| `q` | string | Natural language query (e.g., "companies that recently raised Series B") |
| `collection` | string | Target collection: `companies`, `persons` |
| `campaign_id` | string (optional) | Scope search to a specific campaign |
| `top_k` | integer | Number of results to return (default: 20) |

**Response includes:**
- Matched records with relevance score.
- The specific `extra` key that triggered the match.
- The value of that key.

---

## System Flow — End to End

```
1. User opens the Web UI and creates a campaign
   → POSTs to /api/campaigns with ICP, product profile, and email account config
        │
        ▼
2. Orchestrator creates campaign record, publishes plan.requested
        │
        ▼
3. Planning Service consumes plan.requested
   → Analyses ICP and product profile
   → Produces Plan Document (signals, weights, tone, hooks) plus additive sourcing blocks (`planning_service_role.md`)
   → Persists plan in MongoDB, publishes plan.ready
        │
        ▼
4. Orchestrator receives plan.ready
   → Publishes sourcing.requested with target entity list
   → Web UI shows pipeline progress (stage: sourcing)
        │
        ▼
5. Sourcing Service consumes sourcing.requested
   → For each seed / resolved domain:
       a. Hydrate MongoDB snapshots + hints cache
       b. Decide Pull-all / targeted refill / cache hit via cache-first table
       c. Phase 1 discovery + Tier B validation gates, then Phase 2 enrichment
       d. Emit POC identities (no Apollo/Hunter yet); write companies + POC skeletons + hints to MongoDB
   → Publishes sourcing.completed
        │
        ▼
6. Orchestrator consumes sourcing.completed
   → Publishes prospecting.requested with campaign, plan, and entity IDs
        │
        ▼
7. Prospecting Service consumes prospecting.requested
   → Loads Plan Document
   → Apollo/Hunter/email APIs fill deliverable inbox candidates + verification flags
   → Scores companies + POCs vs ICP weights; semantic search spans `extra` blobs
   → Ranks prospects, filters below min_icp_score → MongoDB persists scores/email state
   → Publishes prospecting.completed with ranked list
   → Web UI shows pipeline progress (stage: prospecting)
        │
        ▼
8. Orchestrator publishes messaging.requested for top N prospects
   → Web UI shows pipeline progress (stage: messaging)
        │
        ▼
9. Messaging Service consumes messaging.requested
   → Loads prospect record + Plan Document
   → Generates personalized email draft via LLM
   → Writes draft to user's email account via provider Draft API
     (e.g., Gmail drafts.create, Microsoft Graph createDraft)
   → Stores draft record in MongoDB (status: draft_created)
   → Publishes draft.written
   → On failure: publishes draft.failed (retries up to configured limit)
        │
        ▼
10. Orchestrator receives draft.written events
   → Updates campaign progress
   → Web UI displays notification: "Draft created for [POC name] at [Company]"
   → User can find the draft in their email client, review, edit, and send manually
        │
        ▼
11. When all prospects are processed: Orchestrator publishes campaign.completed
    → Campaign stats available at /api/campaigns/:id/stats
    → Web UI shows campaign as completed with summary statistics
```

**The system's responsibility ends at step 9.** Once a draft is written to the user's email account, the prospect task is marked complete. All further editing and sending is done by the user in their email client.

---

*This document describes the full design of the Autonomous Email Outreach System. Services coordinate exclusively through RabbitMQ. MongoDB absorbs every authoritative document with cache-first sourcing passes before revisiting Tier A/B sources. Semantic search atop `extra` keys keeps ingestion flexible across heterogeneous providers. Messaging stops at drafts inside the customer's mailbox — outbound sending stays human-owned.*
