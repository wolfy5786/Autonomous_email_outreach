"""Dev helper — publish a plan.requested message to RabbitMQ.

Run from the repo root, against the compose-exposed broker:

    python src/local_infrastructure/scripts/publish_plan_requested.py --campaign-id c-demo-001
"""
import argparse
import asyncio
import json
import os
import sys

import aio_pika


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--queue", default="plan.requested")
    parser.add_argument(
        "--url",
        default=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
    )
    args = parser.parse_args()

    body = json.dumps({"campaign_id": args.campaign_id}).encode("utf-8")

    conn = await aio_pika.connect_robust(args.url)
    async with conn:
        channel = await conn.channel()
        # Declare with the same DLQ args the service uses so declarations match.
        await channel.declare_queue(f"{args.queue}.dlq", durable=True)
        await channel.declare_queue(
            args.queue,
            durable=True,
            arguments={
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": f"{args.queue}.dlq",
            },
        )
        await channel.default_exchange.publish(
            aio_pika.Message(body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key=args.queue,
        )
    print(f"published to {args.queue}: {body.decode()}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
