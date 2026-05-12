# Observability

> **Adoption status on `dev`** — the observability service, the
> `shared.observability` library, and the `TraceEvent` Mongo collection are
> all on `dev`. The `TracedBroker` decorator and per-service wiring described
> below were **not** merged: dev's services (planning, sourcing, messaging)
> have evolved their own broker subscription code separately, and the TS
> orchestrator owns the gateway responsibility. Services that want to appear
> on the campaign timeline should call `configure_logging`, set
> `MongoTraceSink()` after `init_db()`, and emit events via
> `shared.observability.trace_operation(...)` at their own pace. The
> dashboard at `:8090` is live as soon as `trace_events` rows exist.

In-repo observability for the email_outreach system. Built around a single
spine: a `trace_id` that is born when a campaign is created and propagates
through every service in the pipeline. Each service emits append-only
`TraceEvent` records to MongoDB; the observability UI reads from there to
render a per-campaign timeline.

No new external infrastructure (Prometheus / Grafana / Loki / Tempo) is
introduced — the design is deliberately minimal and uses the Mongo + Rabbit we
already run. A future expansion to a metrics/log stack can layer on top
without touching service code.

---

## Architecture

```
 ┌────────────┐
 │  gateway   │    generates trace_id, emits "campaign.created", publishes
 │ (stand-in: │
 │ script)    │
 └─────┬──────┘
       │ plan.requested { trace_id }
       ▼
 ┌────────────┐    TracedBroker auto-extracts trace_id on consume,
 │  planning  │    auto-stamps it on every publish from inside the handler
 └─────┬──────┘
       │ plan.ready { trace_id }
       ▼
 ┌────────────┐
 │ sourcing   │    custom broker; uses trace_operation() to bind context + emit events
 └─────┬──────┘
       │ ...
       ▼
 ┌────────────┐
 │ messaging  │    same TracedBroker pattern as planning
 └─────┬──────┘
       │ writes EmailDraft + emits draft.written
       ▼
                                                ┌─────────────────────┐
 ┌────────────────────────────────────────────► │   trace_events      │
 │           every publish/consume emits a      │   (Mongo collection)│
 │           TraceEvent row via MongoTraceSink  └─────────┬───────────┘
 │                                                        │
 │              ┌─────────────────────────────────────────▼─┐
 │              │   observability service (FastAPI :8090)    │
 │              │   - GET /api/campaigns                     │
 │              │   - GET /api/campaigns/:id/timeline        │
 │              │   - HTML pages at / and /campaigns/:id     │
 │              └────────────────────────────────────────────┘
```

---

## Core primitives (`shared.observability`)

| Surface | Purpose |
| --- | --- |
| `configure_logging(service, level=, env=)` | structlog → JSON; stamps `service`, `env`, `trace_id`, `campaign_id` on every log line |
| `bind_trace_context(trace_id=, campaign_id=)` | manually set ids in the current async context |
| `trace_scope(...)` | context-managed scoped binding (saves/restores prior state on exit) |
| `current_trace_id()` / `current_campaign_id()` | read what's currently bound |
| `TraceSink` (protocol) | pluggable destination for `TraceEvent` records |
| `MongoTraceSink` | writes via Beanie's `event.insert()` |
| `InMemoryTraceSink` | for tests |
| `set_trace_sink(sink)` / `get_trace_sink()` | install / fetch the global active sink |
| `trace_operation(...)` | async context manager: binds scope + emits START/END or ERROR around any block |
| `make_event(...)` | construct a `TraceEvent` without manually importing Beanie |

The two pieces of "magic":

1. The structlog processor `_merge_trace_context` reads the trace ContextVars
   and stamps them on every log line — so any `log.info(...)` inside a
   handler automatically carries `trace_id` and `campaign_id`.
2. `TracedBroker` (decorator in `local_infrastructure/factory/`) wraps any
   `MessageBroker`. On consume it extracts `trace_id`/`campaign_id` from the
   message and binds them via `trace_scope`; on publish it stamps the current
   `trace_id` from context into the outgoing message. Trace IDs therefore
   propagate end-to-end with **zero handler-side changes**.

---

## Data model

`trace_events` collection (Beanie `Document`, defined in
`shared/models/trace_event.py`):

| Field | Notes |
| --- | --- |
| `id` | UUID string (matches repo convention) |
| `trace_id` | required — campaign-scoped identifier shared across services |
| `campaign_id` | optional — business id, indexed for timeline lookups |
| `service` | name of the emitting service |
| `event_name` | e.g. `plan.requested.consume`, `messaging.requested.publish`, `campaign.created` |
| `phase` | `start` \| `end` \| `error` \| `emit` (one-shot) |
| `timestamp` | UTC |
| `duration_ms` | populated on `end` / `error` |
| `error_type` / `error_message` | populated on `error` |
| `metadata` | free-form dict (`topic`, `retry_count`, etc.) |

