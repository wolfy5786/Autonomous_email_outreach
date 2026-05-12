# Observability Stack

## Overview

All services emit structured JSON logs and Prometheus metrics.
Traces are collected via OpenTelemetry and sent to Jaeger.

## Logging

- **Format**: JSON lines to stdout (see `shared/observability/logger.py`)
- **Fields**: timestamp, level, service, message, module, function, line
- **Collection**: Fluent Bit → Elasticsearch → Kibana

## Metrics

| Metric | Type | Service |
|--------|------|---------|
| `http_requests_total` | Counter | orchestrator |
| `pipeline_stage_duration` | Histogram | orchestrator |
| `sourcing_companies_found` | Gauge | sourcing |
| `enrichment_contacts_processed` | Counter | enrichment |
| `emails_sent_total` | Counter | messaging |
| `emails_opened_total` | Counter | messaging |
| `queue_depth` | Gauge | all services |

## Dashboards

- **Pipeline Overview**: Campaign throughput, stage durations, error rates
- **Per-Campaign**: Funnel view (discovered → enriched → contacted → replied)
- **Infrastructure**: RabbitMQ queue depths, MongoDB ops, Postgres connections

## Alerts

- Queue depth > 1000 for any queue
- Error rate > 5% on any service
- Pipeline stage stuck > 30 minutes
- SMTP delivery failure rate > 10%
