# Data Sourcing Map — Autonomous Email Outreach
**Domains:** Software · Healthcare | **Target:** Small startups to mid-size companies

**Enrichment contract:** Phase 2 enrichment is defined by the **three fixed operations** in [`enrichment_redesign.md`](./enrichment_redesign.md) (LinkedIn POC via SERP → crawl4ai, YC directory, company website landing page only). This map keeps **discovery** sources and **optional** signals that sit outside that core.

---

## Overview

The pipeline has two distinct phases that run sequentially. Discovery produces a validated list of company domains (and seeds). **Enrichment** runs only on validated companies and is intentionally narrow: three parallel operations with per-operation provenance and fail-soft semantics ([`enrichment_redesign.md`](./enrichment_redesign.md)). Keeping discovery separate avoids wasting crawl and LLM budget on bad candidates.

---

## Phase 1 — Discovery (Finding Companies)

### Tier A — Structured Directories (scrape-first, highest quality)

| Source | URL | Access | Cost | Key Fields | Domains | Priority |
|---|---|---|---|---|---|---|
| Y Combinator | ycombinator.com/companies | HTML scrape or CSV mirror | Free | Name, domain, batch, description, B2B tag | SW + HC | Primary |
| Product Hunt | producthunt.com | Free API + HTML fallback | Free API key | Launch date, upvotes, tags, maker info, website | SW | Primary |

**Usage notes:**
- **YC:** Filter by `domain=Healthcare` or `B2B SaaS`. Batch year = implicit funding recency proxy. ~4,000 companies total. Refresh quarterly. Same directory backs **enrichment op 2** (founders + latest news) when the company is listed.
- **Product Hunt:** Use upvote count as traction proxy. Makers field can seed contact discovery later. Best for recent software launches (last 24 months).

---

### Tier B — Signal Sources (candidate extraction only, not clean lists)

> These sources output candidate names and URLs that must be validated against a Tier A source before enrichment begins.

| Source | URL | Access | Cost | Signal Type | Domains | Priority |
|---|---|---|---|---|---|---|
| Hacker News | news.ycombinator.com | Algolia HN API (free) | Free | Show HN posts, job threads, product announcements | SW | Fallback |
| LinkedIn (discovery hints) | linkedin.com (various public surfaces) | HTML scrape (public pages only) | Free | Industry, headcount range, founding year, description, website URL | SW + HC | Fallback |

**Usage notes:**
- **HN:** Search `"Show HN"` and `"Who is hiring"` via Algolia API. Extract URL + company name only. Do not treat as a clean list.
- **LinkedIn (discovery):** Throttle heavily; do not scrape aggressively. Useful for **candidate validation** and fallback discovery (employee band, industry). **This is not the same path as enrichment op 1:** POC enrichment uses a **`{company_name} LinkedIn` SERP → first LinkedIn URL → single-page crawl** flow ([`enrichment_redesign.md`](./enrichment_redesign.md)).

---

## Phase 2 — Enrichment (Deepening Known Companies)

Canonical spec: **[`enrichment_redesign.md`](./enrichment_redesign.md)** — three operations, runnable in parallel, each with its own provenance; one operation failing does not abort the others.

### The three operations

| # | Operation | Input | Primary signals / output | Tooling |
|---|-----------|--------|---------------------------|---------|
| 1 | **LinkedIn POC lookup** | Company name | POC name, title, profile URL if inferable; scrape bundle includes About, people visible on page, location, recent posts (whatever renders without navigation) | **SERP:** `{company_name}` + `LinkedIn` → **first LinkedIn URL** in results → **crawl4ai** on that URL only (**no navigation**) → **LLM** selects best POC |
| 2 | **YC directory lookup** | Company name | Founders; latest news / launch blurb if present | YC directory scraper / API; skip cleanly if not in directory |
| 3 | **Company website info** | Company URL, or company name if URL unknown | Summary, value props, signals visible **on the landing page only** | If no URL: **SERP** → treat **top result** as canonical site → **crawl4ai** landing page only (**no navigation** — no `/about`, `/team`, `/blog` crawls) → **LLM** extraction. **Login wall on landing → drop** for this op (`dropped: login_required`). |