Indexes:
- `(campaign_id, timestamp)` — campaign timeline
- `(trace_id, timestamp)` — trace timeline
- `(service, event_name, timestamp)` — service-level slices

---

## What a service has to do

Per-service wiring, in `main.py`:

```python
from shared.models.db import init_db
from shared.observability import MongoTraceSink, configure_logging, set_trace_sink

configure_logging(service="my-service", level=settings.log_level)
mongo_client, db = await init_db(settings.mongo_url, settings.mongo_db)
set_trace_sink(MongoTraceSink())

broker = create_broker()  # already wrapped in TracedBroker by the factory
```

…and set `SERVICE_NAME=my-service` in the Dockerfile env block so the broker
factory tags trace events correctly.

Handlers don't need to change. Their existing `log.info(...)` calls
automatically pick up `trace_id`/`campaign_id`, and any `broker.publish(...)`
they make stamps the same `trace_id` into the outgoing message.

For services that don't go through `TracedBroker` (custom broker like
sourcing, HTTP handlers, scheduled jobs), wrap the operation:

```python
async with trace_operation(
    trace_id=trace_id,
    campaign_id=campaign_id,
    service="sourcing",
    event_name="sourcing.requested.consume",
):
    await do_the_work()
```

---

## Adding a future service (e.g. prospecting)

No infrastructure changes are needed. Steps:

1. Install `structlog` and `beanie` (or just `structlog` if you don't need
   `MongoTraceSink`).
2. In your service's `main.py`:
   - `configure_logging(service="prospecting", ...)`
   - `init_db(...)` then `set_trace_sink(MongoTraceSink())`
   - Use `create_broker()` from `local_infrastructure.factory` — it wraps in
     `TracedBroker` automatically.
3. Add `SERVICE_NAME=prospecting` to your Dockerfile env.
4. The RabbitMQ topology in `local_infrastructure/rabbit_mq/definitions.json`
   already includes `prospecting.*` queues — no broker changes required.

That's it. The new service immediately shows up on the campaign timeline
alongside everyone else.

---

## Running locally

```bash
# Bring up the stack including the observability UI:
docker compose up --build

# Kick a campaign through the pipeline:
python src/local_infrastructure/scripts/seed_campaign.py --id c-demo-001
python src/local_infrastructure/scripts/publish_plan_requested.py --campaign-id c-demo-001

# Then open the UI:
open http://localhost:8090
```

JSON API:

- `GET http://localhost:8090/api/campaigns`
- `GET http://localhost:8090/api/campaigns/c-demo-001/timeline`

---

## Service health endpoints

| Service | Liveness | Readiness | Notes |
| --- | --- | --- | --- |
| planning | `/health` :8080 | `/ready` :8080 — checks Mongo + broker | exposed in docker-compose |
| messaging | `/health` :8081 | `/ready` :8081 — checks Mongo + broker | exposed |
| sourcing | _none_ | _none_ | pure consumer; no HTTP server. Use container aliveness. |
| observability | `/health` :8090 | `/ready` :8090 — checks Mongo | exposed |

Sourcing has no HTTP endpoint by design (adds FastAPI dep otherwise). Adding
one is a clean follow-up if k8s liveness probes are needed.

---

## Known follow-ups (deferred from MVP)

These are intentionally not in v1:

- **RabbitMQ queue depths** in the observability UI (read from management API
  at `:15672`).
- **Live service-health probes** — observability service polling each
  service's `/health` and `/ready` for a "system status" page.
- **Log search** — surfacing structured JSON logs filtered by `trace_id`.
- **Full structlog migration of sourcing's pipeline** — pipeline.py still
  uses stdlib `logging` with `%s` formatting; new code uses structlog.
- **Sourcing on the shared broker** — sourcing keeps its custom (sync,
  bytes-payload) broker. Migration to `local_infrastructure.factory` is a
  separate refactor.
- **Metrics / Prometheus / Grafana** — not in scope; design is forward-
  compatible (TracedBroker is a clean instrumentation point if we ever add
  prometheus_client counters).

---

## Where things live

| Path | What |
| --- | --- |
| `src/shared/observability/` | logging, trace context, trace_sink, trace_emit |
| `src/shared/models/trace_event.py` | the `TraceEvent` Beanie document |
| `src/local_infrastructure/factory/traced_broker.py` | the decorator that wraps every broker |
| `src/observability/` | the FastAPI service that renders the dashboard |
| `docs/observability.md` | this file |
