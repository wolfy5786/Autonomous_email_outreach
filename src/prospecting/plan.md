STEP 7 — Persist scoring results

Build:
1. Update companies.icp_fit_score.
2. Update persons.icp_poc_score.
3. Store campaign-scoped prospecting score details to avoid cross-campaign overwrite.
4. Store scoring_version.
5. Store scored_at.
6. Store campaign_id.
7. Store input sourcing.completed event id if available.
8. Store scoring reasons in a compact form.

Recommended company write:
companies.prospecting_scores.<campaign_id> = {
  icp_fit_score,
  scoring_version,
  scored_at,
  reasons
}

Recommended person write:
persons.prospecting_scores.<campaign_id> = {
  icp_poc_score,
  scoring_version,
  scored_at,
  reasons
}

Stop and test:
- Company icp_fit_score is written.
- POC icp_poc_score is written.
- Campaign-scoped score is written.
- Reprocessing same event does not corrupt existing scores.
- Scores from another campaign are not overwritten.


STEP 8 — Publish prospecting.completed

Build:
1. Publish only after MongoDB score writes succeed.
2. Publish to prospecting.completed.
3. Keep README payload shape: { campaign_id, ranked_prospects[] }.
4. Include ranked prospects after filtering.
5. Include enough prospect identifiers for Messaging Service to continue later.
6. Ack sourcing.completed only after successful publish.
7. Use idempotency so the same input event does not publish twice.

Recommended payload:
{
  "campaign_id": "...",
  "ranked_prospects": [
    {
      "rank": 1,
      "company_id": "...",
      "poc_id": "...",
      "icp_fit_score": 0.86,
      "icp_poc_score": 0.78,
      "total_score": 0.83,
      "scoring_version": "v1"
    }
  ]
}

Stop and test:
- Valid sourcing.completed produces prospecting.completed.
- Mongo writes happen before publish.
- Source message is acked only after publish succeeds.
- Duplicate input does not create duplicate output.
- Output payload is compatible with README queue contract.


STEP 9 — Error handling, retries, and DLQ

Build:
1. Reject malformed sourcing.completed messages without requeue.
2. Treat missing campaign as permanent failure.
3. Treat missing plan as permanent failure unless campaign is temporarily incomplete.
4. Treat MongoDB connection errors as retryable.
5. Treat RabbitMQ publish failures as retryable.
6. Do not ack before successful persistence and publish.
7. Log retry count and x-death headers when present.
8. Keep all logs structured.

Structured log fields:
- service = prospecting
- campaign_id
- event_id if available
- idempotency_key
- trace_id if available
- status
- error_type
- retry_count

Stop and test:
- Bad schema is rejected or DLQed.
- Missing campaign fails safely.
- Missing plan fails safely.
- Mongo transient failure retries.
- RabbitMQ publish failure does not ack early.
- x-death headers are logged when present.



STEP 10 — Health, metrics, and observability

Build:
1. Keep /health.
2. Add /health/live.
3. Add /health/ready.
4. Add /metrics.
5. Readiness checks MongoDB connection.
6. Readiness checks RabbitMQ connection.
7. Export Prometheus metrics.

Metrics:
- prospecting_events_consumed_total
- prospecting_events_completed_total
- prospecting_events_failed_total
- prospecting_events_duplicate_total
- prospecting_scoring_duration_seconds
- prospecting_publish_duration_seconds
- prospecting_ranked_prospects_total
- prospecting_filtered_prospects_total
- prospecting_semantic_search_matches_total
- prospecting_semantic_search_misses_total

Stop and test:
- /health works.
- /health/live works without dependencies.
- /health/ready fails when MongoDB or RabbitMQ is unavailable.
- /metrics exposes expected metrics.
- Metrics increment during local processing.


STEP 11 — Docker, local integration, and deployment assets

Build:
1. Update prospecting Dockerfile.
2. Add Docker Compose path for prospecting + MongoDB + RabbitMQ.
3. Add or update Helm chart files under deploy/charts/prospecting.
4. Configure env vars for MongoDB, RabbitMQ, queue names, scoring version, and log level.
5. Configure KEDA scaling on sourcing.completed.
6. Add ServiceMonitor for /metrics.
7. Do not add public business APIs to Prospecting.

Required Helm files:
- deployment.yaml
- service.yaml
- serviceaccount.yaml
- scaledobject.yaml
- externalsecret.yaml
- networkpolicy.yaml
- poddisruptionbudget.yaml
- servicemonitor.yaml
- values.yaml
- values-dev.yaml

Stop and test:
- Docker image builds.
- Docker Compose starts MongoDB, RabbitMQ, and Prospecting.
- Service consumes a seeded sourcing.completed event.
- Service writes Mongo scores.
- Service publishes prospecting.completed.
- Helm template succeeds.
- KEDA ScaledObject targets sourcing.completed.


STEP 12 — Prospecting-only test suite

Build:
1. Unit test scoring dimensions.
2. Unit test semantic-search fallback behavior.
3. Unit test ranking and filtering.
4. Unit test idempotency skip behavior.
5. Integration test MongoDB persistence.
6. Integration test RabbitMQ consume/publish path.
7. Integration test malformed message handling.
8. End-to-end local test with MongoDB + RabbitMQ + Prospecting only.

Stop and test:
- All unit tests pass.
- All Mongo integration tests pass.
- All RabbitMQ integration tests pass.
- Duplicate event does not duplicate output.
- Malformed event is rejected or DLQed.
- End-to-end Docker Compose test passes.