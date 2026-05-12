---
name: Sourcing requested subscriber
overview: Implement sourcing as an aio-pika client that subscribes to queue sourcing.requested. The message broker is the RabbitMQ Docker container only (config and topology under src/local_infrastructure/rabbit_mq, mounted by root compose). No Python broker abstraction, factory, or broker-interface package — ever. Single repo-root docker-compose, structlog, Ai_rules, docs.
todos:
  - id: infra_compose
    content: "Single compose at repo root only: remove duplicate compose files under src/local_infrastructure; root docker-compose mounts src/local_infrastructure/rabbit_mq definitions + conf for the rabbitmq service; shared network + env_file"
    status: completed
  - id: documentation
    content: README — RabbitMQ runs as container only; src/local_infrastructure/rabbit_mq is server config (JSON definitions, conf), not app broker code; services are AMQP clients via env URL; no COPY local_infrastructure in service images
    status: completed
  - id: logging
    content: Add src/sourcing/logging_setup.py (structlog JSON) — Ai_rules.md §1
    status: completed
  - id: subscriber
    content: Sourcing — aio-pika client connects with RABBITMQ_URL to existing queue sourcing.requested; consume, ack, nack(requeue=False) for DLQ; no factory pattern
    status: completed
  - id: handler
    content: handlers.py — correlation id, bytes to SourcingPipeline.run; PlanNotFoundError → nack/DLQ path
    status: completed
  - id: main
    content: main.py — init_db, run consumer loop until shutdown, structured logs, error on disconnect failure
    status: completed
  - id: deps
    content: requirements.txt — aio-pika + structlog; Dockerfile COPY shared + sourcing only
    status: completed
  - id: env_example
    content: src/sourcing/.env.example — RABBITMQ_URL (rabbitmq hostname in compose), prefetch, LOG_LEVEL
    status: completed
  - id: tests
    content: Pytest for handler/helpers; mock pipeline — Ai_rules.md §5
    status: completed
isProject: false
---

# Sourcing subscriber: AMQP client only, RabbitMQ in Docker

## Broker model (no factory, no “broker” code)

| What we do | What we do **not** do |
|------------|------------------------|
| Run **RabbitMQ as a Docker service** (official image). Topology (exchanges, queues, DLX) comes from [src/local_infrastructure/rabbit_mq/definitions.json](src/local_infrastructure/rabbit_mq/definitions.json) **mounted into the container** by [docker-compose.yml](docker-compose.yml) at repo root. | Implement a **broker abstraction**, **factory**, **MessageBroker interface**, **`create_broker()`**, or restore any deleted `local_infrastructure/factory` Python package. |
| **Sourcing** is a normal **AMQP client** using **aio-pika**: connect with `RABBITMQ_URL`, attach to pre-declared queue **`sourcing.requested`**, consume messages. | Treat “broker” as something we code in Python beyond this client. |

**`src/local_infrastructure`** here means **infrastructure assets** for the stack (RabbitMQ **server** config, scripts, env examples mounted or referenced by compose) — **not** a library the app imports to “create a broker.” Service Dockerfiles **must not** `COPY local_infrastructure` into the image for messaging logic; the running **broker is the container**, not files copied into Python services.

---

## Compose and network (repo root only)

- **Single** [docker-compose.yml](docker-compose.yml) at repository root: defines **rabbitmq** (volumes from `src/local_infrastructure/rabbit_mq/`), **mongo**, and app services on one default network.
- **Remove** redundant compose files under `src/local_infrastructure` after verifying root compose is complete; update doc references that pointed at nested compose paths.
- Services reach RabbitMQ at hostname **`rabbitmq`**, Mongo at **`mongo`**, via **`env_file` / `environment`** on the root compose.

---

## Sourcing application work (`src/sourcing/`)

### Goal

- Consume **`sourcing.requested`** (see [definitions.json](src/local_infrastructure/rabbit_mq/definitions.json); DLQ `sourcing.requested.dlq`).
- Call [`SourcingPipeline.run(body: bytes)`](src/sourcing/pipeline.py) per message.
- Implementation: **subscriber module** = aio-pika **connection + consumer loop** only (no shared factory package).

### Dockerfile

- **COPY** `shared/` + `sourcing/` (+ requirements). **Never** `COPY local_infrastructure` for broker behavior — the broker is external (container).

### [Ai_rules.md](Ai_rules.md)

Structlog, correlation IDs, error logging, type hints, env-only secrets, pytest with mocks.

### Files

- **Docs:** [README.md](README.md) (and optionally [rabbit_mq/README.md](src/local_infrastructure/rabbit_mq/README.md)) — clarify Docker-only broker + config path under `local_infrastructure`.
- **Code:** `main.py`, `logging_setup.py`, `handlers.py` / `subscriber.py`, `requirements.txt`, `Dockerfile`, `.env.example`, `tests/`.

---

## Verification

1. `docker compose up -d` from repo root — RabbitMQ healthy (definitions loaded), Mongo healthy.
2. Run sourcing container or local process with `RABBITMQ_URL` pointing at the **rabbitmq** service.
3. Publish test message; confirm pipeline logs; poison / missing plan → DLQ.

---

## Explicit non-goals

- **No** Python **factory pattern** for messaging.
- **No** new or restored **`broker_interface` / `broker_factory` / `RabbitMQBroker` wrapper** in `local_infrastructure` or elsewhere.
- **No** “coding a broker” — only **running** RabbitMQ in Docker and **connecting** as a client from sourcing.
