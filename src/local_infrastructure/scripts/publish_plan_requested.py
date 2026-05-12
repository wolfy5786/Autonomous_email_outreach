"""Dev helper — publish a ``plan.requested`` message to RabbitMQ.

Acts as a stand-in for the (not-yet-built) gateway service: this is where a
fresh ``trace_id`` is born and a ``campaign.created`` trace event is emitted.
The same primitives — :func:`bind_trace_context`, :func:`make_event`, and
``create_broker`` — apply unchanged when a real gateway service replaces this
script.

Run from the repo root, against the compose-exposed broker:

    python src/local_infrastructure/scripts/publish_plan_requested.py --campaign-id c-demo-001
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid

import structlog

from local_infrastructure.factory.broker_factory import create_broker
from shared.models.db import init_db
from shared.observability import (
    MongoTraceSink,
    bind_trace_context,
    configure_logging,
    get_trace_sink,
    make_event,
    set_trace_sink,
)


async def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--queue", default="plan.requested")
    parser.add_argument(
        "--mongo-url",
        default=os.getenv("MONGO_URI", "mongodb://localhost:27017"),
    )
    parser.add_argument(
        "--mongo-db",
        default=os.getenv("MONGO_DB_NAME", "email_outreach"),
    )
    args = parser.parse_args()

    # SERVICE_NAME is stamped on every trace event the broker emits; set to "gateway"
    # for parity with what a real gateway service will use.
    os.environ.setdefault("SERVICE_NAME", "gateway")
    configure_logging(service="gateway")
    log = structlog.get_logger()

    trace_id = str(uuid.uuid4())
    bind_trace_context(trace_id=trace_id, campaign_id=args.campaign_id)

    mongo_client, _ = await init_db(args.mongo_url, args.mongo_db)
    set_trace_sink(MongoTraceSink())
    sink = get_trace_sink()
    assert sink is not None  # we just set it

    log.info("publishing_plan_requested", queue=args.queue)

    # Emit a one-shot campaign.created event so the campaign appears on the
    # observability timeline from its very first moment.
    await sink.emit(
        make_event(
            trace_id=trace_id,
            campaign_id=args.campaign_id,
            service="gateway",
            event_name="campaign.created",
            phase="emit",
            metadata={"queue": args.queue},
        )
    )

    # Publishing through TracedBroker will:
    #   * inject trace_id from the bound context into the outgoing message
    #   * emit a ``plan.requested.publish`` EMIT event
    broker = create_broker()
    try:
        await broker.publish(args.queue, {"campaign_id": args.campaign_id})
        log.info("plan_requested_published", trace_id=trace_id)
    finally:
        await broker.disconnect()
        set_trace_sink(None)
        mongo_client.close()

    print(f"published trace_id={trace_id} campaign_id={args.campaign_id} queue={args.queue}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
