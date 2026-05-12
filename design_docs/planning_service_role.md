# Planning Service — Plan Document & sourcing configuration

This guide is **additive** to the high-level Planning Service summary in [`README.md`](README.md). It specifies how the Planning Service translates an ICP and product profile into a **Plan Document** stored in **MongoDB**, including optional **per-source discovery filters** the Sourcing Service consumes.

---

## Contents

1. [Purpose](#1-purpose)
2. [Outputs and consumers](#2-outputs-and-consumers)
3. [Canonical vs additive fields](#3-canonical-vs-additive-fields)
4. [LLM inputs](#4-llm-inputs)
5. [Per-source search blocks](#5-per-source-search-blocks)
   - [Product Hunt](#51-product-hunt)
   - [YC / YC directory (`yc_news`)](#52-yc--yc-directory-yc_news)
   - [Hacker News (`hacker_news`)](#53-hacker-news-hacker_news)
6. [Global filters](#6-global-filters)
7. [Outreach context](#7-outreach-context)
8. [Validation rules](#8-validation-rules)
9. [Related documents](#9-related-documents)

---

## 1. Purpose

The Planning Service turns a campaign’s **ICP** and **product profile** into one persisted **Plan Document** that downstream services reuse for the life of that campaign:

- **Sourcing** uses company/personalization signals **and** structured `search_config` blocks to query directories, feeds, and enrichers aligned with [`data_sourcing_map.md`](data_sourcing_map.md).
- **Prospecting** uses `poc_signals`, `scoring_weights`, and the same document for ranking (and orchestrates commercial email enrichment — see README).
- **Messaging** uses tone, angle, personalization hooks, and `outreach_context` when drafting.

---

## 2. Outputs and consumers

| Artifact | Persisted where | Primary consumers |
|----------|----------------|-------------------|
| Plan Document (canonical + additive fields below) | MongoDB `plans` collection | Sourcing, Prospecting, Messaging |

---

## 3. Canonical vs additive fields

The **canonical** shape is summarized under **Plan Record** in [`README.md`](README.md) (`company_signals`, `poc_signals`, `scoring_weights`, `personalization_hooks`, `email_tone`, `email_angle`).

The following **additive** JSON sections are appended to that document (either as sibling top-level keys or nested under a single `sourcing_config` object — whichever the implementation chooses, as long as Sourcing agrees on one shape):

| Key | Purpose |
|-----|---------|
| `search_blocks` | Array of per-source configs (sections [§5](#5-per-source-search-blocks)) |
| `global_filters` | Cross-source constraints ([§6](#6-global-filters)) |
| `outreach_context` | Non-mining knobs for Messaging / sequencing ([§7](#7-outreach-context)) |

---

## 4. LLM inputs

For each campaign plan, the LLM (or hybrid rules + LLM) is given:

- The full **ICP** and **product profile**
- A description of **each integrated data source** (see [`data_sourcing_map.md`](data_sourcing_map.md))
- The **catalog of allowed filters** and valid value ranges **per source** (tables in [§5](#5-per-source-search-blocks))

The model **selects** filters and values from that catalog only — it does not invent new filter names or unconstrained enums.

---

## 5. Per-source search blocks

Each block enables Sourcing to parameterize discovery/enrichment APIs and scrapers. Shape:

```json
{
  "source": "<integration_id>",
  "enabled": true,
  "filters": { }
}
```

### 5.1 Product Hunt

```json
{
  "source": "product_hunt",
  "enabled": true,
  "filters": {
    "topics": ["Developer Tools", "SaaS", "Productivity"],
    "posted_after": "2023-01-01",
    "min_votes": 50
  }
}
```

**Supported filters the LLM may populate:**

| Filter | Type | Description |
|---|---|---|
| `topics` | `string[]` | Product Hunt topic tags (e.g. "AI", "Developer Tools", "Fintech") |
| `posted_after` | `date` | Only include products launched after this date |
| `posted_before` | `date` | Only include products launched before this date |
| `min_votes` | `integer` | Minimum upvote threshold |

### 5.2 YC / YC directory (`yc_news`)

```json
{
  "source": "yc_news",
  "enabled": true,
  "filters": {
    "batch_years": ["W23", "S23", "W24"],
    "industries": ["B2B", "DevTools", "HR Tech"],
    "company_stage": ["seed", "series_a"],
    "regions": ["North America"]
  }
}
```

**Supported filters the LLM may populate:**

| Filter | Type | Description |
|---|---|---|
| `batch_years` | `string[]` | YC batch identifiers (e.g. `W23`, `S24`) |
| `industries` | `string[]` | Industry tags as listed on YC company profiles |
| `company_stage` | `string[]` | Funding stage filter |
| `regions` | `string[]` | Geographic region of the company |

### 5.3 Hacker News (`hacker_news`)

Maps to the HN discovery path in `src/sourcing/discovery/hacker_news.py` (Algolia-backed search).

```json
{
  "source": "hacker_news",
  "enabled": true,
  "filters": {
    "query": "devtools OR observability",
    "tags": ["show_hn", "launch_hn"],
    "min_points": 10,
    "min_comments": 3,
    "created_after": "2024-01-01"
  }
}
```

**Supported filters the LLM may populate:**

| Filter | Type | Description |
|---|---|---|
| `query` | `string` | Free-text search across title, URL, and story text |
| `tags` | `string[]` | Story type(s): `show_hn`, `launch_hn`, `story`, `ask_hn` only |
| `min_points` | `integer` | Minimum score (points); must be ≥ 0 |
| `min_comments` | `integer` | Minimum comment count; must be ≥ 0 |
| `created_after` | `date` | Only include items created on or after this date |

*Additional sources from [`data_sourcing_map.md`](data_sourcing_map.md) should get their own blocks here as integrations land; use the same `{ "source", "enabled", "filters" }` pattern.*

---

## 6. Global filters

Constraints applied across **all** enabled sources after sourcing runs merging/dedupe:

```json
{
  "global_filters": {
    "exclude_domains": ["example.com"],
    "employee_count_range": { "min": 10, "max": 200 },
    "languages": ["en"],
    "exclude_already_contacted": true
  }
}
```

---

## 7. Outreach context

Consumed primarily by **Messaging** and echoed in Orchestrator/UI where useful:

```json
{
  "outreach_context": {
    "campaign_goal": "Book a discovery call",
    "tone": "professional",
    "personalization_hints": ["mention recent Product Hunt launch", "reference YC batch"],
    "sequence_length": 3
  }
}
```

Canonical `email_tone` / `email_angle` in README remain authoritative for draft generation unless the implementation explicitly prefers `outreach_context` fields (document the precedence in code comments).

---

## 8. Validation rules

- The LLM does **not** guess filter values outside the enumerated options.
- If the ICP does not supply enough evidence for a filter, **omit** that filter rather than defaulting arbitrarily.
- Sourcing rejects or ignores malformed blocks and logs structured errors; malformed plans should surface as pipeline failures observable from the Orchestrator.

---

## 9. Related documents

- [`README.md`](README.md) — system architecture, services, Plan Record overview, queues, MongoDB storage
- [`data_sourcing_map.md`](data_sourcing_map.md) — which sources exist, tiers, phases, fallback chains
- [`docs/data-sourcing-service.md`](docs/data-sourcing-service.md) — Sourcing implementation: attribute maps, caches, queues, provenance

