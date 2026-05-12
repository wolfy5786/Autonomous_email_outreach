# Enrichment Redesign — Session Notes

> **Scope:** Documentation only for this working session. No code changes.
> **Status:** Draft / proposal — supersedes the prior multi-source enrichment validation flow conceptually.

## Overview

Enrichment is collapsed from an open-ended multi-source pipeline into exactly **three operations** that run per lead/company. Each produces a distinct slice of evidence that downstream personalization can consume independently.

| # | Operation                       | Input                | Output                                | Tooling                          |
|---|---------------------------------|----------------------|---------------------------------------|----------------------------------|
| 1 | LinkedIn POC lookup             | company name         | point-of-contact profile data         | SERP → crawl4ai + LLM            |
| 2 | YC directory lookup             | company name         | founder names + latest news blurb     | YC directory scraper / API       |
| 3 | Company website info extraction | company URL (or name) | landing-page company info             | SERP fallback → crawl4ai + LLM   |

Operations are independent and may run in parallel. Each emits its own provenance record; failure of one does not abort the others.

---

## 1) LinkedIn search by company name → POC

- **Input:** company name (string).
- **Process:**
  1. **SERP discovery:** run a web search for `{company_name}` + `LinkedIn` (two terms in one query, e.g. `"Acme Corp" LinkedIn`).
  2. **Pick the company page:** open the **first search result whose URL is on LinkedIn** (typically the company page, not articles or third-party listings).
  3. **Single-page scrape:** use **crawl4ai** on that URL only. **No navigation** — do not follow internal links, tabs, or “See all”; extract whatever is visible on that one loaded page.
  4. **Structured signals from the scrape:** capture from the rendered page at minimum **About**, **people / employees surfaced on the page**, **location**, and **recent posts** (snippets visible without clicking through).
  5. **LLM extraction:** pass that scraped bundle to an **LLM** to pick a single best point-of-contact (name, title, profile URL if present in the text).
- **Output:** `{ poc_name, poc_title, poc_profile_url, evidence_url }` (with provenance pointing at the LinkedIn URL actually fetched).
- **Notes:** Treat any login-walled result as a miss — see "Login walls" below. If the first LinkedIn URL is wrong (e.g. homonym company), this operation may mis-target; SERP ranking heuristics or a quick relevance check are optional follow-ups (see open questions).

## 2) YC directory search → founders + latest news

- **Input:** company name (string).
- **Process:**
  - Query the YC company directory.
  - Pull founder names from the company profile.
  - Pull the latest news / launch blurb if present.
- **Output:** `{ founders: [...], latest_news: { title, url, posted_at } }`.
- **Notes:** Skip cleanly if the company is not in YC's directory — this is expected for most leads.

## 3) Company website info extraction

- **Input:** company URL if known; otherwise company name.
- **Process:**
  1. **URL resolution:** if no URL is provided, run a SERP query and take the **top result** as the canonical company site.
  2. **Fetch landing page only:** crawl4ai pulls the landing page. **No navigation** — do not follow internal links, do not crawl `/about`, `/team`, `/pricing`, etc.
  3. **LLM extraction:** summarize what the company does, target market, key value props, signals (funding mentions, customer logos visible on the landing page only).
- **Output:** `{ company_summary, value_props, signals, source_url }`.

### Caution — company website extraction

These rules are **hard constraints** for operation 3:

- **Login walls → drop.** If the landing page requires login, paywall, age-gate, or any auth interstitial to read primary content, **mark the record to be dropped** for this operation. Do not attempt to bypass, do not retry with cookies, do not fall back to cached snapshots. Emit a `dropped: login_required` provenance reason.
- **Landing page only.** Extract strictly from the page fetched at the resolved URL. No link-following, no sitemap crawl, no `robots.txt` discovery beyond the single page. If the landing page is a redirect, follow the redirect once and treat the destination as the landing page.

---

## Operation matrix

| Op | Needs LLM? | Needs crawl4ai? | Can fail-soft? | Drop conditions                       |
|----|------------|-----------------|----------------|---------------------------------------|
| 1  | yes        | yes             | yes            | no result / login wall on profile     |
| 2  | no         | no (or light)   | yes            | company absent from YC directory      |
| 3  | yes        | yes             | yes            | login wall on landing page → **drop** |

## Open questions (parked)

- Rate limiting / auth posture for LinkedIn scraping (legal + technical).
- Whether the **first LinkedIn URL** from the `{company_name} LinkedIn` SERP is always acceptable, or needs title/snippet checks before crawling (wrong company / news article).
- Whether SERP fallback in op 3 should require a domain match heuristic before accepting the top result.
- Caching policy per operation (probably per-domain TTL, but out of scope for this note).

## Relation to existing code

- `src/sourcing/validation/enrichment.py` currently stubs a generic `validate_enrichment(result, rule)` against an `AttributeSourceMapRule`. Under this redesign, validation becomes **per-operation** rather than per-attribute-rule; the source-map abstraction is not needed for the three fixed operations.
- This document is descriptive only — no files in `src/` are changed in this session.
