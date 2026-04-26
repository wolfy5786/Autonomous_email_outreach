# Data Sourcing Service

Implementation-oriented design for the **Sourcing** service: company discovery, attribute mining, validation, and persistence. It aligns with the system overview in [README.md](../README.md) and the repository layout in [Repository_structure.md](../Repository_structure.md).

## Table of contents

1. [Purpose and service boundary](#1-purpose-and-service-boundary)
2. [Relationship to Planning and Prospecting](#2-relationship-to-planning-and-prospecting)
3. [Inputs and outputs](#3-inputs-and-outputs)
4. [End-to-end pipeline](#4-end-to-end-pipeline)
5. [Attribute source map](#5-attribute-source-map)
6. [Source catalog and usage rules](#6-source-catalog-and-usage-rules)
7. [Scraping and extraction pipeline](#7-scraping-and-extraction-pipeline)
8. [Validation gates and failure modes](#8-validation-gates-and-failure-modes)
9. [Storage model](#9-storage-model)
10. [Queue contracts and idempotency](#10-queue-contracts-and-idempotency)
11. [Operational constraints](#11-operational-constraints)

---

## 1. Purpose and service boundary

**Role:** Mine public data to find **relevant companies** and **enrich company records** (attributes, signals, evidence) against the campaign’s Ideal Customer Profile (ICP), using a **cache-first** strategy and layered APIs plus headless scraping.

**In scope**

- Consume `sourcing.requested` and load the **Plan Document** (via `plan_id`) for attribute targets and constraints.
- Build an **attribute-to-source map** before calling external systems.
- **Company discovery:** produce a candidate list of companies that match the ICP (where the plan allows).
- **Company enrichment:** fill `company_record` fields and optional `extra` keys from approved sources.
- Normalize output, attach **provenance** (URL, source name, extraction method, timestamp), compute **data completeness**, and publish `sourcing.completed` or `sourcing.partial`.

**Out of scope (belongs to Prospecting)**

- **POC (person-of-contact) discovery**, title fit, seniority scoring, or ranking prospects.
- **ICP fit scoring** and thresholding.
- Email draft generation or review.

---

## 2. Relationship to Planning and Prospecting

| Service    | Responsibility |
|-----------|----------------|
| **Planning** | Produces the Plan Document: `company_signals`, `poc_signals`, `scoring_weights`, `personalization_hooks`, tone, angle. Sourcing uses **company signals** and hooks to drive *what* to mine; it does **not** use POC scoring weights for sourcing logic. |
| **Sourcing** | Companies + enrichment + evidence; no prospect scores. |
| **Prospecting** | Scores sourced companies/POCs, ranks prospects, handles POC discovery workflows. |

---

## 3. Inputs and outputs

### 3.1 Primary input (queue)

Base contract (from [README.md](../README.md)):

```text
sourcing.requested → { campaign_id, plan_id, target_entities[] }
```

**Implementation extension (recommended):** the Orchestrator may include optional fields Sourcing should accept without breaking older consumers:

```json
{
  "campaign_id": "uuid",
  "plan_id": "uuid",
  "target_entities": [],
  "request_id": "uuid",
  "config": {
    "max_companies": 500,
    "discovery_mode": "yc_only | broad | seed_domains",
    "freshness_override_days": null
  },
  "seeds": {
    "domains": ["example.com"],
    "company_names": ["Acme Inc"]
  }
}
```

- `target_entities` may be empty when the campaign expects **discovery-only** from configured sources (e.g. YC directory + filters); otherwise it lists explicit companies/domains to enrich.
- `request_id` supports idempotency and deduplication of writes (see [§10](#10-queue-contracts-and-idempotency)).

### 3.2 Outputs

- **NoSQL:** Upserted `company_record` documents (see [§9](#9-storage-model)).
- **Events:**
  - `sourcing.completed` — `{ campaign_id, entity_ids[] }` (entity IDs = sourced company IDs).
  - `sourcing.partial` — `{ campaign_id, entity_id, missing_fields[] }` when enrichment is incomplete but still useful.

Optional extension for observability (if all consumers tolerate extra keys):

```json
{
  "campaign_id": "uuid",
  "entity_ids": ["uuid"],
  "stats": {
    "companies_discovered": 120,
    "companies_enriched": 115,
    "rejected_candidates": 40
  }
}
```

---

## 4. End-to-end pipeline

1. **Load plan** — Fetch `plan_record` / Plan Document by `plan_id`; read `company_signals`, `personalization_hooks`, and any campaign-specific flags.
2. **Cache check** — For each candidate or seed company, apply the **cache-first** rules from [README.md](../README.md) (no data → scrape all; partial → targeted gap fill; fresh + complete → no scrape).
3. **Build attribute source map** — Deterministic map from requested attributes → sources, query templates, extraction schemas, fallbacks ([§5](#5-attribute-source-map)).
4. **Company discovery** — If needed, query **allowed discovery sources** (e.g. [YC Startup Directory](https://www.ycombinator.com/companies)) with ICP filters; optionally use **hint** sources ([Hacker News newest](https://news.ycombinator.com/newest)) only to surface leads, not as canonical identity.
5. **Candidate validation** — Relevance, deduplication, domain sanity, blocklists ([§8](#8-validation-gates-and-failure-modes)).
6. **Company mining** — Layer 1 APIs where configured; Layer 2 crawl4ai + LLM extraction for web; **SERP only for known companies** ([§6](#6-source-catalog-and-usage-rules)).
7. **Enrichment validation** — Schema, evidence, confidence, conflicts, completeness.
8. **Store and emit** — Persist records, publish `sourcing.completed` or `sourcing.partial`.

```mermaid
flowchart TD
  PlanReady["Plan Document Ready"] --> BuildMap["Build Attribute Source Map"]
  BuildMap --> CompanyDiscovery["Find Relevant Companies"]
  CompanyDiscovery --> CandidateValidation["Validate Candidate Companies"]
  CandidateValidation --> CompanyMining["Mine Company Attributes"]
  CompanyMining --> EnrichmentValidation["Validate Enrichment"]
  EnrichmentValidation --> StoreData["Store Company Records"]
  StoreData --> PublishEvent["Publish Sourcing Event"]
```

---

## 5. Attribute source map

Before calling external APIs or scrapers, Sourcing builds a **AttributeSourceMap**: a list of rules that bind each logical attribute to one or more sources and extraction strategies.

### 5.1 Rule object schema

| Field | Type | Description |
|-------|------|-------------|
| `attribute` | `string` | Logical name, e.g. `domain`, `industry`, `employee_count`, `funding_stage`, `tech_stack`, `description`, `linkedin_company_url`, `recent_news_summary`. |
| `source_type` | `enum` | `api`, `serp`, `scrape`, `directory`, `hint_feed`. |
| `source_name` | `string` | e.g. `apollo`, `yc_directory`, `company_website`, `serp`, `hn_newest`. |
| `allowed_for_discovery` | `boolean` | If `true`, this source may be used to **enumerate** candidate companies. |
| `allowed_for_enrichment` | `boolean` | If `true`, may be used to **fill attributes** for a known company. |
| `query_template` | `string \| null` | Template with placeholders: `{{company_name}}`, `{{domain}}`, `{{icp_keyword}}`. Used for SERP or directory search. |
| `extraction_schema` | `JSON Schema` | Expected LLM or parser output shape for this attribute from markdown or API JSON. |
| `confidence_weight` | `float` | 0–1; used when merging conflicting values. |
| `priority` | `int` | Lower = tried first among rules for the same attribute. |
| `fallback_sources` | `string[]` | Ordered list of `source_name` values if primary fails or low confidence. |

### 5.2 Discovery vs enrichment

| Mode | Purpose | SERP | YC directory | HN newest |
|------|---------|------|--------------|-----------|
| **Discovery** | Build a list of companies | **No** (not for broad lists) | **Yes** (if ICP = startups) | **Hints only** — queue URLs/names for validation, not authoritative |
| **Enrichment** | Fill fields for a known `name` + `domain` | **Yes** — company-specific queries only | **Yes** — profile page if company is in YC | **Optional** — e.g. “Show HN” link to product page |

**Rule:** **SERP** must include an anchor: company name and/or registered domain, so results are tied to a specific entity—not used to discover the open web unbounded.

### 5.3 Example (illustrative YAML)

```yaml
attributes:
  - attribute: domain
    source_type: directory
    source_name: yc_directory
    allowed_for_discovery: true
    allowed_for_enrichment: true
    extraction_schema:
      type: object
      properties: { domain: { type: string, format: hostname } }
    confidence_weight: 0.95
    priority: 1

  - attribute: recent_news_summary
    source_type: serp
    source_name: serp
    allowed_for_discovery: false
    allowed_for_enrichment: true
    query_template: "{{company_name}} {{domain}} funding OR product launch news"
    extraction_schema:
      type: object
      properties:
        summary: { type: string, maxLength: 500 }
        source_urls: { type: array, items: { type: string, format: uri } }
    confidence_weight: 0.6
    priority: 2
    fallback_sources: ["company_website_blog"]
```

---

## 6. Source catalog and usage rules

### 6.1 Y Combinator — [The YC Startup Directory](https://www.ycombinator.com/companies)

- **Use:** Startup-oriented **discovery** and structured fields available on directory/company pages (e.g. name, description, batch, website).
- **Layer:** Treat as **directory** / **Layer 2 scrape** depending on whether you use a public API or HTML; align with [README.md](../README.md) Layer 1 vs Layer 2 split for your integration.

### 6.2 Hacker News — [newest](https://news.ycombinator.com/newest)

- **Use:** **Hints only** — emerging products, “Show HN”, startup announcements.
- **Do not:** Treat as a complete or stable company database.
- **Pipeline:** Extract candidate company name + URL → run through **candidate validation** → then enrich like any other lead.

### 6.3 SERP (search engine results page)

- **Use:** **Enrichment only** after a specific company is identified (name/domain).
- **Typical queries:** Funding, press, careers page, product launch, site-specific pages.
- **Do not:** Use unconstrained SERP to harvest large company lists (cost, quality, policy).

### 6.4 LinkedIn

- **Use:** Company page fields where contractually and technically permitted (often via official API as **Layer 1** in [README.md](../README.md)); scraping public pages falls under **Layer 2** and must follow [§11](#11-operational-constraints).
- **Typical attributes:** Employee range, industry, description, company URL.

### 6.5 Company website / blog / careers

- **Use:** Primary **enrichment** for description, stack hints, hiring signals, and personalization hooks.
- **Mechanism:** crawl4ai → markdown → low-cost LLM extraction ([§7](#7-scraping-and-extraction-pipeline)).

### 6.6 Alignment with README layers

From [README.md](../README.md):

- **Layer 1:** Structured APIs (Apollo, Hunter, LinkedIn, GitHub, etc.) — prefer when available and sufficient.
- **Layer 2:** Headless browser scraping (crawl4ai, browser-use, Firecrawl) when Layer 1 leaves gaps.

The attribute map should prefer Layer 1 rules first, then Layer 2 with `fallback_sources`.

---

## 7. Scraping and extraction pipeline

### 7.1 Stages

1. **URL discovery** — From directory links, SERP results, sitemap, or known `/about`, `/blog`, `/careers` paths.
2. **Fetch** — Headless fetch with timeouts, redirect limits, and content-type checks.
3. **Markdown conversion** — **crawl4ai** (or equivalent) converts HTML to **markdown** for stable, token-efficient input.
4. **Structured extraction** — A **low-cost LLM** maps markdown (and/or API JSON) to the **extraction JSON Schema** defined in the attribute map.
5. **Evidence capture** — Store snippet spans, selectors, or char offsets where feasible; always store **canonical URL** and **retrieved_at**.

### 7.2 LLM extraction contract

- **Input:** `{ "url", "markdown": "...", "requested_attributes": ["industry", ...] }`
- **Output:** JSON matching the combined `extraction_schema` for those attributes.
- **Constraints:**
  - **Schema-bound:** No free-form prose except fields explicitly allowed (e.g. `recent_news_summary`).
  - **No business decisions:** The LLM does not decide ICP fit or whether to keep a company; deterministic rules and Prospecting do.
  - **Hallucination guard:** If the markdown does not support a field, return `null` and optional `unsupported_reason`.

### 7.3 Cost and quality controls

- Chunk long markdown; extract only requested attributes per chunk.
- Cache markdown and extraction results keyed by `(url, schema_version, content_hash)` to avoid repeat LLM calls.

---

## 8. Validation gates and failure modes

### 8.1 Candidate validation (post-discovery, pre-persist)

- **ICP relevance** — Keyword, industry, stage, geography vs Plan Document (rules or small classifier; deterministic threshold documented per campaign).
- **Deduplication** — Same `domain` (normalized) or strong name+location match → merge or skip.
- **Domain sanity** — Valid TLD, not a parking page, MX optional depending on plan.
- **Blocklist** — Competitors, excluded industries, sanctioned regions if configured.

### 8.2 Enrichment validation

- **Schema validation** — Output must match `extraction_schema`.
- **Evidence** — Required fields must have at least one `source_url` when sourced from web/SERP.
- **Freshness** — Compare to `freshness_timestamp` / campaign `freshness_days` ([README.md](../README.md)).
- **Conflict resolution** — When two sources disagree, use `confidence_weight` and source priority; if still ambiguous, store both under `extra` with provenance and lower confidence.

### 8.3 Failure mode codes

Use in logs, `sourcing.partial` context, and internal `company_record` status if modeled:

| Code | Meaning |
|------|---------|
| `company_rejected` | Failed candidate validation; not stored as active lead. |
| `data_incomplete` | Stored with gaps; `missing_fields` listed in partial event. |
| `source_unavailable` | HTTP error, rate limit, or API down. |
| `extraction_failed` | LLM/parse error or schema mismatch. |
| `validation_failed` | Evidence or sanity check failed. |

---

## 9. Storage model

Compatible with `company_record` in [README.md](../README.md): core fields plus semi-structured `extra`.

### 9.1 Provenance and evidence

Extend each stored attribute (core or `extra`) with optional **provenance** metadata. Two implementation options:

**Option A — Sidecar map** (recommended for query clarity):

```json
{
  "id": "uuid",
  "name": "Example Inc",
  "domain": "example.com",
  "industry": "developer tools",
  "data_completeness": 0.82,
  "freshness_timestamp": "2026-04-25T12:00:00Z",
  "scrape_mode_last": "partial",
  "campaign_ids": ["uuid"],
  "extra": {},
  "provenance": {
    "industry": {
      "source_name": "linkedin_api",
      "source_type": "api",
      "observed_value": "Computer Software",
      "normalized_value": "developer tools",
      "confidence": 0.9,
      "evidence_urls": [],
      "extracted_at": "2026-04-25T12:00:00Z"
    },
    "recent_news_summary": {
      "source_name": "serp",
      "source_type": "serp",
      "confidence": 0.55,
      "evidence_urls": ["https://example.com/press/2026-launch"],
      "snippet": "…",
      "extracted_at": "2026-04-25T12:00:00Z"
    }
  }
}
```

**Option B — Values only in `extra`** with keys like `industry__source` — less normalized but simpler for early prototypes.

### 9.2 Raw artifacts

- Store **full markdown** only when needed for debugging (e.g. S3 object with TTL), or cap size in Mongo `extra.raw_markdown_preview` (first N chars).
- Always store `content_hash` to detect page changes on re-scrape.

---

## 10. Queue contracts and idempotency

### 10.1 Messages (authoritative from [README.md](../README.md))

| Event | Payload |
|-------|---------|
| `sourcing.requested` | `{ campaign_id, plan_id, target_entities[] }` |
| `sourcing.completed` | `{ campaign_id, entity_ids[] }` |
| `sourcing.partial` | `{ campaign_id, entity_id, missing_fields[] }` |

### 10.2 Idempotency and at-least-once delivery

- Queues are **durable** with **at-least-once** delivery; consumers must be **idempotent**.
- **Idempotency key:** `hash(campaign_id + plan_id + request_id + entity_id + operation)` for each upsert.
- **Dedup:** Reprocessing the same `sourcing.requested` should not create duplicate `company_record` rows for the same normalized domain; use upsert on `(domain)` or `external_ids.yc_slug` etc.
- **Partial events:** May be emitted multiple times for the same entity as more fields fill in; downstream consumers should merge by `entity_id`.

### 10.3 Retries and DLQ

- Follow platform defaults ([README.md](../README.md)): retries with DLQ; sourcing workloads may use longer visibility timeouts (see [cloud_INFRASTRUCTURE.md](../cloud_INFRASTRUCTURE.md) for AWS examples).

---

## 11. Operational constraints

- **Rate limits:** Per provider token bucket; global concurrency cap for headless browsers on scraping node pools.
- **Robots.txt / ToS:** Respect site policies; prefer official APIs for LinkedIn and similar.
- **User-Agent:** Identifiable, honest UA string; include contact in comments if required by policy.
- **SERP:** Quota and cost monitoring; block overly generic queries.
- **Secrets:** API keys in secrets manager, not in code (see [Repository_structure.md](../Repository_structure.md), `email-outreach/*` secrets).
- **Observability:** Log `source_name`, `latency_ms`, `outcome` per call; trace IDs across fetch → markdown → LLM.
- **LLM use:** Extraction and summarization only; ICP and POC decisions live in **Prospecting** and **Planning**.

---

## Document history

- **v1** — Initial implementation-oriented Sourcing spec (attribute map, sources, pipeline, storage, queues).

See also: [README.md](../README.md) (Sourcing Service, Data Pipeline, Data Schema, Message Queues), [Repository_structure.md](../Repository_structure.md).
