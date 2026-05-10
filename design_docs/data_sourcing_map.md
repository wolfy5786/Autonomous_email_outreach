# Data Sourcing Map — Autonomous Email Outreach
**Domains:** Software · Healthcare | **Target:** Small startups to mid-size companies

---

## Overview

The pipeline has two distinct phases that run sequentially. Discovery produces a validated list of company domains. Sourcing (enrichment) runs only on that validated list to pull deeper signals. Keeping them separate avoids wasting crawl and LLM budget on bad candidates.

---

## Phase 1 — Discovery (Finding Companies)

### Tier A — Structured Directories (scrape-first, highest quality)

| Source | URL | Access | Cost | Key Fields | Domains | Priority |
|---|---|---|---|---|---|---|
| Y Combinator | ycombinator.com/companies | HTML scrape or CSV mirror | Free | Name, domain, batch, description, B2B tag | SW + HC | Primary |
| Open Corporates | opencorporates.com | Free REST API | Free (check current plan; ~500 API calls/day on free tier) | Legal name, incorporation date, officers, registered address, jurisdiction, active status | SW + HC | Primary |
| Product Hunt | producthunt.com | Free API + HTML fallback | Free API key | Launch date, upvotes, tags, maker info, website | SW | Primary |

**Usage notes:**
- **YC:** Filter by `domain=Healthcare` or `B2B SaaS`. Batch year = implicit funding recency proxy. ~4,000 companies total. Refresh quarterly.
- **Open Corporates:** Use to resolve and validate legal entities (and as a hook for domain discovery where filings link out). Not a funding-round directory; pair with SEC EDGAR and SERP for raise signals. Respect API rate limits.
- **Product Hunt:** Use upvote count as traction proxy. Makers field can seed contact discovery later. Best for recent software launches (last 24 months).

---

### Tier A — Domain-Specific Directories

| Source | URL | Access | Cost | Key Fields | Domains | Priority |
|---|---|---|---|---|---|---|
| NIH Reporter | reporter.nih.gov | Free REST API — no key required | Free | PI, institution, project title, abstract, funding amount, keywords | HC | Primary |

**Usage notes:**
- **NIH Reporter:** Overlaps with SBIR but also surfaces academic spinouts. Use project abstracts to score ICP relevance via LLM.

---

### Tier B — Signal Sources (candidate extraction only, not clean lists)

> These sources output candidate names and URLs that must be validated against a Tier A source before enrichment begins.

| Source | URL | Access | Cost | Signal Type | Domains | Priority |
|---|---|---|---|---|---|---|
| Hacker News | news.ycombinator.com | Algolia HN API (free) | Free | Show HN posts, job threads, product announcements | SW | Fallback |
| LinkedIn Company Pages | linkedin.com/search/results/companies | HTML scrape (public pages only) | Free | Industry, headcount range, founding year, description, website | SW + HC | Fallback |

**Usage notes:**
- **HN:** Search `"Show HN"` and `"Who is hiring"` via Algolia API. Extract URL + company name only. Do not treat as a clean list.
- **LinkedIn:** Throttle requests heavily, dont scrape aggresively.  Employee range is the most reliable field. Use only for validation and fallback discovery.

---

## Phase 2 — Sourcing / Enrichment (Deepening Known Companies)

### Tier A — Web Presence (primary enrichment pipeline)

| Source | Access | Cost | Key Signals | Priority |
|---|---|---|---|---|
| Company website + blog | crawl4ai → markdown → LLM extraction | LLM cost only (cache markdown, TTL 30 days) | Product description, ICP signals, pricing hints, tech mentions, recent announcements | Primary |
| Careers / jobs page | crawl4ai → LLM extraction from /careers, Greenhouse, Lever, Ashby | LLM cost only | Open role count, role types, tech stack in JDs, seniority distribution | Primary |

