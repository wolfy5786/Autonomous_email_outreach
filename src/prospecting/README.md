# Prospecting Service

Consumes `sourcing.completed`, scores + ranks prospects vs the campaign Plan Document, persists scores to MongoDB, and publishes `prospecting.completed`.

## Usage

The service startup is fully containerized:
- Defaults are applied in the Python startup module.
- MongoDB and RabbitMQ connectivity checks run inside the container with retries.

Before starting the stack, create your local `.env` from the tracked example file:

```bash
cp .env.example .env
```

Docker Compose reads `.env` from this directory automatically, so that file is the single place to adjust local runtime values.

From this directory, build and start the service stack:

```bash
docker compose up --build -d rabbitmq mongodb prospecting
```

Check service health:

```bash
docker compose ps
curl http://localhost:8004/health
```

Run the functional test suite in Docker:

```bash
docker compose run --rm tests
```

Stop everything:

```bash
docker compose down -v
```

Optional startup controls:
- `WAIT_FOR_DEPS` (default: `true`) - set to `false` to skip dependency checks.
- `STARTUP_RETRIES` (default: `45`) - dependency-check retries.
- `STARTUP_SLEEP_SECONDS` (default: `2`) - delay between retries.

## Environment variables

- `RABBITMQ_URL`: AMQP url (default: `amqp://guest:guest@localhost:5672/%2F`)
- `RABBITMQ_EXCHANGE`: exchange to publish events to (default: `email_outreach.events`)
- `RABBITMQ_PREFETCH`: consumer prefetch (default: `10`)
- `MONGODB_URI`: MongoDB connection string (required)
- `MONGODB_DB`: Mongo database name (default: `email_outreach`)
- `DEFAULT_MIN_ICP_SCORE`: fallback threshold if `campaigns.config.min_icp_score` is missing (default: `0.0`)

## Expected MongoDB collections (per `README.md`)

- `campaigns` (contains `config.min_icp_score`)
- `plans` (Plan Document; used for `scoring_weights`)
- `companies` (company records; updated with `icp_fit_score`)
- `persons` (POC records; updated with `icp_poc_score`)

