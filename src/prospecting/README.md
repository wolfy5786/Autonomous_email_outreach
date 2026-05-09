# Prospecting Service

Consumes `sourcing.completed`, scores + ranks prospects vs the campaign Plan Document, persists scores to MongoDB, and publishes `prospecting.completed`.

## Local run (with local RabbitMQ)

1. Start RabbitMQ:

```bash
cd src/local_infrastructure/rabbit_mq
cp .env.example .env
docker compose up -d
```

2. Ensure MongoDB is reachable (you can use any MongoDB; local is fine).

3. Run the service:

```bash
cd src/prospecting
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export RABBITMQ_URL="amqp://guest:guest@localhost:5672/%2F"
export RABBITMQ_EXCHANGE="email_outreach.events"
export MONGODB_URI="mongodb://localhost:27017"
export MONGODB_DB="email_outreach"

python -m app.main
```

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

