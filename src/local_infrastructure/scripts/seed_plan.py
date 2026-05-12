"""Dev helper — insert a sample Plan Document into MongoDB (``plans`` collection).

Matches the shape produced by Planning's ``save_plan`` (``_id`` == string ``id``) so
Sourcing's ``PlanRecord.get(plan_id)`` can load it.

Run from the repo root:

    python src/local_infrastructure/scripts/seed_plan.py --campaign-id c-demo-001

By default any existing plan for that ``campaign_id`` is removed first (unique index on
``campaign_id``). Use ``--no-replace`` to attempt a bare insert instead.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError

# Default body matches planning tests' ``valid_llm_output_dict`` (LLMPlanOutput shape).
_SAMPLE_LLM_BODY: dict[str, Any] = {
    "sources": [
        {
            "source": "product_hunt",
            "enabled": True,
            "filters": {
                "topics": ["Developer Tools", "SaaS"],
                "min_votes": 50,
            },
        },
        {
            "source": "yc_news",
            "enabled": True,
            "filters": {
                "batch_years": ["W23", "S23", "W24"],
                "industries": ["B2B", "DevTools"],
            },
        },
    ],
    "global_filters": {
        "employee_count_range": {"min": 50, "max": 500},
        "languages": ["en"],
    },
    "outreach_context": {
        "campaign_goal": "Book a discovery call",
        "tone": "technical",
        "personalization_hints": ["mention recent Product Hunt launch"],
        "sequence_length": 3,
    },
}


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in overlay.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _build_plan_doc(
    *,
    plan_id: str,
    campaign_id: str,
    llm_body: dict[str, Any],
    llm_model: str,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    doc: dict[str, Any] = {
        "id": plan_id,
        "campaign_id": campaign_id,
        "created_at": now,
        "llm_model": llm_model,
        "llm_usage": {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        },
        **llm_body,
    }
    doc["_id"] = plan_id
    return doc


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-id", default="c-demo-001")
    parser.add_argument(
        "--plan-id",
        default=None,
        help="Plan UUID string; default: random v4",
    )
    parser.add_argument(
        "--mongo-url",
        default=os.getenv("MONGO_URL", "mongodb://localhost:27017"),
    )
    parser.add_argument("--db", default=os.getenv("MONGO_DB", "email_outreach"))
    parser.add_argument(
        "--llm-model",
        default="seed/dev",
        help="Stored ``llm_model`` field (planning uses configured model name)",
    )
    parser.add_argument(
        "--from-json",
        type=Path,
        default=None,
        help="JSON file with keys like sources / global_filters / outreach_context "
        "(merged over the built-in sample)",
    )
    parser.add_argument(
        "--no-replace",
        action="store_true",
        help="Do not delete existing plan(s) for this campaign before insert",
    )
    parser.add_argument(
        "--no-attach-campaign",
        action="store_true",
        help="Do not set campaigns.plan_id for this campaign",
    )
    args = parser.parse_args()

    plan_id = args.plan_id or str(uuid.uuid4())
    llm_body = dict(_SAMPLE_LLM_BODY)
    if args.from_json is not None:
        data = json.loads(args.from_json.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            print("--from-json must contain a JSON object", file=sys.stderr)
            return 1
        llm_body = _deep_merge(llm_body, data)
    reserved = {"id", "campaign_id", "created_at", "llm_model", "llm_usage", "_id"}
    llm_body = {k: v for k, v in llm_body.items() if k not in reserved}

    doc = _build_plan_doc(
        plan_id=plan_id,
        campaign_id=args.campaign_id,
        llm_body=llm_body,
        llm_model=args.llm_model,
    )

    client = AsyncIOMotorClient(args.mongo_url)
    try:
        db = client[args.db]
        if not args.no_replace:
            res = await db["plans"].delete_many({"campaign_id": args.campaign_id})
            if res.deleted_count:
                print(
                    f"removed {res.deleted_count} existing plan(s) for campaign "
                    f"{args.campaign_id!r}",
                )
        try:
            await db["plans"].insert_one(doc)
        except DuplicateKeyError as e:
            print(
                f"insert failed (duplicate key): {e}. "
                f"Omit --no-replace or use a fresh --plan-id.",
                file=sys.stderr,
            )
            return 1

        if not args.no_attach_campaign:
            await db["campaigns"].update_one(
                {"_id": args.campaign_id},
                {"$set": {"plan_id": plan_id}},
            )
            print(f"set {args.db}.campaigns.plan_id for {args.campaign_id!r}")

        print(
            f"seeded plan {plan_id!r} for campaign {args.campaign_id!r} "
            f"into {args.db}.plans",
        )
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