**Usage notes:**
- **Website + blog:** Cache markdown per domain (TTL 30 days). Extract: what they sell, who they sell to, recent blog topics. Blog recency = company activity signal.
- **Careers page:** Hiring velocity = growth signal. "VP of Sales" hire = expansion phase. "Data engineer" hire = scaling infra. Always check Greenhouse/Lever/Ashby embeds separately.

---

### Tier A — Funding and Investment Signals

| Source | URL | Access | Cost | Key Fields | Priority |
|---|---|---|---|---|---|
| SERP (targeted per-company) | — | SerpAPI free (100/mo) or direct scrape | SerpAPI free tier / fragile if direct | Recent news, press releases, funding announcements, product launches | Primary |
| SEC EDGAR Form D | efts.sec.gov | Free structured API | Free | Offering type, amount raised, date filed, SIC code, state | Primary |
| OpenCorporates | opencorporates.com | Free API (500 req/day) | Free | Incorporation date, officers, registered address, active status | Fallback |

**Usage notes:**
- **SERP:** Query patterns — `"[company] funding 2024"`, `"[company] launch site:techcrunch.com"`. Use only after company is identified. Never for bulk list harvesting.
- **SEC EDGAR:** Filter by SIC codes `7372` (prepackaged software) and `8099` (health services). Form D = company just raised — surfaces private raises ahead of typical press timelines. 15-day filing lag after raise closes.
- **OpenCorporates:** Use for validation — confirm company is active and real. Officers list can seed contact discovery later. Covers 140+ jurisdictions.

---


---

## Fallback Chains

### Startup discovery — software
```
YC directory  →  ProductHunt  →  HN Show HN
```

### Startup discovery — healthcare
```
NIH Reporter  →  YC 
```

### Funding signal enrichment
```
Open Corporates  →  SEC EDGAR Form D  →  SERP (funding query)
```

### Hiring + product signal enrichment
```
Careers page crawl  →  LinkedIn public page  
```

### Tech stack identification
```
Website crawl + LLM  →  Job posts (stack hints in JDs)
```

---

## Pipeline Architecture Notes

**Phase separation is intentional.** Discovery and enrichment are separate pipelines with a validation gate between them. Any candidate from a Tier B signal source must be cross-checked against a Tier A source before enrichment begins. This prevents wasting crawl and LLM cost on false positives.

**LLM extraction targets:** Company website markdown, career page JDs, NIH Reporter abstracts, SERP snippets. Use a low-cost model (e.g. Haiku or local LLM) for bulk extraction with a structured JSON schema or short summary for news posts. Cache all markdown outputs with a 30-day TTL.

**Rate limit defaults:**
- LinkedIn: max 1 request / 10 seconds, rotate user agents
- Open Corporates API: stay within the free-tier daily request quota (confirm on opencorporates.com)
- SerpAPI free: 100 searches/month — batch wisely

**Service boundary:** **Sourcing** discovers company domains, enriches company records, and identifies **who** qualifies as a POC using public titles, names, and profile URLs (e.g. leadership pages, makers, NIH PIs). **Prospecting** handles **commercial email discovery and verification** (e.g. Apollo.io, Hunter.io), ICP scoring, ranking, and thresholding before messaging.

---

## Quick Reference — Source Index

| Source | Phase | Domain | Access | Cost |
|---|---|---|---|---|
| Y Combinator | Discovery | SW + HC | HTML scrape | Free |
| Open Corporates | Discovery + Enrichment | SW + HC | REST API | Free (limited) |
| Product Hunt | Discovery | SW | API | Free |
| NIH Reporter | Discovery | HC | REST API | Free |
| Hacker News | Discovery (signals) | SW | Algolia API | Free |
| LinkedIn | Discovery (signals) + Enrichment | SW + HC | HTML scrape | Free |
| Company website | Enrichment | SW + HC | crawl4ai | LLM cost only |
| Careers page | Enrichment | SW + HC | crawl4ai | LLM cost only |
| SERP (targeted) | Enrichment | SW + HC | SerpAPI / scrape | Free tier |
| SEC EDGAR | Enrichment | SW + HC | REST API | Free |
