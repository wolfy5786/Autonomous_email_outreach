# Autonomous Email Outreach System

> A distributed, AI-powered outbound sales engine that mines public data, scores prospects, generates personalized messages, routes drafts through human review, and delivers approved emails — all orchestrated through asynchronous message queues with no user authentication required.

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
   - [Review Service](#review-service)
   - [Send Service](#send-service)
4. [Data Pipeline](#data-pipeline)
   - [Cache-First Strategy](#cache-first-strategy)
   - [Scraping Decision Tree](#scraping-decision-tree)
   - [Web Scraping Layers](#web-scraping-layers)
5. [Data Sources](#data-sources)
6. [Data Schema](#data-schema)
7. [Message Queues](#message-queues)
8. [API Endpoints](#api-endpoints)
9. [NoSQL Storage Design](#nosql-storage-design)
10. [Semantic Search on Unknown Columns](#semantic-search-on-unknown-columns)
11. [System Flow — End to End](#system-flow--end-to-end)

---

## System Overview

The system automates the full outbound sales cycle:

1. **Mine** publicly available data to find companies and persons of contact (POC) matching an Ideal Customer Profile (ICP).
2. **Score and rank** prospects against the ICP using a structured scoring model.
3. **Generate** a personalized outbound message per prospect.
4. **Route** drafts through a human review UI before sending.
5. **Send** approved messages via a configurable email channel.

There is **no user authentication**. The review UI is an open internal tool. All inter-service communication is handled exclusively through **message queues**.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DISTRIBUTED WEB ARCHITECTURE                         │
│                                                                             │
│  ┌──────────────┐                                                           │
│  │ Orchestrator │ ← Entry point. Coordinates the full pipeline.            │
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
│                   │  per prospect    │                                     │
│                   └────────┬─────────┘                                     │
│                            │                                               │
│                            ▼                                               │
│                   ┌──────────────────┐                                     │
│                   │   Review UI /    │                                     │
│                   │  Review Service  │                                     │
│                   │  Human approves  │                                     │
│                   │  edits or rejects│                                     │
│                   └────────┬─────────┘                                     │
│                            │                                               │
│                            ▼                                               │
│                   ┌──────────────────┐                                     │
│                   │   Send Service   │                                     │
│                   │  Deliver via     │                                     │
│                   │  email channel   │                                     │
│                   └──────────────────┘                                     │
│                                                                             │
│  ════════════════════════════════════════════════════                      │
│  All services READ and WRITE to shared NoSQL store                         │
│  All services communicate ONLY via message queues                          │
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

**Role:** Generates a personalized outbound email draft for each approved prospect.

**Responsibilities:**
- Consume `messaging.requested` events.
- Load prospect record (company + POC data) and the Plan Document.
- Use an LLM to generate a personalized email leveraging:
  - POC name, title, and company context.
  - Personalization hooks identified during sourcing (news, signals, stack, etc.).
  - Tone and angle guidance from the Plan Document.
- Store the draft email in NoSQL linked to the prospect record.
- Publish `review.requested` event.

---

### Review Service

**Role:** Hosts a human-facing review UI where operators can approve, edit, or reject draft emails before they are sent.

**Responsibilities:**
- Serve the Review UI (no authentication required — internal tool).
- Consume `review.requested` events to populate the review queue in the UI.
- Support three actions per draft: **Approve**, **Edit + Approve**, **Reject**.
- On approval: publish `send.requested` event.
- On rejection: optionally publish `messaging.requested` event for regeneration with feedback.
- Record review decisions and optional reviewer notes in NoSQL.

**UI features:**
- List view of all pending drafts with prospect context.
- Inline editing of subject line and body.
- Bulk approve for batches of similar prospects.
- Rejection with optional regeneration prompt.

---

### Send Service

**Role:** Delivers approved emails through a configurable email channel.

**Responsibilities:**
- Consume `send.requested` events.
- Load the approved draft and prospect record.
- Route through the configured email provider (SMTP, SendGrid, Postmark, AWS SES, etc.).
- Record send status, message ID, and timestamp back to NoSQL.
- Publish `send.completed` or `send.failed` events.
- Implement rate limiting and send-window scheduling to respect provider limits and avoid spam flags.

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
  status:               enum [ pending_review, approved, edited_approved, rejected, sent, failed ]
  reviewer_notes:       string | null
  reviewed_at:          ISO-8601 datetime | null
  sent_at:              ISO-8601 datetime | null
  send_message_id:      string | null
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
  status:               enum [ draft, running, review, completed, paused ]
  created_at:           ISO-8601 datetime
  config: {
    email_channel:      enum [ smtp, sendgrid, postmark, ses ]
    email_channel_config: { ... provider-specific config ... }
    min_icp_score:      float
    freshness_days:     integer
    send_window:        { start_hour: int, end_hour: int, timezone: string }
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

### Queue Definitions

| Queue Name | Published By | Consumed By | Payload |
|---|---|---|---|
| `plan.requested` | Orchestrator | Planning Service | `{ campaign_id }` |
| `plan.ready` | Planning Service | Orchestrator, Sourcing Service | `{ campaign_id, plan_id }` |
| `sourcing.requested` | Orchestrator | Sourcing Service | `{ campaign_id, plan_id, target_entities[] }` |
| `sourcing.completed` | Sourcing Service | Orchestrator, Prospecting Service | `{ campaign_id, entity_ids[] }` |
| `sourcing.partial` | Sourcing Service | Orchestrator | `{ campaign_id, entity_id, missing_fields[] }` |
| `prospecting.completed` | Prospecting Service | Orchestrator, Messaging Service | `{ campaign_id, ranked_prospects[] }` |
| `messaging.requested` | Orchestrator / Review Service | Messaging Service | `{ campaign_id, poc_id, regeneration_prompt? }` |
| `messaging.completed` | Messaging Service | Orchestrator | `{ campaign_id, draft_id }` |
| `review.requested` | Messaging Service | Review Service | `{ draft_id }` |
| `review.completed` | Review Service | Orchestrator | `{ draft_id, decision: approve/reject, notes? }` |
| `send.requested` | Review Service | Send Service | `{ draft_id }` |
| `send.completed` | Send Service | Orchestrator | `{ draft_id, message_id, sent_at }` |
| `send.failed` | Send Service | Orchestrator | `{ draft_id, error, retry_count }` |
| `campaign.completed` | Orchestrator | — (terminal event) | `{ campaign_id, stats }` |

### Queue Behaviors

- All queues are **durable** — messages survive service restarts.
- Consumers use **at-least-once delivery** with idempotency keys on all records.
- Failed messages are moved to a **Dead Letter Queue (DLQ)** after a configurable retry limit.
- Queue depth is monitored by the Orchestrator for backpressure and alerting.

---

## API Endpoints

All endpoints are HTTP/REST. No authentication is required. The Orchestrator Service owns the public API surface.

### Campaign Management

| Method | Path | Description |
|---|---|---|
| `POST` | `/campaigns` | Create and trigger a new outreach campaign |
| `GET` | `/campaigns` | List all campaigns with status |
| `GET` | `/campaigns/:id` | Get campaign details and pipeline status |
| `PATCH` | `/campaigns/:id` | Update campaign config (pause, resume, update send window) |
| `DELETE` | `/campaigns/:id` | Cancel and archive a campaign |

**`POST /campaigns` request body:**
```
{
  name: string,
  icp: { ... },
  product_profile: { ... },
  config: {
    email_channel: "sendgrid" | "smtp" | "postmark" | "ses",
    email_channel_config: { ... },
    min_icp_score: float,
    freshness_days: integer,
    send_window: { start_hour, end_hour, timezone }
  }
}
```

---

### Prospect Management

| Method | Path | Description |
|---|---|---|
| `GET` | `/campaigns/:id/prospects` | List scored and ranked prospects for a campaign |
| `GET` | `/prospects/:id` | Get full prospect record (company + POC + score) |
| `PATCH` | `/prospects/:id/skip` | Mark a prospect as skipped (exclude from messaging) |

---

### Draft Email Management

| Method | Path | Description |
|---|---|---|
| `GET` | `/campaigns/:id/drafts` | List all drafts for a campaign with status |
| `GET` | `/drafts/:id` | Get a specific draft |
| `PATCH` | `/drafts/:id` | Update draft subject or body (used by Review UI) |
| `POST` | `/drafts/:id/approve` | Approve a draft → publishes `send.requested` |
| `POST` | `/drafts/:id/reject` | Reject a draft with optional regeneration prompt |
| `POST` | `/drafts/:id/regenerate` | Request a new draft for this prospect |

---

### Review UI

| Method | Path | Description |
|---|---|---|
| `GET` | `/review` | Serve the human review UI (HTML page) |
| `GET` | `/review/queue` | Get all drafts pending review (JSON) |
| `POST` | `/review/bulk-approve` | Approve a batch of draft IDs |

---

### Data & Cache

| Method | Path | Description |
|---|---|---|
| `GET` | `/companies/:id` | Get a company record from NoSQL |
| `GET` | `/persons/:id` | Get a POC record from NoSQL |
| `POST` | `/companies/:id/refresh` | Force re-scrape of a company regardless of cache |
| `GET` | `/search` | Semantic search across NoSQL records (see below) |

---

### System Health

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Service liveness check |
| `GET` | `/status` | Queue depths, service statuses, DLQ count |
| `GET` | `/campaigns/:id/stats` | Sent count, approval rate, bounce rate per campaign |

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
| `send_log` | `send_id` | Immutable log of all send attempts |

**Indexing strategy:**
- `company_id`, `domain`, `campaign_ids` indexed on `companies`.
- `poc_id`, `company_id`, `email` indexed on `persons`.
- `campaign_id`, `status` indexed on `email_drafts` for Review UI queries.
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
1. Operator POSTs to /campaigns with ICP + product profile
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
        │
        ▼
7. Orchestrator publishes messaging.requested for top N prospects
        │
        ▼
8. Messaging Service consumes messaging.requested
   → Loads prospect record + Plan Document
   → Generates personalized email draft via LLM
   → Stores draft in NoSQL (status: pending_review)
   → Publishes review.requested
        │
        ▼
9. Review Service populates review queue in UI
   → Human operator reviews drafts in browser
   → Approves / edits+approves / rejects
   → On approve: publishes send.requested
   → On reject: optionally publishes messaging.requested with feedback
        │
        ▼
10. Send Service consumes send.requested
    → Loads approved draft and POC email
    → Sends via configured email channel
    → Records send status and message ID in NoSQL
    → Publishes send.completed or send.failed
        │
        ▼
11. Orchestrator aggregates send.completed events
    → When all prospects processed: publishes campaign.completed
    → Campaign stats available at /campaigns/:id/stats
```

---

*This document describes the full design of the Autonomous Email Outreach System. All inter-service communication is asynchronous. All mined data is cached in NoSQL with a cache-first lookup before any scraping is triggered. The semi-structured schema with semantic search on unknown columns ensures flexibility as scraped data varies across sources and targets.*
