This is the core of the plan. For each data source integrated in the Sourcing Service, the plan must include a **search configuration block** containing the filters the LLM has determined are appropriate given the ICP.
 
The LLM is provided with:
- The full ICP
- A description of each available data source
- The complete list of supported search filters and valid values for each source
The LLM outputs which filters to apply and what values to set for each source.
 
#### 1a. Product Hunt
 
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
 
---
 
#### 1b. OpenCorporates
 
```json
{
  "source": "open_corporates",
  "enabled": true,
  "filters": {
    "jurisdiction_code": "us",
    "company_type": "private",
    "incorporation_date_from": "2020-01-01",
    "incorporation_date_to": "2024-01-01",
    "registered_address_country": "US",
    "status": "active",
    "industry_keywords": ["software", "technology", "saas"]
  }
}
```
 
**Supported filters the LLM may populate:**
 
| Filter | Type | Description |
|---|---|---|
| `jurisdiction_code` | `string` | Country or state jurisdiction (e.g. `us`, `gb`, `us_de`) |
| `company_type` | `string` | Legal entity type (e.g. `private`, `llc`, `ltd`) |
| `status` | `string` | Company status: `active`, `dissolved`, `inactive` |
| `incorporation_date_from` | `date` | Earliest incorporation date |
| `incorporation_date_to` | `date` | Latest incorporation date |
| `registered_address_country` | `string` | Country of registered address |
| `industry_keywords` | `string[]` | Keyword hints to match against company descriptions |
 
---
 
#### 1c. YC News (Y Combinator)
 
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
 
---
 
### 2. Global Filters (Cross-Source)
 
Some constraints apply universally across all sources. These are resolved once and applied by the Sourcing Service to all results.
 
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

### 3. Outreach Context
 
Parameters that guide how sourced contacts should eventually be reached out to. This section is populated by the Planning Service and passed through to downstream services.
 
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
 
---

The LLM does not guess or hallucinate filter values. It selects from the explicitly provided filter options. If the ICP does not provide enough signal to populate a filter, that filter is omitted rather than defaulted.