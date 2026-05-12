"""Dev helper — publish a messaging.requested message to RabbitMQ.

Run from the repo root, against the compose-exposed broker:

    python src/local_infrastructure/scripts/publish_messaging_requested.py \
        --campaign-id c-demo-001 --poc-id <id-from-seed_prospecting_mock.py>
"""
import argparse
import asyncio
import json
import os
import sys
import uuid

import aio_pika


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--poc-id", required=True)
    parser.add_argument(
        "--trace-id",
        default=None,
        help="Optional. Auto-generated uuid if omitted.",
    )
    parser.add_argument("--queue", default="messaging.requested")
    parser.add_argument(
        "--url",
        default=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
    )
    args = parser.parse_args()

    payload = {
        "campaign_id": args.campaign_id,
        "poc_id": args.poc_id,
        "trace_id": args.trace_id or str(uuid.uuid4()),
    }
    body = json.dumps(payload).encode("utf-8")

    exchange_name = os.getenv("RABBITMQ_EXCHANGE", "email_outreach.events")
    conn = await aio_pika.connect_robust(args.url)
    async with conn:
        channel = await conn.channel()
        # Topology (queues, DLX, bindings) is provisioned by definitions.json;
        # we just publish to the events exchange with the topic as routing key.
        exchange = await channel.get_exchange(exchange_name, ensure=True)
        await exchange.publish(
            aio_pika.Message(body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key=args.queue,
        )
    print(f"published to {exchange_name} (rk={args.queue}): {body.decode()}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
