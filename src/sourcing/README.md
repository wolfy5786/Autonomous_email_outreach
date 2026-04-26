# Sourcing Service Skeleton

This folder contains the initial skeleton for the data sourcing service in the distributed email outreach architecture.

Current behavior:
- Subscribes to the `sourcing.requested` topic via a broker abstraction.
- Parses the request into a typed contract.
- Runs no-op pipeline stages (load plan, cache check, source map, discovery, validation, enrichment, persist, emit event).
- Logs each stage with request and campaign context.

This is intentionally non-functional scaffolding to establish service boundaries and integration points.