**Hard constraints (aligned with redesign):**
- **Op 1 & 3:** Single fetched page per operation (follow redirects only as specified in redesign); **no** tab clicks, “See all”, or internal link following for deeper pages.
- **Op 2:** No crawl4ai requirement for the core path; optional light HTTP if implementation reads HTML.

---

### Optional extensions (outside the three-op core)

The following are **not** part of the collapsed enrichment model but may appear in roadmap or campaigns that opt in explicitly:

| Source | Access | Cost | Typical use | Notes |
|--------|--------|------|-------------|-------|
| Careers / jobs pages | crawl4ai + LLM on `/careers`, Greenhouse, Lever, Ashby | LLM cost | Hiring velocity, role mix | Contradicts “landing page only” unless promoted to a **fourth** tracked operation |
| Targeted SERP (funding, press) | SerpAPI / scrape | Quota | Funding / launch snippets | Keep queries anchored to `(company_name, domain)`; not used for bulk list harvest |
| SEC EDGAR Form D | efts.sec.gov REST API | Free | Private raise signals, SIC | Filter e.g. `7372`, `8099`; filing lag vs press |

---

## Fallback Chains

### Startup discovery
```
YC directory  →  Product Hunt  →  HN Show HN
```

### Enrichment (collapsed model)
```
Parallel:
  • Op 1 — SERP "{company} LinkedIn" → first linkedin.com URL → crawl4ai (no nav) → LLM POC
  • Op 2 — YC directory (founders + news) — skip if absent
  • Op 3 — SERP canonical site if needed → crawl4ai landing only (no nav) → LLM
```
(No ordering dependency between the three; implement retries/idempotency per operation.)

### Funding signal enrichment (optional extension)
```
SEC EDGAR Form D  →  SERP (anchored funding query)
```

### Hiring + product signals (optional extension)
```
Careers page crawl  →  (optional) other sources per campaign config
```

### Tech stack identification (optional extension)
```
Landing-page-only crawl + LLM  →  Job posts (stack hints in JDs)
```

---

## Pipeline Architecture Notes

**Phase separation is intentional.** Discovery and enrichment are separate pipelines with a validation gate between them. Any candidate from a Tier B signal source must be cross-checked against a Tier A source before enrichment spend.

**Enrichment** follows **[`enrichment_redesign.md`](./enrichment_redesign.md):** three operations, **per-operation validation** (not a generic attribute-source-map matrix for those ops). Discovery and optional extensions may still use structured attribute rules where useful.

**LLM extraction targets:** Single-page markdown from crawl4ai (ops 1 and 3), YC structured fields (op 2), optional SERP snippets for extensions. Prefer a low-cost model with JSON schema. Cache markdown keyed by URL + content hash; respect TTL policy per campaign.

**Rate limit defaults:**
- LinkedIn-related traffic (SERP + single-page fetch): throttle consistently with policy; avoid aggressive parallel hits to linkedin.com.
- SerpAPI free: 100 searches/month — batch wisely (each company may consume SERP for op 1 and possibly op 3).

**Service boundary:** **Sourcing** discovers company domains, runs the **three enrichment operations**, and attaches **POC identity** from public evidence. **Prospecting** handles **commercial email discovery and verification** (e.g. Apollo.io, Hunter.io), ICP scoring, ranking, and thresholding before messaging.

---

## Quick Reference — Source Index

| Source | Phase | Domain | Access | Cost |
|---|---|---|---|---|
| Y Combinator | Discovery + enrichment op 2 | SW + HC | HTML scrape / API | Free |
| Product Hunt | Discovery | SW | API | Free |
| Hacker News | Discovery (signals) | SW | Algolia API | Free |
| LinkedIn | Discovery hints + **enrichment op 1** (SERP → single page) | SW + HC | SERP + crawl4ai | SERP quota + LLM |
| Company website | **Enrichment op 3** (landing only) | SW + HC | SERP (optional) + crawl4ai | LLM |
| SERP | Enrichment op 1 & 3 (discovery URLs) | SW + HC | SerpAPI / scrape | Free tier / quota |
| Careers / jobs | Optional extension | SW + HC | crawl4ai | LLM |
| SEC EDGAR | Optional extension | SW + HC | REST API | Free |
