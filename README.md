# Autonomous Email Outreach System

> A distributed, AI-powered outbound sales engine that mines public data, scores prospects, generates personalized email drafts, and writes them directly to the user's email account — all orchestrated through asynchronous message queues and managed through a Web UI.

---

## Table of Contents

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
   - [Web Scraping Layers](#web-scraping-layers)
6. [Data Sources](#data-sources)
7. [Data Schema](#data-schema)
8. [Message Queues](#message-queues)
9. [API Endpoints](#api-endpoints)
10. [NoSQL Storage Design](#nosql-storage-design)
11. [Semantic Search on Unknown Columns](#semantic-search-on-unknown-columns)
12. [System Flow — End to End](#system-flow--end-to-end)

---

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
│  │ Analyse ICP  │   │  Mine data   │   │  Score and   │                   │
│  │ & product    │   │  Layer 1→2   │   │  rank POCs   │                   │
│  │ Build plan   │   │  Cache-first │   │  vs ICP      │                   │
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
│  All services READ and WRITE to shared NoSQL store                         │
│  All services communicate ONLY via message queues                          │
│  Web UI talks only to the Orchestrator API (HTTP)                          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Services

### Orchestrator Service

**Role:** Entry point and pipeline coordinator. Receives a campaign trigger (ICP definition + product profile), fans out work to downstream services through queues, and monitors pipeline state.

**Responsibilities:**
- Accept a campaign configuration payload (ICP, product profile, target volume, email channel config).
- Publish a `plan.requested` event to kick off the Planning Service.
- Monitor queue depths and service health.
- Handle retry logic for failed pipeline stages.
- Publish a `campaign.completed` event when all prospects have been processed.
- Expose HTTP endpoints for triggering campaigns and querying pipeline status.

**Does not:** Execute business logic. It only coordinates.

---

### Planning Service

**Role:** Analyzes the ICP and product profile to produce a structured **mining plan** — a set of key pointers used by all downstream services.

**Responsibilities:**
- Consume `plan.requested` events from the queue.
- Use an LLM (or rule-based logic) to analyze the ICP and product profile.
- Produce a **Plan Document** containing:
  - Key company attributes to look for during mining (industry, size, tech stack, funding stage, geography, etc.).
  - Key person attributes for POC identification (title, seniority, department, LinkedIn signals, etc.).
  - Scoring weights for each ICP dimension.
  - Personalization hooks to look for (recent news, product launches, job postings, blog posts, etc.).
  - Email tone and angle guidance.
- Persist the Plan Document to NoSQL.
- Publish `plan.ready` event with the plan ID.

**Key output:** A reusable Plan Document that anchors all downstream services to the same ICP interpretation.

---

### Sourcing Service

**Role:** Mines publicly available data to find matching companies and POCs. Implements the cache-first, layered scraping strategy.

**Implementation spec:** [docs/data-sourcing-service.md](docs/data-sourcing-service.md) — attribute source map, company discovery vs enrichment, validation gates, crawl4ai + LLM extraction, storage provenance, and queue payloads.

**Responsibilities:**
- Consume `sourcing.requested` events.
- For each target entity (company or person), execute the **Cache-First Decision** (see Data Pipeline section).
- Coordinate multi-layer scraping when needed:
  - **Layer 1:** Structured APIs (Apollo, Hunter, LinkedIn, GitHub).
  - **Layer 2:** Headless browser scraping (crawl4ai, browser-use, Firecrawl).
- Normalize and store raw mined data in NoSQL under a semi-structured schema.
- Tag each record with a `freshness_timestamp` and `data_completeness_score`.
- Publish `sourcing.completed` or `sourcing.partial` events.

**Does not:** Score prospects. It only collects and stores data.

---

### Prospecting Service

**Role:** Scores and ranks all sourced prospects against the ICP using the Plan Document's scoring weights.

**Responsibilities:**
- Consume `sourcing.completed` events.
- Load the Plan Document for the current campaign.
- For each sourced company and POC, compute an **ICP fit score** across all defined dimensions.
- Handle unknown or missing fields using semantic search against the NoSQL store.
- Rank prospects and apply a minimum threshold filter.
- Write scored and ranked records back to NoSQL.
- Publish `prospecting.completed` events with a list of ranked prospect IDs.

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
- Store the draft record in NoSQL linked to the prospect record with status `draft_created`.
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

### Cache-First Strategy

Before every data mining operation, the Sourcing Service checks the NoSQL store for existing data on the target entity. The outcome determines the scraping mode:

| Condition | Mode | Action |
|---|---|---|
| No data exists | **Scrape All** | Full Layer 1 → Layer 2 scrape for the entity |
| Partial data exists (missing fields or incomplete POC list) | **Scrape Partial** | Targeted scrape to fill specific gaps |
| Sufficient data exists and is within the freshness window | **No Scrape** | Use cached data directly |

**Freshness window** is configurable per entity type (e.g., company data valid for 30 days, POC contact data valid for 14 days).

**Partial data scenarios:**
- Some companies are sourced but POC contact data is missing.
- A company record exists but specific fields required by the Plan Document are absent.
- POC email is present but LinkedIn profile or role tenure is missing.

---

### Scraping Decision Tree

```
Sourcing Service receives target entity
        │
        ▼
Check NoSQL cache for entity
        │
   ┌────┴────────────────────────────────┐
   │                                     │
   ▼                                     ▼
No data found                     Data found
   │                                     │
   ▼                            Check completeness
SCRAPE ALL                       & freshness
(Layer 1 → Layer 2)                      │
                              ┌──────────┴──────────┐
                              │                     │
                              ▼                     ▼
                      Sufficient &          Incomplete or
                      fresh                 stale
                              │                     │
                              ▼                     ▼
                        NO SCRAPE           SCRAPE PARTIAL
                        use cache           (targeted gap fill)
                                            Layer 1 → Layer 2
                                            for missing fields
```

---

### Web Scraping Layers

Data mining is executed in two layers. Layer 2 is only invoked when Layer 1 is insufficient.

```
Target Entity
      │
      ▼
Layer 1: Structured APIs
  ├── Apollo.io         — company & contact database, email addresses
  ├── Hunter.io         — email discovery and verification
  ├── LinkedIn API      — role, seniority, company headcount, tenure
  └── GitHub API        — tech stack signals, open-source activity
      │
      ├── [Sufficient data returned]
      │         └──→ Extract → Normalize → Write to NoSQL cache → Done
      │
      └── [Gap detected — required fields still missing]
                │
                ▼
         Layer 2: Headless Browser Scraping
           ├── crawl4ai       — structured extraction from web pages
           ├── browser-use    — agentic browser automation
           └── Firecrawl      — crawl and extract from company websites, blogs, job boards
                │
                ├── [Sufficient data returned]
                │         └──→ Extract → Normalize → Write to NoSQL cache → Done
                │
                └── [Still insufficient]
                          └──→ Mark record as `data_incomplete`
                               Flag for manual review or skip in ranking
```

**Scraping targets at Layer 2:**
- Company website (About, Team, Product pages).
- Company blog (recent posts for personalization hooks).
- Job postings (signals for team growth, tech stack needs).
- Press releases and news mentions.
- Public LinkedIn profiles (where accessible without login).
- Crunchbase and similar funding databases.

---

## Data Sources

| Source | Type | Layer | Data Provided |
|---|---|---|---|
| Apollo.io | Structured API | 1 | Company info, contacts, emails, phone |
| Hunter.io | Structured API | 1 | Email discovery, domain verification |
| LinkedIn | Structured API | 1 | Role, seniority, headcount, tenure, connections |
| GitHub | Structured API | 1 | Tech stack, open-source repos, engineering team size |
| crawl4ai | Headless Browser | 2 | Structured extraction from any URL |
| browser-use | Headless Browser | 2 | Agentic browsing, form-based pages |
| Firecrawl | Headless Browser | 2 | Full-site crawl, markdown extraction |
| Company websites | Headless Browser | 2 | About, Team, Product, Blog pages |
| Job boards | Headless Browser | 2 | Open roles, tech stack signals |
| Crunchbase | Headless Browser | 2 | Funding rounds, investors, growth stage |
| News / PR sites | Headless Browser | 2 | Recent company news for personalization |

---

## Data Schema

Data is stored in a **semi-structured NoSQL schema**. A core set of fields is enforced as the known schema. Additional fields discovered during scraping are stored as-is and are queryable via semantic search on the column key.

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

---

## Message Queues

All inter-service communication is asynchronous via named message queues. Services never call each other directly.

**Message broker:** The implementation uses **RabbitMQ** (durable queues, at-least-once delivery, dead-letter handling).  The logical queue names below map to RabbitMQ queues (and optional exchanges) in each environment. See [`cloud_INFRASTRUCTURE.md`](./cloud_INFRASTRUCTURE.md) for deployment and scaling details.

### Queue Definitions

| Queue Name | Published By | Consumed By | Payload |
|---|---|---|---|
| `plan.requested` | Orchestrator | Planning Service | `{ campaign_id }` |
| `plan.ready` | Planning Service | Orchestrator, Sourcing Service | `{ campaign_id, plan_id }` |
| `sourcing.requested` | Orchestrator | Sourcing Service | `{ campaign_id, plan_id, target_entities[] }` |
| `sourcing.completed` | Sourcing Service | Orchestrator, Prospecting Service | `{ campaign_id, entity_ids[] }` |
| `sourcing.partial` | Sourcing Service | Orchestrator | `{ campaign_id, entity_id, missing_fields[] }` |
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

### Campaign Management

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

### Prospect Management

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/campaigns/:id/prospects` | List scored and ranked prospects for a campaign |
| `GET` | `/api/prospects/:id` | Get full prospect record (company + POC + score) |
| `PATCH` | `/api/prospects/:id/skip` | Mark a prospect as skipped (exclude from messaging) |

---

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
| `GET` | `/api/companies/:id` | Get a company record from NoSQL |
| `GET` | `/api/persons/:id` | Get a POC record from NoSQL |
| `POST` | `/api/companies/:id/refresh` | Force re-scrape of a company regardless of cache |
| `GET` | `/api/search` | Semantic search across NoSQL records (see below) |

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

## NoSQL Storage Design

**Database type:** Document store (e.g., MongoDB, DynamoDB, Firestore, or CouchDB).

**Collections / Tables:**

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

Because the schema is semi-structured, the `extra` field on company and POC records may contain arbitrary keys discovered during scraping (e.g., `annual_recurring_revenue`, `primary_use_case`, `last_funding_round_lead_investor`).

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
   → Produces Plan Document (signals, weights, tone, hooks)
   → Persists plan, publishes plan.ready
        │
        ▼
4. Orchestrator receives plan.ready
   → Publishes sourcing.requested with target entity list
   → Web UI shows pipeline progress (stage: sourcing)
        │
        ▼
5. Sourcing Service consumes sourcing.requested
   → For each target entity:
       a. Check NoSQL cache
       b. Decide: Scrape All / Scrape Partial / No Scrape
       c. Execute Layer 1 APIs → if gap → Layer 2 headless browser
       d. Normalize and write to NoSQL
   → Publishes sourcing.completed
        │
        ▼
6. Prospecting Service consumes sourcing.completed
   → Loads Plan Document
   → Scores each company and POC against ICP weights
   → Uses semantic search for unknown extra fields
   → Ranks prospects, filters below min_icp_score
   → Writes scores to NoSQL
   → Publishes prospecting.completed with ranked list
   → Web UI shows pipeline progress (stage: prospecting)
        │
        ▼
7. Orchestrator publishes messaging.requested for top N prospects
   → Web UI shows pipeline progress (stage: messaging)
        │
        ▼
8. Messaging Service consumes messaging.requested
   → Loads prospect record + Plan Document
   → Generates personalized email draft via LLM
   → Writes draft to user's email account via provider Draft API
     (e.g., Gmail drafts.create, Microsoft Graph createDraft)
   → Stores draft record in NoSQL (status: draft_created)
   → Publishes draft.written
   → On failure: publishes draft.failed (retries up to configured limit)
        │
        ▼
9. Orchestrator receives draft.written events
   → Updates campaign progress
   → Web UI displays notification: "Draft created for [POC name] at [Company]"
   → User can find the draft in their email client, review, edit, and send manually
        │
        ▼
10. When all prospects are processed: Orchestrator publishes campaign.completed
    → Campaign stats available at /api/campaigns/:id/stats
    → Web UI shows campaign as completed with summary statistics
```

**The system's responsibility ends at step 8.** Once a draft is written to the user's email account, the prospect task is marked complete. All further editing and sending is done by the user in their email client.

---

*This document describes the full design of the Autonomous Email Outreach System. All inter-service communication is asynchronous. All mined data is cached in NoSQL with a cache-first lookup before any scraping is triggered. The semi-structured schema with semantic search on unknown columns ensures flexibility as scraped data varies across sources and targets. The system generates email drafts and places them in the user's email account — it never sends emails directly.*
