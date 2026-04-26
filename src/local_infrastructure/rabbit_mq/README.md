# Local RabbitMQ Infrastructure

This folder provides a local RabbitMQ stack for development only.
It creates durable queues and dead-letter queues (DLQs) aligned to the event names in `README.md`.

## What gets provisioned

- RabbitMQ with management UI (`rabbitmq:3.13-management`)
- Topic exchange: `email_outreach.events`
- Dead-letter exchange: `email_outreach.dlx`
- Durable queue + DLQ for each pipeline event:
  - `plan.requested`
  - `plan.ready`
  - `sourcing.requested`
  - `sourcing.completed`
  - `sourcing.partial`
  - `prospecting.completed`
  - `messaging.requested`
  - `messaging.completed`
  - `review.requested`
  - `review.completed`
  - `send.requested`
  - `send.completed`
  - `send.failed`
  - `campaign.completed`

## Prerequisites

- Docker Desktop
- Docker Compose (v2+)

## Run

1. Create local env file:

   - PowerShell:
     - `Copy-Item .env.example .env`

2. Start RabbitMQ:

   - `docker compose up -d`

3. Verify:

   - AMQP endpoint: `amqp://localhost:5672`
   - Management UI: [http://localhost:15672](http://localhost:15672)
   - Default login: `guest` / `guest` (or values from `.env`)

## Stop and cleanup

- Stop stack: `docker compose down`
- Stop and remove volume data: `docker compose down -v`

## Notes for service integration

- Local env settings for services should use:
  - `BROKER_TYPE=rabbitmq`
  - `RABBITMQ_URL=amqp://<user>:<password>@localhost:5672/<vhost>`
- Production remains on SQS; this folder is local-only infrastructure.
