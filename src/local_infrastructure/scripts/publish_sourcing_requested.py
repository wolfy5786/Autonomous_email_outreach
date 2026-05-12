"""Dev helper — publish a sourcing.requested message to RabbitMQ.

Run from the repo root, against the compose-exposed broker:

    python src/local_infrastructure/scripts/publish_sourcing_requested.py \\
        --campaign-id c-demo-001 --plan-id <uuid-from-seed_plan>

Optional JSON file can add ``target_entities``, ``config``, ``seeds``, ``request_id``, etc.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import aio_pika


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--plan-id", required=True)
    parser.add_argument("--queue", default="sourcing.requested")
    parser.add_argument(
        "--url",
        default=os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/"),
    )
    parser.add_argument(
        "--payload-json",
        type=Path,
        default=None,
        help="JSON object merged onto the base payload (e.g. target_entities, seeds, config)",
    )
    args = parser.parse_args()

    payload: dict[str, Any] = {
        "campaign_id": args.campaign_id,
        "plan_id": args.plan_id,
    }
    if args.payload_json is not None:
        extra = json.loads(args.payload_json.read_text(encoding="utf-8"))
        if not isinstance(extra, dict):
            print("--payload-json must contain a JSON object", file=sys.stderr)
            return 1
        payload.update(extra)

    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")

    exchange_name = os.getenv("RABBITMQ_EXCHANGE", "email_outreach.events")
    conn = await aio_pika.connect_robust(args.url)
    async with conn:
        channel = await conn.channel()
        exchange = await channel.get_exchange(exchange_name, ensure=True)
        await exchange.publish(
            aio_pika.Message(body, delivery_mode=aio_pika.DeliveryMode.PERSISTENT),
            routing_key=args.queue,
        )
    print(f"published to {exchange_name} (rk={args.queue}): {body.decode()}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
