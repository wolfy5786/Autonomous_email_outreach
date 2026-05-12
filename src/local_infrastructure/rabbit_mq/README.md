# RabbitMQ server configuration (Docker)

This directory holds **RabbitMQ server** configuration for local development: `definitions.json` (exchanges, queues, DLX/DLQ bindings), `rabbitmq.conf`, and env templates. It is **not** application Python code.

## How to run the broker

Use the **repository root** [docker-compose.yml](../../../docker-compose.yml) — the only compose file for the dev stack. It mounts `definitions.json` and `rabbitmq.conf` into the `rabbitmq` service and starts MongoDB plus application services on a shared network.

```bash
# From the repository root
docker compose up -d
```

Do **not** rely on a separate compose file in this folder (it was removed in favor of the single root stack).

## What gets provisioned

- RabbitMQ with management UI (`rabbitmq:3.13-management`)
- Topic exchange: `email_outreach.events`
- Dead-letter exchange: `email_outreach.dlx`
- Durable queue + DLQ for each pipeline event (see `definitions.json`), including `plan.requested`, `plan.ready`, `sourcing.requested`, and the rest.

### Who publishes / consumes (v1)

Queues are grouped in `definitions.json` as **work queues** (`*.requested`, consumed by workers) then **coordination queues** (`.ready`, `.completed`, `.partial`, `.written`, `.failed`, consumed **only** by the Orchestrator). **`campaign.completed`** is published by the Orchestrator; no application consumer in v1.

## Verify

- AMQP: `amqp://localhost:5672` (from host)
- Management UI: [http://localhost:15672](http://localhost:15672) — default login from `.env` (often `guest` / `guest`).

## Service integration

Applications connect with **`RABBITMQ_URL`** (and optional prefetch / log level). There is **no** in-repo Python “broker factory”; the broker process is this container. Services are normal AMQP clients.
