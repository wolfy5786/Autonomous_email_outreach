# Enrichment Pipeline Redesign

## Problem

The current enrichment step runs synchronously inside the sourcing pipeline,
blocking discovery while enriching each company. This limits throughput.

## Solution

Split enrichment into its own async stage:

1. **sourcing.completed** → orchestrator publishes **enrichment.requested**
2. Enrichment service consumes, enriches contacts in parallel
3. Publishes **enrichment.completed** → orchestrator triggers prospecting

## Data Flow

```
sourcing.completed
  └─→ enrichment.requested (per company batch)
        └─→ enrichment worker (parallel, rate-limited)
              ├─→ Apollo API (email discovery)
              ├─→ LinkedIn scraper (title verification)
              └─→ Clearbit (company enrichment)
        └─→ enrichment.completed
              └─→ prospecting.requested
```

## Rate Limiting

Each enrichment provider has its own TokenBucket rate limiter:
- Apollo: 5 req/s
- LinkedIn: 1 req/s (aggressive anti-bot)
- Clearbit: 10 req/s

## Error Handling

- Individual contact failures don't fail the batch
- Failed contacts are marked `enrichment_failed` and skipped
- Batch-level failures trigger retry (max 3 attempts)
